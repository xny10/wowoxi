import asyncio
import threading
import time
from pathlib import Path
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from .summary import summaries

LOAD_MORE=Path(__file__).with_name('load_more.js').read_text(encoding='utf-8')

EXTRACT=Path(__file__).with_name('extract_meta.js').read_text(encoding='utf-8')

class Bot:
    def __init__(self,store,events):
        self.db=store;self.events=events;self.thread=None;self.loop=None;self.task=None
        self.stop_requested=threading.Event()
        self.total_count=0;self.last_count_emit=0.0;self.last_emitted_count=0;self._last_status=None
        # Compatibility for optional summary helper logs.
        self.store=self
    def log(self,sid,message):self.emit(message)
    def emit(self,message):self.events.put(('status',self.sid,message))
    @property
    def running(self):return self.thread is not None and self.thread.is_alive()
    def start(self,sid,config):
        if self.running:raise ValueError('Stop sesi aktif terlebih dahulu.')
        self.sid=sid;self.config=config;self.stop_requested.clear()
        self.total_count=self.db.get(sid)['count'];self.last_count_emit=0.0;self.last_emitted_count=self.total_count;self._last_status=None
        self.thread=threading.Thread(target=self._thread,daemon=True);self.thread.start()
    def stop(self):
        self.stop_requested.set()
        loop,task=self.loop,self.task
        if loop and task and not loop.is_closed():
            try:loop.call_soon_threadsafe(task.cancel)
            except RuntimeError:pass
    def set_status(self,status,force=False):
        if force or status!=self._last_status:
            self.db.status(self.sid,status);self._last_status=status
    def maybe_emit_count(self,force=False):
        now=time.monotonic()
        if self.total_count!=self.last_emitted_count and (force or now-self.last_count_emit>=0.8):
            self.events.put(('count',self.sid,self.total_count))
            self.last_count_emit=now;self.last_emitted_count=self.total_count
    def _thread(self):
        try:asyncio.run(self.run())
        finally:
            self.loop=None;self.task=None
            self.maybe_emit_count(force=True)
            self.set_status('stopped',force=True);self.events.put(('done',self.sid,'Berhenti. Hasil tersimpan.'))
    async def capture(self,page):
        result=await page.evaluate(EXTRACT)
        added=self.db.save_rows(self.sid,result.get('rows',())) if result.get('rows') else 0
        result['added']=added
        if added:
            self.total_count+=added
            # Avoid flooding Tkinter/history updates during fast bursts.
            self.maybe_emit_count()
        return result
    async def run(self):
        self.loop=asyncio.get_running_loop();self.task=asyncio.current_task()
        try:
            while not self.stop_requested.is_set():
                try:
                    await self.crawl()
                except asyncio.CancelledError:raise
                except Exception as exc:
                    self.set_status('waiting')
                    self.emit(f'Kendala: {str(exc)[:300] or type(exc).__name__}. Coba lagi 30 detik; Stop tetap tersedia.')
                    await asyncio.sleep(30)
        except asyncio.CancelledError:pass
    async def crawl(self):
        url=self.db.get(self.sid)['url'];cfg=self.config
        self.set_status('running');self.emit('Membuka Firefox…')
        async with async_playwright() as p:
            browser=await p.firefox.launch(headless=cfg['headless'],timeout=30000)
            try:
                context=await asyncio.wait_for(browser.new_context(viewport={'width':1280,'height':800},locale='en-US'),30)
                if cfg['block_media']:
                    async def route(r):
                        if r.request.resource_type in ('image','media','font'):await r.abort()
                        else:await r.continue_()
                    await context.route('**/*',route)
                page=await asyncio.wait_for(context.new_page(),30)
                page.set_default_timeout(8000)
                await page.goto(url,wait_until='domcontentloaded',timeout=60000)
                await asyncio.sleep(3)
                await self.scroll_loop(page, url)
            finally:
                try:await asyncio.wait_for(browser.close(),10)
                except Exception:pass

    async def scroll_loop(self, page, url):
        """No navigation on stagnation: preserve the loaded feed until Stop."""
        cfg = self.config
        previous = None
        idle = 0
        cycle = 0
        retry_at = {}
        next_more_check = 0.0
        last_added_at = time.monotonic()
        while not self.stop_requested.is_set():
            try:
                result = await self.capture(page)
                if result.get("added", 0):
                    last_added_at = time.monotonic()
                clear = True
                if cfg['summary']:
                    clear = await summaries(self, self.sid, page, url, retry_at)
                # Compact state: never move the full list of all loaded Ad IDs to Python.
                # Fallback keeps compatibility with older mocked tests/extractors.
                generation = result.get('generation')
                if generation is None:generation=tuple(result.get('adIds',()))
                state = (round(result.get('scrollY',0),1), result.get('height',0), generation)
                idle = idle + 1 if state == previous else 0
                previous = state
                cycle += 1
                self.maybe_emit_count()
                if cycle % 5 == 1:
                    cards=result.get('totalCards',result.get('containers',0))
                    pending=result.get('pending',0)
                    suffix=f' · antrean DOM {pending}' if pending else ''
                    self.emit(f'{self.total_count} pasangan URL–iklan tersimpan · {cards} kartu unik terbaca{suffix}.')
                if not clear:
                    self.set_status('waiting')
                    if idle % 12 == 0:
                        self.emit('Menunggu dialog ditutup; posisi halaman dipertahankan.')
                    await asyncio.sleep(cfg['scroll'])
                    continue
                # Probe even while waiting; a spinner may turn into a footer button.
                now = time.monotonic()
                if now >= next_more_check:
                    clicked = await page.evaluate(LOAD_MORE)
                    if clicked is True:
                        next_more_check = now + 15
                        self.set_status('waiting')
                        self.emit('Klik See more di bawah hasil. Menunggu kartu berikutnya…')
                        await asyncio.sleep(max(2, min(cfg['scroll'], 5)))
                        continue
                if now < next_more_check:
                    self.set_status('waiting')
                    await asyncio.sleep(max(1, min(cfg['scroll'], 3)))
                    continue
                if idle >= 12:
                    self.set_status('waiting')
                    self.emit(f'Belum ada kartu baru · {int(now-last_added_at)} detik tanpa data baru. Cek See more dan pulihkan scroll tanpa reload.')
                    delay = max(1, min(cfg['refresh'], 5))
                    await asyncio.sleep(delay)
                    await page.evaluate('window.scrollBy(0, -Math.max(300, innerHeight*0.6))')
                    await asyncio.sleep(1)
                    await page.evaluate('window.scrollBy(0, Math.max(600, innerHeight*1.2))')
                else:
                    self.set_status('running')
                    await page.evaluate('window.scrollBy(0, Math.max(400,innerHeight*0.8))')
                    await asyncio.sleep(cfg['scroll'])
            except PlaywrightTimeoutError:
                self.set_status('waiting')
                self.emit('Operasi halaman timeout. Coba lagi di posisi yang sama, tanpa reload.')
                await asyncio.sleep(max(1, min(cfg['refresh'], 5)))
