import asyncio
import csv
import queue
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch
from lite.storage import Store, validate_url
from lite.bot import Bot

URL='https://www.facebook.com/ads/library/?active_status=active&country=ID'

class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)
        self.store=Store(self.path/'test.db');self.sid=self.store.create('Test',URL)
    def tearDown(self):self.tmp.cleanup()
    def test_exact_urls_and_two_ads_same_destination(self):
        url='https://s.shopee.co.id/AbC?payload=X%2BY#ok'
        rows=[{'adId':'123456','destinationUrl':url},{'adId':'234567','destinationUrl':url}]
        self.assertEqual(self.store.save_rows(self.sid,rows),2)
        self.assertEqual(self.store.save_rows(self.sid,rows),0)
        self.assertEqual(self.store.get(self.sid)['count'],2)
        self.assertEqual(self.store.rows(self.sid)[0]['url'],url)
    def test_export_exact_two_columns_and_quotes(self):
        url='https://example.com/Path?q=a,b&x=%22quote%22'
        self.store.save_rows(self.sid,[{'adId':'123456','destinationUrl':url}])
        out=self.path/'export.csv';self.assertEqual(self.store.export(self.sid,out),1)
        with out.open(encoding='utf-8-sig',newline='') as f:r=list(csv.reader(f))
        self.assertEqual(r,[['Destination URL','Link Iklan Aktif'],[url,'https://www.facebook.com/ads/library/?id=123456']])
    def test_pagination_and_export_all(self):
        self.store.save_rows(self.sid,[{'adId':str(100000+i),'destinationUrl':f'https://example.com/{i}'} for i in range(251)])
        self.assertEqual(len(self.store.rows(self.sid)),100)
        self.assertEqual(len(self.store.rows(self.sid,200)),51)
        self.assertEqual(self.store.export(self.sid,self.path/'all.csv'),251)
    def test_recovery_isolation_delete(self):
        other=self.store.create('Other',URL);self.store.status(self.sid,'running')
        Store(self.path/'test.db')
        self.assertEqual(self.store.get(self.sid)['status'],'stopped')
        self.store.delete(self.sid);self.assertEqual(self.store.get(other)['name'],'Other')
    def test_validate_and_reject_invalid_rows(self):
        for url in ('https://facebook.com.evil.test/ads/library/','file:///etc/passwd','https://www.facebook.com/profile'):
            with self.assertRaises(ValueError):validate_url(url)
        self.assertEqual(self.store.save_rows(self.sid,[{'adId':'oops','destinationUrl':'javascript:alert(1)'}]),0)
    def test_concurrent_transactions_no_duplicate_counts(self):
        rows=[{'adId':'123456','destinationUrl':'https://example.com/A'}]
        threads=[threading.Thread(target=self.store.save_rows,args=(self.sid,rows)) for _ in range(5)]
        for t in threads:t.start()
        for t in threads:t.join()
        self.assertEqual(self.store.get(self.sid)['count'],1)
    def test_stop_cancels_worker_and_keeps_results(self):
        events=queue.Queue();bot=Bot(self.store,events);entered=threading.Event()
        async def crawl():
            self.store.save_rows(self.sid,[{'adId':'123456','destinationUrl':'https://example.com/A'}])
            entered.set();await asyncio.sleep(1000)
        bot.crawl=crawl;bot.start(self.sid,{})
        self.assertTrue(entered.wait(3));bot.stop();bot.thread.join(3)
        self.assertFalse(bot.running);self.assertEqual(self.store.get(self.sid)['count'],1)
        self.assertEqual(self.store.get(self.sid)['status'],'stopped')
    def test_error_retries_until_stop(self):
        async def scenario():
            bot=Bot(self.store,queue.Queue());bot.sid=self.sid
            async def crawl():
                if crawl.calls==0:
                    crawl.calls+=1;raise RuntimeError('network error')
                bot.stop_requested.set()
            crawl.calls=0;bot.crawl=crawl
            with patch('lite.bot.asyncio.sleep',new_callable=AsyncMock) as wait:
                await bot.run()
                wait.assert_awaited_once_with(30)
            self.assertEqual(crawl.calls,1)
        asyncio.run(scenario())
    def test_stop_before_loop_starts(self):
        async def scenario():
            bot=Bot(self.store,queue.Queue());bot.sid=self.sid;bot.stop_requested.set();bot.crawl=AsyncMock()
            await bot.run();bot.crawl.assert_not_awaited()
        asyncio.run(scenario())
    def test_import_ui(self):
        from lite.gui import App
        self.assertTrue(callable(App))


class SummaryTests(unittest.TestCase):
    def test_timeout_skips_and_cooldown_preserves_stop(self):
        from lite.summary import summaries
        from playwright.async_api import TimeoutError
        from types import SimpleNamespace
        async def scenario():
            bad=SimpleNamespace(evaluate=AsyncMock(return_value={'key':'a','eligible':True}),click=AsyncMock(side_effect=TimeoutError('unstable')),dispose=AsyncMock())
            good=SimpleNamespace(evaluate=AsyncMock(return_value={'key':'b','eligible':True}),click=AsyncMock(),dispose=AsyncMock())
            page=SimpleNamespace(get_by_role=lambda *a,**k:SimpleNamespace(element_handles=AsyncMock(return_value=[bad,good])),is_closed=lambda:False)
            logs=[];engine=SimpleNamespace(store=SimpleNamespace(log=lambda *a:logs.append(a)))
            with patch('lite.summary.close_summary',new=AsyncMock(return_value=True)),patch('lite.summary.capture',new=AsyncMock()) as capture,patch('lite.summary.asyncio.sleep',new=AsyncMock()):
                retries={}
                self.assertTrue(await summaries(engine,'s',page,'u',retries))
                self.assertTrue(await summaries(engine,'s',page,'u',retries))
                self.assertEqual(bad.click.await_count,1);self.assertEqual(good.click.await_count,1)
                self.assertEqual(capture.await_count,1);self.assertTrue(logs)
                bad.click.side_effect=asyncio.CancelledError()
                with self.assertRaises(asyncio.CancelledError):await summaries(engine,'s',page,'u',{})
        asyncio.run(scenario())

    def test_dialog_prevents_clicks(self):
        from lite.summary import summaries
        async def scenario():
            with patch('lite.summary.close_summary',new=AsyncMock(return_value=False)):
                self.assertFalse(await summaries(None,'s',None,'u'))
        asyncio.run(scenario())

if __name__=='__main__':unittest.main()
