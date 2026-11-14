import json,csv
# find D06 sessions around the invalid one: line 580 has no val, ts 1793557617
raw=[json.loads(l) for l in open('/workspace/readings.jsonl')]
rows=[(i,r) for i,r in enumerate(raw,1) if r['dev']=='D06']
for i,r in rows:
    if 1793555000<r['ts']<1793562000: print(i,r)
