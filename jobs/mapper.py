"""stdin JSONL -> key<TAB>value; no dependencies for Hadoop workers."""
import json
import sys


def map_lines(lines):
    for line in lines:
        if not line.strip():continue
        row=json.loads(line)
        if row['status']!='completed':continue
        key=json.dumps([row['date'],row['channel']],ensure_ascii=False,separators=(',',':'))
        value=json.dumps([1,row['quantity'],row['amount_cents']],separators=(',',':'))
        yield key+'\t'+value


if __name__=='__main__':
    for mapped in map_lines(sys.stdin):print(mapped)
