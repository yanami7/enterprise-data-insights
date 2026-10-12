"""Sorted key<TAB>value -> key<TAB>aggregate."""
import json
import sys


def reduce_lines(lines):
    current=None
    totals=[0,0,0]
    for line in lines:
        if not line.strip():continue
        key,value=line.rstrip('\n').split('\t',1)
        if current is not None and key<current:raise ValueError('Reducer输入必须按key排序')
        if current is not None and key!=current:
            yield current+'\t'+json.dumps(totals,separators=(',',':'))
            totals=[0,0,0]
        current=key
        values=json.loads(value)
        totals=[x+y for x,y in zip(totals,values)]
    if current is not None:yield current+'\t'+json.dumps(totals,separators=(',',':'))


if __name__=='__main__':
    for reduced in reduce_lines(sys.stdin):print(reduced)
