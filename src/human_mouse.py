"""Human-like mouse movement via cubic Bezier paths.

Inspired by sarperavci/human_mouse (MIT) but reimplemented in pure stdlib —
no numpy/scipy dependency.
"""
import math
import random
import time


class MouseState:
    """Track current mouse position (Playwright doesn't expose it)."""

    def __init__(self, x=None, y=None):
        self.x = x
        self.y = y

    def update(self, x, y):
        self.x, self.y = x, y


def bezier_path(start, end, steps=None):
    """Generate a cubic Bezier path with two perpendicular-offset control points.

    Returns a list of (x, y) points. Includes ease-in-out via smoothstep so the
    cursor accelerates → cruises → decelerates instead of moving at constant speed.
    """
    sx, sy = start
    ex, ey = end
    dx, dy = ex - sx, ey - sy
    dist = max(math.hypot(dx, dy), 1.0)

    if steps is None:
        # Roughly 1 step per 25 pixels, clamped to [15, 40]
        steps = max(15, min(40, int(dist / 25)))

    # Perpendicular unit vector (rotate (dx,dy) 90 degrees)
    px, py = -dy / dist, dx / dist

    # Two control points at ~30% and ~70% along the path, offset perpendicularly
    off1 = random.uniform(-0.2, 0.2) * dist
    off2 = random.uniform(-0.2, 0.2) * dist
    cx1 = sx + dx * 0.3 + px * off1
    cy1 = sy + dy * 0.3 + py * off1
    cx2 = sx + dx * 0.7 + px * off2
    cy2 = sy + dy * 0.7 + py * off2

    points = []
    for i in range(steps + 1):
        t = i / steps
        # smoothstep ease-in-out: 3t^2 - 2t^3
        t = t * t * (3 - 2 * t)
        u = 1 - t
        x = u**3 * sx + 3 * u**2 * t * cx1 + 3 * u * t**2 * cx2 + t**3 * ex
        y = u**3 * sy + 3 * u**2 * t * cy1 + 3 * u * t**2 * cy2 + t**3 * ey
        points.append((x, y))
    return points


def human_move(page, target_x, target_y, state):
    """Move mouse from current state to target along a Bezier curve."""
    if state.x is None or state.y is None:
        viewport = page.viewport_size or {"width": 1280, "height": 800}
        state.update(viewport["width"] // 2, viewport["height"] // 2)

    for x, y in bezier_path((state.x, state.y), (target_x, target_y)):
        page.mouse.move(x, y)
        time.sleep(random.uniform(0.005, 0.020))
    state.update(target_x, target_y)


def human_click_locator(page, locator, state, button="left"):
    """Move to a Playwright Locator's center (with jitter) and click. Returns bool."""
    try:
        box = locator.bounding_box(timeout=2000)
    except Exception:
        return False
    if not box:
        return False

    target_x = box["x"] + box["width"] / 2 + random.uniform(-3, 3)
    target_y = box["y"] + box["height"] / 2 + random.uniform(-3, 3)

    human_move(page, target_x, target_y, state)
    time.sleep(random.uniform(0.05, 0.2))   # hover before click
    page.mouse.click(target_x, target_y, button=button)
    return True
