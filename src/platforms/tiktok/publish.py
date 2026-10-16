"""TikTok Studio video publishing. No private API replay or automatic retries."""
import json
import re
import time
from pathlib import Path
from urllib.parse import urlsplit

from profile_stats import logged_in_handle, open_current_account_profile
from platforms.tiktok.publish_store import utc_now

UPLOAD_TIMEOUT = 20 * 60
VERIFY_TIMEOUT = 180


class PublishError(RuntimeError):
    def __init__(self, code, detail):
        super().__init__(detail)
        self.code = code


def validate_publish_source(batch):
    try:
        path = Path(batch['video_path']).resolve(strict=True)
        stat = path.stat()
        if (not path.is_file() or stat.st_size <= 0 or
                str(path) != batch['video_path'] or
                stat.st_size != int(batch['video_size_bytes']) or
                str(stat.st_mtime_ns) != str(batch['video_modified_ns'])):
            raise PublishError('source_changed','视频文件已变化')
        with path.open('rb') as stream:
            stream.read(1)
        return str(path)
    except PublishError:
        raise
    except OSError as exc:
        raise PublishError('source_unavailable','视频不存在或不可读取') from exc


def unique_visible(locator, label):
    visible = [item for item in locator.all() if item.is_visible()]
    if len(visible) != 1:
        raise PublishError('unsupported_page',f'无法唯一定位{label}')
    return visible[0]


def handle_known_upload_prompts(page):
    deadline = time.monotonic() + 30
    titles = [('Turn on automatic content checks?', 'Turn on'),
              ('New editing features added', 'Got it')]
    for _ in range(6):
        handled = False
        for title, button in titles:
            # Scope to the smallest ancestor that contains the title and action.
            title_nodes = page.get_by_text(title, exact=True)
            for node in title_nodes.all():
                if not node.is_visible():
                    continue
                container = node.locator('xpath=ancestor::*[.//button[normalize-space(.)="'+button+'"]][1]')
                action = unique_visible(container.get_by_role('button',name=button,exact=True),button)
                action.click(timeout=5000)
                node.wait_for(state='hidden', timeout=5000)
                handled = True
                break
        if not handled:
            return
        if time.monotonic() >= deadline:
            break
    raise PublishError('unsupported_page','上传提示未能关闭')


def assert_current_identity(browser, expected_handle):
    page = None
    try:
        if len(browser.contexts) != 1:
            raise ValueError('无法唯一确定浏览器会话')
        # Studio may not expose Profile navigation. Read the cookie-backed
        # account navigation on a temporary home tab, without visiting a profile.
        page = browser.contexts[0].new_page()
        page.goto('https://www.tiktok.com/?lang=en-GB',
                  wait_until='domcontentloaded', timeout=60000)
        handle = logged_in_handle(page, 30)
        if handle != expected_handle:
            raise ValueError('当前登录账号发生变化')
        return handle
    except Exception as exc:
        raise PublishError('identity_mismatch','当前登录账号发生变化或无法确认') from exc
    finally:
        if page is not None:
            page.close()


def profile_observation(browser, expected_handle=None):
    try:
        with open_current_account_profile(browser,30,expected_handle) as (page, handle):
            tabs = page.get_by_role('tab',name='Videos',exact=True)
            if tabs.count():
                unique_visible(tabs,'Videos').click(timeout=5000)
            # An empty profile is accepted only with a visible explicit empty state.
            links = page.locator('a[href*="/video/"]')
            try:
                links.first.wait_for(state='attached',timeout=10000)
            except Exception:
                empty = page.get_by_text(re.compile(r'^(No videos yet|Upload your first video|还没有视频|暂无视频)$'))
                if not any(item.is_visible() for item in empty.all()):
                    raise PublishError('baseline_unavailable','无法读取本人主页视频列表')
            urls = {}
            for link in links.all()[:100]:
                href = link.get_attribute('href') or ''
                parsed = urlsplit(href)
                if not parsed.netloc:
                    href = 'https://www.tiktok.com' + href
                match = re.fullmatch(r'/@([A-Za-z0-9._]+)/video/(\d+)/?',urlsplit(href).path)
                if (urlsplit(href).hostname in {'www.tiktok.com','tiktok.com'} and match
                        and match[1].lower() == handle):
                    urls[match[2]] = href.split('?')[0]
            return {'captured_at':utc_now(),'handle':handle,'ids':list(urls),
                    'urls':urls,'complete':False}
    except PublishError:
        raise
    except Exception as exc:
        raise PublishError('identity_mismatch','本人主页账号不一致或无法确认') from exc


def read_video_detail(browser, url, expected_handle, caption):
    page = browser.contexts[0].new_page()
    try:
        page.goto(url,wait_until='domcontentloaded',timeout=60000)
        if urlsplit(page.url).path != urlsplit(url).path:
            raise PublishError('detail_unavailable','作品详情发生跳转')
        # The global "Profile" nav is not evidence of the video's author.
        authors = page.get_by_role('link',name=re.compile(r'^@?'+re.escape(expected_handle)+r'$',re.I)).all()
        handles = set()
        for link in authors:
            href = link.get_attribute('href') or ''
            if re.fullmatch('/@'+re.escape(expected_handle)+'/?',urlsplit(href).path,re.I) and link.is_visible():
                handles.add(expected_handle)
        # Empty captions must be explicitly observed in a description-labelled node.
        if caption:
            unique_visible(page.get_by_text(caption,exact=True),'作品文案')
        else:
            description = unique_visible(page.get_by_role('paragraph',name='Description',exact=True),'空作品文案')
            if description.inner_text() != '':
                raise PublishError('detail_unavailable','作品文案不一致')
        if handles != {expected_handle}:
            raise PublishError('detail_unavailable','作品作者未确认')
        return expected_handle, caption
    finally:
        page.close()


def save_evidence_screenshot(page, record_id):
    if not record_id or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',record_id):
        return None
    try:
        from core.runtime import DATA_DIR
        destination = Path(DATA_DIR)/'publish-evidence'/record_id/'latest.png'
        destination.parent.mkdir(parents=True,exist_ok=True)
        page.screenshot(path=str(destination),full_page=True,timeout=5000)
        return str(destination)
    except Exception:
        return None


def verify_published_video(browser, record, timeout=VERIFY_TIMEOUT):
    deadline = time.monotonic() + timeout
    evidence = {'version':1,'observed_at':utc_now(),'candidate_ids':[],
                'author_handle':record.get('handle'),'correlated_post_id':record.get('post_id'),
                'baseline_complete':False,'match_basis':'exact_post_id_and_detail'}
    error = '主页尚未确认本次作品'
    code = 'not_confirmed'
    while True:
        try:
            observation = profile_observation(browser,record.get('handle'))
            evidence['candidate_ids'] = observation['ids'][:30]
            post_id = record.get('post_id')
            baseline = json.loads(record.get('baseline_json') or '{}')
            evidence['baseline_complete'] = bool(baseline.get('complete'))
            if post_id and post_id not in baseline.get('ids',[]) and post_id in observation['urls']:
                url = observation['urls'][post_id]
                author, caption = read_video_detail(browser,url,record['handle'],record['caption'])
                if author == record['handle'] and caption == record['caption']:
                    with open_current_account_profile(browser,30,record['handle']) as (page,_):
                        screenshot = save_evidence_screenshot(page,record.get('id'))
                        if screenshot:
                            evidence['screenshot_path'] = screenshot
                    evidence['reason'] = '本人主页精确作品ID、作者和文案一致'
                    return {'status':'verified','post_url':url,'verified_at':utc_now(),
                            'error_code':None,'error_detail':None,'evidence_json':json.dumps(evidence,ensure_ascii=False)}
        except Exception as exc:
            code = getattr(exc,'code','verification_unavailable')
            error = str(exc)
            if code == 'identity_mismatch':
                break
        if time.monotonic() >= deadline:
            break
        time.sleep(min(5,max(0,deadline-time.monotonic())))
    evidence['reason'] = error
    return {'status':'pending_confirmation','error_code':code,'error_detail':error,
            'evidence_json':json.dumps(evidence,ensure_ascii=False)}


class PostCorrelation:
    """Observe explicit IDs from normal publish POST responses after one click."""
    def __init__(self):
        self.ids = set()
        self.active = False
        self.requests = []

    @property
    def post_id(self):
        return next(iter(self.ids)) if len(self.ids) == 1 else None

    def begin(self):
        self.active = True

    def on_request(self, request):
        parsed = urlsplit(request.url)
        if (self.active and request.method == 'POST' and
                parsed.hostname in {'www.tiktok.com','tiktok.com'} and
                re.search(r'(?:publish|create|/post/)',parsed.path,re.I) and
                not re.search(r'(?:upload|list|initialize|analytics)',parsed.path,re.I)):
            self.requests.append(request)

    def on_response(self, response):
        parsed = urlsplit(response.url)
        if (not self.active or not any(request is response.request for request in self.requests) or response.request.method != 'POST' or
                parsed.hostname not in {'www.tiktok.com','tiktok.com'} or
                not re.search(r'(?:publish|post|create|upload)',parsed.path,re.I)):
            return
        try:
            data = response.json()
            if not isinstance(data,dict):
                return
            if any(data.get(key) not in (None,0,'0') for key in ('status_code','statusCode')):
                return
            containers = [data] + [data[key] for key in ('data','item','aweme') if isinstance(data.get(key),dict)]
            for container in containers:
                for key in ('post_id','item_id','aweme_id'):
                    value = container.get(key)
                    if value is not None and re.fullmatch(r'\d+',str(value)):
                        self.ids.add(str(value))
        except Exception:
            return


def _caption(page, caption):
    locator = page.get_by_role('textbox',name=re.compile(r'^Description$',re.I))
    if not locator.count():
        labels = page.get_by_text('Description',exact=True)
        if labels.count() == 1:
            locator = labels.locator('xpath=ancestor::*[.//*[@contenteditable="true"] or .//textarea][1]').locator('textarea,[contenteditable="true"]')
    editor = unique_visible(locator,'Description')
    editor.fill(caption,timeout=10000)
    value = editor.input_value() if editor.evaluate('(el)=>el.tagName === "TEXTAREA" || el.tagName === "INPUT"') else editor.inner_text()
    if value.replace('\r\n','\n') != caption.replace('\r\n','\n'):
        raise PublishError('caption_mismatch','Description文案回读不一致')


def open_upload_page(page):
    old_pages = list(page.context.pages)
    upload = page.get_by_role('link',name=re.compile(r'^Upload$',re.I))
    unique_visible(upload,'Upload').click(timeout=30000)
    deadline = time.monotonic()+60
    while time.monotonic() < deadline:
        candidates = [page] + [item for item in page.context.pages if item not in old_pages]
        for candidate in candidates:
            parsed = urlsplit(candidate.url)
            if parsed.scheme == 'https' and parsed.hostname in {'www.tiktok.com','tiktok.com'} and parsed.path.rstrip('/') == '/tiktokstudio/upload':
                candidate.wait_for_load_state('domcontentloaded',timeout=60000)
                return candidate
        page.wait_for_timeout(250)
    raise PublishError('unsupported_page','Upload未进入TikTok Studio上传页')


def upload_video(page, source, alive):
    inputs = page.locator('input[type="file"]')
    candidates = [node for node in inputs.all() if any(
        kind in (node.get_attribute('accept') or '').lower() for kind in ('video','mp4','mov','webm'))]
    if len(candidates) == 1:
        candidates[0].set_input_files(source,timeout=30000)
    elif not candidates:
        with page.expect_file_chooser(timeout=30000) as chooser:
            unique_visible(page.get_by_role('button',name='Select video',exact=True),'Select video').click(timeout=30000)
        chooser.value.set_files(source,timeout=30000)
    else:
        raise PublishError('unsupported_page','视频上传控件不唯一')
    deadline = time.monotonic()+UPLOAD_TIMEOUT
    while time.monotonic()<deadline:
        alive()
        handle_known_upload_prompts(page)
        errors = page.get_by_text(re.compile(r'(upload failed|couldn.t upload|copyright.*(issue|violation)|上传失败)',re.I))
        if any(node.is_visible() for node in errors.all()):
            raise PublishError('upload_failed','视频上传失败或内容检查未通过')
        uploaded = page.get_by_text(re.compile(r'^Uploaded(?:\s|\(|$)',re.I))
        if any(node.is_visible() for node in uploaded.all()):
            return
        page.wait_for_timeout(500)
    raise PublishError('upload_timeout','视频上传超时')


def wait_post_ready(page, alive):
    deadline = time.monotonic()+UPLOAD_TIMEOUT
    while time.monotonic()<deadline:
        alive()
        handle_known_upload_prompts(page)
        errors = page.get_by_text(re.compile(r'(processing failed|copyright.*(issue|violation)|视频处理失败)',re.I))
        if any(node.is_visible() for node in errors.all()):
            raise PublishError('upload_failed','视频处理失败或内容检查未通过')
        post = unique_visible(page.get_by_role('button',name='Post',exact=True),'Post')
        if post.is_enabled():
            return post
        page.wait_for_timeout(500)
    raise PublishError('upload_timeout','视频处理超时')


def run_tiktok_publish(page, browser, store, record_id, verify_only=False):
    record = store.record(record_id)
    if verify_only:
        if record['status'] != 'pending_confirmation':
            raise ValueError('仅待确认作品可重新核验')
        result = verify_published_video(browser,record)
        status = result.pop('status')
        store.transition(record_id,('pending_confirmation',),status,'finished',**result)
        return store.record(record_id)
    if record['status'] != 'running':
        return record
    try:
        source = validate_publish_source(record)
        # The user's workflow starts with Upload, including a first-ever post.
        # Only identify the signed-in account here; inspect its works after Post.
        handle = logged_in_handle(page, 30)
        store.phase(record_id,'authenticating',handle=handle)
        page = open_upload_page(page)
        store.phase(record_id,'uploading')
        def alive():
            if store.record(record_id)['status'] != 'running':
                raise PublishError('cancelled','发布已停止')
        upload_video(page,source,alive)
        validate_publish_source(record)
        store.phase(record_id,'uploaded')
        handle_known_upload_prompts(page)
        store.phase(record_id,'caption')
        _caption(page,record['caption'])
        handle_known_upload_prompts(page)
        now = page.get_by_role('radio',name='Now',exact=True)
        unique_visible(now,'Now').check(timeout=5000)
        post = wait_post_ready(page,alive)
        post.scroll_into_view_if_needed(timeout=10000)
        post.wait_for(state='visible',timeout=30000)
        if not post.is_enabled():
            raise PublishError('upload_timeout','视频处理未完成或Post不可用')
        assert_current_identity(browser,handle)
        observer = PostCorrelation()
        page.on('request',observer.on_request)
        page.on('response',observer.on_response)
        try:
            if not store.transition(record_id,('running',),'committing','submitting',submitted_at=utc_now()):
                return store.record(record_id)
            observer.begin()
            try:
                post.click(timeout=30000)  # Never retry, including click timeout.
            except Exception:
                pass  # Continue observing and verifying a potentially submitted post.
            deadline = time.monotonic()+30
            while time.monotonic()<deadline and not observer.post_id:
                parsed = urlsplit(page.url)
                match = re.fullmatch(r'/@'+re.escape(handle)+r'/video/(\d+)/?',parsed.path)
                if parsed.hostname in {'www.tiktok.com','tiktok.com'} and match:
                    observer.ids.add(match[1])
                    break
                page.wait_for_timeout(250)
        finally:
            page.remove_listener('request',observer.on_request)
            page.remove_listener('response',observer.on_response)
            current = store.record(record_id)
            if current['status'] == 'committing':
                store.transition(record_id,('committing',),'verifying','verifying',post_id=observer.post_id)
        result = verify_published_video(browser,store.record(record_id))
        status = result.pop('status')
        store.transition(record_id,('verifying',),status,'finished',**result)
    except Exception as exc:
        from core.runtime import redact_runtime_text
        current = store.record(record_id)
        code = getattr(exc,'code','unsupported_page')
        detail = redact_runtime_text(str(exc))
        status = 'pending_confirmation' if current['status'] in {'committing','verifying'} else 'failed'
        if current['status'] in {'running','committing','verifying'}:
            evidence = {'version':1,'reason':detail,'observed_at':utc_now(),'candidate_ids':[],
                        'correlated_post_id':current.get('post_id'),'author_handle':current.get('handle'),
                        'baseline_complete':False,'match_basis':'unconfirmed'}
            try:
                from core.runtime import DATA_DIR
                # record IDs are Rust-generated UUIDs; reject path separators defensively.
                if re.fullmatch(r'[A-Za-z0-9_-]{1,100}',record_id):
                    destination = Path(DATA_DIR)/'publish-evidence'/record_id/'latest.png'
                    destination.parent.mkdir(parents=True,exist_ok=True)
                    page.screenshot(path=str(destination),full_page=True,timeout=5000)
                    evidence['screenshot_path'] = str(destination)
            except Exception:
                pass
            store.transition(record_id,(current['status'],),status,'finished',
                             error_code=code,error_detail=detail,evidence_json=json.dumps(evidence))
    return store.record(record_id)
