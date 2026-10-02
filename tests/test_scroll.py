import asyncio
import queue
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch
from playwright.async_api import TimeoutError
from lite.bot import Bot
from lite.storage import Store

class ScrollTests(unittest.IsolatedAsyncioTestCase):
    async def test_scroll_wait_timeout_and_stop(self):
        for mode in ('scroll', 'cards', 'stagnant', 'timeout'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                db = Store(Path(directory)/'test.db')
                bot = Bot(db, queue.Queue())
                bot.sid = db.create('test','https://www.facebook.com/ads/library/')
                bot.config = dict(summary=False, scroll=2, refresh=60)
                page = AsyncMock()
                rounds = 0
                delays = []
                async def capture(page):
                    nonlocal rounds
                    rounds += 1
                    if mode == 'timeout' and rounds == 1:
                        raise TimeoutError('slow')
                    return dict(containers=1, height=30000, scrollY=rounds*640 if mode=='scroll' else 29000,
                                adIds=[str(rounds) if mode=='cards' else '123456'])
                async def sleep(delay):
                    delays.append(delay)
                    if rounds >= 30:
                        bot.stop_requested.set()
                bot.capture = capture
                with patch('lite.bot.asyncio.sleep', side_effect=sleep):
                    await bot.scroll_loop(page, '')
                page.goto.assert_not_called()
                page.reload.assert_not_called()
                if mode in ('scroll', 'cards'):
                    self.assertEqual(set(delays), {2})
                else:
                    self.assertIn(5, delays)
                    self.assertLessEqual(max(delays), 5)

    async def test_cancel_wait(self):
        with tempfile.TemporaryDirectory() as directory:
            db = Store(Path(directory)/'test.db')
            bot = Bot(db, queue.Queue())
            bot.sid = db.create('test','https://www.facebook.com/ads/library/')
            bot.config = dict(summary=False, scroll=2, refresh=60)
            bot.capture = AsyncMock(return_value=dict(containers=0,height=800,scrollY=0,adIds=[]))
            entered = asyncio.Event()
            async def sleep(delay):
                if delay >= 5:
                    entered.set()
                    await asyncio.Future()
            with patch('lite.bot.asyncio.sleep', side_effect=sleep):
                task = asyncio.create_task(bot.scroll_loop(AsyncMock(), ''))
                bot.loop = asyncio.get_running_loop()
                bot.task = task
                await asyncio.wait_for(entered.wait(), 2)
                bot.stop()
                with self.assertRaises(asyncio.CancelledError):
                    await asyncio.wait_for(task, 2)

    async def test_footer_click_keeps_page_and_cooldown(self):
        with tempfile.TemporaryDirectory() as directory:
            db = Store(Path(directory)/'test.db')
            bot = Bot(db, queue.Queue())
            bot.sid = db.create('test','https://www.facebook.com/ads/library/')
            bot.config = dict(summary=False, scroll=2, refresh=60)
            bot.capture = AsyncMock(return_value=dict(height=800,scrollY=0,adIds=[]))
            page = AsyncMock()
            page.evaluate.return_value = True
            rounds = 0
            async def sleep(delay):
                nonlocal rounds
                rounds += 1
                if rounds == 4: bot.stop_requested.set()
            with patch('lite.bot.asyncio.sleep', side_effect=sleep):
                await bot.scroll_loop(page, '')
            self.assertEqual(page.evaluate.await_count, 1)
            page.goto.assert_not_called()
            page.reload.assert_not_called()
