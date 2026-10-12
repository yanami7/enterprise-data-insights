import json
from jobs.mapper import map_lines
from jobs.reducer import reduce_lines


def local_mapreduce(text: str) -> list[dict]:
    # Only a local correctness harness: not distributed Hadoop execution.
    mapped=sorted(map_lines(text.splitlines()))
    return parse_output('\n'.join(reduce_lines(mapped)))


def parse_output(text: str) -> list[dict]:
    rows=[]
    for line in text.splitlines():
        if not line.strip():continue
        key,value=line.split('\t',1)
        day,channel=json.loads(key)
        orders,units,cents=json.loads(value)
        rows.append({'date':day,'channel':channel,'orders':orders,'units':units,'revenue_cents':cents})
    return sorted(rows,key=lambda x:(x['date'],x['channel']))
