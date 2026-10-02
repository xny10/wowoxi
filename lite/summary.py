import asyncio
import re
import time
from playwright.async_api import Error as BrowserError, TimeoutError as BrowserTimeout

async def capture(engine,sid,page,source):
    await engine.capture(page)

def transient_click_error(error):
    return isinstance(error, BrowserTimeout) or bool(re.search(
        r'not attached|detached|not connected', str(error), re.I))


async def close_summary(page):
    """Do not click the page behind a dialog that has not closed yet."""
    dialog = page.get_by_role('dialog').first
    if not await dialog.is_visible():
        return True
    await page.keyboard.press('Escape')
    try:
        await dialog.wait_for(state='hidden', timeout=1500)
        return True
    except BrowserTimeout:
        close = dialog.get_by_role('button', name=re.compile(r'^(Close|Tutup)$', re.I)).first
        try:
            if await close.is_visible():
                await close.click(timeout=3000)
                await dialog.wait_for(state='hidden', timeout=2000)
                return True
        except BrowserError as exc:
            if not transient_click_error(exc) or page.is_closed():
                raise
    return False


async def summaries(engine, sid, page, source, retry_at=None):
    retry_at = {} if retry_at is None else retry_at
    if not await close_summary(page):
        return False
    # Element handles preserve node identity while Facebook inserts/removes cards.
    # A visible DOM element may still be far outside the viewport.
    buttons = await page.get_by_role('button', name=re.compile(
        r'^(See summary details|Lihat detail ringkasan)$', re.I)).element_handles()
    attempts = 0
    try:
        for button in buttons:
            if attempts >= 3:
                break
            try:
                info = await button.evaluate("""el => {
                    const r = el.getBoundingClientRect();
                    const eligible = el.isConnected && r.width > 0 && r.height > 0 &&
                        r.top < innerHeight && r.bottom > 0 &&
                        r.left < innerWidth && r.right > 0;
                    window.__adradarSummaryNodes ||= {ids:new WeakMap(), next:0};
                    const state = window.__adradarSummaryNodes;
                    if (!state.ids.has(el)) state.ids.set(el, ++state.next);
                    return {eligible, key:String(state.ids.get(el))};
                }""")
                key = info['key']
                if not info['eligible'] or retry_at.get(key, 0) > time.monotonic():
                    continue
                attempts += 1
                # Avoid repeatedly hitting the same unstable button every scroll.
                retry_at[key] = time.monotonic() + 30
                await button.click(timeout=4000)
                await asyncio.sleep(0.6)
                await capture(engine, sid, page, source)
                retry_at[key] = float('inf')
            except BrowserError as exc:
                if page.is_closed() or not transient_click_error(exc):
                    raise
                engine.store.log(sid, 'Tombol ringkasan belum stabil/hilang. Dilewati sementara; crawl tetap berjalan.')
            if not await close_summary(page):
                engine.store.log(sid, 'Menunggu dialog ringkasan tertutup sebelum melanjutkan scroll.')
                return False
    finally:
        for button in buttons:
            try:
                await button.dispose()
            except BrowserError:
                pass
    return True
