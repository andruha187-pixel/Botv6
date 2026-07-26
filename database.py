import json,sqlite3,threading
from contextlib import contextmanager
from config import DB_FILE
_LOCK=threading.RLock()
def connect():
    c=sqlite3.connect(DB_FILE,timeout=60); c.row_factory=sqlite3.Row; c.execute("PRAGMA journal_mode=WAL"); c.execute("PRAGMA synchronous=NORMAL"); c.execute("PRAGMA busy_timeout=60000"); return c
@contextmanager
def tx():
    c=connect()
    try: yield c; c.commit()
    except Exception: c.rollback(); raise
    finally: c.close()
def init_database():
    with _LOCK,tx() as c:
        c.executescript("""
CREATE TABLE IF NOT EXISTS markets(condition_id TEXT PRIMARY KEY,coin TEXT,title TEXT,slug TEXT,start_timestamp INTEGER,end_timestamp INTEGER,up_token_id TEXT,down_token_id TEXT,last_seen_timestamp REAL);
CREATE TABLE IF NOT EXISTS snapshots(id INTEGER PRIMARY KEY AUTOINCREMENT,timestamp REAL,condition_id TEXT,coin TEXT,market_second REAL,reference_price REAL,reference_change_5s REAL,reference_change_20s REAL,up_bid REAL,up_ask REAL,up_spread REAL,down_bid REAL,down_ask REAL,down_spread REAL);
CREATE TABLE IF NOT EXISTS paper_trades(id INTEGER PRIMARY KEY AUTOINCREMENT,timestamp REAL,condition_id TEXT,coin TEXT,action TEXT,side TEXT,price REAL,quantity REAL,cost REAL,score REAL,reason TEXT,before_json TEXT,after_json TEXT);
CREATE TABLE IF NOT EXISTS results(condition_id TEXT PRIMARY KEY,coin TEXT,title TEXT,end_timestamp INTEGER,up_qty REAL,down_qty REAL,total_spent REAL,pnl_if_up REAL,pnl_if_down REAL,winner TEXT,realized_pnl REAL,trade_count INTEGER,guaranteed INTEGER,finalized_at REAL);
""")
def upsert_market(d,now):
    with _LOCK,tx() as c:c.execute("INSERT INTO markets VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(condition_id) DO UPDATE SET coin=excluded.coin,title=excluded.title,slug=excluded.slug,start_timestamp=excluded.start_timestamp,end_timestamp=excluded.end_timestamp,up_token_id=excluded.up_token_id,down_token_id=excluded.down_token_id,last_seen_timestamp=excluded.last_seen_timestamp",(d['condition_id'],d['coin'],d['title'],d.get('slug'),d['start_timestamp'],d['end_timestamp'],d['up_token_id'],d['down_token_id'],now))
def insert_snapshot(d):
    with _LOCK,tx() as c:c.execute("INSERT INTO snapshots(timestamp,condition_id,coin,market_second,reference_price,reference_change_5s,reference_change_20s,up_bid,up_ask,up_spread,down_bid,down_ask,down_spread) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",(d['timestamp'],d['condition_id'],d['coin'],d['market_second'],d.get('reference_price'),d.get('reference_change_5s'),d.get('reference_change_20s'),d.get('up_bid'),d.get('up_ask'),d.get('up_spread'),d.get('down_bid'),d.get('down_ask'),d.get('down_spread')))
def insert_paper_trade(d):
    with _LOCK,tx() as c:c.execute("INSERT INTO paper_trades(timestamp,condition_id,coin,action,side,price,quantity,cost,score,reason,before_json,after_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",(d['timestamp'],d['condition_id'],d['coin'],d['action'],d['side'],d['price'],d['quantity'],d['cost'],d['score'],d['reason'],json.dumps(d['before_json'],ensure_ascii=False),json.dumps(d['after_json'],ensure_ascii=False)))
def upsert_result(d):
    with _LOCK,tx() as c:c.execute("INSERT INTO results VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(condition_id) DO UPDATE SET coin=excluded.coin,title=excluded.title,end_timestamp=excluded.end_timestamp,up_qty=excluded.up_qty,down_qty=excluded.down_qty,total_spent=excluded.total_spent,pnl_if_up=excluded.pnl_if_up,pnl_if_down=excluded.pnl_if_down,winner=excluded.winner,realized_pnl=excluded.realized_pnl,trade_count=excluded.trade_count,guaranteed=excluded.guaranteed,finalized_at=excluded.finalized_at",(d['condition_id'],d['coin'],d['title'],d['end_timestamp'],d['up_qty'],d['down_qty'],d['total_spent'],d['pnl_if_up'],d['pnl_if_down'],d['winner'],d['realized_pnl'],d['trade_count'],1 if d.get('guaranteed') else 0,d['finalized_at']))
def statistics():
    with _LOCK,connect() as c:
        return {'markets':c.execute('select count(*) from markets').fetchone()[0],'snapshots':c.execute('select count(*) from snapshots').fetchone()[0],'trades':c.execute('select count(*) from paper_trades').fetchone()[0],'completed':c.execute('select count(*) from results').fetchone()[0],'realized_pnl':float(c.execute('select coalesce(sum(realized_pnl),0) from results').fetchone()[0]),'guaranteed':c.execute('select count(*) from results where guaranteed=1').fetchone()[0]}
