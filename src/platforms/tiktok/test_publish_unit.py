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
        self.store.claim('R1')
        page = MagicMock(url='https://www.tiktok.com/tiktokstudio/upload')
        post = MagicMock()
        radio = MagicMock()
        radio.is_visible.return_value = True
        page.get_by_role.return_value.all.return_value = [radio]
        events = []

        def click(**kwargs):
            events.append('Post')
            self.assertEqual(self.store.record('R1')['status'], 'committing')
            page.url = 'https://www.tiktok.com/@alice/video/101'

        def verify(browser, record):
            events.append('Profile verification')
            self.assertEqual(events, ['Upload', 'video', 'Description', 'Post', 'Profile verification'])
            self.assertEqual(record['post_id'], '101')
            self.assertEqual(record['handle'], 'alice')
            self.assertIsNone(record['baseline_json'])
            return {'status': 'verified', 'post_url': page.url}

        post.click.side_effect = click
        with patch('platforms.tiktok.publish.validate_publish_source', return_value='video.mp4'), \
             patch('platforms.tiktok.publish.logged_in_handle', return_value='alice'), \
             patch('platforms.tiktok.publish.open_upload_page', side_effect=lambda p: (events.append('Upload') or p)), \
             patch('platforms.tiktok.publish.upload_video', side_effect=lambda *args: events.append('video')), \
             patch('platforms.tiktok.publish._caption', side_effect=lambda *args: events.append('Description')), \
             patch('platforms.tiktok.publish.handle_known_upload_prompts'), \
             patch('platforms.tiktok.publish.wait_post_ready', return_value=post), \
             patch('platforms.tiktok.publish.assert_current_identity', return_value='alice'), \
             patch('platforms.tiktok.publish.profile_observation') as baseline, \
             patch('platforms.tiktok.publish.verify_published_video', side_effect=verify):
            result = run_tiktok_publish(page, MagicMock(), self.store, 'R1')
        baseline.assert_not_called()
        post.click.assert_called_once()
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


if __name__ == '__main__':
    unittest.main()
