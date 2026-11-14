import json,csv
cut=1800
# replay ge, tracking active session range at each anomaly
raw=[json.loads(l) for l in open('/workspace/readings.jsonl')]
ref={int(r['line']) for r in csv.DictReader(open('/workspace/out_ge/anomaly.csv'))}
devs={}
for i,r in enumerate(raw,1):
    d=r['dev']; ts=r['ts']
    st=devs.setdefault(d,{'a':None,'closed':[],'n':0})
    a=st['a']
    if a is None:
        st['n']+=1; st['a']={'sid':f"{d}-S{st['n']:03d}",'start':ts,'end':ts}
        continue
    if ts<a['end']:
        print(i,d,ts,'active',a['sid'],a['start'],a['end'],'in_active',a['start']<=ts<=a['end'],'ref_anom',i in ref)
        continue
    if ts-a['end']>=cut:
        st['closed'].append(a); st['n']+=1; st['a']={'sid':f"{d}-S{st['n']:03d}",'start':ts,'end':ts}
    else: a['end']=ts
