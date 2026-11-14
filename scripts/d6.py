import json
cut=1800
rows=[]
with open('/workspace/readings.jsonl') as f:
    for i,l in enumerate(f,1):
        r=json.loads(l)
        if r['dev']=='D06': rows.append((i,r['ts'],r.get('val')))
rows.sort()
prev=None
for i,ts,val in rows:
    if prev is not None and ts-prev>=1700: print('GAP',ts-prev,'from line',pi,prev,'to',i,ts)
    prev=ts; pi=i
print('n',len(rows))
