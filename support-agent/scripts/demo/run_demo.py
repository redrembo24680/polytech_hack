#!/usr/bin/env python3
"""Автозапис демо у реальному браузері (Playwright): по відео на сцену для клієнта і для copilot.

Потрібні запущені: сайт (docker, :3000/:8001) і агент (:8000). Див. README, "Автозапис демо (Playwright)".
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import Page, TimeoutError as PWTimeout, sync_playwright

SIZE = {"width": 1280, "height": 800}
REPLY_TIMEOUT = 120_000
BUBBLE = "div.whitespace-pre-wrap.rounded-bl-md"  # бульбашка агента/адміна на сайті
SICK = "Дитина захворіла, не встигну завтра на 10, можна щось зробити?"
SLANG = "блін, дитина захворіла, не встигаю завтра, можна переставити?"

SCENES = {
    "Q": dict(tenant="dentaplus", client="petro", name="Петро", phone="380671234504",
              msg="Добрий день! Скільки коштує консультація і яка у вас адреса?"),
    "A": dict(tenant="lumen", client="olena", name="Олена", phone="380671234501",
              msg="блін, дитина захворіла, не встигаю завтра на 10, можна переставити?"),
    "B": dict(tenant="lumen", client="max", name="Максим", phone="380501234502",
              msg="Дитина захворіла, не встигну завтра на 10, чи можна переставити без втрати передоплати?"),
    "C": dict(tenant="dentaplus", client="petro", name="Петро", phone="380671234504",
              msg="Хочу скасувати запис і повернути гроші."),
}


class DemoError(Exception):
    pass


def log(msg: str) -> None:
    print(msg, flush=True)


def post(url: str) -> None:
    req = urllib.request.Request(url, method="POST", data=b"")
    urllib.request.urlopen(req, timeout=30).read()


def place(page: Page, x: int, w: int = 760, h: int = 880) -> None:
    """Розставити вікна поруч (лише headed, best effort через CDP)."""
    try:
        cdp = page.context.new_cdp_session(page)
        wid = cdp.send("Browser.getWindowForTarget")["windowId"]
        cdp.send("Browser.setWindowBounds", {"windowId": wid, "bounds": {"left": x, "top": 20, "width": w, "height": h}})
    except Exception:
        pass


def agent_count(page: Page) -> int:
    return page.locator(BUBBLE).count()


def type_human(page: Page, locator, text: str) -> None:
    locator.click()
    page.keyboard.type(text, delay=35)
    page.wait_for_timeout(400)


def send_message(page: Page, text: str) -> int:
    """Надрукувати і надіслати; повертає кількість бульбашок агента ДО відправки."""
    base = agent_count(page)
    box = page.locator("textarea[aria-label='Повідомлення']")
    type_human(page, box, text)
    page.get_by_role("button", name="Надіслати").click()
    return base


def last_bubbles(page: Page, n: int = 2) -> list[str]:
    try:
        texts = page.locator(BUBBLE).all_inner_texts()
    except Exception:
        return []
    return texts[-n:]


def wait_reply(page: Page, base: int, what: str = "відповідь агента", timeout: int = REPLY_TIMEOUT,
               contains: str | None = None) -> str:
    try:
        page.wait_for_function(
            """([sel, n, sub]) => { const b = [...document.querySelectorAll(sel)];
                if (b.length <= n) return false;
                return !sub || b.slice(n).some(e => e.innerText.toLowerCase().includes(sub)); }""",
            arg=[BUBBLE, base, contains], timeout=timeout)
    except PWTimeout:
        raise DemoError(f"Не дочекались: {what} (таймаут {timeout // 1000} с); "
                        f"останні бульбашки агента: {last_bubbles(page)}") from None
    page.wait_for_timeout(2500)  # агент може надіслати кілька бульбашок поспіль
    last = page.locator(BUBBLE).last.inner_text()
    page.wait_for_timeout(3000)  # час прочитати
    return last


def open_customer(page: Page, site: str, sc: dict) -> None:
    page.goto(f"{site}/b/{sc['tenant']}/support")
    page.evaluate("localStorage.clear()")
    page.reload()
    try:
        page.get_by_label("Ім'я").fill("")
        type_human(page, page.get_by_label("Ім'я"), sc["name"])
        type_human(page, page.get_by_label("Телефон"), sc["phone"])
        page.get_by_role("button", name="Почати чат").click()
        page.locator("textarea[aria-label='Повідомлення']").wait_for(timeout=15_000)
    except PWTimeout:
        raise DemoError("Не вдалося відкрити чат підтримки на сайті (форма імені/телефону)") from None


def open_copilot(page: Page, agent: str, sc: dict) -> None:
    page.goto(agent + "/")
    try:
        page.wait_for_function("document.querySelectorAll('#tenant option').length > 1", timeout=15_000)
        page.select_option("#tenant", sc["tenant"])
        page.wait_for_function(
            "(c) => [...document.querySelectorAll('#client option')].some(o => o.value === c)", arg=sc["client"],
            timeout=15_000)
        page.select_option("#client", sc["client"])
        page.wait_for_timeout(1500)
    except PWTimeout:
        raise DemoError("Copilot не завантажився: перевірте, що агент запущено на --agent") from None


def attach_copilot(cop: Page, cust: Page, sc: dict) -> None:
    """Copilot слідкує за сесією чату сайту (ключ chat:{tenant}:{conversation_id})."""
    conv = cust.evaluate(
        "(t) => { const r = localStorage.getItem('support:' + t); return r ? JSON.parse(r).conversationId : null }",
        sc["tenant"])
    if not conv:
        raise DemoError("Не знайшли id розмови на сайті (localStorage)")
    key = f"chat:{sc['tenant']}:{conv}"
    cop.evaluate(
        """(k) => { clearInterval(state.eventTimer); document.getElementById('chat').textContent='';
        document.getElementById('feed').textContent=''; state.seen.clear(); state.last=0; state.sid=k;
        document.getElementById('session-id').textContent='розмова сайту';
        state.eventTimer=setInterval(pollEvents, 700); }""", key)


def approve(cop: Page, tool: str | None, note: str | None, cust: Page | None = None) -> int:
    """Повертає кількість бульбашок агента на сайті безпосередньо ПЕРЕД кліком апруву."""
    sel = ".approval" if tool is None else f".approval:has(b:text-is('{tool}'))"
    card = cop.locator(sel).first
    try:
        card.wait_for(timeout=REPLY_TIMEOUT)
    except PWTimeout:
        raise DemoError(f"Не з'явилась картка апруву {tool or ''}") from None
    cop.wait_for_timeout(3000)  # показати картку
    if note:
        type_human(cop, card.locator("input"), note)
    base = agent_count(cust) if cust is not None else 0
    card.locator("button.ok").click()
    cop.wait_for_timeout(2500)
    return base


def run_scene(scene: str, args, browser) -> None:
    sc = dict(SCENES[scene])
    if scene == "A" and args.slang:
        sc["msg"] = SLANG
    out = Path(args.video_dir)
    out.mkdir(parents=True, exist_ok=True)
    cust_ctx = cop_ctx = None
    try:
        if not args.no_reset:
            post(args.site_api + "/api/admin/reset")
            time.sleep(2)
        opts = dict(record_video_dir=str(out / ".tmp"), record_video_size=SIZE, viewport=SIZE, locale="uk-UA")
        cust_ctx = browser.new_context(**opts)
        cop_ctx = browser.new_context(**opts)
        cust, cop = cust_ctx.new_page(), cop_ctx.new_page()
        if args.headed:
            place(cust, 0)
            place(cop, 780)
        try:
            open_copilot(cop, args.agent, sc)
            open_customer(cust, args.site, sc)
            base = send_message(cust, sc["msg"])
            deadline = time.time() + 30
            while True:  # сесія агента з'являється після першого повідомлення
                try:
                    attach_copilot(cop, cust, sc)
                    break
                except DemoError:
                    if time.time() > deadline:
                        raise
                    time.sleep(1)
            wait_reply(cust, base)
            if scene == "A":
                base = agent_count(cust)
                base = send_message(cust, "1")
                wait_reply(cust, base, "підтвердження перенесення")
            elif scene == "B":
                base = approve(cop, "apply_goodwill_exception", "ок, один раз", cust)
                wait_reply(cust, base, "повідомлення агента після апруву")
            elif scene == "C":
                base = approve(cop, "refund_prepayment", None, cust)
                wait_reply(cust, base, "повідомлення агента після апруву повернення")
                base = approve(cop, "cancel_booking", None, cust)
                wait_reply(cust, base, "фінальне підтвердження скасування", contains="скасован")
            log(f"[{scene}] сцену записано")
        except Exception as e:
            msg = str(e) if isinstance(e, DemoError) else f"{type(e).__name__}: {e}"
            log(f"[{scene}] ПОМИЛКА: {msg}")
            try:
                cust.screenshot(path=str(out / f"{scene}-error.png"))
                cop.screenshot(path=str(out / f"{scene}-error-copilot.png"))
            except Exception:
                pass
    finally:
        paths = {}
        for name, ctx in (("customer", cust_ctx), ("copilot", cop_ctx)):
            if ctx is None:
                continue
            vids = [p.video for p in ctx.pages if p.video]
            ctx.close()  # фіналізує .webm
            for v in vids:
                paths[name] = Path(v.path())
        for name, src in paths.items():
            dst = out / f"{scene}-{name}.webm"
            shutil.move(str(src), dst)
            log(f"    {dst}")
            if args.mp4:
                mp4 = dst.with_suffix(".mp4")
                subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(dst), str(mp4)], check=False)
                log(f"    {mp4}")
        shutil.rmtree(out / ".tmp", ignore_errors=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--scene", default="ALL", choices=["A", "B", "C", "Q", "ALL"])
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--headed", dest="headed", action="store_true", default=True)
    g.add_argument("--headless", dest="headed", action="store_false")
    ap.add_argument("--video-dir", default="demo-videos")
    ap.add_argument("--site", default="http://localhost:3000")
    ap.add_argument("--site-api", default="http://localhost:8001")
    ap.add_argument("--agent", default="http://localhost:8000")
    ap.add_argument("--no-reset", action="store_true")
    ap.add_argument("--slang", action="store_true", help="сцена A: розмовна фраза")
    ap.add_argument("--mp4", action="store_true", help="конвертувати у mp4 (потрібен ffmpeg)")
    args = ap.parse_args()
    if args.mp4 and not shutil.which("ffmpeg"):
        log("ffmpeg не знайдено, --mp4 ігнорується")
        args.mp4 = False
    scenes = ["Q", "A", "B", "C"] if args.scene == "ALL" else [args.scene]
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=not args.headed, slow_mo=250)
        try:
            for s in scenes:
                run_scene(s, args, browser)
        finally:
            browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
