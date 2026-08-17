"""AI-generated short comments for TikTok warmup flows."""
from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping
from urllib.parse import urljoin

import requests

from platform_config import DEFAULT_AI_COMMENT_CONFIG


CredentialReader = Callable[[str], str | None]
AI_COMMENT_API_KEY_ENV = "AM_AI_COMMENT_API_KEY"

DEFAULT_SYSTEM_PROMPT = (
    "你只输出一句适合 TikTok 视频的自然短评论，不要解释，不要换行，"
    "不要包含链接、@或联系方式。评论必须非负面：优先正向，允许中性支持；"
    "不得批评、嘲讽、抱怨、争议化，或攻击创作者、品牌、产品、用户。"
)

URL_RE = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PHONE_RE = re.compile(r"(?<!\w)(?:\+?\d[\d\s().-]{6,}\d)(?!\w)")
CONTACT_RE = re.compile(
    r"\b(?:whatsapp|telegram|telgram|tg|wechat|weixin|line|kakao|snapchat)\b",
    re.IGNORECASE,
)
EXPLANATION_PREFIX_RE = re.compile(
    r"^\s*(?:"
    r"here(?:'s| is)\b.*?:|"
    r"sure\b.*?:|"
    r"certainly\b.*?:|"
    r"comment\s*:|"
    r"caption\s*:|"
    r"评论\s*[：:]|"
    r"当然可以[，,:：]?|"
    r"可以这样评论[：:]?"
    r")",
    re.IGNORECASE,
)
NEGATIVE_TONE_RE = re.compile(
    r"\b(?:"
    r"awful|bad|boring|cringe|cringey|disappointing|dumb|fake|garbage|gross|hate|hated|horrible|"
    r"lame|overpriced|pathetic|problematic|ripoff|scam|scammy|sketchy|stupid|sucks?|terrible|"
    r"toxic|trash|ugly|useless|waste|worst"
    r")\b|"
    r"(?:差评|垃圾|恶心|讨厌|糟糕|难看|无聊|骗局|骗子|虚假|太假|智商税|割韭菜|翻车|避雷|"
    r"拉胯|离谱|尴尬|失望|不行|很差|太差|差劲|有毒|没用|废物)",
    re.IGNORECASE,
)
UNCERTAIN_TONE_RE = re.compile(
    r"\b(?:"
    r"not sure|idk|i don't know|i dont know|doubt(?:ful)?|questionable|seems off|not convinced|"
    r"hard to believe|looks suspicious|looks fake|feels fake"
    r")\b|"
    r"(?:不确定|不好说|有点怀疑|怀疑|可疑|看不懂|不太信|不敢信|真的假的|靠谱吗|有问题)",
    re.IGNORECASE,
)
SARCASM_TONE_RE = re.compile(
    r"\b(?:yeah right|sure jan|as if|what a joke|nice try|lol no|lmao no|hard pass)\b|"
    r"(?:呵呵|笑死|就这|真会玩|开玩笑吧|别逗了|算了吧)",
    re.IGNORECASE,
)
CONTROVERSIAL_TONE_RE = re.compile(
    r"\b(?:cancel(?:led|ed)?|boycott|drama|controversial|fight|argue|politics|political|racist|sexist)\b|"
    r"(?:抵制|争议|吵架|撕逼|政治|种族歧视|性别歧视|网暴)",
    re.IGNORECASE,
)
AUTH_RE = re.compile(r"(Authorization\s*[:=]\s*Bearer\s+)([^\s,;]+)", re.IGNORECASE)
KEY_VALUE_SECRET_RE = re.compile(
    r"\b(api[_-]?key|apikey|token|secret|authorization)(\s*[:=]\s*)([^\s,;]+)",
    re.IGNORECASE,
)


@dataclass
class RawModelResult:
    ok: bool
    content: str = ""
    reason: str = "generated"
    error: str = ""


class ProviderAdapter:
    def generate(
        self,
        context: Mapping[str, Any],
        config: Mapping[str, Any],
        api_key: str,
    ) -> RawModelResult:
        raise NotImplementedError


class ChatCompletionsAdapter(ProviderAdapter):
    """OpenAI-compatible Chat Completions adapter used by Kimi Moonshot."""

    def __init__(self, session: Any = requests):
        self.session = session

    def generate(
        self,
        context: Mapping[str, Any],
        config: Mapping[str, Any],
        api_key: str,
    ) -> RawModelResult:
        url = chat_completions_url(config_value(config, "base_url"))
        timeout = int_config(config, "timeout_seconds", DEFAULT_AI_COMMENT_CONFIG["timeout_seconds"])
        body = build_chat_completions_payload(context, config)
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        try:
            response = self.session.post(url, headers=headers, json=body, timeout=timeout)
            response.raise_for_status()
            data = response.json()
        except requests.Timeout as exc:
            return RawModelResult(False, reason="timeout", error=redact_error(exc))
        except requests.HTTPError as exc:
            return RawModelResult(False, reason=http_error_reason(exc), error=redact_error(http_error_detail(exc)))
        except requests.RequestException as exc:
            return RawModelResult(False, reason="network_error", error=redact_error(exc))
        except ValueError as exc:
            return RawModelResult(False, reason="invalid_response", error=redact_error(exc))

        try:
            choice = data["choices"][0]
            content = choice["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            return RawModelResult(False, reason="invalid_response", error=redact_error(exc))

        if not isinstance(content, str):
            return RawModelResult(False, reason="invalid_response", error="message content is not a string")
        if not content.strip():
            finish_reason = choice.get("finish_reason", "unknown") if isinstance(choice, Mapping) else "unknown"
            return RawModelResult(
                False,
                reason="empty",
                error=f"empty message content; finish_reason={finish_reason}",
            )
        return RawModelResult(True, content=content)


def generate_ai_comment(
    context: Mapping[str, Any],
    config: Mapping[str, Any] | None,
    credential_reader: CredentialReader,
) -> dict[str, Any]:
    """Generate and validate one comment using the configured provider adapter."""
    started = time.monotonic()
    merged_config = normalize_ai_comment_config(config)
    provider = merged_config["provider"]

    if not merged_config["enabled"]:
        return failure("disabled", started)
    if not has_video_context(context):
        return failure("missing_context", started)
    if has_disallowed_video_context(context):
        return failure("unsafe_context", started, source="validation")

    try:
        api_key = credential_reader(provider)
    except Exception as exc:
        return failure("credential_error", started, redact_error(exc))
    if not api_key:
        return failure("missing_api_key", started)

    adapter = get_provider_adapter(provider)
    if adapter is None:
        return failure("unsupported_provider", started)

    raw = adapter.generate(context, merged_config, api_key)
    if not raw.ok:
        return failure(raw.reason, started, raw.error)

    validation = validate_generated_comment(raw.content, merged_config)
    if not validation["ok"]:
        return failure(validation["reason"], started, source="validation")

    return {
        "ok": True,
        "comment": validation["comment"],
        "source": "ai",
        "reason": "generated",
        "latency_ms": elapsed_ms(started),
    }


def validate_generated_comment(text: Any, config: Mapping[str, Any] | None = None) -> dict[str, Any]:
    merged_config = normalize_ai_comment_config(config)
    raw = "" if text is None else str(text)
    stripped = raw.strip()

    if not stripped:
        return validation_failure("empty")
    if "\n" in stripped or "\r" in stripped:
        return validation_failure("multiline")
    if EXPLANATION_PREFIX_RE.search(stripped):
        return validation_failure("prefixed_explanation")

    comment = normalize_inline_space(stripped)
    if not comment:
        return validation_failure("empty")
    if URL_RE.search(comment):
        return validation_failure("url")
    if EMAIL_RE.search(comment) or PHONE_RE.search(comment) or CONTACT_RE.search(comment):
        return validation_failure("contact")
    if "@" in comment:
        return validation_failure("mention")
    if len(comment) > int_config(merged_config, "max_comment_length", DEFAULT_AI_COMMENT_CONFIG["max_comment_length"]):
        return validation_failure("too_long")

    lowered = comment.casefold()
    for word in merged_config.get("blocked_words") or []:
        blocked = str(word).strip().casefold()
        if blocked and blocked in lowered:
            return validation_failure("blocked_word")
    if has_disallowed_tone(comment):
        return validation_failure("unsafe_tone")

    return {
        "ok": True,
        "comment": comment,
        "reason": "valid",
    }


def build_chat_completions_payload(
    context: Mapping[str, Any],
    config: Mapping[str, Any],
) -> dict[str, Any]:
    max_length = int_config(config, "max_comment_length", DEFAULT_AI_COMMENT_CONFIG["max_comment_length"])
    title = normalize_inline_space(str(context.get("title") or ""))
    description = normalize_inline_space(str(context.get("description") or ""))
    language = config_value(config, "language", DEFAULT_AI_COMMENT_CONFIG["language"])
    user_content = (
        f"视频标题：{title}\n"
        f"视频描述：{description}\n"
        f"要求：{max_length}字以内，自然、友好、不要营销；必须是正向或中性支持，"
        f"不要负面、质疑、讽刺、抱怨、争议化，不评价创作者/品牌/产品/用户的缺点。"
        f"语言偏好：{language}。"
    )
    return {
        "model": config_value(config, "model", DEFAULT_AI_COMMENT_CONFIG["model"]),
        "messages": [
            {"role": "system", "content": DEFAULT_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        "thinking": {"type": "disabled"},
        "temperature": 0.6,
        "max_tokens": max(600, max_length * 2),
    }


def chat_completions_url(base_url: str) -> str:
    value = (base_url or DEFAULT_AI_COMMENT_CONFIG["base_url"]).strip()
    if value.rstrip("/").endswith("/chat/completions"):
        return value
    return urljoin(value.rstrip("/") + "/", "chat/completions")


def get_provider_adapter(provider: str) -> ProviderAdapter | None:
    provider = str(provider or "").strip()
    if provider in {"kimi_moonshot", "openai_compatible_custom"}:
        return ChatCompletionsAdapter()
    return None


def read_api_key_from_env(provider: str) -> str | None:
    provider = str(provider or "").strip()
    if provider == "kimi_moonshot":
        return os.environ.get(AI_COMMENT_API_KEY_ENV) or os.environ.get("MOONSHOT_API_KEY")
    return os.environ.get(AI_COMMENT_API_KEY_ENV)


def normalize_ai_comment_config(config: Mapping[str, Any] | None) -> dict[str, Any]:
    merged = dict(DEFAULT_AI_COMMENT_CONFIG)
    if config:
        for key in merged:
            if key in config:
                merged[key] = config[key]
    merged["enabled"] = bool(merged.get("enabled"))
    merged["provider"] = config_value(merged, "provider", DEFAULT_AI_COMMENT_CONFIG["provider"])
    merged["base_url"] = config_value(merged, "base_url", DEFAULT_AI_COMMENT_CONFIG["base_url"])
    merged["model"] = config_value(merged, "model", DEFAULT_AI_COMMENT_CONFIG["model"])
    merged["language"] = config_value(merged, "language", DEFAULT_AI_COMMENT_CONFIG["language"])
    merged["fallback_to_pool"] = bool(merged.get("fallback_to_pool", True))
    merged["timeout_seconds"] = int_config(merged, "timeout_seconds", DEFAULT_AI_COMMENT_CONFIG["timeout_seconds"])
    merged["max_comment_length"] = int_config(
        merged,
        "max_comment_length",
        DEFAULT_AI_COMMENT_CONFIG["max_comment_length"],
    )
    blocked_words = merged.get("blocked_words")
    if not isinstance(blocked_words, list):
        blocked_words = []
    merged["blocked_words"] = [str(word).strip() for word in blocked_words if str(word).strip()]
    return merged


def has_video_context(context: Mapping[str, Any]) -> bool:
    return bool(normalize_inline_space(str(context.get("title") or "")) or normalize_inline_space(str(context.get("description") or "")))


def has_disallowed_video_context(context: Mapping[str, Any]) -> bool:
    title = normalize_inline_space(str(context.get("title") or ""))
    description = normalize_inline_space(str(context.get("description") or ""))
    return has_disallowed_tone(f"{title} {description}")


def has_disallowed_tone(comment: str) -> bool:
    return any(
        pattern.search(comment)
        for pattern in (
            NEGATIVE_TONE_RE,
            UNCERTAIN_TONE_RE,
            SARCASM_TONE_RE,
            CONTROVERSIAL_TONE_RE,
        )
    )


def failure(
    reason: str,
    started: float,
    error: str = "",
    source: str = "ai",
) -> dict[str, Any]:
    result = {
        "ok": False,
        "comment": "",
        "source": source,
        "reason": reason,
        "latency_ms": elapsed_ms(started),
    }
    if error:
        result["error"] = redact_error(error)
    return result


def validation_failure(reason: str) -> dict[str, Any]:
    return {
        "ok": False,
        "comment": "",
        "reason": reason,
    }


def elapsed_ms(started: float) -> int:
    return max(0, int((time.monotonic() - started) * 1000))


def normalize_inline_space(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def config_value(
    config: Mapping[str, Any],
    key: str,
    default: str = "",
) -> str:
    value = config.get(key, default)
    value = str(value or default).strip()
    return value or default


def int_config(config: Mapping[str, Any], key: str, default: int) -> int:
    try:
        value = int(config.get(key, default))
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def redact_error(error: Any) -> str:
    text = str(error or "")
    text = AUTH_RE.sub(r"\1***", text)
    text = KEY_VALUE_SECRET_RE.sub(r"\1\2***", text)
    return text


def http_error_reason(error: requests.HTTPError) -> str:
    status_code = getattr(getattr(error, "response", None), "status_code", None)
    if status_code == 400:
        return "invalid_request"
    if status_code == 401:
        return "unauthorized"
    if status_code == 403:
        return "forbidden"
    if status_code == 404:
        return "not_found"
    if status_code == 429:
        return "rate_limited"
    if isinstance(status_code, int) and status_code >= 500:
        return "server_error"
    return "http_error"


def http_error_detail(error: requests.HTTPError) -> str:
    response = getattr(error, "response", None)
    detail = str(error)
    if response is None:
        return detail
    body = ""
    try:
        data = response.json()
        body = data.get("error") if isinstance(data, dict) else ""
        if isinstance(body, dict):
            body = body.get("message") or str(body)
    except Exception:
        body = getattr(response, "text", "") or ""
    if not body:
        body = getattr(response, "text", "") or ""
    body = " ".join(str(body or "").split())
    if body:
        return f"{detail}; {body[:500]}"
    return detail
