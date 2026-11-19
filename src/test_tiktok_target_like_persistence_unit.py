import unittest
from unittest.mock import MagicMock, patch

from human_mouse import MouseState
from platforms.tiktok import engagement, target_page


class Control:
    def __init__(self, page, name, box):
        self.page, self.name, self.box = page, name, box

    def bounding_box(self, **kwargs):
        return self.box

    def is_enabled(self):
        return True

    def get_attribute(self, name, **kwargs):
        if name == "aria-selected":
            return "true"
        return None

    def inner_text(self, **kwargs):
        return self.page.draft if self.name == "editor" else ""

    def input_value(self):
        return self.inner_text()

    def evaluate(self, script):
        if "pressed:" in script:
            return {
                "pressed": "true" if self.page.liked else "false",
                "label": "Unlike" if self.page.liked else "Like",
                "text": "", "marker": "like-icon",
                "fills": ["rgb(254,44,85)" if self.page.liked else "rgb(255,255,255)"],
                "heart_fills": ["rgb(254,44,85)" if self.page.liked else "rgb(255,255,255)"],
            }
        if "activeElement" in script:
            return self.page.active == self.name
        if "TEXTAREA" in script:
            return bool(getattr(self, "textarea", False))
        return None

    def click(self, **kwargs):
        self.page.events.append(("click", self.name))
        if self.name == "like":
            self.page.liked = not self.page.liked
        elif self.name == "editor":
            self.page.active = "editor"
        elif self.name == "post":
            self.page.comments.append(self.page.draft)
            self.page.draft = ""

    def focus(self, **kwargs):
        self.page.active = self.name

    def fill(self, text, **kwargs):
        self.page.events.append(("fill", self.name))
        self.page.active = self.name
        self.page.draft = text


class Keyboard:
    def __init__(self, page):
        self.page = page

    def type(self, text):
        for ch in text:
            # Model an editor losing focus mid-comment. Page-level keyboard input
            # can then reach a video shortcut instead of the intended editor.
            if self.page.lose_focus and ch.casefold() == "l":
                self.page.active = None
            if self.page.active == "editor":
                self.page.draft += ch
            elif ch.casefold() == "l":
                self.page.liked = not self.page.liked
                self.page.events.append(("shortcut", "like"))


class Mouse:
    def __init__(self, page):
        self.page = page

    def move(self, *args, **kwargs):
        pass

    def click(self, x, y, **kwargs):
        if self.page.move_editor and y > 550:
            # A layout shift occurs after coordinates are captured; a raw mouse
            # click can hit a different control. A locator click stays scoped.
            self.page.like.click()
        elif y > 550:
            (self.page.post if x > 900 else self.page.editor).click()
        else:
            self.page.like.click()


class TargetVideoPage:
    url = "https://www.tiktok.com/@brand/video/101"
    viewport_size = {"width": 1280, "height": 800}

    def __init__(self, lose_focus=False, move_editor=False):
        self.liked = False
        self.active = None
        self.draft = ""
        self.comments = []
        self.events = []
        self.lose_focus, self.move_editor = lose_focus, move_editor
        self.like = Control(self, "like", {"x": 680, "y": 265, "width": 30, "height": 30})
        self.editor = Control(self, "editor", {"x": 690, "y": 580, "width": 200, "height": 35})
        self.post = Control(self, "post", {"x": 1000, "y": 580, "width": 30, "height": 35})
        self.keyboard, self.mouse = Keyboard(self), Mouse(self)

    def locator(self, selector):
        return MagicMock()

    def get_by_role(self, *args, **kwargs):
        return MagicMock()

    def get_by_text(self, *args, **kwargs):
        return MagicMock()


class TargetLikePersistenceTests(unittest.TestCase):
    @patch.object(engagement.time, "sleep")
    @patch.object(engagement, "human_pause")
    @patch.object(engagement, "_open_target_video", return_value=(True, "ok"))
    def test_like_survives_comment_input_and_submission(self, _open, _pause, _sleep):
        for options in ({}, {"lose_focus": True}, {"move_editor": True}):
            with self.subTest(options=options):
                page = TargetVideoPage(**options)
                with patch.object(engagement, "target_like_button", return_value=page.like), \
                        patch.object(engagement, "unique_visible", side_effect=[None, None, page.editor, page.post]):
                    result = engagement.engage_target_video(
                        page, "brand", "101", ["Thanks for the details"], 1.0, 1.0,
                    )
                self.assertTrue(page.liked, page.events)
                self.assertTrue(result["liked"])
                self.assertTrue(result["commented"])
                self.assertEqual(page.comments, ["Thanks for the details"])
                self.assertEqual(page.events.count(("click", "like")), 1)
                self.assertNotIn(("shortcut", "like"), page.events)

    @patch.object(engagement.time, "sleep")
    @patch.object(engagement, "human_pause")
    @patch.object(engagement, "_open_target_video", return_value=(True, "ok"))
    def test_already_liked_video_stays_liked_while_commenting(self, _open, _pause, _sleep):
        page = TargetVideoPage(lose_focus=True, move_editor=True)
        page.liked = True
        page.editor.textarea = True
        with patch.object(engagement, "target_like_button", return_value=page.like), \
                patch.object(engagement, "unique_visible", side_effect=[None, None, page.editor, page.post]):
            result = engagement.engage_target_video(page, "brand", "101", ["Lovely roses"], 1.0, 1.0)
        self.assertTrue(page.liked)
        self.assertEqual(result["like_reason"], "already_liked")
        self.assertFalse(result["like_attempted"])
        self.assertTrue(result["commented"])
        self.assertNotIn(("click", "like"), page.events)
        self.assertEqual(page.comments, ["Lovely roses"])

    @patch.object(engagement, "human_pause")
    def test_a_timeout_after_a_received_click_never_causes_another_click(self, _pause):
        page = TargetVideoPage()
        attempted = set()
        key = ("tiktok", "acc", "101")
        original_click = page.like.click

        def uncertain_click(**kwargs):
            original_click(**kwargs)
            raise TimeoutError("browser received click but confirmation timed out")

        with patch.object(engagement, "target_like_button", return_value=page.like), \
                patch.object(page.like, "click", side_effect=uncertain_click) as click:
            first = engagement._like_target_video(page, MouseState(), attempted_likes=attempted, video_key=key)
            second = engagement._like_target_video(page, MouseState(), attempted_likes=attempted, video_key=key)
        self.assertEqual(first, (False, "click_unconfirmed", True))
        self.assertEqual(second, (False, "already_attempted", False))
        click.assert_called_once_with(timeout=2000)
        self.assertTrue(page.liked)

    @patch.object(engagement, "human_pause")
    def test_attempt_limit_is_scoped_by_account_and_video(self, _pause):
        attempted = {("tiktok", "acc-1", "101")}
        for key in (("tiktok", "acc-2", "101"), ("tiktok", "acc-1", "102")):
            page = TargetVideoPage()
            with patch.object(engagement, "target_like_button", return_value=page.like):
                self.assertEqual(engagement._like_target_video(
                    page, MouseState(), attempted_likes=attempted, video_key=key,
                ), (True, "liked", True))
            self.assertTrue(page.liked)

    @patch.object(engagement, "human_pause")
    def test_lost_focus_after_fill_aborts_submit_without_page_keyboard_input(self, _pause):
        page = TargetVideoPage()
        original_fill = page.editor.fill

        def fill_then_blur(text, **kwargs):
            original_fill(text, **kwargs)
            page.active = None

        with patch.object(page.editor, "fill", side_effect=fill_then_blur), \
                patch.object(engagement, "unique_visible", side_effect=[None, None, page.editor]):
            result = engagement._comment_on_video_page(page, MouseState(), "Lovely roses")
        self.assertFalse(result)
        self.assertEqual(page.comments, [])
        self.assertNotIn(("click", "like"), page.events)

    @patch.object(engagement, "human_pause")
    def test_existing_draft_is_never_overwritten(self, _pause):
        page = TargetVideoPage()
        page.draft = "existing draft"
        with patch.object(engagement, "unique_visible", side_effect=[None, None, page.editor]):
            self.assertFalse(engagement._comment_on_video_page(page, MouseState(), "Lovely roses"))
        self.assertEqual(page.draft, "existing draft")
        self.assertEqual(page.events, [])

    @patch.object(engagement.time, "sleep")
    @patch.object(engagement, "human_pause")
    @patch.object(engagement, "_open_target_video", return_value=(True, "ok"))
    def test_state_reversion_after_comment_is_reported_without_clicking_again(self, _open, _pause, _sleep):
        page = TargetVideoPage()

        def reverted_after_post(*args):
            page.liked = False
            return True

        with patch.object(engagement, "target_like_button", return_value=page.like), \
                patch.object(engagement, "_comment_on_video_page", side_effect=reverted_after_post):
            result = engagement.engage_target_video(page, "brand", "101", ["Lovely roses"], 1.0, 1.0)
        self.assertFalse(result["liked"])
        self.assertEqual(result["like_reason"], "state_reverted_after_comment")
        self.assertEqual(page.events.count(("click", "like")), 1)

    def test_white_svg_without_heart_identity_does_not_mean_unliked(self):
        button = MagicMock()
        button.evaluate.return_value = {
            "pressed": None, "label": "", "text": "", "marker": "",
            "fills": ["rgb(255,255,255)"], "heart_fills": [],
        }
        self.assertIsNone(target_page.toggle_state(button, "like"))

    def test_identified_white_heart_can_still_be_liked(self):
        button = MagicMock()
        button.evaluate.return_value = {
            "pressed": None, "label": "", "text": "", "marker": "like-icon",
            "fills": ["rgb(255,255,255)"], "heart_fills": ["rgb(255,255,255)"],
        }
        self.assertIs(target_page.toggle_state(button, "like"), False)


if __name__ == "__main__":
    unittest.main()
