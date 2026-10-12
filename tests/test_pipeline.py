import json
import pytest
from fastapi.testclient import TestClient
from datahub.pipeline import ROOT,clean,import_csv,summary,report,normalized_jsonl,daily_channel
from datahub.streaming import local_mapreduce
from jobs.reducer import reduce_lines

SAMPLE=(ROOT/'samples'/'orders.csv').read_text(encoding='utf-8')


def test_quality_rejects_known_bad_rows():
    valid,bad=clean(SAMPLE)
    assert len(valid)==12 and len(bad)==6
    assert '订单编号重复' in [r['reason'] for r in bad]
    assert valid[0]['amount_cents']==7980


def test_import_is_idempotent_and_metrics_have_a_defined_scope(tmp_path):
    db=tmp_path/'db.sqlite'
    r=import_csv(SAMPLE,db)
    assert not r['reused']
    assert import_csv(SAMPLE,db)['reused']
    s=summary(db,r['id'])
    assert s['accepted']==12 and s['completed_orders']==10
    # 79.8+199+398+159.6+299+119.4+198+89.7+39.9+298 = 1880.40
    assert s['revenue_cents']==188040
    assert sum(x['revenue_cents'] for x in report(db,r['id'],'channel'))==s['revenue_cents']


def test_sql_and_streaming_match(tmp_path):
    db=tmp_path/'db.sqlite';r=import_csv(SAMPLE,db)
    assert daily_channel(db,r['id'])==local_mapreduce(normalized_jsonl(db,r['id']))


def test_invalid_header_and_reducer_order():
    with pytest.raises(ValueError): clean('a,b\n1,2')
    with pytest.raises(ValueError): list(reduce_lines(['b\t[1,1,1]','a\t[1,1,1]']))


def test_api_import_reconcile_and_export(tmp_path,monkeypatch):
    import datahub.main as main
    monkeypatch.setattr(main,'DB',tmp_path/'api.sqlite')
    client=TestClient(main.app)
    assert client.get('/').status_code==200
    r=client.post('/api/import/demo');assert r.status_code==200
    batch=r.json()['id']
    assert client.get(f'/api/batches/{batch}/reconcile').json()['matches']
    assert client.get(f'/api/batches/{batch}/export').status_code==200
    assert client.get(f'/api/batches/{batch}/report?dimension=invalid').status_code==400
    assert client.get('/api/batches/missing/summary').status_code==404
    assert client.post('/api/import/csv',content='bad',headers={'content-type':'text/plain'}).status_code==400
