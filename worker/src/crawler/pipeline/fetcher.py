import os
import atexit
import asyncio
import queue
import threading
import time
from concurrent.futures import Future
from pathlib import Path
from urllib.parse import urlparse

import httpx
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

from crawler.pipeline.types import FetchResult

_PAGE_POOL = 5

_playwright = None
_context = None
_fetch_queue = queue.Queue()
_fetch_thread = None
_fetch_thread_lock = threading.Lock()
_STOP = object()
_PROFILE_DIR = Path(".chromium-profile")
_STEALTH_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });
Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });
Object.defineProperty(navigator, 'maxTouchPoints', { get: () => 0 });
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
window.chrome = window.chrome || { runtime: {} };
"""


_SOCIAL_ORIGINS = {
    "facebook.com",
    "instagram.com",
    "tripadvisor.com",
    "booking.com",
    "expedia.com",
    "viator.com",
    "getyourguide.com",
    "airbnb.com",
    "klook.com",
    "yelp.com",
    "google.com",
    "business.google.com",
    "toursbylocals.com",
    "peek.com",
    "fareharbor.com",
    "tiqets.com",
    "withlocals.com",
    "tripaneer.com",
    "eventbrite.com",
    "meetup.com",
    "showaround.com",
    "whatsapp.com",
    "messenger.com",
    "telegram.org",
    "wechat.com",
    "line.me",
    "tiktok.com",
    "x.com",
    "linkedin.com",
    "reddit.com",
    "youtube.com",
    "pinterest.com",
}


def _is_social_url(url: str) -> bool:
    for u in _SOCIAL_ORIGINS:
        if u in url:
            return True

    return False


def _is_valid_url(url: str) -> bool:
    p = urlparse(url)
    return p.scheme in ("http", "https") and bool(p.netloc) and "." in p.netloc


async def _get_context():
    global _playwright, _context

    if _context:
        return _context

    _playwright = await async_playwright().start()
    _context = await _playwright.chromium.launch_persistent_context(
        user_data_dir=_PROFILE_DIR,
        headless=True,
        viewport={"width": 1366, "height": 768},
        screen={"width": 1366, "height": 768},
        locale="en-US",
        timezone_id="America/New_York",
        color_scheme="light",
        device_scale_factor=1,
        args=["--disable-blink-features=AutomationControlled"],
    )
    await _context.add_init_script(_STEALTH_SCRIPT)
    return _context


async def _fetch_in_browser(url: str) -> FetchResult:
    attempts = 3
    status_code = None
    content_type = ""
    final_url = None
    text = None

    for attempt in range(attempts):
        page = None
        try:
            context = await _get_context()
            page = await context.new_page()
            response = await page.goto(
                url, wait_until="domcontentloaded", timeout=20000
            )
            if response is None:
                return FetchResult(ok=False, message="Operator request error")

            status_code = response.status
            final_url = page.url
            content_type = (response.headers.get("content-type") or "").lower()
            if status_code >= 500:
                raise PlaywrightError(f"Server error: {status_code}")

            text = await page.content()
            break
        except (PlaywrightTimeoutError, PlaywrightError) as e:
            if attempt < attempts - 1:
                print(f"Retrying fetch... {e}")
                await asyncio.sleep(2 ** attempt)
            else:
                return FetchResult(ok=False, message="Operator request error")
        finally:
            if page:
                try:
                    await page.close()
                except PlaywrightError:
                    pass

    if status_code is None:
        return FetchResult(ok=False, message="Operator request error")

    if not 200 <= status_code < 300:
        return FetchResult(ok=False, message=f"Request error: {status_code}")

    if "html" not in content_type and "<html" not in text.lower():
        return FetchResult(ok=False, message="Non-HTML response")

    return FetchResult(ok=True, url=final_url, text=text)


async def _close_browser_state():
    global _playwright, _context

    try:
        if _context:
            await _context.close()
    except PlaywrightError:
        pass
    finally:
        _context = None

    if _playwright:
        try:
            await _playwright.stop()
        except PlaywrightError:
            pass
        finally:
            _playwright = None


async def _browser_loop():
    tasks = set()
    try:
        while True:
            while len(tasks) < _PAGE_POOL:
                try:
                    item = _fetch_queue.get_nowait()
                except queue.Empty:
                    break

                if item is _STOP:
                    _fetch_queue.task_done()
                    return

                url, future = item
                task = asyncio.create_task(_run_fetch(url, future))
                task.add_done_callback(lambda _: _fetch_queue.task_done())
                tasks.add(task)

            if tasks:
                done, tasks = await asyncio.wait(
                    tasks, timeout=0.05, return_when=asyncio.FIRST_COMPLETED
                )
            else:
                await asyncio.sleep(0.05)
    finally:
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        await _close_browser_state()


async def _run_fetch(url: str, future: Future):
    try:
        future.set_result(await _fetch_in_browser(url))
    except BaseException as exc:
        future.set_exception(exc)


def _run_browser_loop():
    asyncio.run(_browser_loop())


def _ensure_browser_thread():
    global _fetch_thread

    with _fetch_thread_lock:
        if _fetch_thread and _fetch_thread.is_alive():
            return

        _fetch_thread = threading.Thread(
            target=_run_browser_loop,
            name="fetch-browser",
            daemon=True,
        )
        _fetch_thread.start()


def shutdown_browser():
    if _fetch_thread and _fetch_thread.is_alive():
        _fetch_queue.put(_STOP)


atexit.register(shutdown_browser)


def fetch(url: str) -> FetchResult:
    if not url or not _is_valid_url(url):
        return FetchResult(ok=False, message="Invalid URL")

    if _is_social_url(url):
        return FetchResult(ok=False, message="Social URL")

    _ensure_browser_thread()
    future = Future()
    _fetch_queue.put((url, future))
    return future.result()

def stealth_fetch(url: str) -> FetchResult:
    if not url or not _is_valid_url(url):
        return FetchResult(ok=False, message="Invalid URL")

    if _is_social_url(url):
        return FetchResult(ok=False, message="Social URL")

    headers = {
        "Authorization": f"Bearer {os.environ['BRIGHTDATA_FETCH_API_KEY']}",
        "Content-Type": "application/json",
    }
    data = {
        "zone": "webswarm_fetch",
        "url": url,
        "format": "raw",
    }

    response = None
    for attempt in range(2):
        try:
            response = httpx.post(
                "https://api.brightdata.com/request",
                json=data,
                headers=headers,
                timeout=30,
            )
            break
        except httpx.RequestError:
            if attempt == 0:
                time.sleep(2)

    if response is None:
        return FetchResult(ok=False, message="Operator request error")

    if not response.is_success:
        return FetchResult(ok=False, message=f"Request error: {response.status_code}")

    content_type = (response.headers.get("content-type") or "").lower()
    text = response.text
    if "html" not in content_type and "<html" not in text.lower():
        return FetchResult(ok=False, message="Non-HTML response")

    return FetchResult(ok=True, url=url, text=text)
