import csv
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime, timezone
from urllib.parse import urlsplit


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def validate_url(value):
    u = urlsplit(value.strip())
    host = u.hostname or ''
    if u.scheme != 'https' or u.username or u.password or not (host == 'facebook.com' or host.endswith('.facebook.com')) or u.path.rstrip('/') != '/ads/library':
        raise ValueError('Gunakan URL https://www.facebook.com/ads/library/ lengkap dengan filter pencarian.')
    return value.strip()


class Store:
    def __init__(self, path):
        self.path = str(path)
        with closing(self.connect()) as c, c:
            c.executescript('''PRAGMA journal_mode=WAL;
            PRAGMA synchronous=NORMAL;
            CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY,name TEXT,url TEXT,created TEXT,status TEXT,count INTEGER DEFAULT 0);
            CREATE TABLE IF NOT EXISTS ads(id INTEGER PRIMARY KEY,session_id TEXT REFERENCES sessions(id) ON DELETE CASCADE,ad_id TEXT,url TEXT,seen TEXT,UNIQUE(session_id,ad_id,url));
            CREATE INDEX IF NOT EXISTS idx_ads_session_row ON ads(session_id,id);
            ''')
            c.execute("UPDATE sessions SET status='stopped' WHERE status IN ('running','waiting')")

    def connect(self):
        c = sqlite3.connect(self.path, timeout=15)
        c.row_factory = sqlite3.Row
        c.execute('PRAGMA foreign_keys=ON')
        c.execute('PRAGMA synchronous=NORMAL')
        c.execute('PRAGMA temp_store=MEMORY')
        c.execute('PRAGMA busy_timeout=15000')
        return c

    def create(self, name, url):
        url = validate_url(url)
        sid = uuid.uuid4().hex
        with closing(self.connect()) as c, c:
            c.execute('INSERT INTO sessions VALUES(?,?,?,?,?,0)', (sid,name or now(),url,now(),'stopped'))
        return sid

    def get(self, sid):
        with closing(self.connect()) as c:
            r=c.execute('SELECT * FROM sessions WHERE id=?',(sid,)).fetchone()
            if not r:raise ValueError('Sesi tidak ditemukan.')
            return dict(r)

    def history(self, offset=0):
        with closing(self.connect()) as c:
            return [dict(r) for r in c.execute('SELECT * FROM sessions ORDER BY created DESC,rowid DESC LIMIT 100 OFFSET ?',(offset,))]

    def status(self, sid, status):
        with closing(self.connect()) as c,c:
            c.execute('UPDATE sessions SET status=? WHERE id=? AND status<>?',(status,sid,status))

    def save_rows(self,sid,rows):
        valid=[];batch_seen=set();stamp=now()
        for row in rows:
            ident=str(row.get('adId',''));url=row.get('destinationUrl','')
            try:
                u=urlsplit(url)
                if not ident.isdigit() or not 6<=len(ident)<=20 or u.scheme not in ('http','https') or not u.hostname or u.username or u.password:continue
            except ValueError:continue
            key=(ident,url)
            if key in batch_seen:continue
            batch_seen.add(key);valid.append((sid,ident,url,stamp))
        if not valid:return 0
        with closing(self.connect()) as c,c:
            before=c.total_changes
            c.executemany('INSERT OR IGNORE INTO ads(session_id,ad_id,url,seen) VALUES(?,?,?,?)',valid)
            added=c.total_changes-before
            if added:c.execute('UPDATE sessions SET count=count+? WHERE id=?',(added,sid))
        return added

    def rows(self,sid,offset=0):
        with closing(self.connect()) as c:
            return [dict(r) for r in c.execute('SELECT ad_id,url FROM ads WHERE session_id=? ORDER BY id LIMIT 100 OFFSET ?',(sid,offset))]

    def export(self,sid,path):
        # Snapshot read with bounded memory; crawl can continue writing under WAL.
        with closing(self.connect()) as c, open(path,'w',encoding='utf-8-sig',newline='') as f:
            cursor=c.execute('SELECT url,ad_id FROM ads WHERE session_id=? ORDER BY id',(sid,))
            writer=csv.writer(f);writer.writerow(['Destination URL','Link Iklan Aktif'])
            count=0
            while rows:=cursor.fetchmany(1000):
                writer.writerows((r['url'],'https://www.facebook.com/ads/library/?id='+r['ad_id']) for r in rows)
                count+=len(rows)
        return count

    def delete(self,sid):
        with closing(self.connect()) as c,c:
            c.execute('DELETE FROM sessions WHERE id=?',(sid,))
