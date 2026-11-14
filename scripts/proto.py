import json,sys,collections
def run(conv):
    cut=1800
    def is_cut(gap): return gap>=cut if conv=='ge' else gap>cut
    devs={}
    order=[]
    with open('/workspace/readings.jsonl') as f:
        for i,l in enumerate(f,1):
            r=json.loads(l); d=r['dev']; ts=r['ts']; val=r.get('val')
            devs.setdefault(d,{'active':None,'closed':[],'n':0})
            st=devs[d]
            if not order.__contains__(d): order.append(d)
            if st['active'] is None:
                st['n']+=1
                st['active']={'sid':f"{d}-S{st['n']:03d}",'start':ts,'end':ts,'ts':[ts],'vals':[val] if val is not None else [],'cnt':1,'reopen':0}
                continue
            a=st['active']
            if ts<a['end']:
                m=[s for s in st['closed'] if s['start']<=ts<=s['end']]
                if m:
                    s=m[-1]; s['cnt']+=1; s['end_keep']=True
                    if val is not None: s['vals'].append(val)
                    s['ts'].append(ts); s['reopen']+=1; s['reopened']=True
                    s['batch']=True
                    st['active']=s
                    if s in st['closed']: st['closed'].remove(s)
                    continue
                else:
                    st['anom']=st.get('anom',0)+1
                    continue
            gap=ts-a['end']
            if is_cut(gap):
                a['cutgap']=gap; a['state']='closed'; st['closed'].append(a)
                st['n']+=1
                st['active']={'sid':f"{d}-S{st['n']:03d}",'start':ts,'end':ts,'ts':[ts],'vals':[val] if val is not None else [],'cnt':1,'reopen':0}
            else:
                a['end']=ts; a['cnt']+=1; a['ts'].append(ts)
                if val is not None: a['vals'].append(val)
    rows=[]
    for d in sorted(devs):
        for s in devs[d]['closed']+([devs[d]['active']] if devs[d]['active'] else []):
            s.setdefault('state','open')
            rows.append(s)
        rows.sort(key=lambda s:(s['start']))
    return devs,rows
for conv in ['ge','gt']:
    devs,rows=run(conv)
    print(conv,len(rows),sum(1 for s in rows if not s['vals']))
    for s in rows[:3]:
        print(s['sid'],s['start'],s['end'],s['cnt'],min(s['vals']),max(s['vals']),round(sum(s['vals'])/len(s['vals']),6),s['state'],s.get('cutgap'))
