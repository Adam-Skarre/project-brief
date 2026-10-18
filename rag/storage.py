import json,sqlite3,time,math
from pathlib import Path
from contextlib import contextmanager

class Store:
    def __init__(self,path):
        self.path=str(path);Path(path).parent.mkdir(parents=True,exist_ok=True)
        with self.connect() as db:
            db.executescript('''
CREATE TABLE IF NOT EXISTS indices (id TEXT PRIMARY KEY, payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, payload TEXT NOT NULL, expires REAL NOT NULL);
CREATE TABLE IF NOT EXISTS charges (at REAL NOT NULL, kind TEXT NOT NULL, amount REAL NOT NULL);
CREATE TABLE IF NOT EXISTS traces (id TEXT PRIMARY KEY, payload TEXT NOT NULL);
''')
    @contextmanager
    def connect(self):
        db=sqlite3.connect(self.path,timeout=30)
        try:
            with db:yield db
        finally:db.close()
    def put_index(self,id,payload):
        with self.connect() as db:db.execute('INSERT OR REPLACE INTO indices VALUES (?,?)',(id,json.dumps(payload)))
    def get_index(self,id):
        with self.connect() as db:r=db.execute('SELECT payload FROM indices WHERE id=?',(id,)).fetchone()
        if not r:raise ValueError('Index not found; ingest documents first')
        return json.loads(r[0])
    def cache_get(self,key):
        with self.connect() as db:r=db.execute('SELECT payload FROM cache WHERE key=? AND expires>?',(key,time.time())).fetchone()
        return json.loads(r[0]) if r else None
    def cache_put(self,key,value):
        with self.connect() as db:
            db.execute('DELETE FROM cache WHERE expires<?',(time.time(),))
            db.execute('INSERT OR REPLACE INTO cache VALUES (?,?,?)',(key,json.dumps(value),time.time()+3600))
    def reserve(self,amount,kind,daily_cap):
        # Reserve before a request. Failed requests keep their reservation conservatively.
        if not math.isfinite(amount) or amount<=0 or not math.isfinite(daily_cap) or daily_cap<=0:raise ValueError('Configure positive finite cost reservations and daily cap')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            spent=db.execute('SELECT COALESCE(SUM(amount),0) FROM charges WHERE at>?',(time.time()-86400,)).fetchone()[0]
            if spent+amount>daily_cap:raise ValueError('Rolling 24-hour request budget exhausted')
            db.execute('INSERT INTO charges VALUES (?,?,?)',(time.time(),kind,amount))
        return amount
    def trace(self,id,payload):
        with self.connect() as db:db.execute('INSERT OR REPLACE INTO traces VALUES (?,?)',(id,json.dumps(payload)))
