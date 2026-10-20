"""TikTok Studio video publishing. No private API replay or automatic retries."""
import json
import re
import time
import sys
import traceback
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit

from profile_stats import logged_in_handle, open_current_account_profile, ProfileIdentityMismatch
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
            if not any(node.is_visible() for node in tabs.all()):
                tabs = page.get_by_text('Videos', exact=True)
            unique_visible(tabs,'Videos').click(timeout=5000)
            # The profile can retain Popular/Oldest from an earlier visit.
            latest = page.get_by_role('button', name='Latest', exact=True)
            if not any(node.is_visible() for node in latest.all()):
                latest = page.get_by_text('Latest', exact=True)
            if any(node.is_visible() for node in latest.all()):
                unique_visible(latest, 'Latest').click(timeout=5000)
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
        from core.runtime import redact_runtime_text
        code = 'identity_mismatch' if isinstance(exc, ProfileIdentityMismatch) else 'profile_read_failed'
        raise PublishError(code, '本人主页核验失败：' + redact_runtime_text(
            type(exc).__name__ + ': ' + str(exc))) from exc


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
            if not post_id:
                code = 'post_id_unavailable'
                error = '本人主页已读取，但未获取本次提交的作品ID，不能仅凭相同文案确认成功'
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
            from core.runtime import redact_runtime_text
            code = getattr(exc,'code','verification_unavailable')
            error = redact_runtime_text(str(exc))
            print('[publish-verify] ' + code + ': ' + error, flush=True)
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


@contextmanager
def file_selection_step(operation, label, received=None):
    print(f'[publish-upload] {operation} start: {label}', flush=True)
    try:
        yield
    except PublishError:
        # A nested click failure must not be reclassified as a chooser timeout.
        raise
    except Exception as exc:
        # set_files can time out after the page has accepted the file. Never
        # select it again; continue only with same-file upload-card evidence.
        if received is not None:
            print(f'[publish-upload] {operation} exception_type={type(exc).__name__}', flush=True)
            if any(cls.__name__ == 'TimeoutError' for cls in type(exc).__mro__) and received():
                print(f'[publish-upload] {operation} accepted_after_timeout: 视频已被页面接收，继续等待上传', flush=True)
                return
        from core.runtime import redact_runtime_text
        detail = redact_runtime_text(str(exc))
        print(f'[publish-upload] {operation} failed: {label}', flush=True)
        print(redact_runtime_text(traceback.format_exc()), file=sys.stderr, flush=True)
        raise PublishError(operation + '_failed', f'{label}失败：{detail}') from exc
    else:
        print(f'[publish-upload] {operation} complete: {label}', flush=True)


def cdp_receipt_comparison(page, timeout=5000):
    """Read the same target's default JS context without Locator selectors."""
    from core.runtime import redact_runtime_text
    result = {'checked_at': utc_now(), 'context': 'CDP default/main world',
              'page_url': str(page.url), 'frames': [], 'snapshot': None, 'error': None}
    session = None
    try:
        result['frames'] = [{'url': str(frame.url), 'is_main': frame == page.main_frame}
                            for frame in page.frames[:8]]
        session = page.context.new_cdp_session(page)
        response = session.send('Runtime.evaluate', {
            'expression': '''(() => {
                const text = document.body ? document.body.innerText : null;
                return {url: location.href, document_url: document.URL,
                    ready_state: document.readyState, has_body: !!document.body,
                    body_text: text === null ? null : text.slice(0, 100000),
                    body_truncated: text !== null && text.length > 100000};
            })()''',
            'returnByValue': True, 'timeout': timeout, 'silent': True,
        })
        if response.get('exceptionDetails'):
            raise RuntimeError(str(response['exceptionDetails']))
        snapshot = response.get('result', {}).get('value')
        if not isinstance(snapshot, dict):
            raise RuntimeError('CDP未返回可读取的页面快照')
        result['snapshot'] = snapshot
        print('[publish-upload] cdp_comparison: 同一标签页DOM快照已读取', flush=True)
    except Exception as exc:
        result['error'] = str(exc)
        print('[publish-upload] cdp_comparison error: ' + redact_runtime_text(str(exc)), flush=True)
    finally:
        if session is not None:
            try:
                session.detach()
            except Exception as exc:
                result['detach_error'] = str(exc)
        result['finished_at'] = utc_now()
    return json.loads(redact_runtime_text(json.dumps(result, ensure_ascii=False)))


def match_received_video(body, filename):
    if not isinstance(body, str):
        return False, False
    filename_matched = False
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    for index, line in enumerate(lines):
        if not re.fullmatch(re.escape(filename) + r'(?:\s+\d{3,4}[pP])?', line):
            continue
        filename_matched = True
        nearby = []
        for following in lines[index + 1:index + 13]:
            if following.lower() in ('details', 'description', 'cover', 'settings'):
                break
            nearby.append(following)
        if re.search(r'\b\d+(?:\.\d+)?\s*(?:B|KB|MB|GB)\s*/\s*\d+(?:\.\d+)?\s*(?:B|KB|MB|GB)\b|\bUploaded\s*\(\s*\d', '\n'.join(nearby)[:2048], re.I):
            return True, True
    return filename_matched, False


def video_received(page, source, record_id=None):
    from core.runtime import redact_runtime_text
    probe = {'checked_at': utc_now(), 'expected_filename': Path(source).name,
             'body_text': None, 'body_truncated': False,
             'filename_matched': False, 'received': False, 'read_error': None,
             'cdp_comparison': None, 'accepted_via': None, 'attempts': []}
    try:
        filename = Path(source).name
        # Bound the extra wait after set_files times out. Never assign twice.
        for attempt in range(3):
            probe.update(body_text=None, body_truncated=False, read_error=None,
                         filename_matched=False, cdp_comparison=None)
            try:
                body = page.locator('body').inner_text(timeout=2000)
                probe['body_text'] = redact_runtime_text(body[:100000])
                probe['body_truncated'] = len(body) > 100000
                probe['filename_matched'], probe['received'] = match_received_video(body, filename)
            except Exception as exc:
                probe['read_error'] = redact_runtime_text(str(exc))
                print('[publish-upload] receipt_probe error: ' + probe['read_error'], flush=True)
            if probe['received']:
                probe['accepted_via'] = 'locator'
            else:
                # Locator may return stale/initial UI even without raising.
                comparison = cdp_receipt_comparison(page, timeout=2000)
                probe['cdp_comparison'] = comparison
                snapshot = comparison.get('snapshot') or {}
                parsed = urlsplit(snapshot.get('url') or '')
                if (parsed.scheme == 'https' and parsed.hostname in {'www.tiktok.com', 'tiktok.com'}
                        and parsed.path.rstrip('/') == '/tiktokstudio/upload' and snapshot.get('has_body') is True):
                    found, received = match_received_video(snapshot.get('body_text'), filename)
                    probe['filename_matched'] = probe['filename_matched'] or found
                    probe['received'] = received
                    if received:
                        probe['accepted_via'] = 'cdp'
            probe['attempts'].append({key: value for key, value in probe.items()
                                      if key not in ('attempts', 'expected_filename')})
            if probe['received']:
                print('[publish-upload] receipt_probe: 本次文件名及传输大小已确认', flush=True)
                return True
            if attempt < 2:
                page.wait_for_timeout(500)
        print('[publish-upload] receipt_probe: 未找到本次文件名紧邻的传输大小或完成状态', flush=True)
    except Exception as exc:
        probe['read_error'] = redact_runtime_text(str(exc))
        print('[publish-upload] receipt_probe error: ' + redact_runtime_text(str(exc)), flush=True)
    finally:
        probe['finished_at'] = utc_now()
        if record_id and re.fullmatch(r'[A-Za-z0-9_-]{1,100}', record_id):
            try:
                from core.runtime import DATA_DIR
                destination = Path(DATA_DIR) / 'publish-evidence' / record_id / 'receipt-probe.json'
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_text(json.dumps(probe, ensure_ascii=False, indent=2), encoding='utf-8')
                print('[publish-upload] receipt_probe saved: ' + str(destination), flush=True)
            except Exception as exc:
                print('[publish-upload] receipt_probe save_error: ' + redact_runtime_text(str(exc)), flush=True)
    return False


def discard_unsaved_edit(page):
    prompts = page.get_by_text(re.compile(
        r'^A video you were editing wasn[’\x27]t saved\. Continue editing\?$', re.I))
    visible = [node for node in prompts.all() if node.is_visible()]
    if not visible:
        return
    if len(visible) != 1:
        raise PublishError('unsupported_page', '未保存编辑恢复提示不唯一')
    prompt = visible[0]
    container = prompt.locator(
        'xpath=ancestor::*[.//*[normalize-space(.)="Discard"] and .//*[normalize-space(.)="Continue"]][1]')
    discard = unique_visible(container.get_by_role('button', name='Discard', exact=True), '恢复提示中的Discard')
    print('[publish-upload] unsaved_edit: 丢弃上次未保存编辑，上传本次视频', flush=True)
    discard.click(timeout=10000)
    prompt.wait_for(state='hidden', timeout=10000)


def match_uploaded_video(body, filename):
    """Require Uploaded in this file's header, never a percentage alone."""
    if not isinstance(body, str):
        return False
    # Inline filename/resolution/status spans need not introduce line breaks.
    name = re.search(r'(?<![\w.])' + re.escape(filename) + r'(?=\s|\d{3,4}[pP]|Uploaded\b|$)', body)
    if name is None:
        return False
    header = body[name.end():name.end() + 2048]
    header = re.split(r'Details|Description|Cover|Settings', header, maxsplit=1, flags=re.I)[0]
    header = re.sub(r'^\s*\d{3,4}[pP]\s*', '', header)
    if re.search(r'\b(?:not|never)\s+Uploaded\b', header, re.I):
        return False
    return re.search(r'(?<![A-Za-z])Uploaded\b', header, re.I) is not None


def rendered_upload_snapshot(page):
    """Read browser layout text independently of page JS and Locator worlds."""
    from core.runtime import redact_runtime_text
    session = None
    result = {'url': str(page.url), 'has_body': False, 'body_text': None, 'error': None}
    try:
        session = page.context.new_cdp_session(page)
        data = session.send('DOMSnapshot.captureSnapshot', {'computedStyles': ['visibility', 'opacity']})
        if not isinstance(data, dict) or not isinstance(data.get('strings'), list) or not data.get('documents'):
            raise RuntimeError('CDP未返回有效的渲染快照')
        strings = data['strings']
        document = data['documents'][0]
        result['url'] = strings[document['documentURL']]
        layout = document['layout']
        text = []
        for index, value in enumerate(layout['text']):
            if not isinstance(value, int) or not 0 <= value < len(strings):
                continue
            styles = layout.get('styles', [])
            style = [strings[item] if 0 <= item < len(strings) else '' for item in styles[index]] if index < len(styles) else []
            if (style and style[0] in ('hidden', 'collapse')) or (len(style) > 1 and style[1] == '0'):
                continue
            if strings[value].strip():
                text.append(strings[value])
        result['has_body'] = bool(text)
        result['body_text'] = '\n'.join(text)[:100000]
    except Exception as exc:
        result['error'] = str(exc)
    finally:
        if session is not None:
            try:
                session.detach()
            except Exception:
                pass
    return json.loads(redact_runtime_text(json.dumps(result, ensure_ascii=False)))


def save_completion_probe(record_id, source, comparison, rendered, complete):
    if not record_id or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', record_id):
        return
    from core.runtime import DATA_DIR, redact_runtime_text
    try:
        destination = Path(DATA_DIR) / 'publish-evidence' / record_id / 'completion-probe.json'
        destination.parent.mkdir(parents=True, exist_ok=True)
        data = {'checked_at': utc_now(), 'expected_filename': Path(source).name,
                'uploaded': complete, 'cdp_comparison': comparison, 'rendered_snapshot': rendered}
        destination.write_text(redact_runtime_text(json.dumps(data, ensure_ascii=False, indent=2)), encoding='utf-8')
    except Exception as exc:
        print('[publish-upload] completion_probe save_error: ' + redact_runtime_text(str(exc)), flush=True)


def upload_video(page, source, alive, record_id=None):
    # DOMContentLoaded may precede Studio's client-rendered upload controls.
    ready_deadline = time.monotonic()+60
    while True:
        alive()
        discard_unsaved_edit(page)
        inputs = page.locator('input[type="file"]').all()
        candidates = [node for node in inputs if any(
            kind in (node.get_attribute('accept') or '').lower()
            for kind in ('video','mp4','mov','webm'))]
        if not candidates and len(inputs) == 1:
            accept = (inputs[0].get_attribute('accept') or '').strip().lower()
            if accept in ('', '*', '*/*'):
                candidates = inputs
        if len(candidates) == 1:
            with file_selection_step('file_input_set', '向网页文件控件传入视频',
                                     received=lambda: video_received(page, source, record_id)):
                candidates[0].set_input_files(source,timeout=30000)
            break
        if len(candidates) > 1:
            raise PublishError('unsupported_page','视频上传控件不唯一')
        selector = page.get_by_role('button',name=re.compile(r'^Select\s+video$', re.I))
        buttons = [node for node in selector.all() if node.is_visible()]
        if not buttons:
            selector = page.get_by_text('Select video',exact=True)
            buttons = [node for node in selector.all() if node.is_visible()]
        if len(buttons) == 1 and buttons[0].is_enabled():
            with file_selection_step('file_chooser_wait', '等待浏览器文件选择事件'):
                with page.expect_file_chooser(timeout=30000) as chooser:
                    with file_selection_step('select_video_click', '点击Select video'):
                        buttons[0].click(timeout=30000)
                selected = chooser.value
            with file_selection_step('file_chooser_set', '向文件选择事件传入视频',
                                     received=lambda: video_received(page, source, record_id)):
                selected.set_files(source,timeout=30000)
            break
        if len(buttons) > 1:
            raise PublishError('unsupported_page','Select video上传入口不唯一')
        if time.monotonic() >= ready_deadline:
            raise PublishError('upload_control_timeout','等待视频上传控件就绪超时')
        page.wait_for_timeout(250)
    deadline = time.monotonic()+UPLOAD_TIMEOUT
    completion_poll = 0
    while time.monotonic()<deadline:
        alive()
        handle_known_upload_prompts(page)
        errors = page.get_by_text(re.compile(
            r'^\s*(?:upload failed|couldn.t upload(?: your| the)? video|couldn.t upload|上传失败|视频上传失败|copyright check failed|content check failed|版权检查失败|内容检查失败)(?:\s*[:：.!。！-].*|\s*)$', re.I))
        for node in errors.all():
            if node.is_visible():
                from core.runtime import redact_runtime_text
                message = redact_runtime_text(node.inner_text().strip())
                raise PublishError('upload_failed',f'视频上传失败：{message}')
        uploaded = page.get_by_text(re.compile(r'^Uploaded(?:\s|\(|$)',re.I))
        if any(node.is_visible() for node in uploaded.all()):
            print('[publish-upload] upload_complete: 已识别Uploaded，继续填写Description', flush=True)
            return
        # Receipt may be confirmed while Locator still observes stale UI.
        # Read the same target's main world about every five seconds.
        if completion_poll % 10 == 0:
            comparison = cdp_receipt_comparison(page, timeout=2000)
            snapshot = comparison.get('snapshot') or {}
            parsed = urlsplit(snapshot.get('url') or '')
            complete = (parsed.scheme == 'https' and parsed.hostname in {'www.tiktok.com', 'tiktok.com'}
                    and parsed.path.rstrip('/') == '/tiktokstudio/upload'
                    and snapshot.get('has_body') is True
                    and match_uploaded_video(snapshot.get('body_text'), Path(source).name))
            rendered = None
            if not complete:
                rendered = rendered_upload_snapshot(page)
                parsed = urlsplit(rendered.get('url') or '')
                complete = (parsed.scheme == 'https' and parsed.hostname in {'www.tiktok.com', 'tiktok.com'}
                            and parsed.path.rstrip('/') == '/tiktokstudio/upload'
                            and rendered.get('has_body') is True
                            and match_uploaded_video(rendered.get('body_text'), Path(source).name))
            save_completion_probe(record_id, source, comparison, rendered, complete)
            if complete:
                print('[publish-upload] upload_complete: CDP已确认本次视频Uploaded，继续填写Description', flush=True)
                return
        completion_poll += 1
        page.wait_for_timeout(500)
    raise PublishError('upload_timeout','视频上传超时')


def disable_content_check_lite(page):
    label = unique_visible(page.get_by_text('Content check lite', exact=True), 'Content check lite')
    container = label.locator(
        'xpath=ancestor::*[.//*[@role="switch" or @role="checkbox" or '
        '(self::input and @type="checkbox")]][1]')
    control = unique_visible(container.locator(
        '[role="switch"], [role="checkbox"], input[type="checkbox"]'), 'Content check lite开关')
    control.scroll_into_view_if_needed(timeout=10000)
    checked = control.get_attribute('aria-checked')
    if checked in ('true', 'false'):
        if checked == 'true':
            control.click(timeout=5000)
        control.locator('xpath=self::*[@aria-checked="false"]').wait_for(state='attached', timeout=5000)
    else:
        # Studio overlays the native input with its own thumb. Skip pointer
        # interception checks; set_checked still verifies the resulting state.
        control.set_checked(False, force=True, timeout=5000)
    print('[publish-upload] content_check_lite: 已关闭', flush=True)


def wait_post_ready(page, alive):
    deadline = time.monotonic()+UPLOAD_TIMEOUT
    while time.monotonic()<deadline:
        alive()
        handle_known_upload_prompts(page)
        errors = page.get_by_text(re.compile(
            r'^\s*(?:processing failed|video processing failed|视频处理失败|copyright check failed|content check failed|版权检查失败|内容检查失败)(?:\s*[:：.!。！-].*|\s*)$', re.I))
        for node in errors.all():
            if node.is_visible():
                from core.runtime import redact_runtime_text
                message = redact_runtime_text(node.inner_text().strip())
                raise PublishError('upload_failed',f'视频处理失败：{message}')
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
        upload_video(page,source,alive,record_id=record_id)
        validate_publish_source(record)
        store.phase(record_id,'uploaded')
        handle_known_upload_prompts(page)
        store.phase(record_id,'caption')
        _caption(page,record['caption'])
        handle_known_upload_prompts(page)
        now = page.get_by_role('radio',name='Now',exact=True)
        unique_visible(now,'Now').check(timeout=5000)
        disable_content_check_lite(page)
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
            post_now_attempted = False
            while time.monotonic()<deadline and not observer.post_id:
                parsed = urlsplit(page.url)
                match = re.fullmatch(r'/@'+re.escape(handle)+r'/video/(\d+)/?',parsed.path)
                if parsed.hostname in {'www.tiktok.com','tiktok.com'} and match:
                    observer.ids.add(match[1])
                    break
                if not post_now_attempted:
                    prompts = [node for node in page.get_by_text('Continue to post?', exact=True).all()
                               if node.is_visible()]
                    if len(prompts) > 1:
                        raise PublishError('unsupported_page', 'Continue to post确认弹窗不唯一')
                    if prompts:
                        container = prompts[0].locator(
                            'xpath=ancestor::*[.//button[normalize-space(.)="Post now"]][1]')
                        confirm = unique_visible(container.get_by_role('button', name='Post now', exact=True), 'Post now')
                        post_now_attempted = True
                        print('[publish-upload] post_confirmation: 点击Post now', flush=True)
                        try:
                            confirm.click(timeout=10000)  # Never retry an uncertain submission.
                        except Exception:
                            pass  # Observe and verify even if the confirmation click times out.
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
