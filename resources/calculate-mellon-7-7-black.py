#!/usr/bin/env python3
"""Calculate the four Black-led studies from the reviewed cumulative ledger."""
import argparse
from collections import defaultdict
from datetime import date
import importlib.util
import json
import math
from pathlib import Path
import re
import statistics

spec=importlib.util.spec_from_file_location('collector',Path(__file__).with_name('analyze-mellon-7-7-black.py'))
collector=importlib.util.module_from_spec(spec);spec.loader.exec_module(collector)
FAMILIES={
 'Romance':r'romanc|romantic',
 'Action/adventure':r'action|adventure|superhero|wuxia|martial|swashbuckler|kaiju',
 'Thriller/crime/mystery':r'thriller|crime|mystery|detective|police|spy|espionage|heist|noir',
 'Comedy':r'comedy|sitcom|satir|parody|buddy',
 'Science fiction/fantasy':r'science fiction|fantasy|speculative|supernatural|superhero|dystop|apocal|cyberpunk|steampunk|space |vampire|werewolf|zombie|fairy tale|alternate history',
 'Drama':r'drama|tragedy|coming.of.age',
 'Horror':r'horror|zombie|vampire|werewolf|splatter',
 'Music/musical':r'music',
 'Documentary/interview':r'documentary|interview|concert',
 'Western':r'western',
 'Animation':r'animat|anime',
}


def measure(record,codes,role='downloaders',nonhosting=False):
    def weight(value):return value[role]['size']-(value[role]['hosting'] if nonhosting else 0)
    num=sum(weight(v) for c,v in record['countries'].items() if c in codes)
    den=weight(record['world'])
    return {'count':num,'world':den,'share':100*num/den if den else None}


def summary(rows,codes):
    if not rows:return {'objects':0}
    shares=[measure(r,codes)['share'] for r in rows];n=sum(measure(r,codes)['count'] for r in rows);w=sum(r['world']['downloaders']['size'] for r in rows)
    return {'objects':len(rows),'median_share':statistics.median(shares),'pooled_share':100*n/w,
            'africa_weight':n,'world_weight':w,'median_nonhosting_share':statistics.median(measure(r,codes,nonhosting=True)['share'] for r in rows),
            'median_uploader_share':statistics.median(measure(r,codes,role='uploaders')['share'] for r in rows),
            'min_share':min(shares),'max_share':max(shares)}


def totals(weeks):
    result={'world':collector.empty(),'countries':defaultdict(collector.empty)}
    for w in weeks:
        collector.add(result['world'],w['world'])
        for c,v in w['countries'].items():collector.add(result['countries'][c],v)
    result['countries']=dict(result['countries']);return result


def eligible_weeks(value):
    """Exclude partial bins and dated audit gaps; absence of a flag is not an hourly audit."""
    spans=[]
    for line in value['coverage_notes']:
        dates=re.findall(r'\d{4}-\d{2}-\d{2}',line)
        if ('hourly gap:' in line or 'missing Day index' in line) and dates:
            spans.append((min(dates),max(dates)))
    result=[]
    for w in value['weeks']:
        a,b=w['dates'].removesuffix('-partial').split('-to-')
        if not w['partial'] and w['calendar_days']==7 and not any(a<=y and b>=x for x,y in spans):
            result.append(w['week'])
    return result


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--input',type=Path,required=True);ap.add_argument('--source-root',type=Path,required=True)
    ap.add_argument('--language-config',type=Path,required=True);ap.add_argument('--genre-config',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True);ap.add_argument('--reuse-weeks',action='store_true')
    args=ap.parse_args();d=json.loads(args.input.read_text());langs=json.loads(args.language_config.read_text());genres=json.loads(args.genre_config.read_text());objects=d['objects'];af=set(d['africa60'])
    groups={'africa60':sorted(af),'francophone':langs['francophone']['codes'],
            'francophone_africa60':sorted(af & set(langs['francophone']['codes'])),
            'francophone_nonafrica':sorted(set(langs['francophone']['codes'])-af),
            'anglophone_ex_usa':sorted(set(langs['anglophone']['codes'])-{'USA'}),
            'anglophone_africa60':sorted(set(langs['anglophone']['codes']) & af),
            'anglophone_working_ex_usa':sorted((set(langs['anglophone']['codes'])|set(langs['anglophone']['working_language_additions']))-{'USA'}),
            'usa':['USA'],'africa_ex_zaf':sorted(af-{'ZAF'})}
    for key,r in objects.items():
        r['genres']=genres['objects'][key]['genres'];r['genre_families']=[name for name,pat in FAMILIES.items() if any(re.search(pat,g,re.I) for g in r['genres'])]
        if not r['genre_families']:r['genre_families']=['Other' if r['genres'] else 'Unknown']
        r['metrics']={name:{role:measure(r,set(codes),role) for role in collector.ROLES} | {'nonhosting_downloaders':measure(r,set(codes),nonhosting=True)} for name,codes in groups.items()}
    d.update(language_groups=langs,groups=groups,genre_config_sha256=collector.sha(args.genre_config.read_bytes()),language_config_sha256=collector.sha(args.language_config.read_bytes()),genre_family_rules=FAMILIES)
    ranked=sorted(objects,key=lambda k:(-objects[k]['metrics']['africa60']['downloaders']['share'],k));rank={k:i+1 for i,k in enumerate(ranked)}
    for k,r in objects.items():r['africa60_rank']=rank[k]
    top=ranked[:20];d['m3']={'ranked_keys':ranked,'top20':top,'genre_summary':[],
                         'unknown_keys':[k for k,r in objects.items() if not r['genres']],
                         'named_romance_keys':[k for k in ranked if k=='lovebirds' or k.startswith(('bridgerton','queen-charlotte'))]}
    for family in [*FAMILIES,'Other','Unknown']:
        selected=[r for r in objects.values() if family in r['genre_families']]
        if selected:d['m3']['genre_summary'].append({'family':family,**summary(selected,af),'top20_objects':sum(k in top for k in [r['key'] for r in selected])})
    romans=[r for r in objects.values() if 'Romance' in r['genre_families']];other=[r for r in objects.values() if r['genres'] and 'Romance' not in r['genre_families']]
    d['m3']['romance_comparison']={}
    for name,predicate,codes in [('all',lambda r:True,af),('at_least_49_days',lambda r:r['sample_days']>=49,af),
                                  ('days_56_to_112',lambda r:56<=r['sample_days']<=112,af),
                                  ('films',lambda r:r['media_type']=='film',af),
                                  ('serials',lambda r:r['media_type']!='film',af),
                                  ('africa_ex_south_africa',lambda r:True,af-{'ZAF'})]:
        d['m3']['romance_comparison'][name]={'romance':summary([r for r in romans if predicate(r)],codes),'other_tagged':summary([r for r in other if predicate(r)],codes)}
    works=defaultdict(list)
    for r in objects.values():works[r['canonical_work_key'] or r['key']].append(r)
    worksummary={}
    for name,eligible in [('romance',True),('other_tagged',False)]:
        vs=[statistics.median(r['metrics']['africa60']['downloaders']['share'] for r in rs) for rs in works.values() if any(r['genres'] for r in rs) and any('Romance' in r['genre_families'] for r in rs)==eligible]
        worksummary[name]={'works':len(vs),'median_of_work_medians':statistics.median(vs)}
    d['m3']['canonical_work_sensitivity']=worksummary
    d['m3']['top20_nonhosting']=sorted(objects,key=lambda k:(-objects[k]['metrics']['africa60']['nonhosting_downloaders']['share'],k))[:20]
    # Pair on duration and worldwide volume, never on the regional outcome.
    eligible=[r for r in objects.values() if r['in_african_global'] and r['usa_production']['value'] is False and 'English' in r['original_languages']]
    controls=[r for r in objects.values() if r['usa_production']['value'] is True]
    candidates=[]
    for a in eligible:
        for b in controls:
            if (a['media_type']=='film')!=(b['media_type']=='film') or abs(a['year']-b['year'])>2:continue
            dr=max(a['sample_days'],b['sample_days'])/min(a['sample_days'],b['sample_days']);vr=max(a['world']['downloaders']['size'],b['world']['downloaders']['size'])/min(a['world']['downloaders']['size'],b['world']['downloaders']['size'])
            if dr<=1.25 and vr<=1.5:
                candidates.append({'nonusa':a['key'],'usa':b['key'],'duration_ratio':dr,'world_volume_ratio':vr,'score':math.log(dr)+math.log(vr)})
    candidates.sort(key=lambda r:(r['score'],r['nonusa'],r['usa']));selected=[];seen=set()
    for pair in candidates:
        identities={objects[pair[k]]['canonical_work_key'] or pair[k] for k in ('nonusa','usa')}
        if identities&seen:continue
        selected.append(pair);seen.update(identities)
        if len(selected)==3:break
    if not selected:raise ValueError('no defensible M2 matches')
    d['m2']={'eligible_nonusa':[r['key'] for r in eligible],'rule':'Confirmed african-led-global, explicit non-USA production and original English. USA controls: confirmed black-led and explicit USA production. Same film/serial class, sample years within 2, duration ratio <=1.25 and volume ratio <=1.5. Greedy lowest abs-log-ratio cost with distinct canonical works; no geographic outcomes used.',
             'candidate_pairs':candidates,'selected_pairs':selected}
    d['m1']={'keys':['lupin-02','lupin-03','black-panther','black-panther-wakanda-forever']}
    d['m4']={'keys':['black-panther','black-panther-wakanda-forever','ironheart-01','eyes-of-wakanda-01']}
    wanted=sorted(set(d['m1']['keys']+d['m4']['keys']+[p[k] for p in selected for k in ['nonusa','usa']]))
    sources=collector.Sources();weekly={};cache=args.output.parent/'weeks';cache.mkdir(exist_ok=True)
    for key in wanted:
        record=objects[key];repo=args.source_root/f'alpha60-results-{record["year"]}';path=cache/(key+'.json')
        if args.reuse_weeks and path.exists():
            value=json.loads(path.read_text())
            if all(sources.repo(args.source_root/s['repository'])['commit']==s['commit'] and collector.sha((args.source_root/s['repository']/s['path']).read_bytes())==s['sha256'] for s in value['sources']):weekly[key]=value;continue
        refs=[];weeks=[]
        for week in range(1,8):
            name=f'data/geojson.week/{key}-week-{week:05d}.geojson.gz'
            if not (repo/name).is_file():break
            doc=json.loads(sources.read(repo,name,refs));assert doc['id']==key and doc['duration_index']==week and doc['duration_type']=='week'
            w=collector.reduce_features(doc);w['week']=week;w['partial']=w['dates'].endswith('-partial');a,b=w['dates'].removesuffix('-partial').split('-to-');w['calendar_days']=(date.fromisoformat(b)-date.fromisoformat(a)).days+1
            assert 1<=w['calendar_days']<=7
            weeks.append(w)
        audit=f'docs/itemized/{key}-sample-cache-audit.md'
        notes=[]
        if (repo/audit).is_file():
            text=sources.read(repo,audit,refs).decode();zone=text.split('## 2.')[1].split('## 3.')[0] if '## 2.' in text else text
            notes=[line for line in zone.splitlines() if line.strip()]
        value={'weeks':weeks,'sources':refs,'coverage_notes':notes,'first_seven_sum':totals(weeks),'available_weeks':len(weeks)}
        weekly[key]=value;collector.save(path,value);print('weeks',key,len(weeks),flush=True)
    for value in weekly.values():value['eligible_week_indices']=eligible_weeks(value)
    d['weekly']=weekly
    for group in ['m1','m2','m4']:
        ks=(d[group]['keys'] if group!='m2' else [p[k] for p in selected for k in ['nonusa','usa']])
        complete=[i for i in range(1,8) if all(i in weekly[k]['eligible_week_indices'] for k in ks)]
        d[group]['common_full_week_indices']=complete
        d[group]['common_full_weeks']={k:totals([w for w in weekly[k]['weeks'] if w['week'] in complete]) for k in ks}
    for pair in selected:
        ks=[pair['nonusa'],pair['usa']]
        complete=[i for i in range(1,8) if all(i in weekly[k]['eligible_week_indices'] for k in ks)]
        pair['common_full_week_indices']=complete
        pair['common_full_weeks']={k:totals([w for w in weekly[k]['weeks'] if w['week'] in complete]) for k in ks}
    collector.save(args.output,d)
    print(json.dumps({'m2_pairs':selected,'top20':top,'romance_comparison':d['m3']['romance_comparison'],'canonical_work':worksummary},indent=2))

if __name__=='__main__':main()
