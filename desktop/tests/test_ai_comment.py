import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import requests


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import ai_comment
import runtime_cli
from platforms.tiktok import actions as tiktok_actions


class FakeAdapter(ai_comment.ProviderAdapter):
    def __init__(self, result):
        self.result = result
        self.calls = []

    def generate(self, context, config, api_key):
        self.calls.append((context, config, api_key))
        return self.result


class FakeResponse:
    def __init__(self, payload=None, status_error=None, json_error=None, status_code=200, text=""):
        self.payload = payload
        self.status_error = status_error
        self.json_error = json_error
        self.status_code = status_code
        self.text = text

    def raise_for_status(self):
        if self.status_error:
            if getattr(self.status_error, "response", None) is None:
                self.status_error.response = self
            raise self.status_error

    def json(self):
        if self.json_error:
            raise self.json_error
        return self.payload


class FakeSession:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def post(self, url, headers=None, json=None, timeout=None):
        self.calls.append(
            {
                "url": url,
                "headers": headers,
                "json": json,
                "timeout": timeout,
            }
        )
        if self.error:
            raise self.error
        return self.response


class AiCommentGenerationTests(unittest.TestCase):
    def enabled_config(self, **overrides):
        config = {
            "enabled": True,
            "provider": "kimi_moonshot",
            "base_url": "https://api.moonshot.cn/v1",
            "model": "kimi-k3",
            "timeout_seconds": 5,
            "max_comment_length": 80,
            "language": "auto",
            "blocked_words": [],
        }
        config.update(overrides)
        return config

    def test_generate_ai_comment_returns_valid_adapter_comment(self):
        adapter = FakeAdapter(ai_comment.RawModelResult(True, content="  Love this idea!  "))

        with patch.object(ai_comment, "get_provider_adapter", return_value=adapter):
            result = ai_comment.generate_ai_comment(
                {"title": "Useful tool demo", "description": ""},
                self.enabled_config(),
                lambda provider: "moonshot-key",
            )

        self.assertTrue(result["ok"])
        self.assertEqual(result["comment"], "Love this idea!")
        self.assertEqual(result["source"], "ai")
        self.assertEqual(adapter.calls[0][2], "moonshot-key")

    def test_generate_ai_comment_returns_missing_api_key(self):
        result = ai_comment.generate_ai_comment(
            {"title": "Useful tool demo"},
            self.enabled_config(),
            lambda provider: None,
        )

        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "missing_api_key")

    def test_generate_ai_comment_returns_network_failure(self):
        adapter = FakeAdapter(
            ai_comment.RawModelResult(
                False,
                reason="network_error",
                error="Authorization: Bearer secret-token failed",
            )
        )

        with patch.object(ai_comment, "get_provider_adapter", return_value=adapter):
            result = ai_comment.generate_ai_comment(
                {"description": "A useful caption"},
                self.enabled_config(),
                lambda provider: "secret-token",
            )

        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "network_error")
        self.assertNotIn("secret-token", result["error"])

    def test_generate_ai_comment_returns_timeout(self):
        adapter = FakeAdapter(ai_comment.RawModelResult(False, reason="timeout", error="request timed out"))

        with patch.object(ai_comment, "get_provider_adapter", return_value=adapter):
            result = ai_comment.generate_ai_comment(
                {"title": "Useful tool demo"},
                self.enabled_config(),
                lambda provider: "moonshot-key",
            )

        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "timeout")

    def test_generate_ai_comment_returns_validation_failure(self):
        adapter = FakeAdapter(ai_comment.RawModelResult(True, content="Visit https://example.com"))

        with patch.object(ai_comment, "get_provider_adapter", return_value=adapter):
            result = ai_comment.generate_ai_comment(
                {"title": "Useful tool demo"},
                self.enabled_config(),
                lambda provider: "moonshot-key",
            )

        self.assertFalse(result["ok"])
        self.assertEqual(result["source"], "validation")
        self.assertEqual(result["reason"], "url")

    def test_generate_ai_comment_rejects_unsafe_tone_and_falls_back_by_caller_reason(self):
        adapter = FakeAdapter(ai_comment.RawModelResult(True, content="This product looks fake"))

        with patch.object(ai_comment, "get_provider_adapter", return_value=adapter):
            result = ai_comment.generate_ai_comment(
                {"title": "Useful tool demo"},
                self.enabled_config(),
                lambda provider: "moonshot-key",
            )

        self.assertFalse(result["ok"])
        self.assertEqual(result["source"], "validation")
        self.assertEqual(result["reason"], "unsafe_tone")

    def test_generate_ai_comment_skips_unsafe_video_context_before_model_call(self):
        adapter = FakeAdapter(ai_comment.RawModelResult(True, content="Thanks for sharing"))

        with patch.object(ai_comment, "get_provider_adapter", return_value=adapter):
            result = ai_comment.generate_ai_comment(
                {"title": "This product looks fake", "description": ""},
                self.enabled_config(),
                lambda provider: "moonshot-key",
            )

        self.assertFalse(result["ok"])
        self.assertEqual(result["source"], "validation")
        self.assertEqual(result["reason"], "unsafe_context")
        self.assertEqual(adapter.calls, [])

    def test_generate_ai_comment_skips_without_video_context(self):
        result = ai_comment.generate_ai_comment(
            {"title": "", "description": "  "},
            self.enabled_config(),
            lambda provider: "moonshot-key",
        )

        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "missing_context")

    def test_generate_ai_comment_supports_fake_custom_provider_without_business_change(self):
        adapter = FakeAdapter(ai_comment.RawModelResult(True, content="Great breakdown"))

        with patch.object(ai_comment, "get_provider_adapter", return_value=adapter) as get_adapter:
            result = ai_comment.generate_ai_comment(
                {"title": "Useful tool demo"},
                self.enabled_config(provider="openai_compatible_custom", model="custom-model"),
                lambda provider: "custom-key",
            )

        self.assertTrue(result["ok"])
        self.assertEqual(result["comment"], "Great breakdown")
        get_adapter.assert_called_once_with("openai_compatible_custom")
        self.assertEqual(adapter.calls[0][1]["model"], "custom-model")

    def test_choose_comment_text_does_not_fallback_pool_for_unsafe_video_context(self):
        text, event = tiktok_actions.choose_comment_text(
            ["Love this"],
            {"title": "This product looks fake", "description": ""},
            self.enabled_config(),
        )

        self.assertEqual(text, "")
        self.assertEqual(event["status"], "fail")
        self.assertIn("reason=unsafe_context", event["detail"])
        self.assertIn("fallback=none", event["detail"])


class AiCommentAdapterTests(unittest.TestCase):
    def test_chat_completions_adapter_posts_bearer_request_and_parses_content(self):
        session = FakeSession(
            FakeResponse({"choices": [{"message": {"content": "Nice perspective"}}]})
        )
        adapter = ai_comment.ChatCompletionsAdapter(session=session)

        result = adapter.generate(
            {"title": "A helpful workflow", "description": "Short demo"},
            {
                "base_url": "https://api.moonshot.cn/v1/",
                "model": "kimi-k3",
                "timeout_seconds": 7,
                "max_comment_length": 80,
                "language": "English",
            },
            "moonshot-key",
        )

        self.assertTrue(result.ok)
        self.assertEqual(result.content, "Nice perspective")
        call = session.calls[0]
        self.assertEqual(call["url"], "https://api.moonshot.cn/v1/chat/completions")
        self.assertEqual(call["headers"]["Authorization"], "Bearer moonshot-key")
        self.assertEqual(call["timeout"], 7)
        self.assertEqual(call["json"]["model"], "kimi-k3")
        self.assertEqual(call["json"]["thinking"], {"type": "disabled"})
        self.assertEqual(call["json"]["temperature"], 0.6)
        self.assertEqual(call["json"]["max_tokens"], 600)
        self.assertIn("max_tokens", call["json"])
        self.assertNotIn("max_completion_tokens", call["json"])

    def test_chat_completions_adapter_accepts_full_endpoint_base_url(self):
        session = FakeSession(
            FakeResponse({"choices": [{"message": {"content": "Nice perspective"}}]})
        )
        adapter = ai_comment.ChatCompletionsAdapter(session=session)

        adapter.generate(
            {"title": "A helpful workflow"},
            {
                "base_url": "https://api.moonshot.cn/v1/chat/completions",
                "model": "kimi-k3",
            },
            "moonshot-key",
        )

        self.assertEqual(
            session.calls[0]["url"],
            "https://api.moonshot.cn/v1/chat/completions",
        )

    def test_chat_completions_adapter_reports_timeout(self):
        adapter = ai_comment.ChatCompletionsAdapter(
            session=FakeSession(error=requests.Timeout("api_key=secret timed out"))
        )

        result = adapter.generate(
            {"title": "A helpful workflow"},
            {"base_url": "https://api.moonshot.cn/v1", "model": "kimi-k3"},
            "moonshot-key",
        )

        self.assertFalse(result.ok)
        self.assertEqual(result.reason, "timeout")
        self.assertNotIn("secret", result.error)

    def test_chat_completions_adapter_reports_invalid_request_detail(self):
        adapter = ai_comment.ChatCompletionsAdapter(
            session=FakeSession(
                FakeResponse(
                    status_error=requests.HTTPError("400 Client Error: Bad Request"),
                    status_code=400,
                    text="invalid parameter: temperature",
                )
            )
        )

        result = adapter.generate(
            {"title": "A helpful workflow"},
            {"base_url": "https://api.moonshot.cn/v1", "model": "kimi-k2.6"},
            "moonshot-key",
        )

        self.assertFalse(result.ok)
        self.assertEqual(result.reason, "invalid_request")
        self.assertIn("invalid parameter", result.error)

    def test_chat_completions_adapter_reports_invalid_response_shape(self):
        adapter = ai_comment.ChatCompletionsAdapter(session=FakeSession(FakeResponse({"choices": []})))

        result = adapter.generate(
            {"title": "A helpful workflow"},
            {"base_url": "https://api.moonshot.cn/v1", "model": "kimi-k3"},
            "moonshot-key",
        )

        self.assertFalse(result.ok)
        self.assertEqual(result.reason, "invalid_response")

    def test_chat_completions_adapter_reports_empty_content_with_finish_reason(self):
        adapter = ai_comment.ChatCompletionsAdapter(
            session=FakeSession(FakeResponse({"choices": [{"message": {"content": ""}, "finish_reason": "length"}]}))
        )

        result = adapter.generate(
            {"title": "Tip"},
            {"base_url": "https://api.moonshot.cn/v1", "model": "kimi-k2.6"},
            "moonshot-key",
        )

        self.assertFalse(result.ok)
        self.assertEqual(result.reason, "empty")
        self.assertIn("finish_reason=length", result.error)

    def test_runtime_ai_comment_json_output_is_ascii_safe(self):
        payload = {"comment": "Okay I\u2019m testing 中文"}

        with patch("builtins.print") as print_mock:
            runtime_cli.print_json(payload)

        output = print_mock.call_args.args[0]
        output.encode("ascii")
        self.assertIn("\\u2019", output)
        self.assertEqual(json.loads(output)["comment"], payload["comment"])


class AiCommentValidationTests(unittest.TestCase):
    def assert_invalid(self, text, reason, **config):
        result = ai_comment.validate_generated_comment(text, config)
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], reason)

    def test_validate_generated_comment_accepts_clean_single_line(self):
        result = ai_comment.validate_generated_comment("  This is genuinely useful  ")

        self.assertTrue(result["ok"])
        self.assertEqual(result["comment"], "This is genuinely useful")

    def test_validate_generated_comment_accepts_neutral_supportive_comment(self):
        result = ai_comment.validate_generated_comment("Thanks for sharing this perspective")

        self.assertTrue(result["ok"])
        self.assertEqual(result["comment"], "Thanks for sharing this perspective")

    def test_validation_rejects_empty_text(self):
        self.assert_invalid("   ", "empty")

    def test_validation_rejects_multiline_text(self):
        self.assert_invalid("Nice\nSecond line", "multiline")

    def test_validation_rejects_url(self):
        self.assert_invalid("Check www.example.com", "url")

    def test_validation_rejects_mentions(self):
        self.assert_invalid("Great point @creator", "mention")

    def test_validation_rejects_email(self):
        self.assert_invalid("Email me test@example.com", "contact")

    def test_validation_rejects_phone(self):
        self.assert_invalid("Call +1 555 123 4567", "contact")

    def test_validation_rejects_messaging_contact(self):
        self.assert_invalid("Message me on WhatsApp", "contact")

    def test_validation_rejects_too_long(self):
        self.assert_invalid("This comment is too long", "too_long", max_comment_length=8)

    def test_validation_rejects_blocked_word(self):
        self.assert_invalid("This brand is scammy", "blocked_word", blocked_words=["scam"])

    def test_validation_rejects_model_explanation_prefix(self):
        self.assert_invalid("评论：这个视频很实用", "prefixed_explanation")

    def test_validation_rejects_negative_tone(self):
        self.assert_invalid("This is terrible", "unsafe_tone")

    def test_validation_rejects_uncertain_tone(self):
        self.assert_invalid("Not sure about this", "unsafe_tone")

    def test_validation_rejects_sarcastic_tone(self):
        self.assert_invalid("Yeah right, nice try", "unsafe_tone")

    def test_validation_rejects_controversial_tone(self):
        self.assert_invalid("This drama is getting political", "unsafe_tone")

    def test_validation_rejects_chinese_unsafe_tone(self):
        self.assert_invalid("这个产品看起来太假了", "unsafe_tone")


if __name__ == "__main__":
    unittest.main()
