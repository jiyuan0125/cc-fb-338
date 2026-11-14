import json
cut=1800
raw=[json.loads(l) for l in open('/workspace/readings.jsonl')]
devs={}
for i,r in enumerate(raw,1):
    d=r['dev']; ts=r['ts']
    st=devs.setdefault(d,{'a':None,'closed':[],'n':0})
    a=st['a']
    if a is None:
        st['n']+=1; st['a']={'sid':f"{d}-S{st['n']:03d}",'start':ts,'end':ts}; continue
    if ts<a['end']:
        hits=[s for s in st['closed'] if s['start']<=ts<=s['end']]
        print(i,d,ts,'rollback','closed-window-hits',[(s['sid'],s['start'],s['end']) for s in hits], 'active',a['sid'],a['start'],a['end'])
        if hits:
            s=hits[-1]; st['closed'].remove(s); st['a']=s; s['end']=max(s['end'],ts)
        continue
    if ts-a['end']>=cut:
        st['closed'].append(a); st['n']+=1; st['a']={'sid':f"{d}-S{st['n']:03d}",'start':ts,'end':ts}
    else: a['end']=max(a['end'],ts)
