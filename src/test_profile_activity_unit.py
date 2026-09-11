import unittest

from profile_activity import MAX_ACTIVITY_MATCHES, activity_result, comment_like_message


class ActivityTests(unittest.TestCase):
    def test_screenshot_examples_and_grouped_notification(self):
        rows = {
            "one": {"text": "Liliana\nliked your comment: Nice video. · 2d",
                    "paragraphs": ["Liliana", "liked your comment: Nice video. · 2d"]},
            "two": {"text": "Thomas felix, Getti an...\nliked your comment: Thanks for sharing. · 2d",
                    "paragraphs": ["Thomas felix, Getti an...",
                                   "liked your comment: Thanks for sharing. · 2d"]},
        }
        result = activity_result(rows, "loaded_list_stable")
        self.assertTrue(result["has_liked_your_comment"])
        self.assertEqual(result["comment_like_notifications_count"], 2)
        self.assertEqual(result["comment_publish_evidence"], "observed")
        self.assertEqual(result["scope"], "loaded_notifications")

    def test_other_actions_and_quoted_comment_are_not_evidence(self):
        for text in ("liked your video", "started following you", "System Notifications",
                     'commented: someone liked your comment: Nice video.',
                     'Your comment says "liked your comment"'):
            self.assertIsNone(comment_like_message([text]))

    def test_no_matches_is_not_comment_failure(self):
        result = activity_result({"system": {"text": "System Notifications",
                                             "paragraphs": ["System Notifications"]}},
                                 "loaded_list_stable")
        self.assertFalse(result["has_liked_your_comment"])
        self.assertEqual(result["comment_like_notifications_count"], 0)
        self.assertEqual(result["comment_publish_evidence"], "not_confirmed")

    def test_loading_and_ui_failure_are_unknown(self):
        for status in ("timeout", "activity_ui_unavailable"):
            result = activity_result({}, status)
            self.assertIsNone(result["has_liked_your_comment"])
            self.assertIsNone(result["comment_like_notifications_count"])

    def test_timeout_preserves_positive_evidence(self):
        result = activity_result({"one": {"text": "liked your comment: Hi",
                                          "paragraphs": ["liked your comment: Hi"]}}, "timeout")
        self.assertTrue(result["has_liked_your_comment"])
        self.assertEqual(result["scope"], "loaded_notifications")
        self.assertFalse(result["complete"])

    def test_matches_are_bounded_for_storage(self):
        rows = {
            str(index): {
                "text": f"user {index}\nliked your comment: {'x' * 700}",
                "paragraphs": [f"user {index}", f"liked your comment: {'x' * 700}"],
            }
            for index in range(MAX_ACTIVITY_MATCHES + 2)
        }
        result = activity_result(rows, "loaded_list_stable")
        self.assertEqual(result["comment_like_notifications_count"], MAX_ACTIVITY_MATCHES + 2)
        self.assertEqual(len(result["matches"]), MAX_ACTIVITY_MATCHES)
        self.assertLessEqual(len(result["matches"][0]["text"]), 500)
        self.assertLessEqual(len(result["matches"][0]["action"]), 500)


if __name__ == "__main__":
    unittest.main()
