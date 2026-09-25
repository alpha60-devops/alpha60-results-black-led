#!/usr/bin/env python3
"""Independently validate source reductions, cohorts, windows and published tables.

Uses standard-library arithmetic, JSON and HTML parsing rather than importing
the production reducers. The selected raw-export checks cover both cumulative
and interval observations, different years, and partial-week cases.
"""
import argparse
from collections import defaultdict
from datetime import date
import gzip
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import statistics


def sha(raw): return hashlib.sha256(raw).hexdigest()


def reduce_independently(path):
    with gzip.open(path) as stream: doc=json.load(stream)
    totals=defaultdict(lambda:defaultdict(lambda:defaultdict(int)))
    for feature in doc['features']:
        p=feature['properties']
        for role in ['downloaders','uploaders']:
            flags=json.loads(p[role]) if isinstance(p[role],str) else p[role]
            for field,value in flags.items():totals[p['country_code']][role][field]+=value
    return dict(totals)


class Tables(HTMLParser):
    def __init__(self):
        super().__init__();self.tables=[];self.table=None;self.row=None;self.cell=None;self.caption=False
    def handle_starttag(self,tag,attrs):
        if tag=='table':self.table={'caption':'','rows':[]}
        if tag=='caption':self.caption=True
        if tag=='tr':self.row=[]
        if tag in ['td','th']:self.cell=''
        if tag=='br' and self.cell is not None:self.cell+=' '
    def handle_data(self,data):
        if self.cell is not None:self.cell+=data
        if self.caption:self.table['caption']+=data
    def handle_endtag(self,tag):
        if tag in ['td','th']:self.row.append(self.cell);self.cell=None
        if tag=='tr':self.table['rows'].append(self.row);self.row=None
        if tag=='caption':self.caption=False
        if tag=='table':self.tables.append(self.table);self.table=None


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--ledger',type=Path,required=True);ap.add_argument('--site',type=Path,required=True)
    ap.add_argument('--source-root',type=Path,required=True);ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args();raw=args.ledger.read_bytes();d=json.loads(gzip.decompress(raw) if args.ledger.suffix=='.gz' else raw)
    o=d['objects'];checks=[]
    source=args.source_root/d['slice_source']['repository']/d['slice_source']['path']
    assert sha(source.read_bytes())==d['slice_source']['sha256']
    report=json.loads(source.read_bytes());slices={s['slice_key']:s for s in report['slices']}
    for group in ['black-led','african-led-global']:
        expected={r['collection_key'] for r in slices[group]['candidates'] if r['disposition']=='confirmed'}
        assert set(d['cohorts'][group])==expected
    assert set(o)==set(d['cohorts']['black-led']) and len(o)==382
    assert len(d['cohorts']['african-led-global'])==216
    assert len({r['canonical_work_key'] for r in o.values()})==217
    checks.append('Exact authoritative cohorts: 382 Black-led objects, 217 works, 216 African-led-global objects')
    refs={}
    for r in list(o.values())+list(d['weekly'].values()):
        for s in r['sources']:refs[(s['repository'],s['path'])]=s
    for s in refs.values():assert sha((args.source_root/s['repository']/s['path']).read_bytes())==s['sha256'],s['path']
    checks.append(f'All {len(refs)} analytical source file hashes verified')
    for key,r in o.items():
        for role in ['downloaders','uploaders']:
            for field,weight in r['world'][role].items():assert weight==sum(c[role][field] for c in r['countries'].values())
            assert r['world'][role]['size']<=r['source_world'][role]
        for group,codes in d['groups'].items():
            for mode,role,nonhost in [('downloaders','downloaders',False),('uploaders','uploaders',False),('nonhosting_downloaders','downloaders',True)]:
                count=sum(v[role]['size']-(v[role]['hosting'] if nonhost else 0) for c,v in r['countries'].items() if c in codes)
                world=r['world'][role]['size']-(r['world'][role]['hosting'] if nonhost else 0)
                value=r['metrics'][group][mode]
                assert value['count']==count and value['world']==world and abs(value['share']-100*count/world)<1e-12
    checks.append('All object/country/network sums, regional numerators and role-specific denominators reconciled')
    samples=['lovebirds','black-panther','lupin-03','bridgerton-04.2','power-109','eyes-of-wakanda-01']
    for key in samples:
        r=o[key];s=next(s for s in r['sources'] if s['path'].endswith('.geojson.gz'))
        assert reduce_independently(args.source_root/s['repository']/s['path'])==r['countries'],key
    week_samples=[('black-panther',2),('black-panther-wakanda-forever',5),('underground-railroad-01',7),('old-man-201',2)]
    for key,i in week_samples:
        value=d['weekly'][key];w=next(w for w in value['weeks'] if w['week']==i)
        s=next(s for s in value['sources'] if s['path'].endswith(f'-{i:05d}.geojson.gz'))
        assert reduce_independently(args.source_root/s['repository']/s['path'])==w['countries'],(key,i)
    checks.append('Independent raw-feature reductions: six cumulative exports and four interval exports')
    ranks=sorted(o,key=lambda k:(-sum(v['downloaders']['size'] for c,v in o[k]['countries'].items() if c in d['africa60'])/o[k]['world']['downloaders']['size'],k))
    assert ranks==d['m3']['ranked_keys'] and ranks[:20]==d['m3']['top20']
    romance=[r for r in o.values() if 'Romance' in r['genre_families']]
    assert len(romance)==17 and sum('Romance' in o[k]['genre_families'] for k in ranks[:20])==5
    assert round(statistics.median(r['metrics']['africa60']['downloaders']['share'] for r in romance),2)==4.28
    genre=json.loads((args.site/'data/black-led-7.7-genres.json').read_text())
    assert set(genre['objects'])==set(o) and all(r['genres'] for r in genre['objects'].values())
    assert sha((args.site/'data/black-led-7.7-genres.json').read_bytes())==d['genre_config_sha256']
    assert sha((args.site/'data/black-led-7.7-language-groups.json').read_bytes())==d['language_config_sha256']
    registry={r['alpha-3'] for r in json.loads((args.source_root/'alpha60-data/iso-3166/slim-3.json').read_text())}
    for codes in d['groups'].values():assert len(codes)==len(set(codes)) and set(codes)<=registry
    checks.append('All 382 ranks and genre coverage; 17 romance objects, five in top 20; country sets valid ISO-3')
    pairs=d['m2']['selected_pairs'];assert len(pairs)==3
    assert len(d['m2']['eligible_nonusa'])==5
    works=[]
    for p in pairs:
        a,b=o[p['nonusa']],o[p['usa']]
        assert a['in_african_global'] and a['usa_production']['value'] is False and b['usa_production']['value'] is True
        assert 'English' in a['original_languages'] and a['sample_days']==b['sample_days']
        assert abs(a['year']-b['year'])<=2 and (a['media_type']=='film')==(b['media_type']=='film')
        assert max(a['world']['downloaders']['size'],b['world']['downloaders']['size'])/min(a['world']['downloaders']['size'],b['world']['downloaders']['size'])<1.0156
        works.extend([a['canonical_work_key'],b['canonical_work_key']])
    assert len(set(works))==6
    assert d['m1']['common_full_week_indices']==[4,6,7]
    assert d['m4']['common_full_week_indices']==[2,3,4,6,7]
    assert [p['common_full_week_indices'] for p in pairs]==[[3,4,5,6,7],[1,2,3,4,6],[3,5,6]]
    for key,value in d['weekly'].items():
        assert [w['week'] for w in value['weeks']]==list(range(1,8))
        last=None
        for w in value['weeks']:
            a,b=map(date.fromisoformat,w['dates'].removesuffix('-partial').split('-to-'))
            assert (b-a).days+1==7
            if last is not None:assert (a-last).days==1
            last=b
        for role in ['downloaders','uploaders']:
            for field,value2 in value['first_seven_sum']['world'][role].items():assert value2==sum(w['world'][role][field] for w in value['weeks'])
    checks.append('Production/language match constraints, distinct works, consecutive intervals and coverage masks')
    parser=Tables();parser.feed((args.site/'docs/romance-genre.md').read_text())
    alltable=next(t for t in parser.tables if t['caption']=='Complete Black-led ranking')
    assert len(alltable['rows'])==383
    for rank,row in enumerate(alltable['rows'][1:],1):
        k=ranks[rank-1];r=o[k]
        assert int(row[0])==rank and k in row[1]
        assert row[3]==str(r['sample_days']) and row[6]==f"{r['metrics']['africa60']['downloaders']['share']:.2f}%"
    for name in ['francophone','anglophone','romance-genre','wakanda-forever']:
        text=(args.site/'docs'/f'{name}.md').read_text()
        assert text.startswith('---\nlayout: default\n') and '## Methods and reproducibility' in text
        assert '<table>' in text and f'mellon-7.7-{name}.svg' in text
        assert (args.site/'resources'/f'mellon-7.7-{name}.svg').is_file()
        assert f'docs/{name}.html' in (args.site/'index.md').read_text()
    published=json.loads(gzip.decompress((args.site/'data/mellon-7.7-analysis.json.gz').read_bytes()))
    assert published==d
    checks.append('All 382 rendered ranking rows match the ledger; four pages/index/figures and published ledger verified')
    receipt={'status':'PASS','checks':checks,'independent_cumulative_samples':samples,'independent_interval_samples':week_samples,
             'input_sha256':sha(raw),'published_ledger_sha256':sha((args.site/'data/mellon-7.7-analysis.json.gz').read_bytes())}
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt,indent=2))


if __name__=='__main__':main()
