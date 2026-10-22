import csv
import io
import os
from pathlib import Path
from fastapi import FastAPI,Body,HTTPException
from fastapi.responses import FileResponse,Response
from fastapi.staticfiles import StaticFiles
from datahub.pipeline import ROOT,connect,import_csv,report,summary,daily_channel,normalized_jsonl
from datahub.streaming import local_mapreduce

DB=Path(os.environ.get('DATAHUB_DB',str(ROOT/'data'/'analytics.db')))
app=FastAPI(title='基于 Python 的业务数据治理与分析平台',version='0.1.0')
app.mount('/static',StaticFiles(directory=ROOT/'web'),name='static')


@app.get('/')
def home():return FileResponse(ROOT/'web'/'index.html')


@app.get('/favicon.ico',include_in_schema=False)
def favicon():return Response(status_code=204)


@app.get('/health')
def health():return {'status':'ok','engine':'sqlite','streaming':'local_validation','hadoop_cluster':'not_configured'}


@app.get('/api/batches')
def batches():
    with connect(DB) as conn:return [dict(r) for r in conn.execute('SELECT * FROM batches ORDER BY rowid DESC')]


@app.post('/api/import/demo')
def demo():return import_csv((ROOT/'samples'/'orders.csv').read_text(encoding='utf-8'),DB,'synthetic-demo.csv')


@app.post('/api/import/csv')
def upload(text: str=Body(media_type='text/plain',max_length=5_000_000)):
    try:return import_csv(text,DB)
    except ValueError as error:raise HTTPException(400,detail=str(error))


def require(batch):
    try:return summary(DB,batch)
    except KeyError:raise HTTPException(404,detail='批次不存在')


@app.get('/api/batches/{batch}/summary')
def get_summary(batch: str):return require(batch)


@app.get('/api/batches/{batch}/report')
def get_report(batch: str,dimension: str='date'):
    require(batch)
    try:return report(DB,batch,dimension)
    except ValueError as error:raise HTTPException(400,detail=str(error))


@app.get('/api/batches/{batch}/rejects')
def rejects(batch: str):
    require(batch)
    with connect(DB) as conn:return [dict(r) for r in conn.execute('SELECT line,reason FROM rejects WHERE batch_id=? ORDER BY line',(batch,))]


@app.get('/api/batches/{batch}/reconcile')
def reconcile(batch: str):
    require(batch)
    sql=daily_channel(DB,batch)
    mr=local_mapreduce(normalized_jsonl(DB,batch))
    return {'matches':sql==mr,'execution':'local_mapper_sort_reducer_not_hadoop_cluster','sql':sql,'mapreduce':mr}


@app.get('/api/batches/{batch}/export')
def export(batch: str):
    require(batch)
    rows=report(DB,batch)
    buf=io.StringIO();writer=csv.DictWriter(buf,fieldnames=['label','orders','units','revenue_cents']);writer.writeheader();writer.writerows(rows)
    return Response('\ufeff'+buf.getvalue(),media_type='text/csv',headers={'Content-Disposition':'attachment; filename="daily-report.csv"'})
