import json,csv
def run(conv):
    cut=1800
    is_cut=(lambda g:g>=cut) if conv=='ge' else (lambda g:g>cut)
    devs={}
    with open('/workspace/readings.jsonl') as f:
        for i,l in enumerate(f,1):
            r=json.loads(l); d=r['dev']; ts=r['ts']; val=r.get('val')
            st=devs.setdefault(d,{'active':None,'closed':[],'n':0,'anom':[]})
            a=st['active']
            if a is None:
                st['n']+=1
                st['active']={'sid':f"{d}-S{st['n']:03d}",'start':ts,'end':ts,'cnt':1,'vals':[val] if val is not None else [],'nval':0 if val is None else 1,'sum':val or 0,'reopen':0}
                continue
            if ts<a['end']:
                cand=[s for s in st['closed'] if s['start']<=ts<=s['end']]
                if cand:
                    s=sorted(cand,key=lambda s:abs(ts-s['end']))[0]
                    st['closed'].remove(s); st['active']=s
                    s['cnt']+=1; s['reopen']+=1
                    if val is not None: s['vals'].append(val); s['nval']+=1; s['sum']+=val
                    continue
                st['anom'].append(i); continue
            gap=ts-a['end']
            if is_cut(gap):
                a['cutgap']=gap; st['closed'].append(a); st['n']+=1
                st['active']={'sid':f"{d}-S{st['n']:03d}",'start':ts,'end':ts,'cnt':1,'vals':[val] if val is not None else [],'nval':0 if val is None else 1,'sum':val or 0,'reopen':0}
            else:
                a['cnt']+=1; a['end']=ts
                if val is not None: a['vals'].append(val); a['nval']+=1; a['sum']+=val
    rows=[]
    for d,st in devs.items():
        ss=st['closed']+([st['active']] if st['active'] else [])
        for s in ss: s.setdefault('cutgap','')
        rows+=ss
    rows.sort(key=lambda s:(s['sid'][:3],s['start']))
    return rows,devs
for conv,ref in [('ge','/workspace/out_ge/session.csv'),('gt','/workspace/out_gt/session.csv')]:
    rows,devs=run(conv)
    rrows=list(csv.DictReader(open(ref)))
    print(conv,'mine',len(rows),'ref',len(rrows),'anom',sum(len(d['anom']) for d in devs.values()))
    bad=0
    if len(rows)!=len(rrows):
        print('LEN MISMATCH')
    for a,b in zip(rows,rrows):
        exp=(b['sid'],int(b['start']),int(b['end']),int(b['cnt']),int(b['min']),int(b['max']),float(b['sum']))
        got=(a['sid'],a['start'],a['end'],a['cnt'],min(a['vals']),max(a['vals']),float(a['sum']))
        if exp!=got:
            bad+=1
            if bad<6: print('DIFF',exp,got)
    print('diffs',bad)

print("=== by sid ===")
for conv,ref in [('ge','/workspace/out_ge/session.csv'),('gt','/workspace/out_gt/session.csv')]:
    rows,_=run(conv)
    mine={s['sid']:s for s in rows}
    rrows=list(csv.DictReader(open(ref)))
    print(conv,'mine',len(mine),'ref',len(rrows))
    extra=set(mine)-{r['sid'] for r in rrows}
    print('only mine:',extra)
    bad=0
    for b in rrows:
        a=mine.get(b['sid'])
        if not a: print('missing',b['sid']); bad+=1; continue
        exp=(int(b['start']),int(b['end']),int(b['cnt']),int(b['min']),int(b['max']),float(b['sum']))
        got=(a['start'],a['end'],a['cnt'],min(a['vals']),max(a['vals']),float(a['sum']))
        if exp!=got: bad+=1; print('DIFF',b['sid'],exp,got)
    print('diffs',bad)
