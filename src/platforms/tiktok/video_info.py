"""Best-effort TikTok video metadata capture helpers."""
import re

from core.runtime import redact_runtime_text

DEFAULT_MAX_TITLE_LENGTH = 300
DEFAULT_MAX_DESCRIPTION_LENGTH = 600
DEFAULT_CAPTURE_TIMEOUT_MS = 800

GENERIC_TITLES = (
    "tiktok",
    "tiktok - make your day",
    "make your day",
    "for you",
    "log in",
)

CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
VIDEO_URL_RE = re.compile(r"https?://(?:www\.)?tiktok\.com/@([^/?#]+)/video/(\d+)")
VIDEO_PATH_RE = re.compile(r"/@([^/?#]+)/video/(\d+)")


def capture_active_video_info(
    page,
    max_title_length=DEFAULT_MAX_TITLE_LENGTH,
    max_description_length=DEFAULT_MAX_DESCRIPTION_LENGTH,
    capture_timeout_ms=DEFAULT_CAPTURE_TIMEOUT_MS,
):
    """Capture metadata for the currently visible TikTok video.

    This is intentionally best-effort: all Playwright failures are converted into
    a structured result so callers can keep the warmup flow running.
    """
    try:
        page_url = clean_url(getattr(page, "url", "") or "")
        url_info = parse_tiktok_video_url(page_url)
        dom_info = evaluate_active_video_dom(
            page,
            max_title_length=max_title_length,
            max_description_length=max_description_length,
            capture_timeout_ms=capture_timeout_ms,
        )
        info = merge_video_info(url_info, dom_info)
        info["title"] = clean_title(info.get("title"), max_title_length)
        info["description"] = clean_description(
            info.get("description"),
            max_description_length,
        )
        info["author_handle"] = normalize_handle(info.get("author_handle"))
        info["author_name"] = clean_text(info.get("author_name"), 200)
        info["video_url"] = clean_url(info.get("video_url"))
        info["raw_source"] = clean_text(info.get("raw_source"), 80) or "unknown"
        info["capture_error"] = clean_error(info.get("capture_error"))
        info["capture_status"] = resolve_capture_status(info)
        return info
    except Exception as exc:
        return failed_video_info(exc)


def evaluate_active_video_dom(
    page,
    max_title_length=DEFAULT_MAX_TITLE_LENGTH,
    max_description_length=DEFAULT_MAX_DESCRIPTION_LENGTH,
    capture_timeout_ms=DEFAULT_CAPTURE_TIMEOUT_MS,
):
    """Read active-video metadata from the browser DOM."""
    script = """
    ([maxTitleLength, maxDescriptionLength, captureTimeoutMs]) => {
      const clean = (value, limit) => {
        if (!value) return "";
        const text = String(value).replace(/[\\u0000-\\u001f\\u007f]/g, " ")
          .replace(/\\s+/g, " ").trim();
        return limit && text.length > limit ? text.slice(0, limit) : text;
      };
      const isVisible = (el) => {
        if (!el || !el.getBoundingClientRect) return false;
        const rect = el.getBoundingClientRect();
        const style = window.getComputedStyle(el);
        return rect.width > 0 && rect.height > 0 &&
          rect.bottom > 0 && rect.top < window.innerHeight &&
          style.visibility !== "hidden" && style.display !== "none";
      };
      const centerDistance = (el) => {
        const rect = el.getBoundingClientRect();
        const cy = rect.top + rect.height / 2;
        return Math.abs(cy - window.innerHeight / 2);
      };
      const videoUrlPattern = /(?:https?:)?\\/\\/(?:www\\.)?tiktok\\.com\\/@[^"'\\s<>]+\\/video\\/\\d+|\\/@[^"'\\s<>]+\\/video\\/\\d+/i;
      const firstVideoUrl = (value) => {
        const match = clean(value || "").match(videoUrlPattern);
        return match ? match[0] : "";
      };
      const candidates = Array.from(document.querySelectorAll([
        'article',
        '[data-e2e*="feed"]',
        '[data-e2e*="video"]',
        'div[class*="DivItemContainer"]',
        'div[class*="DivVideo"]',
        'section'
      ].join(','))).filter(isVisible);
      candidates.sort((left, right) => centerDistance(left) - centerDistance(right));
      const root = candidates[0] || document.body;

      const firstText = (selectors, limit) => {
        for (const selector of selectors) {
          const nodes = Array.from(root.querySelectorAll(selector)).filter(isVisible);
          for (const node of nodes) {
            const text = clean(node.innerText || node.textContent || node.getAttribute("title") || "", limit);
            if (text) return text;
          }
        }
        return "";
      };
      const firstAttr = (selectors, attr) => {
        for (const selector of selectors) {
          const nodes = Array.from(root.querySelectorAll(selector)).filter(isVisible);
          for (const node of nodes) {
            const value = clean(node.getAttribute(attr) || "");
            if (value) return value;
          }
        }
        return "";
      };
      const closestVideoUrl = (container) => {
        const anchors = Array.from((container || document).querySelectorAll('a[href*="/video/"], a[href*="tiktok.com/@"]'))
          .map((node) => ({
            node,
            href: firstVideoUrl(node.href || node.getAttribute("href") || "")
          }))
          .filter((item) => item.href);
        anchors.sort((left, right) => {
          const leftVisible = isVisible(left.node) ? 0 : 1;
          const rightVisible = isVisible(right.node) ? 0 : 1;
          return leftVisible - rightVisible || centerDistance(left.node) - centerDistance(right.node);
        });
        return anchors[0] ? anchors[0].href : "";
      };
      const firstVideoAttribute = (container) => {
        const nodes = Array.from((container || document).querySelectorAll("*")).slice(0, 2000);
        for (const node of nodes) {
          for (const attr of Array.from(node.attributes || [])) {
            const url = firstVideoUrl(attr.value);
            if (url) return url;
          }
        }
        return "";
      };
      const firstMeta = (selectors) => {
        for (const selector of selectors) {
          const node = document.querySelector(selector);
          const value = clean(node && node.getAttribute("content") || "");
          if (value) return value;
        }
        return "";
      };

      const videoAnchor = closestVideoUrl(root) || firstVideoAttribute(root) || closestVideoUrl(document);
      const authorAnchor = Array.from(root.querySelectorAll('a[href^="/@"], a[href*="tiktok.com/@"]'))
        .map((node) => node.href || node.getAttribute("href") || "")
        .find(Boolean) || "";
      const title = firstText([
        '[data-e2e="video-desc"]',
        '[data-e2e="browse-video-desc"]',
        '[data-e2e*="desc"]',
        'h1',
        'h2',
        '[class*="caption"]',
        '[class*="Caption"]',
        '[class*="desc"]',
        '[class*="Desc"]'
      ], maxTitleLength);
      const description = title || firstAttr([
        '[aria-label]',
        '[title]'
      ], "aria-label") || firstMeta([
        'meta[property="og:description"]',
        'meta[name="description"]'
      ]);
      const metaTitle = firstMeta([
        'meta[property="og:title"]',
        'meta[name="twitter:title"]'
      ]) || clean(document.title || "", maxTitleLength);
      const authorName = firstText([
        '[data-e2e="video-author-uniqueid"]',
        '[data-e2e="browse-username"]',
        'a[href^="/@"]',
        'a[href*="tiktok.com/@"]'
      ], 200);

      return {
        video_url: videoAnchor,
        author_url: authorAnchor,
        author_name: authorName,
        title: title || metaTitle,
        description,
        raw_source: title ? "dom_caption" : (metaTitle ? "meta_title" : "dom_partial"),
        capture_status: "partial",
        capture_error: ""
      };
    }
    """
    # The timeout is passed into JS for future selector tuning; page.evaluate itself
    # is synchronous and should remain short because it only scans the current DOM.
    return page.evaluate(
        script,
        [max_title_length, max_description_length, capture_timeout_ms],
    ) or {}


def merge_video_info(url_info, dom_info):
    dom_info = dom_info or {}
    video_url = clean_url(dom_info.get("video_url")) or clean_url(url_info.get("video_url"))
    parsed_video = parse_tiktok_video_url(video_url)
    author_info = parse_author_url(dom_info.get("author_url"))
    return {
        "video_id": (
            clean_text(url_info.get("video_id"), 128)
            or clean_text(parsed_video.get("video_id"), 128)
            or clean_text(dom_info.get("video_id"), 128)
        ),
        "video_url": video_url or clean_url(dom_info.get("video_url")),
        "author_handle": (
            normalize_handle(url_info.get("author_handle"))
            or normalize_handle(parsed_video.get("author_handle"))
            or normalize_handle(author_info.get("author_handle"))
            or normalize_handle(dom_info.get("author_handle"))
        ),
        "author_name": dom_info.get("author_name"),
        "title": dom_info.get("title"),
        "description": dom_info.get("description"),
        "raw_source": dom_info.get("raw_source") or ("url_only" if url_info else "unknown"),
        "capture_status": dom_info.get("capture_status") or "partial",
        "capture_error": dom_info.get("capture_error") or "",
    }


def parse_tiktok_video_url(url):
    url = clean_url(url)
    if not url:
        return {}
    match = VIDEO_URL_RE.search(url) or VIDEO_PATH_RE.search(url)
    if not match:
        return {}
    author_handle, video_id = match.groups()
    return {
        "author_handle": normalize_handle(author_handle),
        "video_id": video_id,
        "video_url": f"https://www.tiktok.com/@{normalize_handle(author_handle)}/video/{video_id}",
    }


def parse_author_url(url):
    url = clean_url(url)
    if not url:
        return {}
    match = re.search(r"(?:https?://(?:www\.)?tiktok\.com)?/@([^/?#]+)", url)
    if not match:
        return {}
    return {"author_handle": normalize_handle(match.group(1))}


def resolve_capture_status(info):
    if info.get("capture_error") and not has_any_video_field(info):
        return "failed"
    if info.get("title") or info.get("description"):
        return "ok" if (info.get("video_id") or info.get("video_url")) else "partial"
    if has_any_video_field(info):
        return "partial"
    return "failed"


def has_any_video_field(info):
    return any(
        info.get(key)
        for key in ("video_id", "video_url", "author_handle", "author_name", "title", "description")
    )


def failed_video_info(error):
    return {
        "video_id": None,
        "video_url": None,
        "author_handle": None,
        "author_name": None,
        "title": None,
        "description": None,
        "raw_source": "failed",
        "capture_status": "failed",
        "capture_error": clean_error(error),
    }


def normalize_handle(value):
    text = clean_text(value, 120)
    if not text:
        return None
    text = text.strip().lstrip("@")
    if "/" in text:
        text = text.split("/", 1)[0]
    return text or None


def clean_title(value, limit=DEFAULT_MAX_TITLE_LENGTH):
    text = clean_text(value, limit)
    if not text:
        return None
    lowered = text.lower().strip()
    if lowered in GENERIC_TITLES:
        return None
    if lowered.startswith("tiktok - ") and "@" not in lowered and "#" not in lowered:
        return None
    return text


def clean_description(value, limit=DEFAULT_MAX_DESCRIPTION_LENGTH):
    return clean_text(value, limit)


def clean_error(value):
    return clean_text(redact_runtime_text(str(value or "")), 500)


def clean_url(value):
    text = clean_text(value, 1000)
    if not text:
        return None
    if text.startswith("//"):
        text = "https:" + text
    if text.startswith("/@"):
        text = "https://www.tiktok.com" + text
    if not text.startswith(("http://", "https://")):
        return None
    text = text.split("#", 1)[0]
    text = text.split("?", 1)[0]
    return text


def clean_text(value, limit=None):
    if value is None:
        return None
    text = CONTROL_CHARS_RE.sub(" ", str(value))
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return None
    if limit and len(text) > limit:
        return text[:limit]
    return text
