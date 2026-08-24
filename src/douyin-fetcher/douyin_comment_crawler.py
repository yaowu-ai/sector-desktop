from __future__ import annotations

import argparse
import json
import sys
from collections import OrderedDict, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

try:
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover
    sync_playwright = None
    PlaywrightTimeoutError = Exception


DEFAULT_PROFILE_URL = (
    "https://www.douyin.com/user/"
    "MS4wLjABAAAA4hev9gp-vYJbM1gilgT7UGeTLx1dGUhthJkRuWmKYFD3aFt6Rn0RPfNqeh4aPAey"
    "?from_tab_name=main"
)

POST_API_MARKER = "/aweme/v1/web/aweme/post/"
COMMENT_API_MARKER = "/aweme/v1/web/comment/list/"
REPLY_API_MARKER = "/aweme/v1/web/comment/list/reply/"
COMMENT_PROFILE_FIELDS = ("ip_label", "nickname")
OUTPUT_TIMEZONE = timezone(timedelta(hours=8), "Asia/Shanghai")
PROJECT_ROOT = Path(__file__).resolve().parent


class BrowserClosedError(RuntimeError):
    def __init__(self, message: str, partial_comments: list[dict[str, Any]] | None = None) -> None:
        super().__init__(message)
        self.partial_comments = partial_comments


def project_default_path(value: str | None, default_name: str) -> Path:
    if value is None:
        return PROJECT_ROOT / default_name
    return Path(value).expanduser()


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


def remove_response_listener(page: Any, handler: Any) -> None:
    try:
        page.remove_listener("response", handler)
    except Exception as exc:
        if not is_browser_closed_error(exc):
            raise


def id_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def clean_timestamp(value: Any) -> str | None:
    if value in (None, ""):
        return None

    if isinstance(value, str):
        text = value.strip()
        parts = text.split("-")
        if len(parts) == 3 and all(part.isdigit() for part in parts):
            return text
        value = text

    try:
        timestamp = int(value)
    except (TypeError, ValueError):
        return clean_text(value)

    if abs(timestamp) > 10_000_000_000:
        timestamp = timestamp // 1000

    try:
        return datetime.fromtimestamp(timestamp, tz=OUTPUT_TIMEZONE).strftime("%Y-%m-%d")
    except (OSError, OverflowError, ValueError):
        return clean_text(value)


def first_query_value(url: str, *names: str) -> str:
    query = parse_qs(urlparse(url).query)
    for name in names:
        values = query.get(name)
        if values:
            return values[0]
    return ""


def make_video_url(aweme_id: str) -> str:
    return f"https://www.douyin.com/video/{aweme_id}"


def extract_video(aweme: dict[str, Any]) -> dict[str, Any] | None:
    aweme_id = id_text(aweme.get("aweme_id") or aweme.get("item_id"))
    if not aweme_id:
        return None

    desc = clean_text(aweme.get("desc"))
    if not desc:
        desc = clean_text((aweme.get("share_info") or {}).get("share_title"))

    return {
        "aweme_id": aweme_id,
        "desc": desc,
        "create_time": clean_timestamp(aweme.get("create_time")),
        "comment": [],
    }


def extract_comment(raw: dict[str, Any], aweme_id: str, reply_id: str = "") -> dict[str, Any]:
    user = raw.get("user") or {}
    if not isinstance(user, dict):
        user = {}

    comment = {
        "cid": id_text(raw.get("cid") or raw.get("comment_id") or raw.get("id")),
        "text": clean_text(raw.get("text")),
        "aweme_id": aweme_id,
        "create_time": clean_timestamp(raw.get("create_time")),
        "ip_label": clean_text(raw.get("ip_label")),
        "nickname": clean_text(user.get("nickname")),
    }
    if reply_id:
        comment["reply_id"] = reply_id
    return comment


def comment_key(comment: dict[str, Any]) -> str:
    cid = id_text(comment.get("cid"))
    if cid:
        return cid
    return "|".join(
        [
            id_text(comment.get("aweme_id")),
            id_text(comment.get("reply_id")),
            id_text(comment.get("create_time")),
            clean_text(comment.get("text"))[:80],
        ]
    )


def count_comments(comments: list[dict[str, Any]]) -> int:
    total = 0
    for comment in comments:
        total += 1
        total += len(comment.get("sub-comment") or [])
    return total


def count_replies(comments: list[dict[str, Any]]) -> int:
    total = 0
    for comment in comments:
        if not isinstance(comment, dict):
            continue
        total += len(comment.get("sub-comment") or [])
    return total


def normalize_comment_create_times(comments: list[dict[str, Any]]) -> None:
    for comment in comments:
        if not isinstance(comment, dict):
            continue
        comment["create_time"] = clean_timestamp(comment.get("create_time"))
        for reply in comment.get("sub-comment") or []:
            if isinstance(reply, dict):
                reply["create_time"] = clean_timestamp(reply.get("create_time"))


def normalize_video_create_times(videos: list[dict[str, Any]]) -> None:
    for video in videos:
        if not isinstance(video, dict):
            continue
        video["create_time"] = clean_timestamp(video.get("create_time"))
        normalize_comment_create_times(video.get("comment") or [])


def comment_has_profile_fields(comment: dict[str, Any]) -> bool:
    return all(clean_text(comment.get(field)) for field in COMMENT_PROFILE_FIELDS)


def comments_have_profile_fields(comments: list[dict[str, Any]]) -> bool:
    for comment in comments:
        if not isinstance(comment, dict):
            continue
        if not comment_has_profile_fields(comment):
            return False
        for reply in comment.get("sub-comment") or []:
            if isinstance(reply, dict) and not comment_has_profile_fields(reply):
                return False
    return True


def update_comment_fields(target: dict[str, Any], source: dict[str, Any]) -> None:
    for key, value in source.items():
        if key == "sub-comment":
            continue
        if value in (None, "") and key not in COMMENT_PROFILE_FIELDS:
            continue
        target[key] = value


def comment_profile_stats(comments: list[dict[str, Any]]) -> dict[str, int]:
    stats = {"total": 0, "ip_label": 0, "nickname": 0, "both": 0}
    for comment in comments:
        if not isinstance(comment, dict):
            continue
        for item in [comment, *(comment.get("sub-comment") or [])]:
            if not isinstance(item, dict):
                continue
            stats["total"] += 1
            has_ip_label = bool(clean_text(item.get("ip_label")))
            has_nickname = bool(clean_text(item.get("nickname")))
            if has_ip_label:
                stats["ip_label"] += 1
            if has_nickname:
                stats["nickname"] += 1
            if has_ip_label and has_nickname:
                stats["both"] += 1
    return stats


def merge_sub_comments(
    existing: list[dict[str, Any]],
    incoming: list[dict[str, Any]],
    seen_cids: set[str] | None = None,
) -> list[dict[str, Any]]:
    merged: OrderedDict[str, dict[str, Any]] = OrderedDict()
    fallback_index = 0

    for comment in [*existing, *incoming]:
        if not isinstance(comment, dict):
            continue

        cid = id_text(comment.get("cid"))
        if cid:
            key = cid
        else:
            key = f"cidless-reply-{fallback_index}"
            fallback_index += 1

        if key in merged:
            update_comment_fields(merged[key], comment)
            continue

        if cid and seen_cids is not None and cid in seen_cids:
            continue

        item = dict(comment)
        item.pop("sub-comment", None)
        merged[key] = item
        if cid and seen_cids is not None:
            seen_cids.add(cid)

    return list(merged.values())


def merge_comment_lists(
    existing: list[dict[str, Any]],
    incoming: list[dict[str, Any]],
    seen_cids: set[str] | None = None,
) -> list[dict[str, Any]]:
    merged: OrderedDict[str, dict[str, Any]] = OrderedDict()
    pending_replies: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    fallback_index = 0

    for comment in [*existing, *incoming]:
        if not isinstance(comment, dict):
            continue

        cid = id_text(comment.get("cid"))
        key = cid or f"cidless-comment-{fallback_index}"
        fallback_index += 1
        replies = comment.get("sub-comment") or []

        if key in merged:
            update_comment_fields(merged[key], comment)
            pending_replies[key].extend(replies)
            continue

        if cid and seen_cids is not None and cid in seen_cids:
            pending_replies[key].extend(replies)
            continue

        item = dict(comment)
        item["sub-comment"] = []
        merged[key] = item
        pending_replies[key].extend(replies)
        if cid and seen_cids is not None:
            seen_cids.add(cid)

    for key, item in merged.items():
        item["sub-comment"] = merge_sub_comments(item.get("sub-comment") or [], pending_replies.get(key) or [], seen_cids)

    return list(merged.values())


def dedupe_videos_by_cid(videos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen_cids: set[str] = set()
    for video in videos:
        comments = video.get("comment") or []
        video["comment"] = merge_comment_lists(comments, [], seen_cids)
    return videos


def load_existing_videos(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []

    try:
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            return []
        data = json.loads(text)
    except Exception as exc:
        print(f"[warn] failed to read existing output={path}: {exc}")
        return []

    if not isinstance(data, list):
        print(f"[warn] existing output is not a video list: {path}")
        return []

    videos = [item for item in data if isinstance(item, dict)]
    normalize_video_create_times(videos)
    dedupe_videos_by_cid(videos)
    total_comments = sum(count_comments(video.get("comment") or []) for video in videos)
    print(f"[load] existing videos={len(videos)} comments={total_comments} output={path}")
    return videos


def merge_videos(existing: list[dict[str, Any]], incoming: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: OrderedDict[str, dict[str, Any]] = OrderedDict()

    for video in existing:
        aweme_id = id_text(video.get("aweme_id"))
        if not aweme_id:
            continue
        item = dict(video)
        item["comment"] = item.get("comment") or []
        merged[aweme_id] = item

    for video in incoming:
        aweme_id = id_text(video.get("aweme_id"))
        if not aweme_id:
            continue

        if aweme_id not in merged:
            item = dict(video)
            item["comment"] = item.get("comment") or []
            merged[aweme_id] = item
            continue

        item = merged[aweme_id]
        for key in ("desc", "create_time"):
            if video.get(key) not in (None, ""):
                item[key] = video[key]

    result = list(merged.values())
    normalize_video_create_times(result)
    dedupe_videos_by_cid(result)
    return result


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, list):
        normalize_video_create_times(data)
    tmp_path = path.with_name(path.name + ".tmp")
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    tmp_path.write_text(payload, encoding="utf-8")
    try:
        tmp_path.replace(path)
    except PermissionError:
        path.write_text(payload, encoding="utf-8")
        try:
            tmp_path.unlink()
        except OSError:
            pass
    print(f"[write] completed output={path} bytes={path.stat().st_size}", flush=True)


def upsert_completed_video(output_videos: list[dict[str, Any]], video: dict[str, Any]) -> None:
    aweme_id = id_text(video.get("aweme_id"))
    if not aweme_id:
        return

    item = dict(video)
    item["comment"] = item.get("comment") or []
    for index, existing in enumerate(output_videos):
        if id_text(existing.get("aweme_id")) == aweme_id:
            output_videos[index] = item
            break
    else:
        output_videos.append(item)

    dedupe_videos_by_cid(output_videos)


def save_completed_video(path: Path, output_videos: list[dict[str, Any]], video: dict[str, Any]) -> None:
    upsert_completed_video(output_videos, video)
    save_json(path, output_videos)


def scroll_page_and_scrollables(page: Any, pixels: int) -> int:
    try:
        return page.evaluate(
            """(pixels) => {
                window.scrollBy(0, pixels);
                const candidates = [];
                for (const el of document.querySelectorAll('body *')) {
                    const rect = el.getBoundingClientRect();
                    if (rect.width < 120 || rect.height < 120) continue;
                    if (el.scrollHeight <= el.clientHeight + 80) continue;
                    const style = window.getComputedStyle(el);
                    if (style.display === 'none' || style.visibility === 'hidden') continue;
                    candidates.push({ el, area: rect.width * rect.height });
                }
                candidates.sort((a, b) => b.area - a.area);
                for (const item of candidates.slice(0, 10)) {
                    item.el.scrollTop += Math.max(300, Math.floor(item.el.clientHeight * 0.9));
                }
                return candidates.length;
            }""",
            pixels,
        )
    except Exception as exc:
        raise_if_browser_closed(exc, "browser/page was closed while scrolling")
        raise


def click_reply_expanders(page: Any) -> int:
    return page.evaluate(
        """() => {
            const include = /(展开|查看|更多|加载).{0,16}(回复|评论)|(\\d+\\s*条回复)|view.{0,16}repl|show.{0,16}repl|more.{0,16}repl|load.{0,16}more/iu;
            const exclude = /(收起|折叠|隐藏|登录|取消|分享|举报|关注|主页|作者|头像|collapse|hide|login|cancel|share|report|follow|profile|avatar)/iu;
            const nodes = Array.from(document.querySelectorAll('button, [role="button"], span, div'));
            const candidates = [];
            for (const el of nodes) {
                if (el.closest('a[href]') || el.hasAttribute('href')) continue;
                const text = (el.innerText || el.textContent || '').replace(/\\s+/g, ' ').trim();
                const exactReplyExpand = /^[\\s\\-\\u2014\\u2013_]*(展开|查看|更多|加载)\\s*\\d*\\s*条?\\s*(回复|评论)\\s*[vV>]*$/iu;
                const tag = el.tagName.toLowerCase();
                const isButtonLike = tag === 'button' || el.getAttribute('role') === 'button';
                if (!isButtonLike && !exactReplyExpand.test(text)) continue;
                if (!text || text.length > 60) continue;
                if (!include.test(text) || exclude.test(text)) continue;
                const rect = el.getBoundingClientRect();
                if (rect.width < 8 || rect.height < 8) continue;
                if (rect.width > 260 || rect.height > 80) continue;
                const style = window.getComputedStyle(el);
                if (style.display === 'none' || style.visibility === 'hidden' || style.pointerEvents === 'none') continue;
                candidates.push(el);
            }
            let clicked = 0;
            for (const el of candidates.slice(0, 4)) {
                try {
                    el.click();
                    clicked += 1;
                } catch (_) {}
            }
            return clicked;
        }"""
    )


def maybe_wait_for_network(page: Any, timeout_ms: int) -> None:
    try:
        page.wait_for_load_state("networkidle", timeout=timeout_ms)
    except PlaywrightTimeoutError:
        pass
    except Exception as exc:
        raise_if_browser_closed(exc, "browser/page was closed while waiting for network")
        raise


def login_dialog_visible(page: Any) -> bool:
    try:
        return bool(
            page.evaluate(
                r"""() => {
                    const visible = (el) => {
                        const rect = el.getBoundingClientRect();
                        if (rect.width < 8 || rect.height < 8) return false;
                        const style = window.getComputedStyle(el);
                        return style.display !== 'none'
                            && style.visibility !== 'hidden'
                            && style.pointerEvents !== 'none'
                            && rect.bottom > 0
                            && rect.right > 0
                            && rect.left < window.innerWidth
                            && rect.top < window.innerHeight;
                    };

                    const textOf = (el) => (el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim();
                    const loginPattern = /(\u767b\u5f55\u540e|\u626b\u7801\u767b\u5f55|\u9a8c\u8bc1\u7801\u767b\u5f55|\u5bc6\u7801\u767b\u5f55|\u767b\u5f55\u5373\u4ee3\u8868\u540c\u610f|\u624b\u673a\u53f7)/iu;

                    return Array.from(document.querySelectorAll('[role="dialog"], dialog, div, section'))
                        .some((el) => {
                            if (!visible(el)) return false;
                            const rect = el.getBoundingClientRect();
                            if (rect.width < 320 || rect.height < 220) return false;
                            if (rect.width > window.innerWidth * 0.94 || rect.height > window.innerHeight * 0.94) return false;
                            return loginPattern.test(textOf(el));
                        });
                }"""
            )
        )
    except Exception as exc:
        raise_if_browser_closed(exc, "browser/page was closed while checking login dialog")
        return False


def wait_for_manual_login(page: Any, args: argparse.Namespace) -> bool:
    if args.headless:
        print("[warn] login dialog detected, but manual login requires a visible browser; rerun without --headless")
        return False

    input("[login] login dialog detected. Complete login in the browser, then press Enter to continue: ")
    try:
        page.reload(wait_until="domcontentloaded", timeout=args.timeout_ms)
    except PlaywrightTimeoutError:
        print("[warn] reload after manual login timed out; continuing")
    except Exception as exc:
        raise_if_browser_closed(exc, "browser/page was closed while reloading after manual login")
        raise

    wait_for_page(page, args.initial_wait_ms, "browser/page was closed while waiting after manual login")
    maybe_wait_for_network(page, min(args.timeout_ms, 10000))
    return True


def handle_login_dialog(page: Any, args: argparse.Namespace) -> bool:
    if not login_dialog_visible(page):
        return False

    if args.login_prompt:
        return wait_for_manual_login(page, args)

    print("[warn] login dialog detected; dismissing dialog because --no-login-prompt is set")
    return dismiss_login_dialog(page)


def dismiss_login_dialog(page: Any) -> bool:
    """Click the close button on Douyin's login dialog when it is visible."""
    try:
        target = page.evaluate(
            r"""() => {
                const visible = (el) => {
                    const rect = el.getBoundingClientRect();
                    if (rect.width < 8 || rect.height < 8) return false;
                    const style = window.getComputedStyle(el);
                    return style.display !== 'none'
                        && style.visibility !== 'hidden'
                        && style.pointerEvents !== 'none'
                        && rect.bottom > 0
                        && rect.right > 0
                        && rect.left < window.innerWidth
                        && rect.top < window.innerHeight;
                };

                const textOf = (el) => (el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim();
                const loginPattern = /(\u767b\u5f55\u540e|\u626b\u7801\u767b\u5f55|\u9a8c\u8bc1\u7801\u767b\u5f55|\u5bc6\u7801\u767b\u5f55|\u767b\u5f55\u5373\u4ee3\u8868\u540c\u610f|\u624b\u673a\u53f7)/iu;
                const strongLoginPattern = /(\u767b\u5f55\u540e|\u767b\u5f55\u5373\u4ee3\u8868\u540c\u610f)/iu;
                const closePattern = /^(\u00d7|x|\u5173\u95ed|close)$/iu;

                const roots = Array.from(document.querySelectorAll('[role="dialog"], dialog, div, section'))
                    .filter((el) => {
                        if (!visible(el)) return false;
                        const rect = el.getBoundingClientRect();
                        if (rect.width < 320 || rect.height < 220) return false;
                        if (rect.width > window.innerWidth * 0.94 || rect.height > window.innerHeight * 0.94) return false;
                        return loginPattern.test(textOf(el));
                    })
                    .map((el) => {
                        const rect = el.getBoundingClientRect();
                        const centerX = rect.left + rect.width / 2;
                        const centerY = rect.top + rect.height / 2;
                        const text = textOf(el);
                        const centeredDistance = Math.abs(centerX - window.innerWidth / 2)
                            + Math.abs(centerY - window.innerHeight / 2);
                        const score = (strongLoginPattern.test(text) ? 0 : 10000)
                            + centeredDistance
                            + (rect.width * rect.height) / 100000;
                        return { el, rect, score };
                    })
                    .sort((a, b) => a.score - b.score);

                if (!roots.length) return null;

                const root = roots[0].el;
                const rootRect = root.getBoundingClientRect();
                const nodes = Array.from(root.querySelectorAll('button, [role="button"], [aria-label], [title], div, span, svg'));
                const candidates = [];

                for (const el of nodes) {
                    if (!visible(el)) continue;
                    const rect = el.getBoundingClientRect();
                    if (rect.width > 80 || rect.height > 80) continue;

                    const label = [
                        textOf(el),
                        el.getAttribute('aria-label') || '',
                        el.getAttribute('title') || '',
                    ].join(' ').replace(/\s+/g, ' ').trim();

                    const centerX = rect.left + rect.width / 2;
                    const centerY = rect.top + rect.height / 2;
                    const nearTopRight = centerX > rootRect.left + rootRect.width * 0.78
                        && centerY < rootRect.top + rootRect.height * 0.24;

                    if (!nearTopRight || !closePattern.test(label)) continue;

                    candidates.push({
                        x: centerX,
                        y: centerY,
                        score: Math.abs(rootRect.right - centerX) + Math.abs(rootRect.top - centerY),
                    });
                }

                if (candidates.length) {
                    candidates.sort((a, b) => a.score - b.score);
                    return candidates[0];
                }

                return {
                    x: rootRect.right - Math.min(52, rootRect.width * 0.08),
                    y: rootRect.top + Math.min(56, rootRect.height * 0.12),
                };
            }"""
        )
    except Exception as exc:
        raise_if_browser_closed(exc, "browser/page was closed while handling login dialog")
        return False

    if not target:
        return False

    try:
        page.mouse.click(int(target["x"]), int(target["y"]))
        wait_for_page(page, 300, "browser/page was closed while handling login dialog")
        print("[login] dismissed login dialog")
        return True
    except Exception as exc:
        raise_if_browser_closed(exc, "browser/page was closed while handling login dialog")
        return False


def collect_videos(page: Any, args: argparse.Namespace) -> list[dict[str, Any]]:
    videos: OrderedDict[str, dict[str, Any]] = OrderedDict()
    state = {"has_more": None, "max_cursor": None}

    def on_response(response: Any) -> None:
        if POST_API_MARKER not in response.url:
            return
        try:
            data = response.json()
        except Exception:
            return

        added = 0
        for aweme in data.get("aweme_list") or []:
            video = extract_video(aweme)
            if not video:
                continue
            aweme_id = video["aweme_id"]
            if aweme_id not in videos:
                videos[aweme_id] = video
                added += 1

        state["has_more"] = data.get("has_more")
        state["max_cursor"] = data.get("max_cursor")
        if added:
            print(f"[video] added={added} total={len(videos)} max_cursor={state['max_cursor']}")

    page.on("response", on_response)
    try:
        print(f"[open profile] {args.profile_url}")
        page.goto(args.profile_url, wait_until="domcontentloaded", timeout=args.timeout_ms)
    except PlaywrightTimeoutError:
        print("[warn] profile navigation timed out; continuing with captured responses")
    except Exception as exc:
        raise_if_browser_closed(exc, "browser/page was closed while opening profile")
        raise

    wait_for_page(page, args.initial_wait_ms, "browser/page was closed while waiting after profile open")
    maybe_wait_for_network(page, min(args.timeout_ms, 10000))

    if args.login_prompt and not args.headless:
        input("If the page asks for login, complete it in the browser, then press Enter to continue: ")
        try:
            page.reload(wait_until="domcontentloaded", timeout=args.timeout_ms)
        except PlaywrightTimeoutError:
            print("[warn] profile reload timed out; continuing")
        except Exception as exc:
            raise_if_browser_closed(exc, "browser/page was closed while reloading profile")
            raise
        wait_for_page(page, args.initial_wait_ms, "browser/page was closed while waiting after profile reload")
    else:
        handle_login_dialog(page, args)

    idle_rounds = 0
    last_total = len(videos)
    for _ in range(args.video_scroll_rounds):
        if args.max_videos and len(videos) >= args.max_videos:
            break

        handle_login_dialog(page, args)
        scroll_page_and_scrollables(page, args.scroll_pixels)
        wait_for_page(page, args.scroll_wait_ms, "browser/page was closed while waiting after profile scroll")

        current_total = len(videos)
        if current_total == last_total:
            idle_rounds += 1
        else:
            idle_rounds = 0
        last_total = current_total

        if state["has_more"] in (0, False) and idle_rounds >= 2:
            break
        if idle_rounds >= args.video_idle_rounds:
            break

    remove_response_listener(page, on_response)
    result = list(videos.values())
    if args.max_videos:
        result = result[: args.max_videos]
    return result


def collect_comments_for_video(page: Any, video: dict[str, Any], args: argparse.Namespace) -> list[dict[str, Any]]:
    aweme_id = video["aweme_id"]
    top_comments: OrderedDict[str, dict[str, Any]] = OrderedDict()
    replies: defaultdict[str, OrderedDict[str, dict[str, Any]]] = defaultdict(OrderedDict)
    state = {"top_has_more": None, "top_cursor": None}

    def add_reply(parent_cid: str, raw: dict[str, Any]) -> int:
        parent_cid = id_text(parent_cid)
        if not parent_cid:
            return 0
        reply = extract_comment(raw, aweme_id=aweme_id, reply_id=parent_cid)
        key = comment_key(reply)
        if key in replies[parent_cid]:
            return 0
        replies[parent_cid][key] = reply
        return 1

    def add_top_comment(raw: dict[str, Any]) -> int:
        comment = extract_comment(raw, aweme_id=aweme_id)
        comment["sub-comment"] = []
        key = comment_key(comment)
        added = 0
        if key not in top_comments:
            top_comments[key] = comment
            added = 1

        parent_cid = comment["cid"] or key
        for reply_raw in raw.get("reply_comment") or []:
            add_reply(parent_cid, reply_raw)
        return added

    def on_response(response: Any) -> None:
        url = response.url
        is_reply = REPLY_API_MARKER in url
        is_top_comment = COMMENT_API_MARKER in url and not is_reply
        if not is_reply and not is_top_comment:
            return

        response_aweme_id = first_query_value(url, "item_id", "aweme_id")
        if response_aweme_id and response_aweme_id != aweme_id:
            return

        try:
            data = response.json()
        except Exception:
            return

        raw_comments = data.get("comments") or []

        if is_reply:
            parent_cid = first_query_value(url, "comment_id")
            added = sum(add_reply(parent_cid, raw) for raw in raw_comments)
            if added:
                print(f"[reply] aweme_id={aweme_id} parent={parent_cid} added={added}")
            return

        added = sum(add_top_comment(raw) for raw in raw_comments)
        state["top_has_more"] = data.get("has_more")
        state["top_cursor"] = data.get("cursor")
        if added:
            print(f"[comment] aweme_id={aweme_id} added={added} total={len(top_comments)}")

    def build_result() -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for key, comment in top_comments.items():
            parent_cid = comment["cid"] or key
            item = dict(comment)
            item["sub-comment"] = list(replies.get(parent_cid, {}).values())
            result.append(item)
        return result

    def mark_browser_closed(exc: BaseException) -> bool:
        if not isinstance(exc, BrowserClosedError) and not is_browser_closed_error(exc):
            return False
        setattr(args, "_browser_closed", True)
        print(f"[stop] aweme_id={aweme_id} browser/page closed; saving captured comments")
        return True

    page.on("response", on_response)
    try:
        print(f"[open video] {aweme_id}")
        page.goto(make_video_url(aweme_id), wait_until="domcontentloaded", timeout=args.timeout_ms)
    except PlaywrightTimeoutError:
        print(f"[warn] video navigation timed out: {aweme_id}")
    except Exception as exc:
        if mark_browser_closed(exc):
            remove_response_listener(page, on_response)
            return build_result()
        raise

    try:
        wait_for_page(page, args.initial_wait_ms, "browser/page was closed while waiting after video open")
        maybe_wait_for_network(page, min(args.timeout_ms, 10000))
        handle_login_dialog(page, args)
    except Exception as exc:
        if mark_browser_closed(exc):
            remove_response_listener(page, on_response)
            return build_result()
        raise

    idle_rounds = 0
    last_total = -1
    for _ in range(args.comment_scroll_rounds):
        top_count = len(top_comments)
        reply_count = sum(len(items) for items in replies.values())
        total_count = top_count + reply_count
        if args.max_comments_per_video and total_count >= args.max_comments_per_video:
            break

        if args.include_replies:
            try:
                handle_login_dialog(page, args)
                reply_expanders_clicked = click_reply_expanders(page)
                if reply_expanders_clicked:
                    print(f"[reply-expand] clicked={reply_expanders_clicked}")
                wait_for_page(page, args.reply_click_wait_ms, "browser/page was closed after expanding replies")
            except Exception as exc:
                if mark_browser_closed(exc):
                    break
                raise

        try:
            handle_login_dialog(page, args)
            viewport = page.viewport_size or {"width": 1280, "height": 900}
            page.mouse.move(int(viewport["width"] * 0.78), int(viewport["height"] * 0.72))
            page.mouse.wheel(0, args.scroll_pixels)
            scroll_page_and_scrollables(page, args.scroll_pixels)
            wait_for_page(page, args.scroll_wait_ms, "browser/page was closed while waiting after comment scroll")
        except Exception as exc:
            if mark_browser_closed(exc):
                break
            raise

        top_count = len(top_comments)
        reply_count = sum(len(items) for items in replies.values())
        total_count = top_count + reply_count

        if total_count == last_total:
            idle_rounds += 1
        else:
            idle_rounds = 0
        last_total = total_count

        if state["top_has_more"] in (0, False) and idle_rounds >= 2:
            break
        if idle_rounds >= args.comment_idle_rounds:
            break

    remove_response_listener(page, on_response)
    return build_result()


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Crawl all loaded videos from a Douyin profile and write each video's comments "
            "and replies to the project-local comments.json by default."
        )
    )
    parser.add_argument("--profile-url", default=DEFAULT_PROFILE_URL, help="Douyin profile URL.")
    parser.add_argument(
        "--output",
        default=None,
        help="Output JSON file path. Defaults to comments.json beside this script.",
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
        help="Pause for manual login after opening the profile page.",
    )
    parser.add_argument(
        "--no-login-prompt",
        dest="login_prompt",
        action="store_false",
        help="Do not pause for manual login after opening the profile page.",
    )
    parser.set_defaults(headless=False, login_prompt=True)
    parser.add_argument("--max-videos", type=int, default=0, help="Limit video count; 0 means no explicit limit.")
    parser.add_argument(
        "--max-comments-per-video",
        type=int,
        default=0,
        help="Limit top comments plus replies per video; 0 means no explicit limit.",
    )
    parser.add_argument("--videos-only", action="store_true", help="Only fetch the profile video list.")
    parser.add_argument("--no-replies", dest="include_replies", action="store_false", help="Skip reply comments.")
    parser.set_defaults(include_replies=True)
    parser.add_argument(
        "--refetch-existing-comments",
        action="store_true",
        help="Re-open videos that already have comments and merge new comments by cid.",
    )
    parser.add_argument("--timeout-ms", type=int, default=60000)
    parser.add_argument("--initial-wait-ms", type=int, default=3500)
    parser.add_argument("--scroll-wait-ms", type=int, default=1400)
    parser.add_argument("--reply-click-wait-ms", type=int, default=800)
    parser.add_argument("--scroll-pixels", type=int, default=1800)
    parser.add_argument("--video-scroll-rounds", type=int, default=180)
    parser.add_argument("--comment-scroll-rounds", type=int, default=500)
    parser.add_argument("--video-idle-rounds", type=int, default=10)
    parser.add_argument("--comment-idle-rounds", type=int, default=14)
    parser.add_argument("--viewport-width", type=int, default=1463)
    parser.add_argument("--viewport-height", type=int, default=915)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    if sync_playwright is None:
        print("Missing dependency: playwright", file=sys.stderr)
        print("Install dependencies: python -m pip install -r requirements.txt", file=sys.stderr)
        print("Install browser once: python -m playwright install chromium", file=sys.stderr)
        return 2

    output_path = project_default_path(args.output, "comments.json")
    args.output = str(output_path)
    args.user_data_dir = str(project_default_path(args.user_data_dir, ".douyin-browser-profile"))
    existing_videos = load_existing_videos(output_path)
    output_videos = [dict(video) for video in existing_videos]

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

        try:
            try:
                fetched_videos = collect_videos(page, args)
            except BrowserClosedError as exc:
                print(f"[stop] {exc}; saving existing output before exit")
                save_json(output_path, output_videos)
                return 1

            videos = merge_videos(existing_videos, fetched_videos)
            dedupe_videos_by_cid(videos)
            if not fetched_videos:
                print(
                    "[warn] no video API data captured from the profile page; "
                    "check login status or try --headed --login-prompt"
                )

            if args.videos_only:
                save_json(output_path, videos)
                print(f"[save] videos={len(videos)} output={output_path}")
                return 0

            if not videos:
                save_json(output_path, output_videos)
                print(f"[save] videos=0 output={output_path}")
                return 0

            for index, video in enumerate(videos, start=1):
                print(f"[progress] {index}/{len(videos)} aweme_id={video['aweme_id']}")
                existing_comments = video.get("comment") or []
                existing_comment_count = count_comments(existing_comments)
                existing_reply_count = count_replies(existing_comments)
                existing_has_profile_fields = comments_have_profile_fields(existing_comments)
                should_refetch_missing_replies = (
                    args.include_replies
                    and existing_comment_count
                    and existing_reply_count == 0
                )
                if (
                    existing_comment_count
                    and not args.refetch_existing_comments
                    and existing_has_profile_fields
                    and not should_refetch_missing_replies
                ):
                    print(f"[skip] aweme_id={video['aweme_id']} existing_comments={existing_comment_count}")
                    save_completed_video(output_path, output_videos, video)
                    continue
                if should_refetch_missing_replies and not args.refetch_existing_comments:
                    print(f"[refetch] aweme_id={video['aweme_id']} existing_replies=0; trying to fetch replies")
                if existing_comment_count and not existing_has_profile_fields:
                    print(f"[refetch] aweme_id={video['aweme_id']} missing ip_label/nickname fields")

                fetched_comments = collect_comments_for_video(page, video, args)
                fetched_stats = comment_profile_stats(fetched_comments)
                if not fetched_stats["total"]:
                    print(
                        "[warn] "
                        f"aweme_id={video['aweme_id']} no fresh comment API data captured; "
                        "ip_label/nickname cannot be filled from existing old data"
                    )
                else:
                    print(
                        "[fields] "
                        f"aweme_id={video['aweme_id']} fetched={fetched_stats['total']} "
                        f"ip_label={fetched_stats['ip_label']} "
                        f"nickname={fetched_stats['nickname']} "
                        f"both={fetched_stats['both']}"
                    )
                video["comment"] = merge_comment_lists(existing_comments, fetched_comments)
                dedupe_videos_by_cid(videos)
                comment_count = len(video["comment"])
                reply_count = sum(len(item.get("sub-comment") or []) for item in video["comment"])
                saved_stats = comment_profile_stats(video["comment"])
                save_completed_video(output_path, output_videos, video)
                print(
                    "[save] "
                    f"aweme_id={video['aweme_id']} comments={comment_count} replies={reply_count} "
                    f"ip_label={saved_stats['ip_label']}/{saved_stats['total']} "
                    f"nickname={saved_stats['nickname']}/{saved_stats['total']}"
                )
                if getattr(args, "_browser_closed", False):
                    print("[stop] browser/page closed; stopped after saving current progress")
                    return 1
        finally:
            try:
                context.close()
            except Exception as exc:
                if not is_browser_closed_error(exc):
                    raise

    print(f"[done] wrote {output_path} bytes={output_path.stat().st_size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
