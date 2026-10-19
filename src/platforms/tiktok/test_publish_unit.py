"""Local publishing safety tests; browser fixtures do not prove TikTok acceptance."""
import json
import contextlib
import io
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from platforms.tiktok.publish import (
    PublishError, PostCorrelation, run_tiktok_publish, validate_publish_source,
    verify_published_video, handle_known_upload_prompts, wait_post_ready, upload_video,
)
from platforms.tiktok.publish_store import PublishStore


def fixture_db():
    conn = sqlite3.connect(":memory:")
    conn.executescript("""
    CREATE TABLE publish_batches(id TEXT PRIMARY KEY, platform TEXT, video_path TEXT,
      video_size_bytes INTEGER,video_modified_ns TEXT,caption TEXT,created_at TEXT);
    CREATE TABLE publish_records(id TEXT PRIMARY KEY,batch_id TEXT,account_id TEXT,
      provider TEXT,profile_binding_json TEXT,ordinal INTEGER,status TEXT,phase TEXT,
      handle TEXT,baseline_json TEXT,submitted_at TEXT,post_id TEXT,post_url TEXT,
      error_code TEXT,error_detail TEXT,evidence_json TEXT,verified_at TEXT,updated_at TEXT);
    INSERT INTO publish_batches VALUES('B1','tiktok','missing.mp4',1,'1','海边\n#旅行','2026-10-15T00:00:00Z');
    INSERT INTO publish_records(id,batch_id,account_id,provider,profile_binding_json,
      ordinal,status,phase,updated_at) VALUES('R1','B1','tiktok_1','bitbrowser','{}',0,'queued','queued','now');
    """)
    return conn


class PublishSafetyTests(unittest.TestCase):
    def setUp(self):
        self.conn = fixture_db()
        self.store = PublishStore(self.conn)
        # Other fixtures describe pages without a recovery prompt. Exercise the
        # real recovery handler separately below, including its upload ordering.
        if not self._testMethodName.startswith('test_unsaved_edit_'):
            recovery = patch('platforms.tiktok.publish.discard_unsaved_edit')
            recovery.start()
            self.addCleanup(recovery.stop)

    def tearDown(self):
        self.conn.close()

    def test_claim_and_submission_cas_never_replay(self):
        self.assertTrue(self.store.claim('R1'))
        self.assertFalse(self.store.claim('R1'))
        self.assertTrue(self.store.transition('R1', ('running',), 'committing', 'submitting', submitted_at='now'))
        self.assertFalse(self.store.transition('R1', ('running',), 'committing', 'submitting'))
        with self.assertRaises(ValueError):
            self.store.transition('R1', ('committing',), 'queued', 'queued')

    def test_file_metadata_change_rejected(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[3]) as directory:
            path = Path(directory) / '中文 video.mp4'
            path.write_bytes(b'video')
            batch = dict(video_path=str(path.resolve()),video_size_bytes=5,
                         video_modified_ns=str(path.stat().st_mtime_ns))
            self.assertEqual(validate_publish_source(batch), str(path.resolve()))
            path.write_bytes(b'changed')
            with self.assertRaisesRegex(PublishError, '视频文件已变化'):
                validate_publish_source(batch)

    def test_cancel_wins_prevents_post(self):
        self.store.claim('R1')
        self.store.transition('R1', ('running',), 'cancelled', 'finished')
        page = MagicMock()
        result = run_tiktok_publish(page, MagicMock(), self.store, 'R1')
        self.assertEqual(result['status'], 'cancelled')
        page.get_by_role.assert_not_called()

    def test_response_correlation_ignores_unrelated_and_ambiguous(self):
        observer = PostCorrelation()
        response = MagicMock(url='https://www.tiktok.com/api/publish')
        response.request.url = response.url
        response.request.method = 'GET'
        response.json.return_value = {'post_id': '101'}
        observer.on_response(response)
        self.assertIsNone(observer.post_id)
        observer.begin()
        observer.on_response(response)
        self.assertIsNone(observer.post_id)
        response.request.method = 'POST'
        observer.on_request(response.request)
        observer.on_response(response)
        self.assertEqual(observer.post_id, '101')
        response.json.return_value = {'post_id': '102'}
        observer.on_response(response)
        self.assertIsNone(observer.post_id)

    def test_missing_correlation_never_verifies_same_caption(self):
        record = {'handle':'alice','post_id':None,'baseline_json':json.dumps({'ids':['100']}),
                  'caption':'海边\n#旅行'}
        with patch('platforms.tiktok.publish.profile_observation', return_value={
                'handle':'alice','ids':['100','202'],'urls':{'202':'https://www.tiktok.com/@alice/video/202'}}):
            result = verify_published_video(MagicMock(),record,timeout=0)
        self.assertEqual(result['status'],'pending_confirmation')
        self.assertIsNone(result.get('post_url'))

    def test_exact_id_requires_detail_author_and_caption(self):
        record = {'handle':'alice','post_id':'101','baseline_json':'{"ids":["100"]}', 'caption':'海边\n#旅行'}
        with patch('platforms.tiktok.publish.profile_observation',return_value={
                'handle':'alice','ids':['100','101'],'urls':{'101':'https://www.tiktok.com/@alice/video/101'}}), \
             patch('platforms.tiktok.publish.read_video_detail',return_value=('alice','海边\n#旅行')), \
             patch('platforms.tiktok.publish.open_current_account_profile') as own_profile:
            own_profile.return_value.__enter__.return_value = (MagicMock(), 'alice')
            result = verify_published_video(MagicMock(),record,timeout=0)
        self.assertEqual(result['status'],'verified')

    def test_post_identity_change_remains_pending(self):
        with patch('platforms.tiktok.publish.profile_observation',side_effect=PublishError('identity_mismatch','核验账号不一致')):
            result = verify_published_video(MagicMock(), {'handle':'alice','post_id':'101'}, timeout=0)
        self.assertEqual(result['status'],'pending_confirmation')
        self.assertEqual(result['error_code'],'identity_mismatch')

    def test_terminal_verified_cannot_regress(self):
        self.store.claim('R1')
        self.store.transition('R1',('running',),'committing','submitting')
        self.store.transition('R1',('committing',),'verifying','verifying')
        self.store.transition('R1',('verifying',),'verified','finished')
        with self.assertRaises(ValueError):
            self.store.transition('R1',('verified',),'pending_confirmation','finished')

    def test_late_upload_response_does_not_correlate(self):
        observer = PostCorrelation()
        request = MagicMock(url='https://www.tiktok.com/api/publish',method='POST')
        observer.on_request(request)  # Before Post, still in flight.
        observer.begin()
        response = MagicMock(url=request.url,request=request)
        response.json.return_value = {'post_id':'101'}
        observer.on_response(response)
        self.assertIsNone(observer.post_id)
        request = MagicMock(url='https://www.tiktok.com/api/upload',method='POST')
        observer.on_request(request)
        response.request = request
        response.url = request.url
        observer.on_response(response)
        self.assertIsNone(observer.post_id)

    def test_verify_only_never_reads_source_or_uploads(self):
        self.store.claim('R1')
        self.store.transition('R1',('running',),'committing','submitting')
        self.store.transition('R1',('committing',),'pending_confirmation','finished')
        page = MagicMock()
        with patch('platforms.tiktok.publish.verify_published_video',return_value={
                'status':'pending_confirmation','error_code':'not_confirmed','error_detail':'尚未找到'}), \
             patch('platforms.tiktok.publish.validate_publish_source') as validate:
            run_tiktok_publish(page,MagicMock(),self.store,'R1',verify_only=True)
        validate.assert_not_called()
        page.get_by_role.assert_not_called()
        self.assertEqual(self.store.record('R1')['status'],'pending_confirmation')

    def test_upload_failure_never_posts(self):
        self.store.claim('R1')
        page = MagicMock()
        with patch('platforms.tiktok.publish.validate_publish_source',return_value='video.mp4'), \
             patch('platforms.tiktok.publish.logged_in_handle',return_value='alice'), \
             patch('platforms.tiktok.publish.profile_observation',return_value={'handle':'alice','ids':[],'complete':False}), \
             patch('platforms.tiktok.publish.assert_current_identity'), \
             patch('platforms.tiktok.publish.open_upload_page',return_value=page), \
             patch('platforms.tiktok.publish.upload_video',side_effect=PublishError('upload_failed','视频上传失败')):
            result = run_tiktok_publish(page,MagicMock(),self.store,'R1')
        self.assertEqual(result['status'],'failed')
        self.assertEqual(result['error_code'],'upload_failed')
        self.assertIsNone(result['submitted_at'])

    def test_first_publication_opens_upload_before_any_profile_observation(self):
        self.store.claim('R1')
        page = MagicMock()
        events = []

        def open_upload(current):
            self.assertIs(current, page)
            events.append('Upload')
            return page

        with patch('platforms.tiktok.publish.validate_publish_source', return_value='video.mp4'), \
             patch('platforms.tiktok.publish.logged_in_handle', return_value='alice'), \
             patch('platforms.tiktok.publish.profile_observation', side_effect=PublishError(
                 'baseline_unavailable', 'Upload your first video')) as observe, \
             patch('platforms.tiktok.publish.open_current_account_profile') as own_profile, \
             patch('platforms.tiktok.publish.open_upload_page', side_effect=open_upload) as upload_page, \
             patch('platforms.tiktok.publish.upload_video', side_effect=PublishError(
                 'upload_failed', 'test stops after reaching upload')) as upload:
            result = run_tiktok_publish(page, MagicMock(), self.store, 'R1')

        upload_page.assert_called_once_with(page)
        upload.assert_called_once()
        observe.assert_not_called()
        own_profile.assert_not_called()
        self.assertEqual(events, ['Upload'])
        self.assertEqual(result['handle'], 'alice')
        self.assertEqual(result['error_code'], 'upload_failed')
        self.assertIsNone(result['submitted_at'])

    def test_identity_check_reads_navigation_without_opening_profile(self):
        from platforms.tiktok.publish import assert_current_identity
        browser = MagicMock()
        browser.contexts = [MagicMock()]
        page = browser.contexts[0].new_page.return_value
        with patch('platforms.tiktok.publish.logged_in_handle', return_value='alice'), \
             patch('platforms.tiktok.publish.open_current_account_profile') as profile:
            self.assertEqual(assert_current_identity(browser, 'alice'), 'alice')
        profile.assert_not_called()
        self.assertEqual(page.goto.call_args.args[0], 'https://www.tiktok.com/?lang=en-GB')
        page.close.assert_called_once()

    def test_post_precedes_own_profile_verification_without_baseline(self):
        self._assert_post_flow(False)

    def test_post_now_confirmation_precedes_profile_verification(self):
        self._assert_post_flow(True)

    def _assert_post_flow(self, confirmation):
        self.store.claim('R1')
        page = MagicMock(url='https://www.tiktok.com/tiktokstudio/upload')
        post = MagicMock()
        radio = MagicMock()
        radio.is_visible.return_value = True
        page.get_by_role.return_value.all.return_value = [radio]
        events = []
        title = MagicMock()
        title.is_visible.side_effect = lambda: events == ['Upload', 'video', 'Description', 'Content check off', 'Post']
        confirm = MagicMock()
        confirm.is_visible.return_value = True
        title.locator.return_value.get_by_role.return_value.all.return_value = [confirm]
        page.get_by_text.return_value.all.return_value = [title] if confirmation else []

        def confirm_click(**kwargs):
            events.append('Post now')
            page.url = 'https://www.tiktok.com/@alice/video/101'

        confirm.click.side_effect = confirm_click

        def click(**kwargs):
            events.append('Post')
            self.assertEqual(self.store.record('R1')['status'], 'committing')
            if not confirmation:
                page.url = 'https://www.tiktok.com/@alice/video/101'

        def verify(browser, record):
            events.append('Profile verification')
            self.assertEqual(events, ['Upload', 'video', 'Description', 'Content check off', 'Post'] +
                             (['Post now'] if confirmation else []) + ['Profile verification'])
            self.assertEqual(record['post_id'], '101')
            self.assertEqual(record['handle'], 'alice')
            self.assertIsNone(record['baseline_json'])
            return {'status': 'verified', 'post_url': page.url}

        post.click.side_effect = click
        with patch('platforms.tiktok.publish.validate_publish_source', return_value='video.mp4'), \
             patch('platforms.tiktok.publish.logged_in_handle', return_value='alice'), \
             patch('platforms.tiktok.publish.open_upload_page', side_effect=lambda p: (events.append('Upload') or p)), \
             patch('platforms.tiktok.publish.upload_video', side_effect=lambda *args, **kwargs: events.append('video')), \
             patch('platforms.tiktok.publish._caption', side_effect=lambda *args: events.append('Description')), \
             patch('platforms.tiktok.publish.handle_known_upload_prompts'), \
             patch('platforms.tiktok.publish.disable_content_check_lite', side_effect=lambda p: events.append('Content check off')), \
             patch('platforms.tiktok.publish.wait_post_ready', return_value=post), \
             patch('platforms.tiktok.publish.assert_current_identity', return_value='alice'), \
             patch('platforms.tiktok.publish.profile_observation') as baseline, \
             patch('platforms.tiktok.publish.verify_published_video', side_effect=verify):
            result = run_tiktok_publish(page, MagicMock(), self.store, 'R1')
        baseline.assert_not_called()
        post.click.assert_called_once()
        if confirmation:
            confirm.click.assert_called_once_with(timeout=10000)
            page.get_by_text.assert_called_with('Continue to post?', exact=True)
            title.locator.return_value.get_by_role.assert_called_with('button', name='Post now', exact=True)
        else:
            confirm.click.assert_not_called()
        self.assertEqual(result['status'], 'verified')
        self.assertEqual(result['post_url'], 'https://www.tiktok.com/@alice/video/101')

    def test_identity_change_still_blocks_submission_without_profile_navigation(self):
        from platforms.tiktok.publish import assert_current_identity
        browser = MagicMock(contexts=[MagicMock()])
        with patch('platforms.tiktok.publish.logged_in_handle', return_value='bob'), \
             patch('platforms.tiktok.publish.open_current_account_profile') as profile:
            with self.assertRaises(PublishError) as caught:
                assert_current_identity(browser, 'alice')
        self.assertEqual(caught.exception.code, 'identity_mismatch')
        profile.assert_not_called()
        browser.contexts[0].new_page.return_value.close.assert_called_once()

    def test_empty_profile_first_video_message_is_recognized_after_post(self):
        from platforms.tiktok.publish import profile_observation
        page = MagicMock()
        page.get_by_role.return_value.count.return_value = 0
        page.locator.return_value.first.wait_for.side_effect = TimeoutError('no videos')
        page.locator.return_value.all.return_value = []
        empty = MagicMock()
        empty.is_visible.return_value = True

        def text_nodes(expression):
            self.assertIsNotNone(expression.fullmatch('Upload your first video'))
            nodes = MagicMock()
            nodes.all.return_value = [empty]
            return nodes

        page.get_by_text.side_effect = text_nodes
        with patch('platforms.tiktok.publish.open_current_account_profile') as profile:
            profile.return_value.__enter__.return_value = (page, 'alice')
            result = profile_observation(MagicMock(), 'alice')
        self.assertEqual(result['ids'], [])
        self.assertEqual(result['handle'], 'alice')

    def test_unknown_task_never_becomes_fyp(self):
        from platforms.tiktok.runner import requested_tiktok_task
        with patch.dict('os.environ',{'AM_TASK_TYPE':'publish'}):
            self.assertEqual(requested_tiktok_task(),'publish')
        with patch.dict('os.environ',{'AM_TASK_TYPE':'publish_verify'}):
            self.assertEqual(requested_tiktok_task(),'publish_verify')
        with patch.dict('os.environ',{'AM_TASK_TYPE':'publish_unknown'}):
            with self.assertRaises(ValueError):
                requested_tiktok_task()

    def test_known_prompts_absent_or_reverse_order(self):
        for initial in ([], ['New editing features added','Turn on automatic content checks?']):
            state = list(initial)
            clicks = []
            page = MagicMock()
            def get_text(title, exact=True):
                node = MagicMock()
                node.is_visible.side_effect = lambda: bool(state) and state[0] == title
                button = MagicMock()
                button.is_visible.return_value = True
                def click(**kwargs):
                    clicks.append(state.pop(0))
                button.click.side_effect = click
                node.locator.return_value.get_by_role.return_value.all.return_value = [button]
                collection = MagicMock()
                collection.all.return_value = [node]
                return collection
            page.get_by_text.side_effect = get_text
            handle_known_upload_prompts(page)
            self.assertEqual(clicks,initial)
            self.assertEqual(state,[])

    def test_content_check_lite_only_clicks_enabled_switch(self):
        from platforms.tiktok.publish import disable_content_check_lite
        for checked in ('true', 'false', None):
            with self.subTest(checked=checked):
                page = MagicMock()
                label = MagicMock()
                label.is_visible.return_value = True
                page.get_by_text.return_value.all.return_value = [label]
                control = MagicMock()
                control.is_visible.return_value = True
                control.get_attribute.return_value = checked
                label.locator.return_value.locator.return_value.all.return_value = [control]
                disable_content_check_lite(page)
                page.get_by_text.assert_called_once_with('Content check lite', exact=True)
                if checked == 'true':
                    control.click.assert_called_once_with(timeout=5000)
                else:
                    control.click.assert_not_called()
                if checked is None:
                    control.set_checked.assert_called_once_with(False, timeout=5000)
                else:
                    control.set_checked.assert_not_called()
                    control.locator.return_value.wait_for.assert_called_once_with(state='attached', timeout=5000)

    def test_content_check_lite_unconfirmed_off_blocks_post(self):
        from platforms.tiktok.publish import disable_content_check_lite
        page = MagicMock()
        label = MagicMock()
        label.is_visible.return_value = True
        page.get_by_text.return_value.all.return_value = [label]
        control = MagicMock()
        control.is_visible.return_value = True
        control.get_attribute.return_value = 'true'
        control.locator.return_value.wait_for.side_effect = TimeoutError('switch remained on')
        label.locator.return_value.locator.return_value.all.return_value = [control]
        with self.assertRaises(TimeoutError):
            disable_content_check_lite(page)
        control.click.assert_called_once()

    def test_processing_waits_until_post_enabled(self):
        page = MagicMock()
        page.get_by_text.return_value.all.return_value = []
        button = MagicMock()
        button.is_visible.return_value = True
        button.is_enabled.side_effect = [False,False,True]
        page.get_by_role.return_value.all.return_value = [button]
        alive = MagicMock()
        with patch('platforms.tiktok.publish.handle_known_upload_prompts'):
            self.assertIs(wait_post_ready(page,alive),button)
        self.assertEqual(alive.call_count,3)
        self.assertEqual(page.wait_for_timeout.call_count,2)

    def test_upload_visible_error_and_timeout(self):
        for fail in (True,False):
            page = MagicMock()
            file_input = MagicMock()
            file_input.get_attribute.return_value='video/*'
            page.locator.return_value.all.return_value=[file_input]
            error = MagicMock()
            error.is_visible.return_value=fail
            uploaded = MagicMock()
            uploaded.is_visible.return_value=False
            page.get_by_text.side_effect=lambda expression: type('Nodes',(),{'all':lambda self: [error] if 'upload failed' in expression.pattern else [uploaded]})()
            with patch('platforms.tiktok.publish.handle_known_upload_prompts'), \
                 patch('platforms.tiktok.publish.time.monotonic',side_effect=[0,0,0,2000]):
                with self.assertRaises(PublishError) as caught:
                    upload_video(page,'video.mp4',lambda:None)
            self.assertEqual(caught.exception.code,'upload_failed' if fail else 'upload_timeout')
            file_input.set_input_files.assert_called_once()

    def test_upload_waits_for_delayed_hidden_file_input(self):
        page = MagicMock()
        node = MagicMock()
        node.get_attribute.return_value = 'video/*'
        page.locator.return_value.all.side_effect = [[], [node]]
        page.get_by_role.return_value.all.return_value = []
        page.get_by_text.side_effect = lambda expression, **kwargs: type('Nodes', (), {
            'all': lambda self: [] if isinstance(expression, str) or 'upload failed' in expression.pattern
            else [type('Uploaded', (), {'is_visible': lambda self: True})()]})()
        with patch('platforms.tiktok.publish.handle_known_upload_prompts'):
            upload_video(page, 'video.mp4', lambda: None)
        node.set_input_files.assert_called_once_with('video.mp4', timeout=30000)
        page.wait_for_timeout.assert_called_once_with(250)
        page.expect_file_chooser.assert_not_called()

    def test_upload_accepts_single_untyped_input(self):
        page = MagicMock()
        node = MagicMock()
        node.get_attribute.return_value = None
        page.locator.return_value.all.return_value = [node]
        page.get_by_role.return_value.all.return_value = []
        page.get_by_text.side_effect = lambda expression, **kwargs: type('Nodes', (), {
            'all': lambda self: [] if isinstance(expression, str) or 'upload failed' in expression.pattern
            else [type('Uploaded', (), {'is_visible': lambda self: True})()]})()
        with patch('platforms.tiktok.publish.handle_known_upload_prompts'):
            upload_video(page, 'video.mp4', lambda: None)
        node.set_input_files.assert_called_once_with('video.mp4', timeout=30000)
        page.expect_file_chooser.assert_not_called()

    def test_upload_control_timeout_does_not_select_file(self):
        page = MagicMock()
        page.locator.return_value.all.return_value = []
        page.get_by_role.return_value.all.return_value = []
        page.get_by_text.return_value.all.return_value = []
        with patch('platforms.tiktok.publish.time.monotonic', side_effect=[0, 61]):
            with self.assertRaises(PublishError) as caught:
                upload_video(page, 'video.mp4', lambda: None)
        self.assertEqual(caught.exception.code, 'upload_control_timeout')
        page.expect_file_chooser.assert_not_called()

    def test_upload_does_not_choose_between_two_video_inputs(self):
        page = MagicMock()
        nodes = [MagicMock(), MagicMock()]
        for node in nodes:
            node.get_attribute.return_value = 'video/*'
        page.locator.return_value.all.return_value = nodes
        with self.assertRaises(PublishError) as caught:
            upload_video(page, 'video.mp4', lambda: None)
        self.assertEqual(caught.exception.code, 'unsupported_page')
        for node in nodes:
            node.set_input_files.assert_not_called()

    def test_upload_uses_text_file_chooser_when_button_role_is_absent(self):
        page = MagicMock()
        page.locator.return_value.all.return_value = []
        page.get_by_role.return_value.all.return_value = []
        entry = MagicMock()
        entry.is_visible.return_value = True
        entry.is_enabled.return_value = True
        uploaded = MagicMock()
        uploaded.is_visible.return_value = True
        def text_nodes(expression, **kwargs):
            collection = MagicMock()
            collection.all.return_value = ([entry] if isinstance(expression, str)
                                           else [] if 'upload failed' in expression.pattern
                                           else [uploaded])
            return collection
        page.get_by_text.side_effect = text_nodes
        with patch('platforms.tiktok.publish.handle_known_upload_prompts'):
            upload_video(page, 'video.mp4', lambda: None)
        entry.click.assert_called_once_with(timeout=30000)
        page.expect_file_chooser.return_value.__enter__.return_value.value.set_files.assert_called_once_with(
            'video.mp4', timeout=30000)

    def test_copyright_explanations_do_not_abort_upload_or_processing(self):
        descriptions = [
            'We will check your video for copyright and other potential violations.',
            'No copyright issues found',
            'Check for copyright issues before posting',
        ]
        for processing in (False, True):
            with self.subTest(processing=processing):
                page = MagicMock()
                node = MagicMock()
                node.get_attribute.return_value = 'video/*'
                node.is_visible.return_value = True
                node.is_enabled.return_value = True
                page.locator.return_value.all.return_value = [node]
                page.get_by_role.return_value.all.return_value = [node]
                observations = iter([descriptions, ['Uploaded (36.49MB)']])
                current = descriptions

                def texts(expression):
                    nonlocal current
                    if expression.pattern.startswith('^Uploaded'):
                        current = next(observations)
                        # First progress observation has no completed upload.
                        if current == descriptions:
                            current = ['Uploaded (36.49MB)']
                            matched = []
                        else:
                            matched = current
                    else:
                        matched = [text for text in current if expression.search(text)]
                    collection = MagicMock()
                    nodes = []
                    for text in matched:
                        item = MagicMock()
                        item.is_visible.return_value = True
                        item.inner_text.return_value = text
                        nodes.append(item)
                    collection.all.return_value = nodes
                    return collection

                page.get_by_text.side_effect = texts
                with patch('platforms.tiktok.publish.handle_known_upload_prompts'):
                    if processing:
                        self.assertIs(wait_post_ready(page, lambda: None), node)
                    else:
                        upload_video(page, 'video.mp4', lambda: None)
                        page.wait_for_timeout.assert_called_once_with(500)

    def test_explicit_upload_and_processing_error_preserves_actual_message(self):
        for processing, message in ((False, 'Upload failed: network disconnected'),
                                    (True, 'Processing failed: unsupported format')):
            with self.subTest(processing=processing):
                page = MagicMock()
                file_input = MagicMock()
                file_input.get_attribute.return_value = 'video/*'
                page.locator.return_value.all.return_value = [file_input]
                error = MagicMock()
                error.is_visible.return_value = True
                error.inner_text.return_value = message
                page.get_by_text.return_value.all.return_value = [error]
                with patch('platforms.tiktok.publish.handle_known_upload_prompts'):
                    with self.assertRaises(PublishError) as caught:
                        if processing:
                            wait_post_ready(page, lambda: None)
                        else:
                            upload_video(page, 'video.mp4', lambda: None)
                self.assertEqual(caught.exception.code, 'upload_failed')
                self.assertIn(message, str(caught.exception))
                page.get_by_role.assert_not_called()

    def test_set_files_timeout_continues_only_when_current_video_is_received(self):
        for direct in (False, True):
            with self.subTest(direct=direct):
                page = MagicMock()
                node = MagicMock()
                node.get_attribute.return_value = 'video/*'
                node.is_visible.return_value = True
                node.is_enabled.return_value = True
                page.locator.return_value.all.return_value = [node] if direct else []
                page.get_by_role.return_value.all.return_value = [node]
                setter = node.set_input_files if direct else page.expect_file_chooser.return_value.__enter__.return_value.value.set_files
                setter.side_effect = TimeoutError('Timeout 30000ms exceeded')
                filename = MagicMock()
                filename.is_visible.return_value = True
                card = MagicMock()
                card.inner_text.return_value = 'video.mp4\n3.6MB/36.49MB\n9.89%\nCancel'
                filename.locator.return_value.all.return_value = [card]
                page.locator.return_value.inner_text.return_value = card.inner_text.return_value
                uploaded = MagicMock()
                uploaded.is_visible.return_value = True
                def text_nodes(expression, **kwargs):
                    collection = MagicMock()
                    collection.all.return_value = [filename] if expression == 'video.mp4' else (
                        [uploaded] if not isinstance(expression, str) and expression.pattern.startswith('^Uploaded') else [])
                    return collection
                page.get_by_text.side_effect = text_nodes
                with patch('platforms.tiktok.publish.handle_known_upload_prompts'):
                    upload_video(page, 'video.mp4', lambda: None)
                setter.assert_called_once_with('video.mp4', timeout=30000)

    def test_receipt_requires_current_filename_and_upload_status(self):
        from platforms.tiktok.publish import video_received
        page = MagicMock()
        page.get_by_text.return_value.all.return_value = []
        page.locator.return_value.inner_text.return_value = ''
        self.assertFalse(video_received(page, 'video.mp4'))
        node = MagicMock()
        node.is_visible.return_value = True
        page.get_by_text.return_value.all.return_value = [node]
        card = MagicMock()
        node.locator.return_value.all.return_value = [card]
        card.inner_text.return_value = 'video.mp4\nSelect video'
        page.locator.return_value.inner_text.return_value = card.inner_text.return_value
        self.assertFalse(video_received(page, 'video.mp4'))
        card.inner_text.return_value = 'video.mp4\nUploaded (36.49MB)\nReplace'
        page.locator.return_value.inner_text.return_value = card.inner_text.return_value
        self.assertTrue(video_received(page, 'video.mp4'))

    def test_receipt_progress_does_not_depend_on_cancel_button_tag(self):
        from platforms.tiktok.publish import video_received
        page = MagicMock()
        filename = MagicMock()
        filename.is_visible.return_value = True
        page.get_by_text.return_value.all.return_value = [filename]
        card = MagicMock()
        card.inner_text.return_value = '1.mp4\n1080P\n11.96MB/36.49MB\n16 seconds left\n32.79%\nCancel'
        page.locator.return_value.inner_text.return_value = card.inner_text.return_value
        def ancestors(selector):
            if 'button' in selector:
                raise RuntimeError('Cancel is not a native button')
            collection = MagicMock()
            collection.all.return_value = [card]
            return collection
        filename.locator.side_effect = ancestors
        self.assertTrue(video_received(page, '1.mp4'))
        page.get_by_text.assert_not_called()

    def test_file_selection_errors_identify_exact_operation_without_retry(self):
        for operation in ('file_input_set', 'select_video_click', 'file_chooser_wait', 'file_chooser_set'):
            with self.subTest(operation=operation):
                page = MagicMock()
                node = MagicMock()
                node.get_attribute.return_value = 'video/*'
                node.is_visible.return_value = True
                node.is_enabled.return_value = True
                page.locator.return_value.all.return_value = [node] if operation == 'file_input_set' else []
                page.get_by_role.return_value.all.return_value = [node]
                page.locator.return_value.inner_text.return_value = ''
                chooser = page.expect_file_chooser.return_value
                if operation == 'file_input_set':
                    node.set_input_files.side_effect = TimeoutError('Timeout 30000ms exceeded. Call log: input upload')
                elif operation == 'select_video_click':
                    node.click.side_effect = TimeoutError('Timeout 30000ms exceeded. Call log: click')
                elif operation == 'file_chooser_wait':
                    chooser.__exit__.side_effect = TimeoutError('Timeout 30000ms exceeded. Call log: filechooser')
                else:
                    chooser.__enter__.return_value.value.set_files.side_effect = TimeoutError('Timeout 30000ms exceeded. Call log: set files')
                stdout, stderr = io.StringIO(), io.StringIO()
                with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                    with self.assertRaises(PublishError) as caught:
                        upload_video(page, 'private-video.mp4', lambda: None)
                self.assertEqual(caught.exception.code, operation + '_failed')
                self.assertIn(operation, stdout.getvalue())
                self.assertIn('Call log:', str(caught.exception))
                self.assertIn('Traceback', stderr.getvalue())
                self.assertIn('Call log:', stderr.getvalue())
                self.assertNotIn('private-video.mp4', stdout.getvalue())
                self.assertLessEqual(node.click.call_count, 1)
                self.assertLessEqual(node.set_input_files.call_count, 1)

    def test_receipt_reads_visible_upload_text_without_filename_locator(self):
        from platforms.tiktok.publish import video_received
        page = MagicMock()
        page.get_by_text.side_effect = RuntimeError('exact-text selector unavailable')
        page.locator.return_value.inner_text.return_value = (
            'TikTok Studio\n1.mp4\n1080P\nCancel\n3.48MB/36.49MB\n'
            'Duration: 0m40s\n50 seconds left\n9.54%\nDetails\nDescription\n1')
        self.assertTrue(video_received(page, '1.mp4'))
        page.get_by_text.assert_not_called()

    def test_receipt_rejects_other_file_or_unrelated_percentage(self):
        from platforms.tiktok.publish import video_received
        page = MagicMock()
        for text in ('other.mp4\n3.48MB/36.49MB\n9.54%',
                     '1.mp4\nDetails\nDescription\n99% discount',
                     '1.mp4\nSelect video', '1.mp4\n1080P\n50%'):
            with self.subTest(text=text):
                page.locator.return_value.inner_text.return_value = text
                self.assertFalse(video_received(page, '1.mp4'))

    def test_receipt_probe_errors_are_reported(self):
        from platforms.tiktok.publish import video_received
        page = MagicMock()
        page.locator.return_value.inner_text.side_effect = RuntimeError('CDP read failed')
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertFalse(video_received(page, '1.mp4'))
        self.assertIn('CDP read failed', output.getvalue())

    def test_file_receipt_only_recovers_timeout_not_other_errors(self):
        from platforms.tiktok.publish import file_selection_step
        class DriverTimeout(TimeoutError):
            pass
        received = MagicMock(return_value=True)
        with file_selection_step('file_chooser_set', 'select', received=received):
            raise DriverTimeout('Timeout 30000ms exceeded')
        received.assert_called_once()
        received.reset_mock()
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(PublishError):
                with file_selection_step('file_chooser_set', 'select', received=received):
                    raise RuntimeError('file permission denied')
        received.assert_not_called()

    def test_receipt_diagnostic_preserves_read_text_and_match_result(self):
        from platforms.tiktok.publish import video_received
        page = MagicMock(url='https://www.tiktok.com/tiktokstudio/upload')
        raw = 'TikTok Studio\n1.mp41080P\r\n5.01MB/36.49MB\n13.74%'
        page.locator.return_value.inner_text.return_value = raw
        with patch('platforms.tiktok.publish.Path.mkdir'), \
             patch('platforms.tiktok.publish.Path.write_text') as write:
            self.assertFalse(video_received(page, '1.mp4', record_id='batch_0'))
        report = json.loads(write.call_args.args[0])
        self.assertEqual(report['body_text'], raw)
        self.assertEqual(report['expected_filename'], '1.mp4')
        self.assertFalse(report['received'])
        self.assertFalse(report['filename_matched'])
        self.assertTrue(report['checked_at'])
        self.assertTrue(report['finished_at'])
        self.assertEqual(write.call_args.kwargs['encoding'], 'utf-8')

    def test_unsaved_edit_discard_is_scoped_to_recovery_prompt(self):
        from platforms.tiktok.publish import discard_unsaved_edit
        page = MagicMock()
        prompt = MagicMock()
        prompt.is_visible.return_value = True
        page.get_by_text.return_value.all.return_value = [prompt]
        discard = MagicMock()
        discard.is_visible.return_value = True
        prompt.locator.return_value.get_by_role.return_value.all.return_value = [discard]
        discard_unsaved_edit(page)
        pattern = page.get_by_text.call_args.args[0]
        self.assertIsNotNone(pattern.fullmatch('A video you were editing wasn’t saved. Continue editing?'))
        discard.click.assert_called_once_with(timeout=10000)
        prompt.wait_for.assert_called_once_with(state='hidden', timeout=10000)
        prompt.locator.return_value.get_by_role.assert_called_once_with('button', name='Discard', exact=True)

    def test_unsaved_edit_absent_does_not_click_discard(self):
        from platforms.tiktok.publish import discard_unsaved_edit
        page = MagicMock()
        page.get_by_text.return_value.all.return_value = []
        discard_unsaved_edit(page)
        page.get_by_role.assert_not_called()

    def test_unsaved_edit_is_discarded_before_file_assignment(self):
        page = MagicMock()
        events = []
        prompt, discard, file_input, uploaded = (MagicMock() for _ in range(4))
        for node in (prompt, discard, uploaded):
            node.is_visible.return_value = True
        prompt.locator.return_value.get_by_role.return_value.all.return_value = [discard]
        discard.click.side_effect = lambda **kwargs: events.append('discard')
        prompt.wait_for.side_effect = lambda **kwargs: events.append('prompt_hidden')
        file_input.get_attribute.return_value = 'video/*'
        file_input.set_input_files.side_effect = lambda *args, **kwargs: events.append('file_set')
        page.locator.return_value.all.return_value = [file_input]
        def nodes(expression, **kwargs):
            result = MagicMock()
            result.all.return_value = ([prompt] if 'Continue editing' in expression.pattern else
                                      [uploaded] if expression.pattern.startswith('^Uploaded') else [])
            return result
        page.get_by_text.side_effect = nodes
        with patch('platforms.tiktok.publish.handle_known_upload_prompts'):
            upload_video(page, 'video.mp4', lambda: None)
        self.assertEqual(events, ['discard', 'prompt_hidden', 'file_set'])
        file_input.set_input_files.assert_called_once_with('video.mp4', timeout=30000)

    def test_receipt_diagnostic_records_read_error_without_changing_result(self):
        from platforms.tiktok.publish import video_received
        page = MagicMock(url='https://www.tiktok.com/tiktokstudio/upload')
        page.locator.return_value.inner_text.side_effect = RuntimeError('CDP read failed')
        with patch('platforms.tiktok.publish.Path.mkdir'), \
             patch('platforms.tiktok.publish.Path.write_text') as write:
            self.assertFalse(video_received(page, '1.mp4', record_id='batch_0'))
        report = json.loads(write.call_args.args[0])
        self.assertIsNone(report['body_text'])
        self.assertIn('CDP read failed', report['read_error'])

    def test_locator_read_failure_accepts_same_video_from_cdp(self):
        from platforms.tiktok.publish import video_received
        page = MagicMock(url='https://www.tiktok.com/tiktokstudio/upload')
        page.main_frame.url = page.url
        page.frames = [page.main_frame]
        page.locator.return_value.inner_text.side_effect = TimeoutError('waiting for body')
        session = page.context.new_cdp_session.return_value
        snapshot = {'url': page.url, 'document_url': page.url, 'ready_state': 'complete',
                    'has_body': True, 'body_text': '1.mp4\n5.01MB/36.49MB\n13.74%',
                    'body_truncated': False}
        session.send.return_value = {'result': {'type': 'object', 'value': snapshot}}
        with patch('platforms.tiktok.publish.Path.mkdir'), \
             patch('platforms.tiktok.publish.Path.write_text') as write:
            self.assertTrue(video_received(page, '1.mp4', record_id='batch_0'))
        report = json.loads(write.call_args.args[0])
        self.assertIn('waiting for body', report['read_error'])
        self.assertEqual(report['cdp_comparison']['snapshot'], snapshot)
        self.assertEqual(report['cdp_comparison']['page_url'], page.url)
        page.context.new_cdp_session.assert_called_once_with(page)
        method, params = session.send.call_args.args
        self.assertEqual(method, 'Runtime.evaluate')
        self.assertEqual(params['timeout'], 2000)
        self.assertTrue(params['returnByValue'])
        session.detach.assert_called_once()
        self.assertTrue(report['received'])
        self.assertEqual(report['accepted_via'], 'cdp')

    def test_cdp_comparison_failure_is_saved_and_session_detached(self):
        from platforms.tiktok.publish import video_received
        page = MagicMock(url='https://www.tiktok.com/tiktokstudio/upload')
        page.frames = []
        page.locator.return_value.inner_text.side_effect = TimeoutError('waiting for body')
        session = page.context.new_cdp_session.return_value
        session.send.side_effect = RuntimeError('CDP context unavailable')
        with patch('platforms.tiktok.publish.Path.mkdir'), \
             patch('platforms.tiktok.publish.Path.write_text') as write:
            self.assertFalse(video_received(page, '1.mp4', record_id='batch_0'))
        report = json.loads(write.call_args.args[0])
        self.assertIn('CDP context unavailable', report['cdp_comparison']['error'])
        self.assertEqual(session.detach.call_count, 3)

    def test_readable_initial_page_is_cross_checked_with_cdp(self):
        from platforms.tiktok.publish import video_received
        page = MagicMock(url='https://www.tiktok.com/tiktokstudio/upload')
        page.locator.return_value.inner_text.return_value = 'Videos\nPhotos\nSelect video to upload'
        page.context.new_cdp_session.return_value.send.return_value = {'result': {'value': {
            'url': page.url, 'has_body': True, 'body_text': '1.mp4\n1080P\n0B/36.49MB\n0%'}}}
        self.assertTrue(video_received(page, '1.mp4'))
        page.context.new_cdp_session.assert_called_once_with(page)

    def test_receipt_poll_accepts_delayed_upload_without_reselecting(self):
        from platforms.tiktok.publish import video_received
        page = MagicMock(url='https://www.tiktok.com/tiktokstudio/upload')
        page.locator.return_value.inner_text.side_effect = [
            'Select video to upload', '1.mp4\n1080P\n5.01MB/36.49MB\n13.74%']
        with patch('platforms.tiktok.publish.cdp_receipt_comparison', return_value={
                'snapshot': {'url': page.url, 'has_body': True, 'body_text': 'Select video to upload'}}) as compare:
            self.assertTrue(video_received(page, '1.mp4'))
        compare.assert_called_once()
        page.wait_for_timeout.assert_called_once_with(500)
        page.expect_file_chooser.assert_not_called()

    def test_uploaded_detection_uses_same_video_cdp_when_locator_misses(self):
        page = MagicMock(url='https://www.tiktok.com/tiktokstudio/upload')
        file_input = MagicMock()
        file_input.get_attribute.return_value = 'video/*'
        page.locator.return_value.all.return_value = [file_input]
        page.get_by_text.return_value.all.return_value = []
        snapshot = {'url': page.url, 'has_body': True,
                    'body_text': '1.mp4\n1080P\nUploaded\n(36.49MB)\nReplace\nDetails\nDescription\n1'}
        with patch('platforms.tiktok.publish.handle_known_upload_prompts'), \
             patch('platforms.tiktok.publish.cdp_receipt_comparison', return_value={'snapshot': snapshot}) as compare, \
             patch('platforms.tiktok.publish.time.monotonic', side_effect=[0, 0, 0, 0, 2000]):
            upload_video(page, '1.mp4', lambda: None)
        compare.assert_called_once()
        page.wait_for_timeout.assert_not_called()
        file_input.set_input_files.assert_called_once()

    def test_uploaded_text_requires_completion_in_current_file_card(self):
        from platforms.tiktok.publish import match_uploaded_video
        self.assertTrue(match_uploaded_video('1.mp4\n1080P\nUploaded (36.49MB)\nDetails', '1.mp4'))
        for text in ('1.mp4\nUploading...\n36.49MB/36.49MB\n100%',
                     'other.mp4\nUploaded (36.49MB)',
                     '1.mp4\nDetails\nDescription\nUploaded (36.49MB)',
                     '1.mp4\nNot Uploaded'):
            self.assertFalse(match_uploaded_video(text, '1.mp4'))

    def test_cdp_uploaded_detection_advances_record_to_caption(self):
        self.store.claim('R1')
        page = MagicMock(url='https://www.tiktok.com/tiktokstudio/upload')
        file_input = MagicMock()
        file_input.get_attribute.return_value = 'video/*'
        page.locator.return_value.all.return_value = [file_input]
        page.get_by_text.return_value.all.return_value = []
        snapshot = {'url': page.url, 'has_body': True,
                    'body_text': '1.mp4\n1080P\nUploaded (36.49MB)\nDetails\nDescription\n1'}
        def caption_step(current_page, caption):
            self.assertIs(current_page, page)
            self.assertEqual(caption, '海边\n#旅行')
            self.assertEqual(self.store.record('R1')['phase'], 'caption')
            raise PublishError('caption_probe', 'stop test before any Post')
        with patch('platforms.tiktok.publish.validate_publish_source', return_value='1.mp4'), \
             patch('platforms.tiktok.publish.logged_in_handle', return_value='alice'), \
             patch('platforms.tiktok.publish.open_upload_page', return_value=page), \
             patch('platforms.tiktok.publish.handle_known_upload_prompts'), \
             patch('platforms.tiktok.publish.cdp_receipt_comparison', return_value={'snapshot': snapshot}), \
             patch('platforms.tiktok.publish._caption', side_effect=caption_step) as caption:
            result = run_tiktok_publish(page, MagicMock(), self.store, 'R1')
        caption.assert_called_once()
        self.assertEqual(result['error_code'], 'caption_probe')
        self.assertIsNone(result['submitted_at'])

    def test_receipt_poll_stops_after_three_unconfirmed_reads(self):
        from platforms.tiktok.publish import video_received
        page = MagicMock(url='https://www.tiktok.com/tiktokstudio/upload')
        page.locator.return_value.inner_text.return_value = 'Select video to upload'
        with patch('platforms.tiktok.publish.cdp_receipt_comparison', return_value={
                'snapshot': {'url': page.url, 'has_body': True, 'body_text': 'other.mp4\n5MB/36MB'}}) as compare:
            self.assertFalse(video_received(page, '1.mp4'))
        self.assertEqual(compare.call_count, 3)
        self.assertEqual(page.wait_for_timeout.call_count, 2)

    def test_uploaded_header_does_not_require_text_line_boundaries(self):
        from platforms.tiktok.publish import match_uploaded_video
        for text in ('1.mp41080PUploaded (36.49MB)Replace\nDetails',
                     '1.mp4 1080P Replace Uploaded\u00a0(36.49 MB) Details',
                     '1.mp4\n1080P\nUploaded\n(\n36.49\nMB\n)\nDetails'):
            self.assertTrue(match_uploaded_video(text, '1.mp4'), text)
        self.assertFalse(match_uploaded_video('other1.mp4 Uploaded (36MB) Details', '1.mp4'))

    def test_rendered_completion_snapshot_uses_browser_layout_text(self):
        from platforms.tiktok.publish import rendered_upload_snapshot
        page = MagicMock()
        session = page.context.new_cdp_session.return_value
        session.send.return_value = {
            'strings': ['https://www.tiktok.com/tiktokstudio/upload', '1.mp4', '1080P',
                        'Uploaded', '(36.49MB)', 'Details', 'visible', '1', 'hidden'],
            'documents': [{'documentURL': 0, 'layout': {
                'text': [1, 2, 3, 4, 5], 'styles': [[6, 7]] * 5}}]}
        snapshot = rendered_upload_snapshot(page)
        self.assertEqual(snapshot['body_text'], '1.mp4\n1080P\nUploaded\n(36.49MB)\nDetails')
        self.assertEqual(session.send.call_args.args[0], 'DOMSnapshot.captureSnapshot')
        session.detach.assert_called_once()

    def test_completion_uses_rendered_snapshot_if_script_text_is_stale(self):
        page = MagicMock(url='https://www.tiktok.com/tiktokstudio/upload')
        file_input = MagicMock()
        file_input.get_attribute.return_value = 'video/*'
        page.locator.return_value.all.return_value = [file_input]
        page.get_by_text.return_value.all.return_value = []
        with patch('platforms.tiktok.publish.handle_known_upload_prompts'), \
             patch('platforms.tiktok.publish.cdp_receipt_comparison', return_value={'snapshot': {
                 'url': page.url, 'has_body': True, 'body_text': 'Select video to upload'}}), \
             patch('platforms.tiktok.publish.rendered_upload_snapshot', return_value={
                 'url': page.url, 'has_body': True, 'body_text': '1.mp41080PUploaded (36.49MB) Details'}) as rendered, \
             patch('platforms.tiktok.publish.time.monotonic', side_effect=[0, 0, 0, 2000]):
            upload_video(page, '1.mp4', lambda: None)
        rendered.assert_called_once_with(page)
        page.wait_for_timeout.assert_not_called()
        file_input.set_input_files.assert_called_once()


if __name__ == '__main__':
    unittest.main()
