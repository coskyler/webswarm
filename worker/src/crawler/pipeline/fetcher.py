import os
import atexit
import asyncio
import queue
import threading
import time
from concurrent.futures import Future, TimeoutError
from urllib.parse import urlparse

import httpx
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

from crawler.pipeline.types import FetchResult
from crawler.storage import get_storage

s3 = get_storage()

_PAGE_POOL = os.getenv("PAGE_POOL_SIZE")

_playwright = None
_browser = None
_context = None
_context_lock = None
_fetch_queue = queue.Queue()
_fetch_thread = None
_fetch_thread_lock = threading.Lock()
_fetch_tasks = {}
_fetch_tasks_lock = threading.Lock()
_fetch_loop = None
_STOP = object()
_STEALTH_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
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


def _is_not_found(result: FetchResult) -> bool:
    return result.message in {"Request error: 404", "Request error: 410"}


def _is_browser_crash_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return any(
        marker in message
        for marker in (
            "target page, context or browser has been closed",
            "target crashed",
            "browser has been closed",
            "browser closed",
            "context has been closed",
            "page has been closed",
        )
    )


async def _get_context():
    global _playwright, _browser, _context, _context_lock

    if _context:
        return _context

    if _context_lock is None:
        _context_lock = asyncio.Lock()

    async with _context_lock:
        if _context:
            return _context

        _playwright = await async_playwright().start()
        _browser = await _playwright.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        _context = await _browser.new_context(
            viewport={"width": 1366, "height": 768},
            locale="en-US",
            timezone_id="America/New_York",
            color_scheme="light",
        )
        await _context.add_init_script(_STEALTH_SCRIPT)
        return _context


async def _restart_browser_state():
    global _context_lock

    if _context_lock is None:
        _context_lock = asyncio.Lock()

    async with _context_lock:
        await _close_browser_state()


async def _fetch_in_browser(url: str, trace) -> FetchResult:
    attempts = 3
    status_code = None
    content_type = ""
    final_url = None
    text = None
    attempt_results = []

    for attempt in range(attempts):
        page = None
        attempt_start = time.perf_counter()
        try:
            context = await _get_context()
            page = await context.new_page()
            response = await page.goto(
                url, wait_until="domcontentloaded", timeout=20000
            )

            for selector in ("main", "article"):
                try:
                    await page.wait_for_selector(selector, timeout=3000)
                    break
                except PlaywrightTimeoutError:
                    pass
            else:
                try:
                    await page.wait_for_load_state("networkidle", timeout=2000)
                except PlaywrightTimeoutError:
                    pass
            if response is None:
                attempt_results.append({"attempt": attempt + 1, "result": "no response", "latency": round(time.perf_counter() - attempt_start, 3)})
                trace.add("fetch", ok=False, message="Operator request error", attempts=attempt_results)
                return FetchResult(ok=False, message="Operator request error")

            status_code = response.status
            final_url = page.url
            content_type = (response.headers.get("content-type") or "").lower()
            if status_code >= 500:
                raise PlaywrightError(f"Server error: {status_code}")

            text = await page.content()
            attempt_results.append(
                {
                    "attempt": attempt + 1,
                    "result": "ok",
                    "latency": round(time.perf_counter() - attempt_start, 3),
                }
            )
            break
        except (PlaywrightTimeoutError, PlaywrightError) as e:
            if _is_browser_crash_error(e):
                await _restart_browser_state()
            attempt_results.append(
                {"attempt": attempt + 1, "result": type(e).__name__, "message": str(e).split("\n", 1)[0], "latency": round(time.perf_counter() - attempt_start, 3)}
            )
            if attempt < attempts - 1:
                print(f"Retrying fetch... {e}")
                await asyncio.sleep(2 ** attempt)
            else:
                trace.add("fetch", ok=False, message="Operator request error", attempts=attempt_results)
                return FetchResult(ok=False, message="Operator request error")
        finally:
            if page:
                try:
                    await page.close()
                except PlaywrightError:
                    pass

    if status_code is None:
        trace.add("fetch", ok=False, message="Operator request error", attempts=attempt_results)
        return FetchResult(ok=False, message="Operator request error")

    if not 200 <= status_code < 300:
        trace.add("fetch", ok=False, final_url=final_url, message=f"Request error: {status_code}", attempts=attempt_results)
        return FetchResult(ok=False, message=f"Request error: {status_code}")

    if "html" not in content_type and "<html" not in text.lower():
        trace.add("fetch", ok=False, final_url=final_url, message="Non-HTML response", attempts=attempt_results)
        return FetchResult(ok=False, message="Non-HTML response")

    trace.add("fetch", ok=True, final_url=final_url, attempts=attempt_results)
    return FetchResult(ok=True, url=final_url, text=text)


async def _close_browser_state():
    global _playwright, _browser, _context, _context_lock

    try:
        if _context:
            await _context.close()
    except PlaywrightError:
        pass
    finally:
        _context = None

    if _browser:
        try:
            await _browser.close()
        except PlaywrightError:
            pass
        finally:
            _browser = None

    if _playwright:
        try:
            await _playwright.stop()
        except PlaywrightError:
            pass
        finally:
            _playwright = None

    _context_lock = None


async def _browser_loop():
    global _fetch_loop

    _fetch_loop = asyncio.get_running_loop()
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

                url, future, trace = item
                if future.cancelled():
                    _fetch_queue.task_done()
                    continue

                task = asyncio.create_task(_run_fetch(url, future, trace))
                with _fetch_tasks_lock:
                    _fetch_tasks[future] = task

                def _fetch_done(_, future=future):
                    with _fetch_tasks_lock:
                        _fetch_tasks.pop(future, None)
                    _fetch_queue.task_done()

                task.add_done_callback(_fetch_done)
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


async def _run_fetch(url: str, future: Future, trace):
    try:
        result = await _fetch_in_browser(url, trace)
        if not future.cancelled():
            future.set_result(result)
    except BaseException as exc:
        if not future.cancelled():
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


def fetch(url: str, trace) -> FetchResult:
    if not url or not _is_valid_url(url):
        trace.add("fetch", ok=False, message="Invalid URL")
        return FetchResult(ok=False, message="Invalid URL")

    if _is_social_url(url):
        trace.add("fetch", ok=False, message="Social URL")
        return FetchResult(ok=False, message="Social URL")
    
    cached = s3.get(url)

    if cached:
        trace.add("fetch", ok=cached.ok, message="Found in S3")
        return cached

    _ensure_browser_thread()
    future = Future()
    _fetch_queue.put((url, future, trace))
    try:
        result = future.result(timeout=90)
    except TimeoutError:
        future.cancel()
        with _fetch_tasks_lock:
            task = _fetch_tasks.get(future)
        if task and _fetch_loop:
            _fetch_loop.call_soon_threadsafe(task.cancel)
        trace.add("fetch", ok=False, message="Fetch timed out")
        return FetchResult(ok=False, message="Fetch timed out")
    if result.ok or _is_not_found(result):
        s3.put(url, result)
        return result

    stealth_result = _stealth_fetch(url, trace)

    s3.put(url, stealth_result)
    return stealth_result


def _stealth_fetch(url: str, trace) -> FetchResult:
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
    attempt_results = []
    for attempt in range(2):
        attempt_start = time.perf_counter()
        try:
            response = httpx.post(
                "https://api.brightdata.com/request",
                json=data,
                headers=headers,
                timeout=30,
            )
            attempt_results.append(
                {
                    "attempt": attempt + 1,
                    "result": "response",
                    "latency": round(time.perf_counter() - attempt_start, 3),
                }
            )
            break
        except httpx.RequestError as e:
            attempt_results.append(
                {"attempt": attempt + 1, "result": type(e).__name__, "message": str(e).split("\n", 1)[0], "latency": round(time.perf_counter() - attempt_start, 3)}
            )
            if attempt == 0:
                time.sleep(2)

    if response is None:
        trace.add("stealth_fetch", ok=False, message="Operator request error", attempts=attempt_results)
        return FetchResult(ok=False, message="Operator request error", used_stealth=True)

    if not response.is_success:
        trace.add("stealth_fetch", ok=False, message=f"Request error: {response.status_code}", attempts=attempt_results)
        return FetchResult(ok=False, message=f"Request error: {response.status_code}", used_stealth=True)

    content_type = (response.headers.get("content-type") or "").lower()
    text = response.text
    if "html" not in content_type and "<html" not in text.lower():
        trace.add("stealth_fetch", ok=False, message="Non-HTML response", attempts=attempt_results)
        return FetchResult(ok=False, message="Non-HTML response", used_stealth=True)

    trace.add("stealth_fetch", ok=True, attempts=attempt_results)
    return FetchResult(ok=True, url=url, text=text, used_stealth=True)
