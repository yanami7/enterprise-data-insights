import csv
import hashlib
import io
import json
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
import sqlite3
from contextlib import contextmanager

COLUMNS = ('order_id','date','region','channel','product','status','quantity','unit_price')
ROOT = Path(__file__).resolve().parents[1]


def clean(text: str) -> tuple[list[dict],list[dict]]:
    reader=csv.DictReader(io.StringIO(text.lstrip('\ufeff')))
    if reader.fieldnames != list(COLUMNS):
        raise ValueError('CSV表头应为 '+','.join(COLUMNS))
    valid, rejected, seen = [], [], set()
    for number,row in enumerate(reader,2):
        reason=''
        try:
            if None in row or any(v is None for v in row.values()): raise ValueError('字段数量不一致')
            row={k:v.strip() for k,v in row.items()}
            if not all(row.values()): raise ValueError('缺少必填字段')
            try: date.fromisoformat(row['date'])
            except ValueError: raise ValueError('日期无效')
            if len(row['date'])!=10: raise ValueError('日期格式须为YYYY-MM-DD')
            if row['status'] not in ('completed','cancelled','refunded'): raise ValueError('订单状态无效')
            try: qty=int(row['quantity'])
            except ValueError: raise ValueError('数量须为整数')
            price=Decimal(row['unit_price'])
            if qty<=0 or qty>100000: raise ValueError('数量须为1至100000的整数')
            if not price.is_finite() or price<0 or price>10000000: raise ValueError('单价无效')
            if price != price.quantize(Decimal('.01')): raise ValueError('单价最多两位小数')
            if any(len(row[k])>100 for k in ('order_id','region','channel','product')): raise ValueError('文本字段过长')
            if row['order_id'] in seen: raise ValueError('订单编号重复')
            seen.add(row['order_id'])
            valid.append({**row,'quantity':qty,'unit_price_cents':int(price*100),'amount_cents':int(price*100)*qty})
        except (ValueError,InvalidOperation) as error:
            reason='金额格式无效' if isinstance(error,InvalidOperation) else str(error)
        if reason: rejected.append({'line':number,'reason':reason,'raw':row})
    if not valid and not rejected: raise ValueError('CSV中没有数据')
    return valid,rejected


@contextmanager
def connect(path: Path):
    path.parent.mkdir(parents=True,exist_ok=True)
    conn=sqlite3.connect(path)
    conn.row_factory=sqlite3.Row
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS batches(id TEXT PRIMARY KEY, source TEXT, accepted INTEGER, rejected INTEGER);
        CREATE TABLE IF NOT EXISTS orders(batch_id TEXT, order_id TEXT, date TEXT, region TEXT,
          channel TEXT, product TEXT, status TEXT, quantity INTEGER, amount_cents INTEGER,
          PRIMARY KEY(batch_id,order_id));
        CREATE TABLE IF NOT EXISTS rejects(batch_id TEXT, line INTEGER, reason TEXT, raw_json TEXT);
    ''')
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def import_csv(text: str,path: Path,source: str='uploaded.csv') -> dict:
    batch=hashlib.sha256(text.encode('utf-8')).hexdigest()[:24]
    valid,rejected=clean(text)
    with connect(path) as conn:
        old=conn.execute('SELECT * FROM batches WHERE id=?',(batch,)).fetchone()
        if old:return {**dict(old),'reused':True}
        conn.execute('INSERT INTO batches VALUES(?,?,?,?)',(batch,source,len(valid),len(rejected)))
        conn.executemany('INSERT INTO orders VALUES(?,?,?,?,?,?,?,?,?)',[(batch,r['order_id'],r['date'],r['region'],r['channel'],r['product'],r['status'],r['quantity'],r['amount_cents']) for r in valid])
        conn.executemany('INSERT INTO rejects VALUES(?,?,?,?)',[(batch,r['line'],r['reason'],json.dumps(r['raw'],ensure_ascii=False)) for r in rejected])
    return {'id':batch,'source':source,'accepted':len(valid),'rejected':len(rejected),'reused':False}


def report(path: Path,batch: str,dimension: str='date') -> list[dict]:
    if dimension not in ('date','region','channel','product'):raise ValueError('不支持的统计维度')
    with connect(path) as conn:
        return [dict(r) for r in conn.execute(f'''SELECT {dimension} AS label,COUNT(*) AS orders,
            SUM(quantity) AS units,SUM(amount_cents) AS revenue_cents
            FROM orders WHERE batch_id=? AND status='completed' GROUP BY {dimension} ORDER BY {dimension}''',(batch,))]


def daily_channel(path: Path,batch: str) -> list[dict]:
    with connect(path) as conn:
        return [dict(r) for r in conn.execute('''SELECT date,channel,COUNT(*) AS orders,SUM(quantity) AS units,
            SUM(amount_cents) AS revenue_cents FROM orders WHERE batch_id=? AND status='completed'
            GROUP BY date,channel ORDER BY date,channel''',(batch,))]


def summary(path: Path,batch: str) -> dict:
    with connect(path) as conn:
        info=conn.execute('SELECT * FROM batches WHERE id=?',(batch,)).fetchone()
        if info is None:raise KeyError('批次不存在')
        metrics=dict(conn.execute('''SELECT COUNT(*) AS completed_orders,COALESCE(SUM(amount_cents),0) AS revenue_cents,
            COALESCE(SUM(quantity),0) AS units FROM orders WHERE batch_id=? AND status='completed' ''',(batch,)).fetchone())
        return {**dict(info),**metrics,'rejection_rate':round(info['rejected']/(info['accepted']+info['rejected']),4),
            'metric_definition':'收入只统计completed订单，取消与退款不计入；币种人民币，金额存储为分。'}


def normalized_jsonl(path: Path,batch: str) -> str:
    with connect(path) as conn:
        rows=conn.execute('SELECT * FROM orders WHERE batch_id=? ORDER BY order_id',(batch,))
        return ''.join(json.dumps(dict(r),ensure_ascii=False)+'\n' for r in rows)
