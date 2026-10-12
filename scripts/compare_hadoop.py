"""Compare real Hadoop output against the SQL reference, if a cluster was used."""
import argparse
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from datahub.pipeline import ROOT,import_csv,daily_channel
from datahub.streaming import parse_output

parser=argparse.ArgumentParser()
parser.add_argument('output',type=Path)
parser.add_argument('--input',type=Path,default=ROOT/'samples'/'orders.csv')
args=parser.parse_args()
db=ROOT/'data'/'analytics.db'
batch=import_csv(args.input.read_text(encoding='utf-8'),db,args.input.name)['id']
match=daily_channel(db,batch)==parse_output(args.output.read_text(encoding='utf-8'))
print('SQL与Hadoop结果一致' if match else '结果不一致')
raise SystemExit(0 if match else 1)
