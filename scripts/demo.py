import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from datahub.pipeline import ROOT,import_csv,summary,normalized_jsonl,daily_channel
from datahub.streaming import local_mapreduce

parser=argparse.ArgumentParser();parser.add_argument('--input',type=Path,default=ROOT/'samples'/'orders.csv');args=parser.parse_args()
db=ROOT/'data'/'analytics.db'
r=import_csv(args.input.read_text(encoding='utf-8'),db,args.input.name)
text=normalized_jsonl(db,r['id'])
(ROOT/'data'/'normalized.jsonl').write_text(text,encoding='utf-8')
result={'batch':r, 'summary':summary(db,r['id']),'sql_matches_local_mapreduce':daily_channel(db,r['id'])==local_mapreduce(text),
    'hadoop_cluster_executed':False}
print(json.dumps(result,ensure_ascii=False,indent=2))
