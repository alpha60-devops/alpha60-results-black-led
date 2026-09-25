#!/usr/bin/env python3
"""Add an available-coverage weekly M4 ledger without changing the dated study."""
import argparse
from datetime import date
import gzip
import importlib.util
import json
from pathlib import Path

spec = importlib.util.spec_from_file_location('collector', Path(__file__).with_name('analyze-mellon-7-7-black.py'))
collector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(collector)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--itu-config', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--weeks', type=int, choices=[10, 15, 26], default=26)
    args = parser.parse_args()
    raw = args.input.read_bytes()
    original = json.loads(gzip.decompress(raw) if args.input.suffix == '.gz' else raw)
    policy = json.loads(args.itu_config.read_text())
    assert policy['reference_year'] == 2026 and policy['reference_users_billions'] == 6.1
    result = {
        'schema_version': 1, 'requested_weeks': list(range(1, args.weeks+1)),
        'original_ledger_sha256': collector.sha(raw),
        'africa60': original['africa60'], 'slice_source': original['slice_source'],
        'itu_policy': policy, 'itu_policy_sha256': collector.sha(args.itu_config.read_bytes()),
        'unit': 'Seven-day top-level weekly GeoJSON swarm weights; repeated observations, not people or cumulative prefixes.',
        'missing_policy': 'Unobserved and short trailing bins are unplotted; full calendar bins can still have sampling gaps.',
        'objects': {},
    }
    assert len(set(result['africa60'])) == 60
    sources = collector.Sources()
    for key in original['m4']['keys']:
        prior = original['objects'][key]
        repo = args.source_root / f"alpha60-results-{prior['year']}"
        refs = []
        meta = json.loads(sources.read(repo, f'data/json/{key}-cumulative.json', refs))
        assert meta['sample_duration'] == prior['dates']
        year = int(meta['sample_duration'][:4])
        users = policy['years'][str(year)]['users_billions']
        factor = policy['reference_users_billions'] / users
        record = {'year': year, 'sample_duration': meta['sample_duration'], 'source_users_billions': users,
                  'factor': factor, 'weeks': [], 'exclusions': [],
                  'data_version': meta['data_version'], 'geolocation_version': meta['ip_geolocation_version']}
        audit = sources.read(repo, f'docs/itemized/{key}-sample-cache-audit.md', refs).decode()
        record['coverage_notes'] = [line for line in audit.splitlines() if 'missing' in line.lower() or 'hourly gap:' in line]
        for week in result['requested_weeks']:
            filename = f'data/geojson.week/{key}-week-{week:05d}.geojson.gz'
            if not (repo / filename).exists():
                record['exclusions'].append({'week': week, 'reason': 'not available'})
                continue
            doc = json.loads(sources.read(repo, filename, refs))
            assert doc['id'] == key and doc['duration_type'] == 'week' and doc['duration_index'] == week
            start, end = doc['datestamp'].removesuffix('-partial').split('-to-')
            days = (date.fromisoformat(min(end, meta['sample_duration'][-10:]))-date.fromisoformat(start)).days+1
            if days != 7:
                assert 1 <= days < 7
                record['exclusions'].append({'week': week, 'reason': 'short trailing interval', 'dates': doc['datestamp'], 'days': days})
                continue
            row = collector.reduce_features(doc)
            # The original seven-week comparison is retained exactly.
            if week <= 7:
                old = original['weekly'][key]['weeks'][week-1]
                for field in ['world', 'countries', 'features', 'dates']:
                    assert row[field] == old[field], (key, week, field)
            row.update(week=week, partial=doc['datestamp'].endswith('-partial'), africa60=collector.empty())
            for code, values in row['countries'].items():
                if code in result['africa60']: collector.add(row['africa60'], values)
            row['adjusted'] = {region: {role: {field: value*factor for field,value in values.items()}
                                       for role,values in row[region].items()} for region in ['world','africa60']}
            record['weeks'].append(row)
            print(key, week, row['dates'], flush=True)
            del doc
        record['sources'] = refs
        result['objects'][key] = record
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, separators=(',', ':'))+'\n')


if __name__ == '__main__':
    main()
