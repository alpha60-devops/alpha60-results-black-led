#!/usr/bin/env python3
"""Rank annual cumulative media objects by a geographic slice’s downloader share.

Reads committed annual aggregate GeoJSON, once per top-level feature. Produces
a Markdown table and JSON evidence; no CSV or network access is required.
"""
import argparse
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from datetime import date
from fractions import Fraction
import gzip
import hashlib
import json
from multiprocessing import get_context
from pathlib import Path
import shutil
import subprocess


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def state(repo):
    def git(*args):
        return subprocess.check_output(['git', '-C', str(repo), *args], text=True)
    return {'commit': git('rev-parse', 'HEAD').strip(),
            'tracked': set(git('ls-files', '-z').split('\0')),
            'dirty': {row[3:] for row in git('status', '--porcelain', '-z').split('\0') if row}}


def read(repo, version, relative, sources):
    if relative not in version['tracked'] or relative in version['dirty']:
        raise ValueError(f'Uncommitted analytical input: {repo / relative}')
    raw = (repo / relative).read_bytes()
    sources.append({'repository': repo.name, 'commit': version['commit'], 'path': relative,
                    'sha256': sha(raw),
                    'url': f'https://github.com/alpha60-devops/{repo.name}/blob/{version["commit"]}/{relative}'})
    return json.loads(gzip.decompress(raw) if relative.endswith('.gz') else raw)


def reduce_sample(job):
    repo, version, key, codes = job
    sources = []
    meta = read(repo, version, f'data/json/{key}-cumulative.json', sources)
    geo = read(repo, version, f'data/geojson.cumulative/{key}-cumulative-aggregate.geojson.gz', sources)
    assert meta['collection_key'] == geo['id'] == key
    assert geo['duration_type'] == 'cumulative' and geo['duration_index'] == 0
    assert geo['swarm_geo_partition_by'] == 'hexagon'
    assert geo['swarm_hexagon_resolution'] == 5 and geo['swarm_size_min'] == 3
    assert geo['datestamp'] == meta['sample_duration']
    start, end = meta['sample_duration'].split('-to-')
    assert date.fromisoformat(start) <= date.fromisoformat(end)
    countries = defaultdict(lambda: {'downloaders': 0, 'uploaders': 0})
    world = {'downloaders': 0, 'uploaders': 0}
    regional = dict(world)
    hosting = {'world': dict(world), 'regional': dict(world)}
    for feature in geo['features']:
        properties = feature['properties']
        code = properties['country_code']
        for role in world:
            values = properties[role]
            if isinstance(values, str):
                values = json.loads(values)
            count, hosted = values['size'], values['hosting']
            assert type(count) is int and type(hosted) is int and 0 <= hosted <= count
            countries[code][role] += count
            world[role] += count
            hosting['world'][role] += hosted
            if code in codes:
                regional[role] += count
                hosting['regional'][role] += hosted
    for role in world:
        assert sum(value[role] for value in countries.values()) == world[role]
        assert sum(value[role] for code, value in countries.items() if code in codes) == regional[role]
        assert 0 <= regional[role] <= world[role], (key, role)
    return {'key': key, 'name': meta['collection_name'], 'collection_id': meta['collection_id'],
            'repository_year': int(repo.name[-4:]), 'sample_year': meta['sample_year_start'],
            'start': start, 'end': end, 'sample_days': meta['sample_days'],
            'calendar_days': (date.fromisoformat(end) - date.fromisoformat(start)).days + 1,
            'data_version': meta['data_version'], 'geojson_version': geo['data_version'],
            'ip_geolocation_version': meta['ip_geolocation_version'],
            'features': len(geo['features']), 'world': world, 'regional': regional,
            'companion_json_world': {role: meta['collection_cumulative']['unique_btiha']['u' + role + '_total'] for role in world},
            'hosting': hosting, 'countries': dict(sorted(countries.items())), 'sources': sources,
            'audit_url': f'https://alpha60-devops.github.io/{repo.name}/docs/itemized/{key}-sample-cache-audit.html'}


def share(record, role='downloaders'):
    return Fraction(record['regional'][role], record['world'][role])


def render(data, output, ledger):
    label = data['region_label']
    codes = data['country_codes']
    black = data['region'] == 'africa-60'
    stylesheet = 'mellon-7.7-analysis.css' if black else 'mellon-7.6-analysis.css'
    back = 'Black-led' if black else 'AAPI-Led'
    ranked = data['ranking']
    count = data['top_count']
    samples = {row['repository_year']: [] for row in data['samples']}
    for row in data['samples']:
        samples[row['repository_year']].append(row)
    records = {(row['key'], row['repository_year']): row for row in data['samples']}
    top = [records[(entry['key'], entry['repository_year'])] for entry in ranked[:count]]
    lines = ['---', 'layout: default', f'title: "Top {count} media objects by {label} share"',
             'author: "Benjamin De Kosnik <bkoz@gnu.org>"',
             'description: "Cumulative downloader geography across the 2017–2026 annual repositories"',
             '---', '', '{::nomarkdown}',
             '<img src="../resources/a60-logo-block-gray.simple.svg?sanitize=true" height="50" width="100" alt="Alpha60">',
             *(['<link rel="stylesheet" href="../resources/izzi-table-wcag-22.css">'] if not black else []),
             f'<link rel="stylesheet" href="../resources/{stylesheet}">', '{:/}', '',
             f'[{back} results](../index.html)', '', f'# Top {count} media objects by {label} share', '',
             f'Calculated {data["analysis_date"]} from `alpha60-results-2017` through `alpha60-results-2026`.', '',
             f'Ranked **{len(ranked):,} distinct media objects** by the percentage of their cumulative worldwide '
             f'downloader weight located in **{label}**. Each row uses its full available sample window; '
             f'weights describe repeated observed swarm participation. The top {count} sample windows span '
             f'**{min(r["sample_days"] for r in top)}–{max(r["sample_days"] for r in top)} days**.', '',
             f'<div class="analysis-table-scroll" role="region" aria-label="Top {count} media objects by {label} share" tabindex="0" markdown="1">', '',
             f'| Rank | Media object | Sample window | Days | {label} % | {label} downloader weight | Worldwide downloader weight |',
             '| ---: | --- | --- | ---: | ---: | ---: | ---: |']
    for rank, row in enumerate(top, 1):
        media_label = row['name'] + (' · ' + str(row['collection_id']) if row['collection_id'] else '')
        media_label = media_label.replace('|', '\\|')
        lines.append(f'| {rank} | [{media_label}]({row["audit_url"]})<br>`{row["key"]}` | '
                     f'{row["start"]} to {row["end"]} | {row["sample_days"]:,} | '
                     f'**{float(share(row)) * 100:.2f}%** | {row["regional"]["downloaders"]:,} | {row["world"]["downloaders"]:,} |')
    lines += ['', '</div>', '', '## Definition and method', '',
              f'`{label} % = 100 × {label} cumulative downloader weight / worldwide cumulative downloader weight`.', '',
              f'- Country membership follows the project’s [current {label} definition]('
              + data['definition_source']['url'] + f'). The {len(codes)} ISO-3 codes are: '
              + ', '.join('`' + code + '`' for code in codes) + '.',
              '- Numerator and denominator sum `downloaders.size` over the same top-level features in each '
              '`*-cumulative-aggregate.geojson.gz`. The worldwide denominator retains every country code, '
              'including unclassified locations. Nested by-BTIH features, weekly exports and JSON cumulative '
              'prefixes are not added to these totals.',
              '- The export uses H3 resolution 5 and minimum swarm size 3. The percentage therefore describes '
              'the published geographic weights; it does not use the companion cumulative JSON total '
              'as its denominator. Hosting and other network categories remain included.',
              '- The scope includes every media object with cumulative data in the ten annual repositories, '
              'without a contributor-identity, production-country or minimum-volume filter. Each collection '
              'key is one object; separate episodes and episode groups remain separate objects.',
              '- Rank uses exact numerator/denominator fractions before display rounding. Exact ties are '
              'ordered by greater worldwide downloader weight, then collection key. A common ITU scaling '
              'factor would cancel in this within-object percentage.',
              '- Sample windows, media scopes, inventories and geolocation versions differ. Interpret the '
              'ranking as geographic concentration within each observed sample.', '', '## Coverage and repeated keys', '',
              f'All **{len(data["samples"]):,} annual samples** have matching cumulative JSON, cumulative aggregate '
              f'GeoJSON and audit pages. **{len(data["excluded_zero_denominator"])}** samples have a zero worldwide '
              'downloader denominator. For repeated collection keys, the latest sample end date is retained '
              '(then latest start date, then repository year); samples are not pooled.', '']
    for duplicate in data['duplicates']:
        kept = duplicate['retained']
        discarded = ', '.join(f'{r["repository_year"]} ({r["start"]} to {r["end"]})' for r in duplicate['discarded'])
        lines.append(f'- `{duplicate["key"]}`: retain {kept["repository_year"]} '
                     f'({kept["start"]} to {kept["end"]}); supersede {discarded}.')
    lines += ['', '<div class="analysis-table-scroll" role="region" aria-label="Annual source coverage" tabindex="0" markdown="1">', '',
              '| Repository year | Annual samples | Pinned source revision |', '| --- | ---: | --- |']
    for year, version in sorted(data['repositories'].items()):
        lines.append(f'| {year} | {len(samples[int(year)])} | [{version[:10]}]('
                     f'https://github.com/alpha60-devops/alpha60-results-{year}/tree/{version}) |')
    import os
    relative = Path(os.path.relpath(ledger, output.parent)).as_posix()
    script = '../resources/rank-geographic-share.py'
    lines += ['', '</div>', '', '## Evidence and reproduction', '',
              f'The [JSON calculation ledger]({relative}) contains the complete ranking, all {len(data["samples"])} annual '
              'sample records, country sums for both roles, duplicate decisions, exact source revisions '
              'and SHA-256 hashes. Object links in the table open their annual audit pages.', '',
              f'Regenerate with [the ranking script]({script}):', '', '```bash',
              'python3 resources/rank-geographic-share.py \\',
              f'  --region {data["region"]} \\',
              '  --source-root /path/to/checkouts \\',
              f'  --top {count} \\',
              f'  --output docs/{output.name} \\',
              f'  --ledger data/{ledger.name}', '```', '']
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text('\n'.join(lines))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--region', choices=['asia-28', 'africa-60'], required=True)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--ledger', type=Path, required=True)
    parser.add_argument('--workers', type=int, default=2)
    parser.add_argument('--top', type=int, default=25)
    args = parser.parse_args()
    root = args.source_root.resolve()
    definitions = root / 'alpha60-results'
    references = []
    definition_state = state(definitions)
    definition = read(definitions, definition_state, 'resources/h15-v3/h15-v3.generated.json', references)
    codes = sorted(row['code'] for row in definition['country_sets'][args.region])
    expected = {'asia-28': 28, 'africa-60': 60}[args.region]
    assert len(codes) == len(set(codes)) == expected
    if args.region == 'asia-28':
        assert 'TWN' in codes
    label = {'asia-28': 'Asia-28', 'africa-60': 'Africa-60'}[args.region]
    jobs, versions = [], {}
    for year in range(2017, 2027):
        repo = root / f'alpha60-results-{year}'
        version = state(repo)
        versions[str(year)] = version['commit']
        keys = {p.name.removesuffix('-cumulative.json') for p in (repo / 'data/json').glob('*-cumulative.json')}
        geos = {p.name.removesuffix('-cumulative-aggregate.geojson.gz') for p in (repo / 'data/geojson.cumulative').glob('*-cumulative-aggregate.geojson.gz')}
        audits = {p.name.removesuffix('-sample-cache-audit.md') for p in (repo / 'docs/itemized').glob('*-sample-cache-audit.md')}
        assert keys == geos == audits, (year, keys ^ geos, keys ^ audits)
        jobs.extend((repo, version, key, set(codes)) for key in sorted(keys))
    samples = []
    with ProcessPoolExecutor(max_workers=args.workers, mp_context=get_context('spawn')) as pool:
        for row in pool.map(reduce_sample, jobs):
            samples.append(row)
            if len(samples) % 50 == 0:
                print(f'Reduced {len(samples)}/{len(jobs)} annual samples', flush=True)
    by_key = defaultdict(list)
    for row in samples:
        by_key[row['key']].append(row)
    chosen, duplicates = [], []
    for key, rows in sorted(by_key.items()):
        rows.sort(key=lambda r: (r['end'], r['start'], r['repository_year']), reverse=True)
        chosen.append(rows[0])
        if len(rows) > 1:
            slim = lambda r: {field: r[field] for field in ['repository_year', 'start', 'end', 'world', 'regional']}
            duplicates.append({'key': key, 'retained': slim(rows[0]), 'discarded': [slim(r) for r in rows[1:]]})
    excluded = [row['key'] for row in chosen if not row['world']['downloaders']]
    ranked = sorted((row for row in chosen if row['world']['downloaders']),
                    key=lambda row: (-share(row), -row['world']['downloaders'], row['key']))
    assert 1 <= args.top <= len(ranked)
    data = {'schema_version': 2, 'analysis_date': date.today().isoformat(),
            'region': args.region, 'region_label': label, 'country_codes': codes, 'top_count': args.top,
            'definition_source': references[0], 'definition_id': definition['definition_id'],
            'repositories': versions, 'metric': f'Cumulative {label} downloader weight / worldwide geographic downloader weight',
            'samples': samples, 'duplicates': duplicates, 'excluded_zero_denominator': excluded,
            'ranking': [{'rank': i, 'key': row['key'], 'repository_year': row['repository_year'],
                         'regional_weight': row['regional']['downloaders'], 'world_weight': row['world']['downloaders'],
                         'regional_percent': float(share(row)) * 100} for i, row in enumerate(ranked, 1)]}
    for year, commit in versions.items():
        assert state(root / f'alpha60-results-{year}')['commit'] == commit
    args.ledger.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(data, ensure_ascii=False, separators=(',', ':')) + '\n').encode()
    args.ledger.write_bytes(gzip.compress(raw, mtime=0) if args.ledger.suffix == '.gz' else raw)
    render(data, args.output, args.ledger)
    helper = args.output.parent.parent / 'resources' / Path(__file__).name
    helper.parent.mkdir(parents=True, exist_ok=True)
    if helper.resolve() != Path(__file__).resolve():
        shutil.copyfile(Path(__file__), helper)
    print(f'Wrote {args.output}: {len(ranked)} ranked objects from {len(samples)} annual samples.', flush=True)
    for row in data['ranking'][:args.top]:
        print(row['rank'], row['key'], row['repository_year'], f'{row["regional_percent"]:.4f}%', flush=True)


if __name__ == '__main__':
    main()
