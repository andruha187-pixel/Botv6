import json,logging,threading,time
from collections import deque
from datetime import datetime
import requests,websocket
from config import BINANCE_WS_URL,CLOB_API_URL,GAMMA_API_URL,HTTP_TIMEOUT
from models import BookSide,Market
logger=logging.getLogger('FEEDS'); _STOP=threading.Event(); _LOCK=threading.RLock(); _LATEST={}; _HISTORY={'BTC':deque(maxlen=5000),'ETH':deque(maxlen=5000)}; HTTP=requests.Session()
def dl(v):
    if isinstance(v,list): return v
    if isinstance(v,str):
        try:
            p=json.loads(v); return p if isinstance(p,list) else []
        except: return []
    return []
def ts(v):
    if isinstance(v,(int,float)): return int(v)
    if not isinstance(v,str): return None
    try:return int(datetime.fromisoformat(v.replace('Z','+00:00')).timestamp())
    except:return None
def coin(*v):
    t=' '.join(str(x or '') for x in v).lower()
    return 'BTC' if ('bitcoin' in t or 'btc' in t) else 'ETH' if ('ethereum' in t or 'eth' in t) else None
def st(slug):
    try:return int(str(slug).rstrip('/').split('-')[-1])
    except:return None
def parse(raw,event):
    cid=raw.get('conditionId') or raw.get('condition_id'); title=raw.get('question') or raw.get('title') or event.get('title') or 'Unknown'; slug=raw.get('slug') or event.get('slug'); c=coin(title,slug)
    if not cid or c not in {'BTC','ETH'}: return None
    outcomes=[str(x).strip().upper() for x in dl(raw.get('outcomes'))]; tokens=[str(x) for x in dl(raw.get('clobTokenIds'))]
    if len(tokens)<2:return None
    up=down=None
    for i,o in enumerate(outcomes):
        if i>=len(tokens):break
        if o in {'UP','YES'}:up=tokens[i]
        elif o in {'DOWN','NO'}:down=tokens[i]
    up=up or tokens[0]; down=down or tokens[1]; start=st(slug) or ts(raw.get('startDate')) or ts(event.get('startDate')); end=(start+300) if st(slug) else ts(raw.get('endDate')) or ts(event.get('endDate'))
    if not start or not end:return None
    return Market(str(cid),c,str(title),str(slug) if slug else None,int(start),int(end),str(up),str(down))
def event(slug):
    for url,params in ((f'{GAMMA_API_URL}/events/slug/{slug}',None),(f'{GAMMA_API_URL}/events',{'slug':slug})):
        try:
            r=HTTP.get(url,params=params,timeout=HTTP_TIMEOUT)
            if r.status_code==404:continue
            r.raise_for_status(); p=r.json()
            if isinstance(p,dict):return p
            if isinstance(p,list) and p:return p[0]
        except:pass
    return None
def discover_current_markets():
    now=int(time.time()); current=(now//300)*300; found={}
    for c,prefix in {'BTC':'btc-updown-5m','ETH':'eth-updown-5m'}.items():
        candidates=[]
        for start in (current,current+300,current-300):
            e=event(f'{prefix}-{start}')
            if not e:continue
            for raw in e.get('markets',[]):
                m=parse(raw,e) if isinstance(raw,dict) else None
                if m:candidates.append(m);break
        if candidates:
            active=[m for m in candidates if m.start_timestamp-5<=now<=m.end_timestamp+5]; found[c]=min(active or candidates,key=lambda m:abs(now-m.start_timestamp))
    return found
def fetch_books(markets):
    token_map={}; payload=[]
    for m in markets:
        token_map[m.up_token_id]=(m.condition_id,'UP'); token_map[m.down_token_id]=(m.condition_id,'DOWN'); payload += [{'token_id':m.up_token_id},{'token_id':m.down_token_id}]
    if not payload:return {}
    r=HTTP.post(f'{CLOB_API_URL}/books',json=payload,timeout=HTTP_TIMEOUT); r.raise_for_status(); result={}
    for b in r.json():
        tid=str(b.get('asset_id') or ''); mapped=token_map.get(tid)
        if not mapped:continue
        bids=[];asks=[]
        for x in b.get('bids',[]):
            try:bids.append((float(x['price']),float(x['size'])))
            except:pass
        for x in b.get('asks',[]):
            try:asks.append((float(x['price']),float(x['size'])))
            except:pass
        bb=max((p for p,_ in bids),default=None); ba=min((p for p,_ in asks),default=None); cid,side=mapped
        min_order_size = float(b.get("min_order_size") or 1.0)
        tick_size = float(b.get("tick_size") or 0.01)
        result.setdefault(cid, {})[side] = BookSide(
            bid=bb,
            ask=ba,
            bid_size=next((s for p, s in bids if p == bb), None),
            ask_size=next((s for p, s in asks if p == ba), None),
            spread=(ba - bb) if bb is not None and ba is not None else None,
            min_order_size=min_order_size,
            tick_size=tick_size,
        )
    return result
def latest_reference(c):
    with _LOCK:
        i=_LATEST.get(c); return i[1] if i else None
def reference_change(c,seconds):
    with _LOCK: latest=_LATEST.get(c); hist=list(_HISTORY.get(c,[]))
    if not latest or not hist:return None
    old=min(hist,key=lambda i:abs(i[0]-(latest[0]-seconds))); return latest[1]-old[1]
def on_message(ws,msg):
    try:
        p=json.loads(msg); d=p.get('data') or p; s=str(d.get('s') or ''); c='BTC' if s=='BTCUSDT' else 'ETH' if s=='ETHUSDT' else None
        if not c:return
        t=float(d.get('T') or d.get('E') or int(time.time()*1000))/1000; price=float(d['p'])
        with _LOCK:_LATEST[c]=(t,price);_HISTORY[c].append((t,price))
    except:logger.exception('Binance message processing failed')
def loop():
    while not _STOP.is_set():
        try:websocket.WebSocketApp(BINANCE_WS_URL,on_message=on_message).run_forever(ping_interval=20,ping_timeout=10)
        except:logger.exception('Binance websocket failed')
        _STOP.wait(5)
def start_binance():_STOP.clear();t=threading.Thread(target=loop,daemon=True);t.start();return t
def stop():_STOP.set()
