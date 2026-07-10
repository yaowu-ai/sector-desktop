from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from http.cookies import SimpleCookie
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import parse_qs, urlparse

try:
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover
    sync_playwright = None
    PlaywrightTimeoutError = Exception


CHAT_URL = "https://www.douyin.com/chat?isPopup=1"
OUTPUT_TIMEZONE = timezone(timedelta(hours=8), "Asia/Shanghai")
DEFAULT_CUTOFF_YEAR = 2024
PROJECT_ROOT = Path(__file__).resolve().parent

CHAT_URL_MARKERS = (
    "/chat",
    "/im/",
    "/message",
    "/conversation",
    "/session",
    "/inbox",
    "conversation",
    "message",
)
DOUYIN_HOST_MARKERS = ("douyin.com", "douyinpic.com", "douyinvod.com")

USER_ID_KEYS = (
    "user_id",
    "uid",
    "id",
    "webcast_uid",
    "to_user_id",
    "from_user_id",
)
SEC_UID_KEYS = ("sec_uid", "sec_user_id", "secUserId")
SHORT_ID_KEYS = ("short_id", "shortId", "display_id", "displayId")
NICKNAME_KEYS = ("nickname", "nick_name", "nickName", "name", "display_name", "remark_name", "alias")
IP_KEYS = ("ip_label", "ip_location", "ipLocation", "city", "province", "location")
USER_INFO_API_MARKER = "/aweme/v1/web/im/user/info/"
USER_INFO_REQUEST_ID_KEYS = (
    "uid",
    "uids",
    "user_id",
    "user_ids",
    "to_user_id",
    "to_user_ids",
    "from_user_id",
    "from_user_ids",
    "sec_uid",
    "sec_uids",
    "sec_user_id",
    "sec_user_ids",
)
CONVERSATION_ID_KEYS = (
    "conversation_id",
    "conversationId",
    "conversation_short_id",
    "conversationShortId",
    "chat_id",
    "session_id",
    "sessionId",
    "room_id",
    "roomId",
)
MESSAGE_ID_KEYS = (
    "message_id",
    "messageId",
    "server_message_id",
    "serverMessageId",
    "msg_id",
    "msgId",
    "client_message_id",
    "clientMessageId",
    "uuid",
)
TIME_KEYS = (
    "create_time",
    "createTime",
    "created_at",
    "createdAt",
    "send_time",
    "sendTime",
    "server_time",
    "serverTime",
    "timestamp",
    "time",
)
SENDER_ID_KEYS = (
    "sender",
    "sender_id",
    "senderId",
    "from_user_id",
    "fromUserId",
    "from_uid",
    "fromUid",
    "uid",
)
TEXT_KEYS = (
    "text",
    "content",
    "message",
    "msg",
    "body",
    "desc",
    "summary",
    "push_content",
    "pushContent",
    "text_content",
    "textContent",
    "conversation_digest",
    "conversationDigest",
)
SELF_KEYS = ("is_self", "isSelf", "from_self", "fromSelf", "is_sender", "isSender")
SYSTEM_MESSAGE_PATTERNS = (
    "对方回复",
    "关注你之前",
    "只能发送一条",
    "请礼貌发言",
    "自觉遵守",
    "抖音自律公约",
    "系统消息",
    "安全提示",
    "风险提示",
    "撤回了一条消息",
    "以上是打招呼",
)


class BrowserClosedError(RuntimeError):
    pass


def project_default_path(value: str | None, default_name: str) -> Path:
    if value is None:
        return PROJECT_ROOT / default_name
    return Path(value).expanduser()


@dataclass
class Message:
    message_id: str = ""
    text: str = ""
    create_time: str | None = None
    raw_time: Any = None
    sender_id: str = ""
    sender_nickname: str = ""
    is_from_self: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "time": self.create_time or "",
            "message": self.text,
        }


@dataclass
class Chat:
    conversation_id: str = ""
    user_id: str = ""
    sec_uid: str = ""
    short_id: str = ""
    nickname: str = ""
    ip_label: str = ""
    messages: OrderedDict[str, Message] = field(default_factory=OrderedDict)

    def merge_user(self, user: dict[str, Any]) -> None:
        self.user_id = self.user_id or clean_id(first_value(user, USER_ID_KEYS))
        self.sec_uid = self.sec_uid or clean_id(first_value(user, SEC_UID_KEYS))
        self.short_id = self.short_id or clean_id(first_value(user, SHORT_ID_KEYS))
        self.nickname = self.nickname or clean_text(first_value(user, NICKNAME_KEYS))
        self.ip_label = self.ip_label or clean_text(first_value(user, IP_KEYS))

    def merge_message(self, message: Message) -> None:
        if not message.text:
            return
        if message.is_from_self is True:
            return
        if (
            self.nickname
            and message.sender_nickname
            and clean_text(message.sender_nickname) != clean_text(self.nickname)
        ):
            return
        if is_system_message_text(message.text):
            return
        key = message_key(message)
        existing = self.messages.get(key)
        if existing is None:
            self.messages[key] = message
            return
        existing.message_id = existing.message_id or message.message_id
        existing.create_time = existing.create_time or message.create_time
        existing.raw_time = existing.raw_time if existing.raw_time not in (None, "") else message.raw_time
        existing.sender_id = existing.sender_id or message.sender_id
        existing.sender_nickname = existing.sender_nickname or message.sender_nickname
        if existing.is_from_self is None:
            existing.is_from_self = message.is_from_self

    def to_dict(self) -> dict[str, Any]:
        return {
            "nickname": self.nickname,
            "short_id": self.short_id,
            "content": [message.to_dict() for message in sorted_messages(self.messages.values())],
        }


class ChatStore:
    def __init__(self) -> None:
        self.chats: OrderedDict[str, Chat] = OrderedDict()
        self.chat_aliases: dict[str, str] = {}
        self.users_by_id: dict[str, dict[str, Any]] = {}
        self.response_count = 0
        self.relevant_response_count = 0

    def get_chat(self, key: str, conversation_id: str = "") -> Chat:
        key = key or conversation_id or "unknown"
        key = self.chat_aliases.get(key, key)
        chat = self.chats.get(key)
        if chat is None:
            chat = Chat(conversation_id=conversation_id)
            self.chats[key] = chat
        elif conversation_id and not chat.conversation_id:
            chat.conversation_id = conversation_id
        return chat

    def merge_chat(self, target: Chat, source: Chat) -> None:
        target.conversation_id = target.conversation_id or source.conversation_id
        target.user_id = target.user_id or source.user_id
        target.sec_uid = target.sec_uid or source.sec_uid
        target.short_id = target.short_id or source.short_id
        target.nickname = target.nickname or source.nickname
        target.ip_label = target.ip_label or source.ip_label
        for message in source.messages.values():
            target.merge_message(message)

    def get_or_merge_chat_for_user(self, candidate_keys: list[str], conversation_id: str = "") -> Chat:
        candidate_keys = [key for key in candidate_keys if key]
        if not candidate_keys:
            return self.get_chat(conversation_id or "unknown", conversation_id)

        canonical_key = ""
        for key in candidate_keys:
            resolved = self.chat_aliases.get(key, key)
            if resolved in self.chats:
                canonical_key = resolved
                break

        if not canonical_key:
            canonical_key = candidate_keys[0]
            chat = self.get_chat(canonical_key, conversation_id)
        else:
            chat = self.chats[canonical_key]
            if conversation_id and not chat.conversation_id:
                chat.conversation_id = conversation_id

        for key in candidate_keys:
            resolved = self.chat_aliases.get(key, key)
            if resolved != canonical_key and resolved in self.chats:
                self.merge_chat(chat, self.chats[resolved])
                del self.chats[resolved]
            self.chat_aliases[key] = canonical_key
        return chat

    def add_user(self, user: dict[str, Any]) -> None:
        user_id = clean_id(first_value(user, USER_ID_KEYS))
        sec_uid = clean_id(first_value(user, SEC_UID_KEYS))
        short_id = clean_id(first_value(user, SHORT_ID_KEYS))
        key = user_id or sec_uid or short_id
        if not key:
            return

        existing = self.users_by_id.setdefault(key, {})
        for item_key, value in user.items():
            if existing.get(item_key) in (None, "") and value not in (None, ""):
                existing[item_key] = value

    def add_chat_user(self, conversation_id: str, user: dict[str, Any]) -> None:
        self.add_user(user)
        user_id = clean_id(first_value(user, USER_ID_KEYS))
        sec_uid = clean_id(first_value(user, SEC_UID_KEYS))
        short_id = clean_id(first_value(user, SHORT_ID_KEYS))
        nickname = clean_text(first_value(user, NICKNAME_KEYS))
        candidate_keys = [conversation_id, user_id, sec_uid, short_id, nickname]
        chat = self.get_or_merge_chat_for_user(candidate_keys, conversation_id)
        chat.merge_user(user)

    def find_chat_by_nickname(self, nickname: str) -> Chat | None:
        nickname = clean_text(nickname)
        if not nickname:
            return None
        for chat in self.chats.values():
            if clean_text(chat.nickname) == nickname:
                return chat
        return None

    def add_user_info_response(self, url: str, payload: Any) -> None:
        requested_ids = extract_user_ids_from_url(url)
        users = extract_user_info_records(payload)
        for index, user in enumerate(users):
            if not isinstance(user, dict):
                continue
            requested_id = requested_ids[index] if index < len(requested_ids) else ""
            user = dict(user)
            if requested_id:
                if requested_id.isdigit():
                    user.setdefault("uid", requested_id)
                elif requested_id.startswith("MS"):
                    user.setdefault("sec_uid", requested_id)
            self.add_chat_user("", user)

    def add_message(self, conversation_id: str, message: Message, users: Iterable[dict[str, Any]]) -> None:
        users = list(users)
        for user in users:
            self.add_user(user)

        peer_user = choose_peer_user(users, message)
        key = conversation_id
        if not key and peer_user:
            key = clean_id(first_value(peer_user, USER_ID_KEYS)) or clean_id(first_value(peer_user, SEC_UID_KEYS))
        if not key and message.sender_id and not message.is_from_self:
            key = message.sender_id
        if not key:
            key = message.sender_nickname or message.message_id or message.text[:48]

        chat = self.get_chat(key, conversation_id)
        if peer_user:
            chat.merge_user(peer_user)
        elif message.sender_id and not message.is_from_self:
            chat.user_id = chat.user_id or message.sender_id
            chat.nickname = chat.nickname or message.sender_nickname
        chat.merge_message(message)

    def merge_dom_snapshot(self, snapshot: dict[str, Any]) -> None:
        if not snapshot:
            return
        conversation_id = clean_id(snapshot.get("conversation_id"))
        nickname = clean_text(snapshot.get("nickname"))
        chat = self.find_chat_by_nickname(nickname) or self.get_chat(conversation_id or nickname or "dom-current-chat", conversation_id)
        chat.nickname = chat.nickname or nickname
        for item in snapshot.get("messages") or []:
            if not isinstance(item, dict):
                continue
            text = clean_text(item.get("text"))
            if not text:
                continue
            if is_system_message_text(text):
                continue
            if is_before_cutoff_time(item.get("create_time")):
                continue
            message = Message(
                message_id=clean_id(item.get("message_id")),
                text=text,
                create_time=clean_text(item.get("create_time")),
                raw_time=item.get("create_time"),
                sender_nickname=clean_text(item.get("sender_nickname")) or ("syr" if item.get("is_from_self") else chat.nickname),
                is_from_self=item.get("is_from_self"),
            )
            chat.merge_message(message)

    def to_list(self) -> list[dict[str, Any]]:
        chats = list(self.chats.values())
        chats.sort(key=lambda item: chat_sort_key(item))
        return [chat.to_dict() for chat in chats if chat.messages or (chat.nickname and chat.short_id)]


def is_browser_closed_error(exc: BaseException) -> bool:
    text = f"{exc.__class__.__name__}: {exc}".lower()
    return (
        "targetclosederror" in text
        or "target page, context or browser has been closed" in text
        or "target closed" in text
    )


def raise_if_browser_closed(exc: BaseException, message: str) -> None:
    if is_browser_closed_error(exc):
        raise BrowserClosedError(message) from exc


def wait_for_page(page: Any, timeout_ms: int, message: str = "browser/page was closed while waiting") -> None:
    try:
        page.wait_for_timeout(timeout_ms)
    except Exception as exc:
        raise_if_browser_closed(exc, message)
        raise


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).replace("\u200b", "").replace("\ufeff", "").strip()
    text = re.sub(r"\s+", " ", text)
    return text


def clean_id(value: Any) -> str:
    text = clean_text(value)
    if text.lower() in {"none", "null", "undefined", "0"}:
        return ""
    return text


def is_system_message_text(value: Any) -> bool:
    text = clean_text(value)
    return any(pattern in text for pattern in SYSTEM_MESSAGE_PATTERNS)


def first_value(data: dict[str, Any], keys: Iterable[str]) -> Any:
    for key in keys:
        if key in data and data.get(key) not in (None, ""):
            return data.get(key)
    return None


def clean_timestamp(value: Any) -> str | None:
    if value in (None, ""):
        return None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if re.search(r"\d{4}[-/]\d{1,2}[-/]\d{1,2}", text):
            return text
        if re.fullmatch(r"\d+", text):
            value = int(text)
        else:
            return text
    try:
        timestamp = int(value)
    except (TypeError, ValueError):
        return clean_text(value)

    if abs(timestamp) > 10_000_000_000_000:
        timestamp = timestamp // 1_000_000
    elif abs(timestamp) > 10_000_000_000:
        timestamp = timestamp // 1000

    try:
        return datetime.fromtimestamp(timestamp, tz=OUTPUT_TIMEZONE).strftime("%Y-%m-%d %H:%M:%S")
    except (OSError, OverflowError, ValueError):
        return clean_text(value)


def timestamp_sort_value(value: Any) -> int:
    if value in (None, ""):
        return 0
    if isinstance(value, (int, float)):
        number = int(value)
        if abs(number) > 10_000_000_000_000:
            return number // 1_000_000
        if abs(number) > 10_000_000_000:
            return number // 1000
        return number
    text = clean_text(value)
    if re.fullmatch(r"\d+", text):
        return timestamp_sort_value(int(text))
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M:%S", "%Y/%m/%d %H:%M"):
        try:
            return int(datetime.strptime(text, fmt).replace(tzinfo=OUTPUT_TIMEZONE).timestamp())
        except ValueError:
            pass
    return 0


def explicit_year_from_time(value: Any) -> int | None:
    text = clean_text(value)
    if not text:
        return None
    match = re.search(r"(20\d{2})\s*[年/-]", text)
    if match:
        return int(match.group(1))
    match = re.search(r"(?<!\d)(\d{2})\s*年", text)
    if match:
        return 2000 + int(match.group(1))
    return None


def is_before_cutoff_time(value: Any, cutoff_year: int = DEFAULT_CUTOFF_YEAR) -> bool:
    year = explicit_year_from_time(value)
    return year is not None and year < cutoff_year


def snapshot_has_before_cutoff_time(snapshot: dict[str, Any], cutoff_year: int = DEFAULT_CUTOFF_YEAR) -> bool:
    for item in snapshot.get("messages") or []:
        if isinstance(item, dict) and is_before_cutoff_time(item.get("create_time"), cutoff_year):
            return True
    return False


def message_key(message: Message) -> str:
    if message.message_id:
        return message.message_id
    return "|".join(
        [
            message.sender_id,
            message.sender_nickname,
            clean_text(message.create_time),
            message.text[:100],
        ]
    )


def sorted_messages(messages: Iterable[Message]) -> list[Message]:
    return list(messages)


def chat_sort_key(chat: Chat) -> tuple[int, str]:
    latest = 0
    for message in chat.messages.values():
        latest = max(latest, timestamp_sort_value(message.raw_time or message.create_time))
    return (-latest, chat.nickname or chat.short_id or chat.user_id or chat.conversation_id)


def is_relevant_response_url(url: str) -> bool:
    lower_url = url.lower()
    if not any(marker in lower_url for marker in DOUYIN_HOST_MARKERS):
        return False
    return any(marker in lower_url for marker in CHAT_URL_MARKERS)


def is_douyin_url(url: str) -> bool:
    lower_url = url.lower()
    return any(marker in lower_url for marker in DOUYIN_HOST_MARKERS)


def is_user_info_response_url(url: str) -> bool:
    return USER_INFO_API_MARKER in url.lower()


def extract_user_ids_from_url(url: str) -> list[str]:
    query = parse_qs(urlparse(url).query)
    result: list[str] = []
    for key in USER_INFO_REQUEST_ID_KEYS:
        for value in query.get(key, []):
            for item in re.split(r"[,|]", value):
                item = clean_id(item)
                if item and item not in result:
                    result.append(item)
    return result


def extract_user_info_records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, list):
            direct_users = [item for item in data if isinstance(item, dict) and looks_user_like(item)]
            if direct_users:
                return dedupe_users(direct_users)
        if isinstance(data, dict) and looks_user_like(data):
            return [data]
    return extract_users(payload)


def looks_user_like(data: dict[str, Any]) -> bool:
    has_name = any(clean_text(data.get(key)) for key in NICKNAME_KEYS)
    has_id = any(clean_id(data.get(key)) for key in (*USER_ID_KEYS, *SEC_UID_KEYS, *SHORT_ID_KEYS))
    has_ip = any(clean_text(data.get(key)) for key in IP_KEYS)
    return (has_name and has_id) or (has_id and has_ip)


def looks_message_like(data: dict[str, Any]) -> bool:
    has_message_id = any(clean_id(data.get(key)) for key in MESSAGE_ID_KEYS)
    has_time = any(data.get(key) not in (None, "") for key in TIME_KEYS)
    has_text = bool(extract_text(data))
    has_sender = any(clean_id(data.get(key)) for key in SENDER_ID_KEYS)
    return has_text and (has_message_id or has_time or has_sender)


def looks_conversation_like(data: dict[str, Any]) -> bool:
    has_conversation = any(clean_id(data.get(key)) for key in CONVERSATION_ID_KEYS)
    has_user = any(key in data for key in ("user", "user_info", "to_user", "from_user", "participant", "members"))
    has_last_message = any(key in data for key in ("last_message", "lastMessage", "last_msg", "lastMsg"))
    return has_conversation and (has_user or has_last_message or any(clean_text(data.get(key)) for key in NICKNAME_KEYS))


def extract_conversation_id(data: dict[str, Any]) -> str:
    return clean_id(first_value(data, CONVERSATION_ID_KEYS))


def extract_message_id(data: dict[str, Any]) -> str:
    return clean_id(first_value(data, MESSAGE_ID_KEYS))


def extract_sender_id(data: dict[str, Any]) -> str:
    value = first_value(data, SENDER_ID_KEYS)
    if isinstance(value, dict):
        return clean_id(first_value(value, (*USER_ID_KEYS, *SEC_UID_KEYS)))
    return clean_id(value)


def extract_time_value(data: dict[str, Any]) -> Any:
    return first_value(data, TIME_KEYS)


def decode_jsonish_text(value: str) -> Any:
    text = value.strip()
    if not text:
        return ""
    if not ((text.startswith("{") and text.endswith("}")) or (text.startswith("[") and text.endswith("]"))):
        return value
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        return value


def extract_text(value: Any, depth: int = 0) -> str:
    if depth > 5 or value is None:
        return ""
    if isinstance(value, str):
        decoded = decode_jsonish_text(value)
        if decoded is not value:
            return extract_text(decoded, depth + 1)
        text = clean_text(value)
        if not text:
            return ""
        if text.startswith(("http://", "https://")):
            return text
        return text
    if isinstance(value, (int, float, bool)):
        return ""
    if isinstance(value, list):
        parts = [extract_text(item, depth + 1) for item in value]
        return clean_text(" ".join(part for part in parts if part))
    if not isinstance(value, dict):
        return ""

    for key in TEXT_KEYS:
        if key in value:
            text = extract_text(value.get(key), depth + 1)
            if text and not looks_like_metadata_text(text):
                return text

    for key in ("text_info", "textInfo", "rich_text", "richText", "image", "sticker", "audio", "video", "card"):
        if key in value:
            text = extract_text(value.get(key), depth + 1)
            if text and not looks_like_metadata_text(text):
                return text

    return ""


def looks_like_metadata_text(text: str) -> bool:
    if not text:
        return True
    if len(text) > 1000 and re.search(r'[{}":,\[\]]', text):
        return True
    return False


def extract_users(data: Any, depth: int = 0) -> list[dict[str, Any]]:
    if depth > 5 or data is None:
        return []
    users: list[dict[str, Any]] = []
    if isinstance(data, list):
        for item in data:
            users.extend(extract_users(item, depth + 1))
        return dedupe_users(users)
    if not isinstance(data, dict):
        return []

    if looks_user_like(data):
        users.append(data)

    user_hint = re.compile(r"(user|author|member|participant|profile|sender|receiver|from|to)", re.I)
    for key, value in data.items():
        if user_hint.search(str(key)):
            users.extend(extract_users(value, depth + 1))
    return dedupe_users(users)


def dedupe_users(users: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    result: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for user in users:
        if not isinstance(user, dict):
            continue
        user_id = clean_id(first_value(user, USER_ID_KEYS))
        sec_uid = clean_id(first_value(user, SEC_UID_KEYS))
        short_id = clean_id(first_value(user, SHORT_ID_KEYS))
        nickname = clean_text(first_value(user, NICKNAME_KEYS))
        key = user_id or sec_uid or short_id or nickname
        if not key:
            continue
        existing = result.setdefault(key, {})
        for item_key, value in user.items():
            if existing.get(item_key) in (None, "") and value not in (None, ""):
                existing[item_key] = value
    return list(result.values())


def choose_peer_user(users: list[dict[str, Any]], message: Message) -> dict[str, Any] | None:
    if not users:
        return None
    if message.sender_id and not message.is_from_self:
        for user in users:
            if clean_id(first_value(user, USER_ID_KEYS)) == message.sender_id:
                return user
    for user in users:
        nickname = clean_text(first_value(user, NICKNAME_KEYS))
        user_id = clean_id(first_value(user, USER_ID_KEYS))
        if nickname and nickname == message.sender_nickname:
            return user
        if user_id and user_id == message.sender_id and not message.is_from_self:
            return user
    if len(users) == 1:
        return users[0]
    return None


def extract_sender_nickname(data: dict[str, Any], sender_id: str) -> str:
    for key in ("sender", "sender_user", "senderUser", "from_user", "fromUser", "user", "author"):
        value = data.get(key)
        if not isinstance(value, dict):
            continue
        nickname = clean_text(first_value(value, NICKNAME_KEYS))
        if nickname:
            return nickname
    for user in extract_users(data):
        user_id = clean_id(first_value(user, USER_ID_KEYS))
        if sender_id and user_id == sender_id:
            return clean_text(first_value(user, NICKNAME_KEYS))
    return ""


def extract_self_flag(data: dict[str, Any]) -> bool | None:
    for key in SELF_KEYS:
        if key not in data:
            continue
        value = data.get(key)
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        text = clean_text(value).lower()
        if text in {"true", "1", "yes"}:
            return True
        if text in {"false", "0", "no"}:
            return False
    return None


def parse_json_payload(payload: Any, store: ChatStore) -> None:
    walk_payload(payload, store, [], "")


def walk_payload(node: Any, store: ChatStore, ancestors: list[dict[str, Any]], inherited_conversation_id: str) -> None:
    if isinstance(node, list):
        for item in node:
            walk_payload(item, store, ancestors, inherited_conversation_id)
        return
    if not isinstance(node, dict):
        return

    conversation_id = extract_conversation_id(node) or inherited_conversation_id
    users = extract_users(node)
    if looks_conversation_like(node):
        chat = store.get_chat(conversation_id, conversation_id)
        for user in users:
            chat.merge_user(user)
            store.add_user(user)
        if not chat.nickname:
            chat.nickname = clean_text(first_value(node, NICKNAME_KEYS))
        if not chat.ip_label:
            chat.ip_label = clean_text(first_value(node, IP_KEYS))

    if looks_user_like(node):
        store.add_chat_user(conversation_id, node)

    if looks_message_like(node):
        text = extract_text(node)
        raw_time = extract_time_value(node)
        sender_id = extract_sender_id(node)
        message = Message(
            message_id=extract_message_id(node),
            text=text,
            create_time=clean_timestamp(raw_time),
            raw_time=raw_time,
            sender_id=sender_id,
            sender_nickname=extract_sender_nickname(node, sender_id),
            is_from_self=extract_self_flag(node),
        )
        inherited_users: list[dict[str, Any]] = []
        for ancestor in ancestors:
            inherited_users.extend(extract_users(ancestor, depth=0))
        store.add_message(conversation_id, message, [*inherited_users, *users])

    next_ancestors = [*ancestors[-4:], node]
    for value in node.values():
        if isinstance(value, (dict, list)):
            walk_payload(value, store, next_ancestors, conversation_id)


def login_dialog_visible(page: Any) -> bool:
    try:
        return bool(
            page.evaluate(
                """() => {
                    if (document.querySelector('[id^="douyin_login"], [id*="login_comp"], #login-full-panel')) {
                        return true;
                    }
                    const text = document.body ? document.body.innerText : '';
                    return /扫码登录|验证码登录|手机号登录|登录后|请登录|未登录|login/i.test(text);
                }"""
            )
        )
    except Exception as exc:
        raise_if_browser_closed(exc, "browser/page was closed while checking login state")
        return False


def chat_page_ready(page: Any) -> bool:
    try:
        return bool(
            page.evaluate(
                """() => {
                    if (document.querySelector('[id^="douyin_login"], [id*="login_comp"], #login-full-panel')) {
                        return false;
                    }
                    const textLength = document.body && document.body.innerText ? document.body.innerText.trim().length : 0;
                    const scrollables = Array.from(document.querySelectorAll('*')).filter((el) => {
                        const rect = el.getBoundingClientRect();
                        return rect.left < 520 && rect.width > 160 && rect.height > 240 && el.scrollHeight > el.clientHeight + 20;
                    });
                    return textLength > 150 || scrollables.length > 1;
                }"""
            )
        )
    except Exception as exc:
        raise_if_browser_closed(exc, "browser/page was closed while checking chat readiness")
        return False


def wait_for_manual_login(page: Any, args: argparse.Namespace) -> bool:
    if args.headless:
        print("[warn] login appears to be required, but manual login needs --headed")
        return False
    if not args.login_prompt:
        print(f"[warn] cookie auto-login failed or expired; update {args.cookie_file} or rerun with --headed --login-prompt")
        return False
    if args.login_wait_seconds > 0:
        print(f"[login] 请在弹出的浏览器完成登录，脚本最多等待 {args.login_wait_seconds} 秒")
        deadline = time.monotonic() + args.login_wait_seconds
        while time.monotonic() < deadline:
            wait_for_page(page, 1000, "browser/page was closed while waiting for manual login")
            if not login_dialog_visible(page) and chat_page_ready(page):
                wait_for_page(page, args.initial_wait_ms, "browser/page was closed after login")
                return True
        print("[warn] login wait timed out")
        return False

    input("[login] 如页面要求登录，请在浏览器完成登录，然后按 Enter 继续：")
    try:
        page.reload(wait_until="domcontentloaded", timeout=args.timeout_ms)
    except PlaywrightTimeoutError:
        print("[warn] chat reload timed out; continuing")
    except Exception as exc:
        raise_if_browser_closed(exc, "browser/page was closed while reloading chat")
        raise
    wait_for_page(page, args.initial_wait_ms, "browser/page was closed after login reload")
    return True


def maybe_wait_for_network(page: Any, timeout_ms: int) -> None:
    try:
        page.wait_for_load_state("networkidle", timeout=timeout_ms)
    except PlaywrightTimeoutError:
        pass
    except Exception as exc:
        raise_if_browser_closed(exc, "browser/page was closed while waiting for network")
        raise


def scroll_page_and_scrollables(page: Any, delta_y: int) -> None:
    try:
        page.evaluate(
            """(deltaY) => {
                const scrollables = Array.from(document.querySelectorAll('*')).filter((el) => {
                    const style = window.getComputedStyle(el);
                    const overflowY = style.overflowY || '';
                    return /(auto|scroll|overlay)/.test(overflowY) && el.scrollHeight > el.clientHeight + 20;
                });
                window.scrollBy(0, deltaY);
                for (const el of scrollables) {
                    const rect = el.getBoundingClientRect();
                    if (rect.width < 80 || rect.height < 80) continue;
                    el.scrollTop += deltaY;
                }
            }""",
            delta_y,
        )
    except Exception as exc:
        raise_if_browser_closed(exc, "browser/page was closed while scrolling")
        raise


def scroll_message_panels(page: Any, delta_y: int) -> None:
    try:
        page.evaluate(
            """(deltaY) => {
                const width = window.innerWidth || document.documentElement.clientWidth || 1200;
                const scrollables = Array.from(document.querySelectorAll('*')).filter((el) => {
                    const style = window.getComputedStyle(el);
                    const overflowY = style.overflowY || '';
                    if (!/(auto|scroll|overlay)/.test(overflowY)) return false;
                    if (el.scrollHeight <= el.clientHeight + 20) return false;
                    const rect = el.getBoundingClientRect();
                    return rect.width > 220 && rect.height > 160 && rect.left > width * 0.18;
                });
                scrollables.sort((a, b) => {
                    const ar = a.getBoundingClientRect();
                    const br = b.getBoundingClientRect();
                    return (br.width * br.height) - (ar.width * ar.height);
                });
                for (const el of scrollables.slice(0, 3)) {
                    el.scrollTop += deltaY;
                }
            }""",
            delta_y,
        )
    except Exception as exc:
        raise_if_browser_closed(exc, "browser/page was closed while scrolling messages")
        raise


def scroll_conversation_list(page: Any, delta_y: int) -> None:
    try:
        page.evaluate(
            """(deltaY) => {
                const width = window.innerWidth || document.documentElement.clientWidth || 1200;
                const scrollables = Array.from(document.querySelectorAll('*')).filter((el) => {
                    const style = window.getComputedStyle(el);
                    const overflowY = style.overflowY || '';
                    if (!/(auto|scroll|overlay)/.test(overflowY)) return false;
                    if (el.scrollHeight <= el.clientHeight + 20) return false;
                    const rect = el.getBoundingClientRect();
                    return rect.left < Math.min(460, width * 0.32) && rect.width > 180 && rect.height > 240;
                });
                scrollables.sort((a, b) => {
                    const ar = a.getBoundingClientRect();
                    const br = b.getBoundingClientRect();
                    return (br.width * br.height) - (ar.width * ar.height);
                });
                const target = scrollables[0];
                if (target) {
                    target.scrollTop += deltaY;
                } else {
                    window.scrollBy(0, deltaY);
                }
            }""",
            delta_y,
        )
    except Exception as exc:
        raise_if_browser_closed(exc, "browser/page was closed while scrolling conversation list")
        raise


def mark_conversation_candidates(page: Any, limit: int) -> list[dict[str, Any]]:
    try:
        return page.evaluate(
            """(limit) => {
                const width = window.innerWidth || document.documentElement.clientWidth || 1200;
                const height = window.innerHeight || document.documentElement.clientHeight || 900;
                const old = document.querySelectorAll('[data-chat-crawler-index]');
                old.forEach((el) => el.removeAttribute('data-chat-crawler-index'));

                const seen = new Set();
                const candidates = [];
                const nodes = Array.from(document.querySelectorAll('li, [role="listitem"], [role="button"], button, a, div'));
                for (const el of nodes) {
                    const rect = el.getBoundingClientRect();
                    if (rect.width < 120 || rect.height < 36) continue;
                    if (rect.left > width * 0.45) continue;
                    if (rect.right < 80 || rect.top < 0 || rect.top > height - 24) continue;
                    const text = (el.innerText || el.textContent || '').replace(/\\s+/g, ' ').trim();
                    if (!text || text.length < 2 || text.length > 220) continue;
                    if (/登录|扫码|隐私政策|用户协议|设置|反馈|创作者服务|消息通知设置/.test(text)) continue;
                    const key = `${Math.round(rect.left)}:${Math.round(rect.top)}:${text.slice(0, 60)}`;
                    if (seen.has(key)) continue;
                    seen.add(key);
                    candidates.push({ el, rect, text });
                }

                candidates.sort((a, b) => a.rect.top - b.rect.top || b.rect.width - a.rect.width);
                const result = [];
                for (const item of candidates) {
                    if (result.some((prev) => Math.abs(prev.top - item.rect.top) < 8 && prev.text === item.text)) continue;
                    const index = result.length;
                    item.el.setAttribute('data-chat-crawler-index', String(index));
                    result.push({
                        index,
                        text: item.text,
                        top: item.rect.top,
                        x: item.rect.left + item.rect.width / 2,
                        y: item.rect.top + item.rect.height / 2,
                    });
                    if (result.length >= limit) break;
                }
                return result;
            }""",
            limit,
        )
    except Exception as exc:
        raise_if_browser_closed(exc, "browser/page was closed while reading conversation list")
        raise


def click_conversation_candidate(page: Any, index: int) -> bool:
    selector = f'[data-chat-crawler-index="{index}"]'
    try:
        element = page.query_selector(selector)
        if element is None:
            return False
        element.click(timeout=3000)
        return True
    except PlaywrightTimeoutError:
        return False
    except Exception as exc:
        raise_if_browser_closed(exc, "browser/page was closed while clicking conversation")
        return False


def click_conversation_point(page: Any, x: int, y: int) -> bool:
    try:
        page.mouse.click(x, y)
        return True
    except Exception as exc:
        raise_if_browser_closed(exc, "browser/page was closed while clicking conversation row")
        return False


def read_opened_conversation_snapshot(
    page: Any,
    args: argparse.Namespace,
    visited: set[str],
    candidate_signature: str,
) -> tuple[dict[str, Any], str]:
    best_snapshot: dict[str, Any] = {}
    best_nickname = ""
    for attempt in range(max(1, args.conversation_retry_rounds)):
        if attempt:
            wait_for_page(
                page,
                args.conversation_retry_wait_ms,
                "browser/page was closed while waiting for conversation switch",
            )
        snapshot = get_dom_chat_snapshot(page)
        current_nickname = clean_text(snapshot.get("nickname"))
        has_messages = bool(snapshot.get("messages"))
        if current_nickname or has_messages:
            best_snapshot = snapshot
            best_nickname = current_nickname
        signature = current_nickname or candidate_signature
        if (current_nickname or has_messages) and signature not in visited:
            return snapshot, current_nickname
    return best_snapshot, best_nickname


def get_dom_chat_snapshot(page: Any) -> dict[str, Any]:
    try:
        return page.evaluate(
            """() => {
                const width = window.innerWidth || document.documentElement.clientWidth || 1200;
                const height = window.innerHeight || document.documentElement.clientHeight || 900;
                const clean = (value) => String(value || '').replace(/\\s+/g, ' ').trim();
                const visible = (el) => {
                    const rect = el.getBoundingClientRect();
                    const style = window.getComputedStyle(el);
                    return rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.display !== 'none';
                };
                const rightNodes = Array.from(document.querySelectorAll('h1,h2,h3,[class*=title],[class*=name],[class*=nick],span,div'))
                    .filter((el) => visible(el) && el.getBoundingClientRect().left > 360);
                let nickname = '';
                for (const el of rightNodes) {
                    const rect = el.getBoundingClientRect();
                    const text = clean(el.innerText || el.textContent);
                    if (!text || text.length > 40) continue;
                    if (rect.top < 140 && !/\\d{1,2}:\\d{2}|昨天|今天|星期|年|月|日/.test(text)) {
                        nickname = text;
                        break;
                    }
                }

                const timeLike = /((20\\d{2}[-/.年]\\d{1,2}[-/.月]\\d{1,2})|([01]?\\d|2[0-3]):[0-5]\\d|昨天|今天|星期|周[一二三四五六日天])/;
                const controlText = /发送|按 Enter|表情|更多|关闭|搜索|已读|在线|文件|输入/;
                const chatLeft = Math.max(300, width * 0.20);
                const chatRight = width - 80;
                const chatTop = 70;
                const chatBottom = height - 95;
                const messageMid = chatLeft + (chatRight - chatLeft) * 0.5;
                const isSelfSide = (left, right) => {
                    return left > messageMid || (right > chatRight - 120 && left > chatLeft + 140);
                };
                const inPeerHalf = (left, right) => {
                    return (left + right) / 2 <= messageMid;
                };
                const systemNoticeText = /对方回复|关注你之前|只能发送一条|文字消息|请礼貌发言|自觉遵守|抖音自律公约|系统消息|安全提示|风险提示|撤回了一条消息|以上是打招呼/;
                const cnSystemNoticeText = /\\u5bf9\\u65b9\\u56de\\u590d|\\u5173\\u6ce8\\u4f60\\u4e4b\\u524d|\\u53ea\\u80fd\\u53d1\\u9001\\u4e00\\u6761|\\u8bf7\\u793c\\u8c8c\\u53d1\\u8a00|\\u81ea\\u89c9\\u9075\\u5b88|\\u6296\\u97f3\\u81ea\\u5f8b\\u516c\\u7ea6|\\u7cfb\\u7edf\\u6d88\\u606f|\\u5b89\\u5168\\u63d0\\u793a|\\u98ce\\u9669\\u63d0\\u793a|\\u64a4\\u56de\\u4e86\\u4e00\\u6761\\u6d88\\u606f|\\u4ee5\\u4e0a\\u662f\\u6253\\u62db\\u547c/;
                const cnControlText = /\\u53d1\\u9001\\u6d88\\u606f|\\u641c\\u7d22|\\u8868\\u60c5|\\u66f4\\u591a|\\u5173\\u95ed|\\u8f93\\u5165|\\u5728\\u7ebf|\\u6587\\u4ef6|\\u5df2\\u8bfb|\\u9001\\u8fbe|\\u5df2\\u53d1\\u9001|Enter/;
                const cnTimeLike = /\\b\\d{1,2}[/-]\\d{1,2}\\b|\\b20\\d{2}[/-]\\d{1,2}[/-]\\d{1,2}\\b|\\b([01]?\\d|2[0-3]):[0-5]\\d\\b|\\u4eca\\u5929|\\u6628\\u5929|\\u661f\\u671f|\\u5468[\\u4e00\\u4e8c\\u4e09\\u56db\\u4e94\\u516d\\u65e5\\u5929]/;
                const ignoreMessageText = (text) => {
                    if (!text || text.length > 1000) return true;
                    if (systemNoticeText.test(text) || cnSystemNoticeText.test(text)) return true;
                    if (controlText.test(text) || cnControlText.test(text)) return true;
                    if ((timeLike.test(text) || cnTimeLike.test(text)) && text.length <= 32) return true;
                    if (/^宸茶$|^閫佽揪$|^宸插彂閫?/.test(text)) return true;
                    return false;
                };
                const forEachTextNode = (callback) => {
                    const roots = [document.body].filter(Boolean);
                    const seenRoots = new Set();
                    for (let rootIndex = 0; rootIndex < roots.length; rootIndex += 1) {
                        const root = roots[rootIndex];
                        if (!root || seenRoots.has(root)) continue;
                        seenRoots.add(root);
                        const walker = document.createTreeWalker(
                            root,
                            NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT,
                            {
                                acceptNode(node) {
                                    if (node.nodeType === Node.TEXT_NODE) return NodeFilter.FILTER_ACCEPT;
                                    if (node.nodeType === Node.ELEMENT_NODE && node.shadowRoot) {
                                        roots.push(node.shadowRoot);
                                    }
                                    return NodeFilter.FILTER_SKIP;
                                }
                            }
                        );
                        for (let node = walker.nextNode(); node; node = walker.nextNode()) {
                            if (node.nodeType === Node.TEXT_NODE) {
                                callback(node);
                            } else if (node.nodeType === Node.ELEMENT_NODE && node.shadowRoot) {
                                roots.push(node.shadowRoot);
                            }
                        }
                    }
                };
                const leftHalfBoundsForNode = (node, minWidth = 8, minHeight = 8) => {
                    const parent = node.parentElement;
                    if (!parent || !visible(parent)) return null;
                    const range = document.createRange();
                    range.selectNodeContents(node);
                    const rects = Array.from(range.getClientRects()).filter((rect) => rect.width >= minWidth && rect.height >= minHeight);
                    range.detach();
                    if (!rects.length) return null;
                    const left = Math.min(...rects.map((rect) => rect.left));
                    const right = Math.max(...rects.map((rect) => rect.right));
                    const top = Math.min(...rects.map((rect) => rect.top));
                    const bottom = Math.max(...rects.map((rect) => rect.bottom));
                    if (left < chatLeft || right > chatRight || top < chatTop || bottom > chatBottom) return null;
                    if (!inPeerHalf(left, right)) return null;
                    return { left, right, top, bottom };
                };
                const bubbleFor = (el) => {
                    for (let node = el, depth = 0; node && depth < 6; node = node.parentElement, depth += 1) {
                        if (!visible(node)) continue;
                        const rect = node.getBoundingClientRect();
                        if (rect.left < chatLeft || rect.right > chatRight || rect.top < chatTop || rect.bottom > chatBottom) continue;
                        if (rect.width < 24 || rect.height < 18 || rect.width > Math.min(860, width * 0.68)) continue;
                        const style = window.getComputedStyle(node);
                        const background = style.backgroundColor || '';
                        const radius = Math.max(
                            parseFloat(style.borderTopLeftRadius || '0'),
                            parseFloat(style.borderTopRightRadius || '0'),
                            parseFloat(style.borderBottomLeftRadius || '0'),
                            parseFloat(style.borderBottomRightRadius || '0')
                        );
                        const hasBackground = background && !/rgba\\(0, 0, 0, 0\\)|transparent/i.test(background);
                        if ((radius >= 6 && hasBackground) || /bubble|message|msg|content|text/i.test(String(node.className || ''))) return node;
                    }
                    return null;
                };

                const timeNodes = Array.from(document.querySelectorAll('div,span,p'))
                    .filter((el) => {
                        if (!visible(el)) return false;
                        const rect = el.getBoundingClientRect();
                        if (rect.left < chatLeft || rect.right > chatRight || rect.top < chatTop || rect.top > chatBottom) return false;
                        const text = clean(el.innerText || el.textContent);
                        return text && text.length <= 32 && (timeLike.test(text) || cnTimeLike.test(text)) && !controlText.test(text) && !cnControlText.test(text);
                    })
                    .map((el) => {
                        const rect = el.getBoundingClientRect();
                        return { text: clean(el.innerText || el.textContent), top: rect.top, bottom: rect.bottom };
                    })
                    .sort((a, b) => a.top - b.top);
                forEachTextNode((node) => {
                    const text = clean(node.nodeValue || '');
                    if (!text || text.length > 32) return;
                    if (!(timeLike.test(text) || cnTimeLike.test(text))) return;
                    if (controlText.test(text) || cnControlText.test(text)) return;
                    const parent = node.parentElement;
                    if (!parent || !visible(parent)) return;
                    const range = document.createRange();
                    range.selectNodeContents(node);
                    const rects = Array.from(range.getClientRects()).filter((rect) => rect.width >= 8 && rect.height >= 8);
                    range.detach();
                    if (!rects.length) return;
                    const left = Math.min(...rects.map((rect) => rect.left));
                    const right = Math.max(...rects.map((rect) => rect.right));
                    const top = Math.min(...rects.map((rect) => rect.top));
                    const bottom = Math.max(...rects.map((rect) => rect.bottom));
                    if (left < chatLeft || right > chatRight || top < chatTop || bottom > chatBottom) return;
                    timeNodes.push({ text, top, bottom });
                });
                timeNodes.sort((a, b) => a.top - b.top);

                const timeForTop = (top) => {
                    for (let i = timeNodes.length - 1; i >= 0; i -= 1) {
                        if (timeNodes[i].bottom <= top + 2) return timeNodes[i].text;
                    }
                    return '';
                };

                const leftHalfTextMessages = [];
                forEachTextNode((node) => {
                    const text = clean(node.nodeValue || '');
                    if (ignoreMessageText(text)) return;
                    const bounds = leftHalfBoundsForNode(node);
                    if (!bounds) return;
                    leftHalfTextMessages.push({
                        message_id: `left-half:${timeForTop(bounds.top)}:${Math.round(bounds.top)}:${text.slice(0, 64)}`,
                        text,
                        create_time: timeForTop(bounds.top),
                        sender_nickname: nickname,
                        is_from_self: false,
                        top: bounds.top,
                        bottom: bounds.bottom,
                    });
                });

                const leftHalfAttributeMessages = [];
                for (const el of Array.from(document.querySelectorAll('[aria-label], [title]'))) {
                    if (!visible(el)) continue;
                    const rect = el.getBoundingClientRect();
                    if (rect.left < chatLeft || rect.right > chatRight || rect.top < chatTop || rect.bottom > chatBottom) continue;
                    if (!inPeerHalf(rect.left, rect.right)) continue;
                    const text = clean(el.getAttribute('aria-label') || el.getAttribute('title') || '');
                    if (ignoreMessageText(text)) continue;
                    leftHalfAttributeMessages.push({
                        message_id: `left-attr:${timeForTop(rect.top)}:${Math.round(rect.top)}:${text.slice(0, 64)}`,
                        text,
                        create_time: timeForTop(rect.top),
                        sender_nickname: nickname,
                        is_from_self: false,
                        top: rect.top,
                        bottom: rect.bottom,
                    });
                }

                leftHalfTextMessages.push(...leftHalfAttributeMessages);
                if (leftHalfTextMessages.length) {
                    const uniqueLeftHalf = [];
                    const seenLeftHalf = new Set();
                    for (const item of leftHalfTextMessages.sort((a, b) => b.top - a.top)) {
                        const key = `${item.create_time}|${Math.round(item.top / 8)}|${item.text}`;
                        if (seenLeftHalf.has(key)) continue;
                        seenLeftHalf.add(key);
                        uniqueLeftHalf.push(item);
                    }
                    return { nickname, messages: uniqueLeftHalf };
                }

                const dataIndexItems = Array.from(document.querySelectorAll('.messageMessageListlist [data-index], [class*="messageMessageList"] [data-index], [data-index]'))
                    .filter((el) => {
                        if (!visible(el)) return false;
                        const rect = el.getBoundingClientRect();
                        if (rect.left < chatLeft || rect.right > chatRight || rect.top < chatTop || rect.bottom > chatBottom) return false;
                        return clean(el.innerText || el.textContent);
                    })
                    .map((el) => {
                        const rect = el.getBoundingClientRect();
                        return { el, top: rect.top, bottom: rect.bottom };
                    })
                    .sort((a, b) => a.top - b.top);

                const textRectsIn = (root) => {
                    const result = [];
                    const walker = document.createTreeWalker(
                        root,
                        NodeFilter.SHOW_TEXT,
                        {
                            acceptNode(node) {
                                const text = clean(node.nodeValue || '');
                                if (!text) return NodeFilter.FILTER_REJECT;
                                if (systemNoticeText.test(text)) return NodeFilter.FILTER_REJECT;
                                if (controlText.test(text)) return NodeFilter.FILTER_REJECT;
                                if ((timeLike.test(text) || cnTimeLike.test(text)) && text.length <= 32) return NodeFilter.FILTER_REJECT;
                                if (/^已读$|^送达$|^已发送$/.test(text)) return NodeFilter.FILTER_REJECT;
                                return NodeFilter.FILTER_ACCEPT;
                            }
                        }
                    );
                    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
                        const range = document.createRange();
                        range.selectNodeContents(node);
                        const rects = Array.from(range.getClientRects()).filter((rect) => rect.width >= 8 && rect.height >= 8);
                        range.detach();
                        if (!rects.length) continue;
                        const left = Math.min(...rects.map((rect) => rect.left));
                        const right = Math.max(...rects.map((rect) => rect.right));
                        const top = Math.min(...rects.map((rect) => rect.top));
                        const bottom = Math.max(...rects.map((rect) => rect.bottom));
                        if (left < chatLeft || right > chatRight || top < chatTop || bottom > chatBottom) continue;
                        result.push({
                            text: clean(node.nodeValue || ''),
                            left,
                            right,
                            top,
                            bottom,
                            area: (right - left) * (bottom - top),
                        });
                    }
                    return result;
                };

                const dataIndexMessages = [];
                let currentDataIndexTime = '';
                for (const item of dataIndexItems) {
                    const rawLines = String(item.el.innerText || item.el.textContent || '')
                        .split(/\\n+/)
                        .map((line) => clean(line))
                        .filter(Boolean);
                    const timeLines = rawLines.filter((line) => line.length <= 32 && (timeLike.test(line) || cnTimeLike.test(line)) && !controlText.test(line) && !cnControlText.test(line));
                    const messageLines = rawLines.filter((line) => {
                        if (!line) return false;
                        if ((timeLike.test(line) || cnTimeLike.test(line)) && line.length <= 32) return false;
                        if (systemNoticeText.test(line) || cnSystemNoticeText.test(line)) return false;
                        if (controlText.test(line) || cnControlText.test(line)) return false;
                        if (/^已读$|^送达$|^已发送$/.test(line)) return false;
                        return true;
                    });
                    if (timeLines.length && !messageLines.length) {
                        currentDataIndexTime = timeLines[timeLines.length - 1];
                        continue;
                    }
                    if (!messageLines.length) continue;
                    if (timeLines.length) {
                        currentDataIndexTime = timeLines[timeLines.length - 1];
                    }

                    const textRects = textRectsIn(item.el);
                    if (!textRects.length) continue;
                    const left = Math.min(...textRects.map((rect) => rect.left));
                    const right = Math.max(...textRects.map((rect) => rect.right));
                    const top = Math.min(...textRects.map((rect) => rect.top));
                    const bottom = Math.max(...textRects.map((rect) => rect.bottom));
                    const fromSelf = isSelfSide(left, right);
                    const side = fromSelf ? 'right' : 'left';
                    const messageText = clean(messageLines.join(' '));
                    if (!messageText) continue;
                    dataIndexMessages.push({
                        message_id: `data-index:${item.el.getAttribute('data-index')}:${currentDataIndexTime}:${side}:${messageText.slice(0, 64)}`,
                        text: messageText,
                        create_time: currentDataIndexTime,
                        sender_nickname: fromSelf ? 'syr' : nickname,
                        is_from_self: fromSelf,
                        top,
                        bottom,
                        order: Number(item.el.getAttribute('data-index') || dataIndexMessages.length),
                    });
                }
                if (dataIndexMessages.length) {
                    const uniqueByDataIndex = [];
                    const seenByDataIndex = new Set();
                    for (const item of dataIndexMessages.sort((a, b) => b.top - a.top)) {
                        const key = `${item.create_time}|${item.sender_nickname}|${item.text}`;
                        if (seenByDataIndex.has(key)) continue;
                        seenByDataIndex.add(key);
                        uniqueByDataIndex.push(item);
                    }
                    const peerByDataIndex = uniqueByDataIndex.filter((item) => !item.is_from_self);
                    if (peerByDataIndex.length) return { nickname, messages: peerByDataIndex };
                }

                const rawCandidates = Array.from(document.querySelectorAll('div,span,p,pre'))
                    .filter((el) => {
                        if (!visible(el)) return false;
                        const rect = el.getBoundingClientRect();
                        if (rect.left < chatLeft || rect.right > chatRight || rect.top < chatTop || rect.bottom > chatBottom) return false;
                        if (rect.width < 20 || rect.height < 14) return false;
                        const text = clean(el.innerText || el.textContent);
                        if (!text || text.length > 1000) return false;
                        if (systemNoticeText.test(text)) return false;
                        if (controlText.test(text)) return false;
                        if ((timeLike.test(text) || cnTimeLike.test(text)) && text.length <= 32) return false;
                        const bubble = bubbleFor(el);
                        if (bubble) return true;
                        const parentText = el.parentElement ? clean(el.parentElement.innerText || el.parentElement.textContent) : '';
                        if (parentText && parentText !== text && parentText.length < text.length + 80) return false;
                        return rect.width <= Math.min(680, width * 0.5);
                    })
                    .map((el) => {
                        const bubble = bubbleFor(el) || el;
                        const rect = bubble.getBoundingClientRect();
                        const text = clean(bubble.innerText || bubble.textContent || el.innerText || el.textContent);
                        return {
                            text,
                            left: rect.left,
                            right: rect.right,
                            top: rect.top,
                            bottom: rect.bottom,
                            width: rect.width,
                            height: rect.height,
                            area: rect.width * rect.height,
                        };
                    })
                    .sort((a, b) => a.area - b.area);

                const textNodeCandidates = [];
                const walker = document.createTreeWalker(
                    document.body,
                    NodeFilter.SHOW_TEXT,
                    {
                        acceptNode(node) {
                            const text = clean(node.nodeValue || '');
                            if (!text || text.length > 1000) return NodeFilter.FILTER_REJECT;
                            if (systemNoticeText.test(text)) return NodeFilter.FILTER_REJECT;
                            if (controlText.test(text)) return NodeFilter.FILTER_REJECT;
                            if ((timeLike.test(text) || cnTimeLike.test(text)) && text.length <= 32) return NodeFilter.FILTER_REJECT;
                            return NodeFilter.FILTER_ACCEPT;
                        }
                    }
                );
                for (let node = walker.nextNode(); node; node = walker.nextNode()) {
                    const parent = node.parentElement;
                    if (!parent || !visible(parent)) continue;
                    const range = document.createRange();
                    range.selectNodeContents(node);
                    const rects = Array.from(range.getClientRects()).filter((rect) => rect.width >= 12 && rect.height >= 10);
                    range.detach();
                    if (!rects.length) continue;
                    const left = Math.min(...rects.map((rect) => rect.left));
                    const right = Math.max(...rects.map((rect) => rect.right));
                    const top = Math.min(...rects.map((rect) => rect.top));
                    const bottom = Math.max(...rects.map((rect) => rect.bottom));
                    if (left < chatLeft || right > chatRight || top < chatTop || bottom > chatBottom) continue;
                    const text = clean(node.nodeValue || '');
                    textNodeCandidates.push({
                        text,
                        left,
                        right,
                        top,
                        bottom,
                        width: right - left,
                        height: bottom - top,
                        area: (right - left) * (bottom - top),
                        fromTextNode: true,
                    });
                }

                const bubbles = [];
                for (const candidate of [...rawCandidates, ...textNodeCandidates]) {
                    const duplicate = bubbles.some((item) => {
                        const sameText = item.text === candidate.text || item.text.includes(candidate.text) || candidate.text.includes(item.text);
                        const overlaps = Math.abs(item.top - candidate.top) < 10 || (candidate.top < item.bottom && candidate.bottom > item.top);
                        return sameText && overlaps;
                    });
                    if (!duplicate) bubbles.push(candidate);
                }

                const messageNodes = bubbles
                    .sort((a, b) => b.top - a.top)
                    .map((item, index) => {
                        const fromSelf = isSelfSide(item.left, item.right);
                        const side = fromSelf ? 'right' : 'left';
                        let createTime = '';
                        for (let i = timeNodes.length - 1; i >= 0; i -= 1) {
                            if (timeNodes[i].bottom <= item.top + 2) {
                                createTime = timeNodes[i].text;
                                break;
                            }
                        }
                        return {
                            message_id: `dom:${createTime}:${side}:${item.text.slice(0, 64)}`,
                            text: item.text,
                            create_time: createTime,
                            sender_nickname: fromSelf ? 'syr' : nickname,
                            is_from_self: fromSelf,
                            top: item.top,
                            order: index,
                        };
                    });

                const unique = [];
                const seen = new Set();
                for (const item of messageNodes) {
                    const key = `${item.create_time}|${item.sender_nickname}|${item.text}`;
                    if (seen.has(key)) continue;
                    seen.add(key);
                    unique.push(item);
                }
                return { nickname, messages: unique.filter((item) => !item.is_from_self) };
            }"""
        )
    except Exception as exc:
        raise_if_browser_closed(exc, "browser/page was closed while reading DOM messages")
        raise


def save_json(output_path: Path, chats: list[dict[str, Any]]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(chats, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_cookie_file(cookie_path: Path) -> list[dict[str, Any]]:
    if not cookie_path.exists() or cookie_path.stat().st_size == 0:
        return []

    raw = cookie_path.read_text(encoding="utf-8").strip()
    if not raw:
        return []
    raw = re.sub(r"^\s*cookie\s*:\s*", "", raw, flags=re.I)

    cookies: list[dict[str, Any]] = []
    lines = [line.strip() for line in raw.splitlines() if line.strip() and not line.lstrip().startswith("#")]
    if lines and all("\t" in line for line in lines):
        for line in lines:
            parts = line.split("\t")
            if len(parts) < 7:
                continue
            domain, _include_subdomains, path, secure, expires, name, value = parts[:7]
            if not name:
                continue
            cookie: dict[str, Any] = {
                "name": name,
                "value": value,
                "domain": domain or ".douyin.com",
                "path": path or "/",
                "secure": secure.upper() == "TRUE",
            }
            try:
                expiry = int(expires)
                if expiry > 0:
                    cookie["expires"] = expiry
            except ValueError:
                pass
            cookies.append(cookie)
        return cookies

    simple_cookie = SimpleCookie()
    simple_cookie.load(raw)
    for name, morsel in simple_cookie.items():
        if not name:
            continue
        cookies.append(
            {
                "name": name,
                "value": morsel.value,
                "domain": ".douyin.com",
                "path": "/",
                "secure": True,
            }
        )
    return cookies


def add_cookie_file(context: Any, cookie_file: str) -> None:
    if not cookie_file:
        return
    cookie_path = Path(cookie_file)
    cookies = parse_cookie_file(cookie_path)
    if not cookies:
        return
    context.add_cookies(cookies)
    print(f"[cookies] loaded={len(cookies)} file={cookie_path}")


def load_existing_chats(output_path: Path) -> ChatStore:
    store = ChatStore()
    if not output_path.exists() or output_path.stat().st_size == 0:
        return store
    try:
        raw = json.loads(output_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return store
    if not isinstance(raw, list):
        return store
    for item in raw:
        if not isinstance(item, dict):
            continue
        conversation_id = clean_id(item.get("conversation_id"))
        user_id = clean_id(item.get("user_id"))
        sec_uid = clean_id(item.get("sec_uid"))
        short_id = clean_id(item.get("short_id"))
        nickname = clean_text(item.get("nickname"))
        chat = store.get_chat(conversation_id or user_id or sec_uid or short_id or nickname, conversation_id)
        chat.user_id = user_id
        chat.sec_uid = sec_uid
        chat.short_id = short_id
        chat.nickname = nickname
        chat.ip_label = clean_text(item.get("ip_label"))
        for raw_message in item.get("messages") or item.get("content") or []:
            if not isinstance(raw_message, dict):
                continue
            message = Message(
                message_id=clean_id(raw_message.get("message_id")),
                text=clean_text(raw_message.get("text") or raw_message.get("message")),
                create_time=clean_text(raw_message.get("time") or raw_message.get("create_time")),
                raw_time=raw_message.get("time") or raw_message.get("create_time"),
                sender_id=clean_id(raw_message.get("sender_id")),
                sender_nickname=clean_text(raw_message.get("username") or raw_message.get("sender_nickname")),
                is_from_self=raw_message.get("is_from_self"),
            )
            chat.merge_message(message)
    return store


def attach_response_listener(page: Any, store: ChatStore, args: argparse.Namespace) -> Any:
    def on_response(response: Any) -> None:
        try:
            url = response.url
            store.response_count += 1
            content_type = response.headers.get("content-type", "")
            is_json = "json" in content_type.lower()
            if args.users_only:
                if not is_user_info_response_url(url) or not is_json:
                    return
                payload = response.json()
                store.relevant_response_count += 1
                store.add_user_info_response(url, payload)
                if args.debug_responses:
                    print(f"[user-info] parsed url={url.split('?', 1)[0][:160]}")
                return

            should_parse = is_relevant_response_url(url) or (args.parse_all_douyin_json and is_json and is_douyin_url(url))
            if not should_parse:
                return
            if "json" not in content_type.lower() and not any(marker in url.lower() for marker in CHAT_URL_MARKERS):
                return
            payload = response.json()
            store.relevant_response_count += 1
            if is_user_info_response_url(url):
                store.add_user_info_response(url, payload)
            parse_json_payload(payload, store)
            if args.debug_responses:
                print(f"[response] parsed url={url.split('?', 1)[0][:160]}")
        except Exception as exc:
            if is_browser_closed_error(exc):
                return
            if args.debug_responses:
                try:
                    path = response.url.split("?", 1)[0][:160]
                    content_type = response.headers.get("content-type", "")
                except Exception:
                    path = "<unknown>"
                    content_type = ""
                print(f"[debug] skipped response url={path} content_type={content_type} error={exc}")

    page.on("response", on_response)
    return on_response


def remove_response_listener(page: Any, handler: Any) -> None:
    try:
        page.remove_listener("response", handler)
    except Exception as exc:
        if not is_browser_closed_error(exc):
            raise


def crawl_chat_users(page: Any, store: ChatStore, args: argparse.Namespace) -> None:
    print(f"[open chat] {args.chat_url}")
    try:
        page.goto(args.chat_url, wait_until="domcontentloaded", timeout=args.timeout_ms)
    except PlaywrightTimeoutError:
        print("[warn] chat navigation timed out; continuing with captured responses")
    except Exception as exc:
        raise_if_browser_closed(exc, "browser/page was closed while opening chat")
        raise

    wait_for_page(page, args.initial_wait_ms, "browser/page was closed while waiting after chat open")
    maybe_wait_for_network(page, min(args.timeout_ms, 10000))

    if login_dialog_visible(page):
        if not wait_for_manual_login(page, args):
            return

    last_count = len(store.to_list())
    idle_rounds = 0
    for round_index in range(args.list_scroll_rounds):
        wait_for_page(page, args.list_scroll_wait_ms, "browser/page was closed while waiting for user info responses")
        current_count = len(store.to_list())
        if current_count == last_count:
            idle_rounds += 1
        else:
            idle_rounds = 0
        print(f"[users] round={round_index + 1} users={current_count} idle={idle_rounds}")
        if idle_rounds >= args.list_idle_rounds:
            break
        last_count = current_count
        scroll_conversation_list(page, args.list_scroll_pixels)


def crawl_chats(page: Any, store: ChatStore, args: argparse.Namespace) -> None:
    print(f"[open chat] {args.chat_url}")
    try:
        page.goto(args.chat_url, wait_until="domcontentloaded", timeout=args.timeout_ms)
    except PlaywrightTimeoutError:
        print("[warn] chat navigation timed out; continuing with captured responses")
    except Exception as exc:
        raise_if_browser_closed(exc, "browser/page was closed while opening chat")
        raise

    wait_for_page(page, args.initial_wait_ms, "browser/page was closed while waiting after chat open")
    maybe_wait_for_network(page, min(args.timeout_ms, 10000))

    if login_dialog_visible(page):
        if not wait_for_manual_login(page, args):
            return

    store.merge_dom_snapshot(get_dom_chat_snapshot(page))

    visited: set[str] = set()
    idle_rounds = 0
    last_message_count = sum(len(chat.messages) for chat in store.chats.values())

    for round_index in range(args.list_scroll_rounds):
        candidates: list[dict[str, Any]] = mark_conversation_candidates(page, args.max_visible_conversations)
        if args.coordinate_clicks:
            for row_index in range(args.coordinate_visible_rows):
                candidates.append(
                    {
                        "index": -1,
                        "text": f"coord:{round_index}:{row_index}",
                        "x": args.coordinate_click_x,
                        "y": args.coordinate_first_y + row_index * args.coordinate_row_height,
                        "coordinate": True,
                    }
                )
        new_clicks = 0

        for candidate in candidates:
            candidate_signature = clean_text(candidate.get("text"))[:120]
            if not candidate_signature:
                continue
            if not candidate.get("coordinate") and candidate_signature in visited:
                continue

            clicked = (
                click_conversation_point(page, int(candidate["x"]), int(candidate["y"]))
                if candidate.get("coordinate")
                else click_conversation_candidate(page, int(candidate["index"]))
            )
            if not clicked:
                continue
            wait_for_page(page, args.conversation_wait_ms, "browser/page was closed after opening conversation")

            snapshot, current_nickname = read_opened_conversation_snapshot(page, args, visited, candidate_signature)
            if not current_nickname and not snapshot.get("messages"):
                continue
            signature = current_nickname or candidate_signature
            if signature in visited:
                continue
            visited.add(signature)
            if args.max_conversations and len(visited) > args.max_conversations:
                break

            new_clicks += 1
            store.merge_dom_snapshot(snapshot)
            current_chat = store.find_chat_by_nickname(current_nickname) if current_nickname else None
            last_user_message_count = len(current_chat.messages) if current_chat else 0
            message_idle_rounds = 0
            reached_cutoff = snapshot_has_before_cutoff_time(snapshot)

            for history_round in range(args.message_scroll_rounds):
                if reached_cutoff:
                    break
                scroll_message_panels(page, -args.message_scroll_pixels)
                wait_for_page(page, args.message_scroll_wait_ms, "browser/page was closed after message scroll")
                snapshot = get_dom_chat_snapshot(page)
                reached_cutoff = snapshot_has_before_cutoff_time(snapshot)
                store.merge_dom_snapshot(snapshot)
                current_chat = store.find_chat_by_nickname(current_nickname) if current_nickname else None
                current_user_message_count = len(current_chat.messages) if current_chat else 0
                if current_user_message_count == last_user_message_count:
                    message_idle_rounds += 1
                else:
                    message_idle_rounds = 0
                last_user_message_count = current_user_message_count
                if message_idle_rounds >= args.message_idle_rounds:
                    break

            final_snapshot = get_dom_chat_snapshot(page)
            store.merge_dom_snapshot(final_snapshot)
            current_chat = store.find_chat_by_nickname(current_nickname) if current_nickname else None
            save_json(Path(args.output), store.to_list())
            total_chats = len(store.to_list())
            total_messages = sum(len(chat.messages) for chat in store.chats.values())
            user_messages = len(current_chat.messages) if current_chat else 0
            snapshot_messages = len(snapshot.get("messages") or [])
            final_snapshot_messages = len(final_snapshot.get("messages") or [])
            cutoff_text = " cutoff<2024" if reached_cutoff or snapshot_has_before_cutoff_time(final_snapshot) else ""
            print(
                f"[save-chat] visited={len(visited)} nickname={current_nickname or '<unknown>'} "
                f"user_messages={user_messages} snapshot={snapshot_messages} final={final_snapshot_messages} "
                f"chats={total_chats} messages={total_messages}{cutoff_text}"
            )

        if args.max_conversations and len(visited) >= args.max_conversations:
            break

        scroll_conversation_list(page, args.list_scroll_pixels)
        wait_for_page(page, args.list_scroll_wait_ms, "browser/page was closed after chat list scroll")
        current_message_count = sum(len(chat.messages) for chat in store.chats.values())
        if new_clicks == 0:
            idle_rounds += 1
        else:
            idle_rounds = 0
        last_message_count = current_message_count
        if idle_rounds >= args.list_idle_rounds:
            break
        print(
            f"[list-next] batch={round_index + 1} candidates={len(candidates)} "
            f"processed={len(visited)} new_users={new_clicks} idle={idle_rounds}"
        )

    save_json(Path(args.output), store.to_list())
    total_chats = len(store.to_list())
    total_messages = sum(len(chat.messages) for chat in store.chats.values())
    print(f"[write-complete] output={args.output} chats={total_chats} messages={total_messages}")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Crawl Douyin chat conversations and write user/message data to the project-local chats.json by default."
    )
    parser.add_argument("--chat-url", default=CHAT_URL, help="Douyin chat URL.")
    parser.add_argument(
        "--output",
        default=None,
        help="Output JSON file path. Defaults to chats.json beside this script.",
    )
    parser.add_argument(
        "--cookie-file",
        default=None,
        help="Cookie header/Netscape cookie file. Defaults to .douyin-chat-cookie.txt beside this script.",
    )
    parser.add_argument(
        "--user-data-dir",
        default=None,
        help="Persistent browser profile directory. Defaults to .douyin-browser-profile beside this script.",
    )
    parser.add_argument("--headless", dest="headless", action="store_true", help="Run Chromium in the background.")
    parser.add_argument("--headed", dest="headless", action="store_false", help="Show the Chromium browser window.")
    parser.add_argument(
        "--login-prompt",
        dest="login_prompt",
        action="store_true",
        help="Pause for manual login after opening the chat page.",
    )
    parser.add_argument(
        "--no-login-prompt",
        dest="login_prompt",
        action="store_false",
        help="Do not pause for manual login after opening the chat page.",
    )
    parser.add_argument(
        "--login-wait-seconds",
        type=int,
        default=0,
        help="When headed login is required, wait this many seconds for browser login instead of reading Enter.",
    )
    parser.set_defaults(headless=False, login_prompt=False)
    parser.add_argument("--max-conversations", type=int, default=0, help="Limit conversations; 0 means no limit.")
    parser.add_argument("--fresh", action="store_true", help="Ignore existing chats.json and rewrite from a fresh crawl.")
    parser.add_argument(
        "--users-only",
        dest="users_only",
        action="store_true",
        help="Only collect private-message users from im/user/info responses; content is left empty.",
    )
    parser.add_argument(
        "--with-content",
        dest="users_only",
        action="store_false",
        help="Also try to collect message content from loaded conversations.",
    )
    parser.set_defaults(users_only=False)
    parser.add_argument(
        "--coordinate-clicks",
        dest="coordinate_clicks",
        action="store_true",
        help="Click the visible conversation rows by coordinates; useful because Douyin chat list text is not normal DOM.",
    )
    parser.add_argument(
        "--dom-clicks",
        dest="coordinate_clicks",
        action="store_false",
        help="Use DOM candidate clicking instead of coordinate row clicking.",
    )
    parser.set_defaults(coordinate_clicks=True)
    parser.add_argument("--coordinate-click-x", type=int, default=150)
    parser.add_argument("--coordinate-first-y", type=int, default=116)
    parser.add_argument("--coordinate-row-height", type=int, default=94)
    parser.add_argument("--coordinate-visible-rows", type=int, default=8)
    parser.add_argument("--max-visible-conversations", type=int, default=30)
    parser.add_argument("--timeout-ms", type=int, default=60000)
    parser.add_argument("--initial-wait-ms", type=int, default=4500)
    parser.add_argument("--conversation-wait-ms", type=int, default=1300)
    parser.add_argument("--conversation-retry-rounds", type=int, default=5)
    parser.add_argument("--conversation-retry-wait-ms", type=int, default=700)
    parser.add_argument("--list-scroll-wait-ms", type=int, default=1200)
    parser.add_argument("--message-scroll-wait-ms", type=int, default=800)
    parser.add_argument("--list-scroll-pixels", type=int, default=650)
    parser.add_argument("--message-scroll-pixels", type=int, default=1800)
    parser.add_argument("--list-scroll-rounds", type=int, default=120)
    parser.add_argument("--message-scroll-rounds", type=int, default=80)
    parser.add_argument("--message-idle-rounds", type=int, default=6)
    parser.add_argument("--list-idle-rounds", type=int, default=3)
    parser.add_argument("--viewport-width", type=int, default=1463)
    parser.add_argument("--viewport-height", type=int, default=915)
    parser.add_argument("--debug-responses", action="store_true", help="Print parsed chat/message response URLs.")
    parser.add_argument(
        "--parse-all-douyin-json",
        dest="parse_all_douyin_json",
        action="store_true",
        help="Parse every JSON response from Douyin domains, not only obvious chat endpoints.",
    )
    parser.add_argument(
        "--no-parse-all-douyin-json",
        dest="parse_all_douyin_json",
        action="store_false",
        help="Only parse obvious chat/message/session responses.",
    )
    parser.set_defaults(parse_all_douyin_json=False)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    if sync_playwright is None:
        print("Missing dependency: playwright", file=sys.stderr)
        print("Install dependencies: python -m pip install -r requirements.txt", file=sys.stderr)
        print("Install browser once: python -m playwright install chromium", file=sys.stderr)
        return 2

    output_path = project_default_path(args.output, "chats.json")
    args.output = str(output_path)
    args.user_data_dir = str(project_default_path(args.user_data_dir, ".douyin-browser-profile"))
    if args.cookie_file is None:
        args.cookie_file = str(PROJECT_ROOT / ".douyin-chat-cookie.txt")
    elif args.cookie_file:
        args.cookie_file = str(Path(args.cookie_file).expanduser())
    store = ChatStore() if args.fresh or args.users_only else load_existing_chats(output_path)

    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=args.user_data_dir,
            headless=args.headless,
            viewport={"width": args.viewport_width, "height": args.viewport_height},
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
        )
        page = context.pages[0] if context.pages else context.new_page()

        def close_extra_page(new_page: Any) -> None:
            if new_page == page:
                return
            try:
                url = ""
                try:
                    url = new_page.url
                except Exception:
                    pass
                print(f"[popup] closed unexpected page url={url or '<unknown>'}")
                new_page.close()
            except Exception as exc:
                if not is_browser_closed_error(exc):
                    print(f"[warn] failed to close unexpected page: {exc}")

        context.on("page", close_extra_page)
        for extra_page in list(context.pages):
            close_extra_page(extra_page)

        add_cookie_file(context, args.cookie_file)
        handler = attach_response_listener(page, store, args)
        try:
            try:
                if args.users_only:
                    crawl_chat_users(page, store, args)
                else:
                    crawl_chats(page, store, args)
            except BrowserClosedError as exc:
                print(f"[stop] {exc}; saving current output before exit")
                save_json(output_path, store.to_list())
                return 1
            finally:
                remove_response_listener(page, handler)
        finally:
            try:
                context.close()
            except Exception as exc:
                if not is_browser_closed_error(exc):
                    raise

    chats = store.to_list()
    save_json(output_path, chats)
    message_count = sum(len(item.get("content") or []) for item in chats)
    print(
        f"[done] chats={len(chats)} messages={message_count} "
        f"responses={store.relevant_response_count}/{store.response_count} output={output_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
