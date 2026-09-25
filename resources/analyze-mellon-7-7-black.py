#!/usr/bin/env python3
"""Reduce pinned Round 3 Black-led annual exports for Mellon 7.7.

Published cumulative aggregate features are used once; nested by-BTIH features
are never added again. All counts are observed export weights, not people.
"""
import argparse
from collections import defaultdict
from datetime import date
import gzip
import hashlib
import json
from pathlib import Path
import re
import subprocess

FIELDS = ['size','mobile','satellite','tor','tor_exit_nodes','vpn','relay','proxy','hosting','service']
ROLES = ['downloaders','uploaders']


def sha(raw): return hashlib.sha256(raw).hexdigest()
def empty(): return {r:{f:0 for f in FIELDS} for r in ROLES}
def add(a,b):
    for r in ROLES:
        for f in FIELDS: a[r][f] += b[r][f]
def save(path,data): path.write_text(json.dumps(data,ensure_ascii=False,separators=(',',':'))+'\n')


class Sources:
    def __init__(self): self.repos={}
    def repo(self,path):
        path=Path(path)
        if str(path) not in self.repos:
            commit=subprocess.check_output(['git','-C',str(path),'rev-parse','HEAD'],text=True).strip()
            changed=subprocess.check_output(['git','-C',str(path),'status','--porcelain','-z'],text=True).split('\0')
            dirty={r[3:] for r in changed if r}
            tracked=set(subprocess.check_output(['git','-C',str(path),'ls-files','-z'],text=True).split('\0'))
            self.repos[str(path)]={'commit':commit,'dirty':dirty,'tracked':tracked}
        return self.repos[str(path)]
    def read(self,repo,relative,records):
        state=self.repo(repo)
        if relative not in state['tracked'] or relative in state['dirty']:
            raise ValueError(f'uncommitted analytical source: {repo}/{relative}')
        raw=(repo/relative).read_bytes()
        records.append({'repository':repo.name,'commit':state['commit'],'path':relative,'sha256':sha(raw),
                        'url':f'https://github.com/alpha60-devops/{repo.name}/blob/{state["commit"]}/{relative}'})
        return gzip.decompress(raw) if relative.endswith('.gz') else raw


def reduce_features(doc):
    if doc.get('swarm_hexagon_resolution') != 5 or doc.get('swarm_size_min') != 3:
        raise ValueError('unexpected publication partition/threshold')
    world=empty();countries=defaultdict(empty)
    for feature in doc['features']:
        p=feature['properties']
        for r in ROLES:
            if isinstance(p[r],str):p[r]=json.loads(p[r])
            for f in FIELDS:
                n=p[r][f]
                if not isinstance(n,int) or n<0 or (f!='size' and n>p[r]['size']):
                    raise ValueError(f'invalid {r}/{f}: {n}')
        add(world,p);add(countries[p['country_code']],p)
    for r in ROLES:
        for f in FIELDS: assert sum(v[r][f] for v in countries.values())==world[r][f]
    return {'world':world,'countries':dict(sorted(countries.items())),'features':len(doc['features']),
            'dates':doc.get('datestamp'),'data_version':doc.get('data_version'),
            'partition':'hexagon','hexagon_resolution':5,'publication_minimum':3}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source-root',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--reuse',action='store_true')
    args=ap.parse_args();root=args.source_root;out=args.output;out.mkdir(parents=True,exist_ok=True)
    cache=out/'objects';cache.mkdir(exist_ok=True);sources=Sources();refs=[]
    report=json.loads(sources.read(root/'alpha60-results','resources/h15-v3/h15-v3.generated.json',refs))
    slices={s['slice_key']:s for s in report['slices']}
    rows={r['collection_key']:r for r in slices['black-led']['candidates'] if r['disposition']=='confirmed'}
    african={r['collection_key'] for r in slices['african-led-global']['candidates'] if r['disposition']=='confirmed'}
    assert len(rows)==slices['black-led']['confirmed_count'] and african<=rows.keys()
    result={'schema_version':1,'slice_definition':report['definition_id'],'slice_artifact_digest':report['artifact_digest'],
            'slice_source':refs[0],'africa60':[r['code'] for r in report['country_sets']['africa-60']],
            'cohorts':{'black-led':sorted(rows),'african-led-global':sorted(african)},
            'unit':'Published cumulative geographic swarm weights, not people, views, or completed downloads.',
            'denominator':'Worldwide sum of matching top-level aggregate GeoJSON feature weights, including unknown country codes.',
            'objects':{}}
    for ix,(key,row) in enumerate(sorted(rows.items())):
        dest=cache/(key+'.json')
        if args.reuse and dest.exists():
            value=json.loads(dest.read_text())
            if all(sources.repo(root/s['repository'])['commit']==s['commit'] and
                   sha((root/s['repository']/s['path']).read_bytes())==s['sha256'] for s in value['sources']):
                result['objects'][key]=value;continue
        refs=[];m=json.loads(sources.read(root/'alpha60-swarm-metadata',f'metadata/{key}.json',refs))
        year=(row['years'][0] if len(row['years'])==1 else m.get('sample_year_start'))
        if year not in row['years']: raise ValueError(f'ambiguous annual source for {key}')
        repo=root/f'alpha60-results-{year}'
        meta=json.loads(sources.read(repo,f'data/json/{key}-cumulative.json',refs))
        geo=json.loads(sources.read(repo,f'data/geojson.cumulative/{key}-cumulative-aggregate.geojson.gz',refs))
        if geo['id']!=key or geo['duration_type']!='cumulative':raise ValueError('wrong cumulative object')
        value=reduce_features(geo)
        assert value['dates']==meta['sample_duration']
        unique=meta['collection_cumulative']['unique_btiha']
        value.update(key=key,label=m['collection_name'],year=year,sample_days=meta['sample_days'],
                     collection_id=meta['collection_id'],media_type=m['media_object']['type'],
                     canonical_work_key=m['media_object']['canonical_work_key'],
                     genres=m['release']['genres'],production_countries=m['release']['countries_of_origin'],
                     original_languages=m['release']['original_languages'],usa_production=row['usa_production'],
                     slice_counts=row['reviewed_counts'],in_african_global=key in african,
                     source_world={r:unique['u'+r+'_total'] for r in ROLES},
                     geolocation_version=meta['ip_geolocation_version'],sources=refs,
                     metadata_sample_year=m.get('sample_year_start'),
                     audit_url=f'https://alpha60-devops.github.io/{repo.name}/docs/itemized/{key}-sample-cache-audit.html')
        for r in ROLES:
            assert value['world'][r]['size']<=value['source_world'][r],key
        save(dest,value);result['objects'][key]=value
        if ix%25==0:print(f'{ix+1}/{len(rows)} {key}',flush=True)
    save(out/'cumulative.json',result)
    print('Collected',len(rows),'objects',flush=True)

if __name__=='__main__':main()
