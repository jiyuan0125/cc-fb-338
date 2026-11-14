import json, collections
path='/workspace/readings.jsonl'
lines=[]
bad=[]
with open(path) as f:
    for i,l in enumerate(f,1):
        l=l.strip()
        if not l: continue
        try: r=json.loads(l)
        except Exception as e: bad.append((i,l[:80],repr(e))); continue
        lines.append((i,r))
print("records",len(lines),"bad",len(bad))
print("keys",collections.Counter(tuple(sorted(r)) for _,r in lines))
devs=collections.Counter(r['dev'] for _,r in lines)
print("devs",devs)
missing=[(i,r) for i,r in lines if 'val' not in r]
print("missing val",len(missing),missing[:5])
print("ts range",min(r['ts'] for _,r in lines),max(r['ts'] for _,r in lines))
# per dev arrival-order rollbacks
for d in sorted(devs):
    seq=[(i,r['ts'],r.get('val')) for i,r in lines if r['dev']==d]
    rb=[(i,ts) for (pi,pts,_),(i,ts,_) in zip(seq,seq[1:]) if ts<pts]
    print(d,len(seq),"rollbacks",len(rb),rb[:10])
# equal 1800 gaps in arrival order
eq=[]
for d in sorted(devs):
    seq=[(i,r['ts']) for i,r in lines if r['dev']==d]
    for (pi,pts),(i,ts) in zip(seq,seq[1:]):
        if ts-pts==1800: eq.append((d,pi,pts,i,ts))
print("eq1800 arrival-order",len(eq),eq[:20])
