"""Record demo scenarios with Playwright for the presentation.

Usage (from site/demo-video):
    uv run python record.py --scenario agent
    uv run python record.py --scenario all

Each scenario resets the demo data, drives a real browser with visible typing
and a fake cursor, and saves videos/<scenario>.mp4 (and the raw .webm).
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

import httpx
import imageio_ffmpeg
from playwright.sync_api import Locator, Page, sync_playwright

HERE = Path(__file__).parent
OUT = HERE / "videos"
VIEWPORT = {"width": 1440, "height": 900}

STUB_TEXTS = (
    "Агент підтримки ще не підключений",
    "Агент тимчасово недоступний",
)

# Draws a visible cursor and click ripple, since Playwright videos have no pointer.
CURSOR_JS = """
(() => {
  if (window.__demoCursor) return;
  window.__demoCursor = true;
  const install = () => {
    const hide = document.createElement('style');
    hide.textContent = 'nextjs-portal { display: none !important; }';
    document.head.appendChild(hide);
    const c = document.createElement('div');
    c.id = '__demo_cursor';
    Object.assign(c.style, {
      position: 'fixed', left: '0px', top: '0px', width: '22px', height: '22px',
      marginLeft: '-11px', marginTop: '-11px', borderRadius: '50%',
      background: 'rgba(99,102,241,0.35)', border: '2px solid rgba(79,70,229,0.9)',
      zIndex: '2147483647', pointerEvents: 'none', transition: 'transform 80ms ease',
    });
    document.body.appendChild(c);
    document.addEventListener('mousemove', (e) => {
      c.style.left = e.clientX + 'px';
      c.style.top = e.clientY + 'px';
    }, true);
    document.addEventListener('mousedown', () => { c.style.transform = 'scale(0.7)'; }, true);
    document.addEventListener('mouseup', () => { c.style.transform = 'scale(1)'; }, true);
  };
  if (document.body) install(); else document.addEventListener('DOMContentLoaded', install);
})();
"""


class Director:
    """Small helpers that make the recording readable for humans."""

    def __init__(self, page: Page, pace: float):
        self.page = page
        self.pace = pace

    def pause(self, seconds: float) -> None:
        time.sleep(seconds * self.pace)

    def move_to(self, target: Locator) -> None:
        target.scroll_into_view_if_needed()
        box = target.bounding_box()
        if box:
            self.page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2, steps=25)

    def click(self, target: Locator) -> None:
        self.move_to(target)
        self.pause(0.4)
        target.click()
        self.pause(0.6)

    def type(self, target: Locator, text: str) -> None:
        self.click(target)
        target.press_sequentially(text, delay=int(45 * self.pace) or 1)
        self.pause(0.5)

    def scroll(self, pixels: int, steps: int = 12) -> None:
        for _ in range(steps):
            self.page.mouse.wheel(0, pixels / steps)
            time.sleep(0.04)
        self.pause(0.8)


def reset_demo(api: str) -> None:
    r = httpx.post(f"{api}/api/admin/reset", timeout=30)
    r.raise_for_status()


def wait_agent_turn(page: Page, timeout_s: float) -> str:
    """Wait until the chat input is enabled again and return the last message text."""
    box = page.get_by_label("Повідомлення")
    page.wait_for_function(
        "el => !el.disabled", arg=box.element_handle(), timeout=timeout_s * 1000
    )
    time.sleep(1.5)  # let async replies (polled every 2s) land
    return page.locator("main").inner_text()


# --- scenarios -------------------------------------------------------------


def scenario_agent(d: Director, base: str, args: argparse.Namespace) -> None:
    """Customer asks support to move a booking; then the admin sees the AI change."""
    page = d.page
    page.goto(f"{base}/b/{args.tenant}")
    d.pause(2)
    d.click(page.get_by_role("link", name="Підтримка").first)
    page.wait_for_url("**/support")
    d.pause(1)

    d.type(page.get_by_label("Ім'я"), args.client_name)
    d.type(page.get_by_label("Телефон"), args.client_phone)
    d.click(page.get_by_role("button", name="Почати чат"))
    page.get_by_label("Повідомлення").wait_for()
    d.pause(1)

    for message in args.message:
        d.type(page.get_by_label("Повідомлення"), message)
        d.click(page.get_by_role("button", name="Надіслати"))
        text = wait_agent_turn(page, args.agent_timeout)
        if any(s in text for s in STUB_TEXTS):
            print("WARNING: агент не відповів (заглушка). Перевірте AGENT_URL у site/.env.", file=sys.stderr)
        d.pause(args.read_time)

    # Admin view: the change made by the agent, with the AI badge and timeline.
    page.goto(f"{base}/admin/{args.tenant}")
    page.wait_for_selector('[data-testid^="chip-"]')
    d.pause(2)
    chip = page.get_by_test_id(f"chip-{args.booking_id}")
    if chip.count():
        d.click(chip)
        d.pause(1.5)
        dialog = page.get_by_role("dialog")
        if dialog.count():
            d.move_to(dialog)
            d.scroll(500)
        d.pause(3)
        page.keyboard.press("Escape")
        d.pause(1)
    d.click(page.get_by_role("link", name="Підтримка").first)
    d.pause(3)


def scenario_tour(d: Director, base: str, args: argparse.Namespace) -> None:
    """Product tour: home, business page, online booking, admin panel."""
    page = d.page
    page.goto(base)
    d.pause(2)
    d.click(page.locator(f'a[href="/b/{args.tenant}"]').first)
    d.pause(1.5)
    d.scroll(600)
    d.scroll(-600)
    d.click(page.get_by_role("link", name="Записатись").first)
    d.pause(1)

    d.click(page.locator("button[aria-pressed]").first)  # first service
    d.click(page.get_by_role("button", name="Будь-хто"))
    days = page.get_by_role("group", name="День").locator("button")
    d.click(days.nth(1))
    slots = page.locator("[aria-live=polite] button[aria-pressed]")
    slots.first.wait_for()
    d.click(slots.nth(min(2, slots.count() - 1)))
    d.type(page.get_by_label("Ім'я"), "Софія")
    d.type(page.get_by_label("Телефон"), "+380 67 555 12 34")
    d.click(page.get_by_role("button", name="Підтвердити запис"))
    d.pause(3)

    page.goto(f"{base}/admin/{args.tenant}")
    page.wait_for_selector('[data-testid^="chip-"]')
    d.pause(2)
    d.click(page.get_by_role("button", name="Наступний тиждень"))
    d.pause(1.5)
    d.click(page.get_by_role("button", name="Сьогодні"))
    d.pause(1)
    for item in ("Клієнти", "Майстри", "Послуги", "Налаштування"):
        d.click(page.get_by_role("link", name=item).first)
        d.pause(1.5)
        if item == "Налаштування":
            d.scroll(700)
            d.pause(2)


def scenario_widget(d: Director, base: str, args: argparse.Namespace) -> None:
    """The same AI support embedded on a business's own website."""
    page = d.page
    page.goto(f"{base}/demo-salon-site.html")
    d.pause(2)
    d.scroll(500)
    d.scroll(-500)
    d.click(page.locator("#bookly-widget-button"))
    frame = page.frame_locator("#bookly-widget-panel iframe")
    frame.get_by_label("Ім'я").wait_for()
    d.pause(1)
    frame.get_by_label("Ім'я").click()
    frame.get_by_label("Ім'я").press_sequentially(args.client_name, delay=45)
    frame.get_by_label("Телефон").click()
    frame.get_by_label("Телефон").press_sequentially(args.client_phone, delay=45)
    frame.get_by_role("button", name="Почати чат").click()
    box = frame.get_by_label("Повідомлення")
    box.wait_for()
    box.click()
    box.press_sequentially(args.widget_message, delay=45)
    frame.get_by_role("button", name="Надіслати").click()
    box.wait_for(state="visible")
    page.wait_for_timeout(1000)
    frame.locator("textarea:not([disabled])").wait_for(timeout=args.agent_timeout * 1000)
    d.pause(args.read_time)


SCENARIOS = {"agent": scenario_agent, "tour": scenario_tour, "widget": scenario_widget}


def to_mp4(src: Path, dst: Path) -> None:
    # Bundled static ffmpeg: Homebrew's build on this machine is broken (missing libx265).
    subprocess.run(
        [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-i", str(src),
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-movflags", "+faststart", str(dst)],
        check=True,
    )


def record(name: str, args: argparse.Namespace) -> Path:
    reset_demo(args.api)
    raw_dir = OUT / f"_raw_{name}"
    shutil.rmtree(raw_dir, ignore_errors=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not args.headed)
        context = browser.new_context(
            viewport=VIEWPORT,
            record_video_dir=str(raw_dir),
            record_video_size=VIEWPORT,
            locale="uk-UA",
            timezone_id="Europe/Kyiv",
        )
        context.add_init_script(CURSOR_JS)
        page = context.new_page()
        page.set_default_timeout(30_000)
        try:
            SCENARIOS[name](Director(page, args.pace), args.base, args)
        finally:
            video = page.video
            context.close()
            browser.close()
        webm = Path(video.path())
    OUT.mkdir(exist_ok=True)
    final_webm = OUT / f"{name}.webm"
    shutil.move(webm, final_webm)
    shutil.rmtree(raw_dir, ignore_errors=True)
    mp4 = OUT / f"{name}.mp4"
    to_mp4(final_webm, mp4)
    if not args.keep_demo_state:
        reset_demo(args.api)
    return mp4


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scenario", choices=[*SCENARIOS, "all"], default="all")
    ap.add_argument("--base", default="http://localhost:3000")
    ap.add_argument("--api", default="http://localhost:8001")
    ap.add_argument("--tenant", default="lumen")
    ap.add_argument("--client-name", default="Олена")
    ap.add_argument("--client-phone", default="+380 67 123 45 01")
    ap.add_argument("--booking-id", default="b-olena-1", help="booking to open in admin after the chat")
    ap.add_argument(
        "--message", action="append",
        help="customer message (repeat for several turns)",
    )
    ap.add_argument("--widget-message", default="Підкажіть, скільки коштує стрижка?")
    ap.add_argument("--agent-timeout", type=float, default=120, help="seconds to wait for each agent reply")
    ap.add_argument("--read-time", type=float, default=4, help="pause after each agent reply, seconds")
    ap.add_argument("--pace", type=float, default=1.0, help=">1 slower, <1 faster")
    ap.add_argument("--headed", action="store_true", help="show the browser while recording")
    ap.add_argument("--keep-demo-state", action="store_true", help="don't reset data after recording")
    args = ap.parse_args()
    if not args.message:
        args.message = ["Привіт! Дитина захворіла, не зможу завтра на 10:00. Можна перенести на інший день?"]

    names = list(SCENARIOS) if args.scenario == "all" else [args.scenario]
    for name in names:
        print(f"recording {name}…")
        print(f"  saved {record(name, args)}")


if __name__ == "__main__":
    main()
