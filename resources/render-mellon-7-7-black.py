#!/usr/bin/env python3
"""Render the four Mellon 7.7 reports in the existing Black-led Jekyll site.

Static comparisons use matplotlib. Weekly line graphs use a C++20 compiler,
RapidJSON and Izzi. All figure and table values come from the JSON ledgers.
"""
import argparse
import gzip
import html
import importlib.util
import json
from pathlib import Path
import re
import shutil
import xml.etree.ElementTree as ET

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('calculate', Path(__file__).with_name('calculate-mellon-7-7-black.py'))
calc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(calc)
BLUE, ORANGE, GRAY = '#175b8c', '#a34419', '#626a74'
TITLES = {'lupin-02': 'Lupin 02', 'lupin-03': 'Lupin 03', 'black-panther': 'Black Panther',
          'black-panther-wakanda-forever': 'Wakanda Forever', 'ironheart-01': 'Ironheart 01',
          'eyes-of-wakanda-01': 'Eyes of Wakanda 01', 'power-109': 'The Power 109',
          'atlanta-410': 'Atlanta 410', 'intergalactic-01': 'Intergalactic 01',
          'underground-railroad-01': 'The Underground Railroad 01',
          'black-mirror-06': 'Black Mirror 06', 'old-man-201': 'The Old Man 201'}
PAGES = [('francophone', 'Francophone countries: Lupin and Black Panther'),
         ('anglophone', 'Anglophone countries and USA production'),
         ('romance-genre', 'Romance and Africa60: the full Black-led cohort'),
         ('wakanda-forever', 'Black Panther, Ironheart and Eyes of Wakanda in Africa60')]


def esc(value): return html.escape(str(value))
def number(value): return f'{value:,.0f}'
def percent(value): return '—' if value is None else f'{value:.2f}%'
def link(label, url): return f'<a href="{esc(url)}">{esc(label)}</a>'
def title(key): return TITLES.get(key, key)


def table(caption, headers, rows):
    out = '\n{::nomarkdown}\n'
    out += f'<div class="analysis-table-scroll" role="region" aria-label="{esc(caption)}" tabindex="0">\n<table>\n<caption>{esc(caption)}</caption>\n<thead><tr>'
    out += ''.join(f'<th scope="col">{esc(h)}</th>' for h in headers) + '</tr></thead>\n<tbody>\n'
    for row in rows:
        out += '<tr>' + ''.join((f'<th scope="row">{v}</th>' if i == 0 else f'<td>{v}</td>') for i, v in enumerate(row)) + '</tr>\n'
    return out + '</tbody></table>\n</div>\n{:/}\n\n'


def disclosure(label, body):
    return f'\n<details markdown="1"><summary>{esc(label)}</summary>\n\n{body}\n</details>\n\n'


def header(name, heading):
    return f'''---
layout: default
title: "{heading}"
author: "Benjamin De Kosnik <bkoz@gnu.org>"
description: "Mellon 7.7: {heading}"
---

{{::nomarkdown}}
<img src="../resources/a60-logo-block-gray.simple.svg?sanitize=true" height="50" width="100" alt="Alpha60">
<link rel="stylesheet" href="../resources/mellon-7.7-analysis.css">
{{:/}}

[Black-led results](../index.html) · [M1](francophone.html) · [M2](anglophone.html) · [M3](romance-genre.html) · [M4](wakanda-forever.html)

# {heading}

Mellon 7.7 · Published 2026-09-24 · Round 3 slice definitions

'''


def figure(name, alt, caption):
    return f'''\n{{::nomarkdown}}
<figure class="analysis-figure">
<div class="analysis-chart-scroll" role="region" aria-label="{esc(alt)}" tabindex="0"><img src="../resources/mellon-7.7-{name}.svg" alt="{esc(alt)}"></div>
<figcaption>{esc(caption)} {link('Download SVG', '../resources/mellon-7.7-'+name+'.svg')}.</figcaption>
</figure>
{{:/}}\n\n'''


def save_figure(site, fig, name, heading, description):
    path = site / 'resources' / f'mellon-7.7-{name}.svg'
    fig.savefig(path, bbox_inches='tight', metadata={'Date': None, 'Creator': 'Alpha60 Mellon 7.7'})
    plt.close(fig)
    ns = 'http://www.w3.org/2000/svg'
    ET.register_namespace('', ns)
    tree = ET.parse(path)
    root = tree.getroot()
    root.set('role', 'img')
    root.set('aria-labelledby', 'chart-title chart-description')
    ET.SubElement(root, '{'+ns+'}title', {'id': 'chart-title'}).text = heading
    ET.SubElement(root, '{'+ns+'}desc', {'id': 'chart-description'}).text = description
    tree.write(path, encoding='unicode')


class Reports:
    def __init__(self, data, names, genres, site, weekly_m4=None, graphs=None):
        self.d, self.o, self.names, self.genres, self.site = data, data['objects'], names, genres, site
        self.weekly_m4, self.graphs = weekly_m4, graphs

    def country(self, code): return f'{self.names.get(code, code)} ({code})'
    def object(self, key): return link(title(key), self.o[key]['audit_url']) + f'<br><code>{esc(key)}</code>'
    def metric(self, record, group='africa60', role='downloaders', nonhosting=False):
        return calc.measure(record, set(self.d['groups'].get(group, [group])), role, nonhosting)
    def share(self, record, group='africa60', **kw): return percent(self.metric(record, group, **kw)['share'])

    def country_list(self, codes):
        return '; '.join(self.country(c) for c in sorted(codes)) + '.\n\n'

    def samples(self, keys):
        rows = []
        for k in keys:
            r = self.o[k]
            rows.append([self.object(k), r['dates'].replace('-to-', ' to '), number(r['sample_days']),
                         number(r['world']['downloaders']['size']), number(r['source_world']['downloaders']),
                         percent(100*r['world']['downloaders']['size']/r['source_world']['downloaders'])])
        return table('Full cumulative samples and export coverage', ['Object / audit', 'Sample dates', 'Days', 'World export weight', 'World source total', 'Export / source'], rows)

    def coverage(self, keys):
        rows = []
        for k in keys:
            w = self.d['weekly'][k]
            partial = ', '.join(str(v['week']) for v in w['weeks'] if v['partial']) or 'None'
            notes = [x.lstrip('- ') for x in w['coverage_notes'] if 'hourly gap:' in x or 'missing Day index' in x]
            note = '; '.join(notes) or ('Day-product or release evidence; no separate hourly completeness claim' if any('Evidence:' in x for x in w['coverage_notes']) else 'No hourly discontinuity reported in source audit')
            rows.append([self.object(k), partial, esc(note)])
        return disclosure('Coverage flags and source-audit limits', table('Coverage relevant to window checks', ['Object', 'Partial week flags in 1–7', 'Audit evidence'], rows))

    def weekly_table(self, study, groups):
        keys = self.d[study]['keys']
        rows = []
        for k in keys:
            for label, record in [('Weeks 1–7', self.d['weekly'][k]['first_seven_sum']), ('Common unflagged weeks', self.d[study]['common_full_weeks'][k])]:
                rows.append([self.object(k), label, number(record['world']['downloaders']['size'])] + [self.share(record, g) for g in groups])
        return table('Matched elapsed-window sensitivity', ['Object', 'Window', 'World interval weight'] + [g.replace('_', ' ')+' share' for g in groups], rows)

    def methods(self, keys, weekly=True):
        source = self.d['slice_source']
        result = '''\n## Methods and reproducibility

**Cohort.** These studies use the [published Round 3 slices](https://alpha60-devops.github.io/alpha60-results/docs/slices.html), definition `h15-round3-20260923-v3`: 382 confirmed Black-led media objects and its 216-object African-led-global subset. African-led-global uses reviewed African identity or named African origin/descent; Black-led also includes reviewed Black/African-American/diaspora evidence. The geographic qualification branch does not assert that every qualifying person identifies as Black. Candidate-only rows are excluded. These analyses use the annual exports for that cohort; the site's earlier curated roster has a different scope.

**Measurement.** “Downloader weight” is the sum of published geographic swarm weights. It is not a count of viewers, completed downloads, citizens, or distinct people. Regional share = 100 × regional downloader weight / worldwide downloader weight **from the same export and window**. Unknown-country weights stay in the denominator. Uploaders have their own denominator. Percentages are not population or Internet-penetration adjusted. Hosting exclusion subtracts the hosting field from numerator and denominator only; overlapping network flags are never summed, and this does not identify residential people or remove all VPNs.

**Source boundary.** Read top-level features from the annual cumulative aggregate GeoJSON once. Do not add its nested torrent features again. Exports use H3 resolution 5, publication minimum 3, and data version `20260701`. Values omitted by publication filtering are not imputed; a missing country is shown as “not reported” in country tables. This analysis uses published GeoJSON, not newly regenerated raw sample-cache counts. The source total and export coverage are recorded separately. All ten fields for both downloader/uploader roles are retained in the ledger.

'''
        if weekly:
            result += '''**Time checks.** Numbered weekly GeoJSON top-level features are interval observations. Weeks 1–7 are the first seven bins from each sample's start, not necessarily from its release date. Their sums can exceed the full cumulative weight because observations recur across weeks. Never compare a weekly sum with a cumulative count as if both were unique totals. The “common unflagged” check removes a week from all compared objects when any has a partial flag, a short bin, or an overlapping dated audit gap. Unflagged bins do not certify complete raw hourly sampling. No missing hours or days are rescaled.

'''
        result += f"[Pinned slice evidence]({source['url']}); SHA-256 `{source['sha256']}`. Each object and weekly file has its own repository revision, hash and source link in the ledger.\n\n"
        result += '''- [Full calculation ledger, compressed JSON](../data/mellon-7.7-analysis.json.gz).
- [Compact object metrics and all 382 ranks, JSON](../data/mellon-7.7-summary.json).
- [Language sets and references](../data/black-led-7.7-language-groups.json); [genre annotations and evidence](../data/black-led-7.7-genres.json).
- Download the [collector](../resources/analyze-mellon-7-7-black.py), [calculator](../resources/calculate-mellon-7-7-black.py), [report/figure renderer](../resources/render-mellon-7-7-black.py) and [validation script](../resources/check-mellon-7-7-black.py) into one directory. The collector and calculator use Python's standard library; the renderer also requires matplotlib.

With the source repositories checked out at the ledger's recorded commits:

```sh
python3 analyze-mellon-7-7-black.py --source-root /path/to/checkouts --output calculations
python3 calculate-mellon-7-7-black.py --input calculations/cumulative.json --source-root /path/to/checkouts --language-config black-led-7.7-language-groups.json --genre-config black-led-7.7-genres.json --output calculations/analysis.json
```

'''
        if keys:
            result += disclosure('Pinned measurement sources', '\n'.join(f"- [{k}: cumulative aggregate GeoJSON]({next(s['url'] for s in self.o[k]['sources'] if s['path'].endswith('.geojson.gz'))}); [sample audit]({self.o[k]['audit_url']})." for k in keys) + '\n')
        return result

    def francophone(self):
        keys = self.d['m1']['keys']
        text = header('francophone', PAGES[0][1])
        text += '''**Lupin does not uniformly lead.** Its two samples have Francophone world shares of **10.15% and 8.37%**, above *Wakanda Forever* (**6.71%**) but below the original *Black Panther* (**13.13%**). Within Francophone Africa60, only Lupin 02 exceeds Wakanda Forever. These four observations do not establish a general advantage for French or non-USA production.

## Which countries count?

The operational Francophone set follows the **OIF 2022 “everyday French” country list, footnote 4**, including France's separately coded overseas territories: 36 sovereign country codes plus 12 territory codes. It is broader than countries with French as a sole official language. Canada, Belgium and Switzerland are represented by whole-country codes because this comparison does not have language-region boundaries. The fixed set is applied to every sample year; it does not assert that each observed peer speaks French. [OIF source](https://www.francophonie.org/sites/default/files/2022-03/Synthese_La_langue_francaise_dans_le_monde_2022.pdf).

'''
        text += disclosure('All 48 Francophone country and territory codes', self.country_list(self.d['groups']['francophone']))
        text += f"The intersection with Alpha60's exact Africa60 contains **{len(self.d['groups']['francophone_africa60'])} codes**:\n\n" + self.country_list(self.d['groups']['francophone_africa60'])
        text += '## Cumulative comparison\n\nLupin 02 and 03 are recorded as French productions with explicit non-USA production. Both Black Panther films have explicit USA production. Production classification comes from the reviewed slice evidence, not from inferred citizenship.\n\n'
        text += self.samples(keys)
        text += table('Regional weight and share of the worldwide export', ['Object', 'Francophone weight', 'Francophone share', 'Francophone Africa60 share', 'Francophone outside Africa60 share', 'All Africa60 share'], [[self.object(k), number(self.metric(self.o[k], 'francophone')['count'])] + [self.share(self.o[k], g) for g in ['francophone','francophone_africa60','francophone_nonafrica','africa60']] for k in keys])
        text += figure('francophone', 'Black Panther has the highest full-window Francophone share; Lupin 02 and 03 exceed Wakanda Forever.', 'Stacked components are Francophone Africa60 and the rest of the Francophone set; denominator is each worldwide cumulative export.')
        countries = ['FRA','CAN','BEL','CHE','DZA','MAR','CIV','SEN','TUN','MUS']
        text += table('Selected Francophone country shares of worldwide downloader weight', ['Country'] + [title(k) for k in keys], [[esc(self.country(c))] + [self.share(self.o[k], c) if c in self.o[k]['countries'] else 'Not reported' for k in keys] for c in countries])
        text += '''Lupin 03 has the largest **France** share (4.19%), yet only 1.08% in Francophone Africa60. The original Black Panther is stronger in Algeria, Morocco, Côte d'Ivoire and Senegal than either Lupin sample. Grouping France and Francophone African countries into one number conceals this difference. Wakanda Forever's higher **all-Africa60** share is driven mainly outside the Francophone subset.

## Window and network checks

The ordering of all-Francophone shares survives both weeks 1–7 and the common unflagged weeks **4, 6 and 7**. For Francophone Africa60, the order is Black Panther, Lupin 02, Wakanda Forever, Lupin 03 in all three windows. Lupin 03's reported 23-hour gap is in December, beyond its first seven weeks; its full-window figure remains unadjusted.

'''
        text += self.weekly_table('m1', ['francophone','francophone_africa60'])
        text += table('Full-window network and uploader sensitivity', ['Object','Francophone share excluding hosting','Francophone Africa60 excluding hosting','Francophone uploader share'], [[self.object(k),self.share(self.o[k],'francophone',nonhosting=True),self.share(self.o[k],'francophone_africa60',nonhosting=True),self.share(self.o[k],'francophone',role='uploaders')] for k in keys])
        text += self.coverage(keys)
        text += '''## Observations and next questions

1. Separate France and other non-African Francophone countries from Francophone Africa60 when testing a French-language association. Neither geography nor production origin identifies the language of a downloaded edition.
2. Lupin 03 shifts toward France while losing Francophone Africa60 share relative to Lupin 02. Compare language tracks, subtitle editions and torrent availability before attributing that shift to audience preference.
3. Black Panther's 2018 sample and the later samples cover different release stages and years. More films and serials with matched observation windows are needed to estimate a production-country effect.

'''
        return text + self.methods(keys)

    def anglophone(self):
        pairs = self.d['m2']['selected_pairs']
        keys = [p[v] for p in pairs for v in ['nonusa','usa']]
        text = header('anglophone', PAGES[1][1])
        text += '''**No consistent USA-production advantage appears in these three matched comparisons.** Atlanta has more non-USA Anglophone share than The Power; The Underground Railroad slightly exceeds Intergalactic; Black Mirror exceeds The Old Man. All three non-USA-produced objects have a higher USA share than their matched USA-produced controls, although hosting exclusion reverses that difference for The Power versus Atlanta.

## Language geography and cohort

The core set contains **86 ISO-3 country/territory codes** from the reference's official or predominant English tables: 57 sovereign states and 29 separately coded territories. USA is reported separately, leaving **85 non-USA Anglophone codes**. Countries listed only under “working language” enter a second, broader sensitivity set. This is a fixed geographic classification, not a measure of individual language use or a retrospective claim about each country's legal status. [Pinned reference revision](''' + self.d['language_groups']['anglophone']['source_url'] + ''').

'''
        text += disclosure('Core Anglophone countries and territories, excluding USA', self.country_list(self.d['groups']['anglophone_ex_usa']))
        text += disclosure('Anglophone Africa60 intersection and working-language additions', f"**{len(self.d['groups']['anglophone_africa60'])} core Africa60 codes:**\n\n" + self.country_list(self.d['groups']['anglophone_africa60']) + '**Working-language additions (sensitivity only):**\n\n' + self.country_list(self.d['language_groups']['anglophone']['working_language_additions']))
        text += '''### How the pairs were selected

The non-USA pool is confirmed **African-led-global**, explicit non-USA production, and recorded original English. The control pool is confirmed **Black-led** with explicit USA production. For this Anglophone question, the English-language restriction yields five eligible non-USA objects from four canonical works; objects with missing language metadata are not silently assigned English. Lupin is covered separately in M1.

Match within film/serial class and within two sample-start years; require duration ratio ≤1.25 and worldwide cumulative export-weight ratio ≤1.5. Sort by the sum of absolute log duration and volume ratios, then greedily take three pairs without reusing a canonical work. **Regional shares are not used for selection.** All selected pairs have exactly equal sample lengths and world volumes within 1.56%. The full candidate list and tie-breaking rules are in the ledger. A season versus episode comparison remains possible within the serial class; these are descriptive matches, not causal controls.

'''
        rows = []
        for p in pairs:
            a,b = p['nonusa'],p['usa']
            rows.append([self.object(a),self.object(b),f"{self.o[a]['year']} / {self.o[b]['year']}",f"{self.o[a]['sample_days']} / {self.o[b]['sample_days']}",f"{number(self.o[a]['world']['downloaders']['size'])} / {number(self.o[b]['world']['downloaders']['size'])}",f"{100*(p['world_volume_ratio']-1):.2f}%"])
        text += table('Non-USA versus USA production matches', ['Non-USA object','USA object','Sample years','Days','World export weights','Volume difference'], rows)
        text += '''All three selected non-USA works have reviewed UK country-of-origin evidence. The Power's canonical country-name list is empty, but its completed slice decision cites explicit Wikidata P495 = United Kingdom; the missing display list is not the basis of the non-USA decision. [Production evidence](https://www.wikidata.org/wiki/Q108372670).

## Geography of the matched objects

'''
        text += table('Worldwide cumulative downloader shares', ['Object','Production group','Anglophone except USA','USA','Anglophone Africa60','All Africa60','Broader English set except USA'], [[self.object(k),'Non-USA' if not self.o[k]['usa_production']['value'] else 'USA']+[self.share(self.o[k],g) for g in ['anglophone_ex_usa','usa','anglophone_africa60','africa60','anglophone_working_ex_usa']] for k in keys])
        text += figure('anglophone','Non-USA Anglophone and USA shares vary across the three matched production pairs.','Full cumulative export shares. The two bars for each object are disjoint country groups; they do not exhaust the world.')
        countries = ['GBR','CAN','AUS','IND','PHL','ZAF','NGA','KEN','USA']
        text += disclosure('Country distributions for all six objects',table('Selected country shares of worldwide downloader weight',['Country']+[title(k) for k in keys],[[esc(self.country(c))]+[self.share(self.o[k],c) if c in self.o[k]['countries'] else 'Not reported' for k in keys] for c in countries]))
        text += '''The 2021 pair is strikingly similar in USA share: **39.46% Intergalactic and 38.45% Underground Railroad**. Their difference in Africa60 is larger, at 2.86% versus 4.73%. Conversely, Black Mirror exceeds The Old Man in both USA and non-USA Anglophone share. These patterns cross the production boundary.

## Sensitivity to hosting and coverage

'''
        text += table('Full-window network sensitivity', ['Object','Anglophone except USA, excluding hosting','USA, excluding hosting','USA hosting / USA downloader weight','Anglophone except USA uploader share','USA uploader share'], [[self.object(k),self.share(self.o[k],'anglophone_ex_usa',nonhosting=True),self.share(self.o[k],'usa',nonhosting=True),percent(100*self.o[k]['countries']['USA']['downloaders']['hosting']/self.o[k]['countries']['USA']['downloaders']['size']),self.share(self.o[k],'anglophone_ex_usa',role='uploaders'),self.share(self.o[k],'usa',role='uploaders')] for k in keys])
        text += '''The Power's USA share falls from 13.64% to **6.08%** after excluding hosting, below Atlanta's **6.63%**. In contrast, the two 2021 objects retain USA shares around 37–38%. Hosting sensitivity therefore changes a specific pairwise interpretation, rather than supporting a universal correction.

The direction of each pair's non-USA Anglophone difference survives weeks 1–7 and a per-pair check removing partial or gap-affected weeks. Underground Railroad is missing eight Day products, including a day in week 7, so its equal nominal duration does not mean equal observed coverage. No replacement counts are invented.

'''
        rows=[]
        for p in pairs:
            for k in [p['nonusa'],p['usa']]:
                for label,r in [('Weeks 1–7',self.d['weekly'][k]['first_seven_sum']),('Common weeks '+', '.join(map(str,p['common_full_week_indices'])),p['common_full_weeks'][k])]:
                    rows.append([self.object(k),label,number(r['world']['downloaders']['size']),self.share(r,'anglophone_ex_usa'),self.share(r,'usa'),self.share(r)])
        text += disclosure('Matched elapsed-window counts and shares',table('Per-pair elapsed-window checks',['Object','Window','World interval weight','Anglophone except USA','USA','Africa60'],rows))
        text += self.coverage(keys)
        text += '''## Observations and next questions

1. Production origin alone does not order the matched distributions. Repeating the match on a larger non-USA pool, with complete original-language metadata, would test whether these three pairs generalize.
2. Atlanta's Africa60 concentration is higher than The Power's despite almost identical world volume. Genre, release schedule and torrent availability remain plausible alternative explanations.
3. Investigate the common high USA concentration of the 2021 pair using torrent and network inventories. It persists after hosting exclusion and should not be dismissed as hosting alone.

'''
        return text + self.samples(keys) + self.methods(keys)

    def romance(self):
        m = self.d['m3']; keys = m['top20']
        text = header('romance-genre', PAGES[2][1])
        text += '''**Romance has exceptional leaders, but a modest overall advantage.** The Lovebirds ranks **1st of 382** at **29.44% Africa60 share**; Queen Charlotte ranks **11th** at **15.85%**. Across all 17 romance-tagged objects, the median is **4.28%**, versus **3.77%** for the other 365. The romance median is lower within television/serial objects and almost equal to the rest when South Africa is excluded.

## Cohort, genre definition and ranking

M3 ranks **all 382 confirmed Round 3 Black-led media objects**, representing **217 canonical works**, by their own full cumulative Africa60 downloader weight divided by their own worldwide export weight. It uses neither a USA-production filter nor the older 88-object site roster. The numerator uses the exact Africa60 set supplied with the authoritative slices.

Genre annotations combine canonical metadata, non-deprecated Wikidata P136 claims, and genre descriptors from cached Wikipedia lead definitions. The same enrichment rule is applied across the whole cohort, not only to top-ranked objects. All 382 now have at least one source tag; annotations and revision/hash evidence are downloadable below. Broad genre families overlap: a romantic comedy counts under both romance and comedy. The romance rule matches “romance” or “romantic”; genre labels are not inferred from swarm performance. Film/serial strata follow the metadata type, which can classify documentary and interview objects coarsely.

The 217-work check groups repeated episodes/seasons by canonical work and first takes each work's median object share. A work is romance-tagged if any sampled object carries a romance tag. This reduces repeated-franchise weighting without claiming independent or randomly sampled works.

'''
        text += disclosure('Exact Africa60 country and territory set',self.country_list(self.d['africa60']))
        text += '## Top 20 by Africa60 share\n\n'
        text += figure('romance-genre','The Lovebirds leads the top 20 at 29.44%; five top-20 objects carry a romance tag.','Each bar is a full cumulative export share. Orange marks any romance tag; blue marks other tagged objects. Sample lengths differ and are listed below.')
        rows=[]
        for k in keys:
            r=self.o[k]; g=self.genres['objects'][k]
            url=(g.get('lead_descriptor_evidence') or {}).get('source_url') or g.get('source_url')
            tags='; '.join(r['genre_families'])
            rows.append([r['africa60_rank'],self.object(k),number(r['sample_days']),number(self.metric(r)['count']),number(r['world']['downloaders']['size']),self.share(r),link(tags,url) if url else esc(tags)])
        text += table('The full-cohort Africa60 top 20',['Rank','Object / audit','Days','Africa60 weight','World export weight','Africa60 share','Genre families / evidence'],rows)
        text += '''Five of the top 20 have a romance tag: Lovebirds, Coming 2 America, Queen Charlotte, Cinderella and Songbird. That is **25% of the top 20**, versus **4.45% of the cohort**. The leading group is nevertheless diverse: ten thriller/crime/mystery objects, eight science-fiction/fantasy, five action/adventure, four comedy, two music/musical, two documentary/interview and two Western objects. These counts overlap and must not be added as exclusive categories. Short samples include Coming 2 America (23 days) and two Into the Badlands episodes (21 and 8 days).

'''
        text += table('Overlapping genre families across all 382 objects',['Genre family','Objects','Top-20 objects','Median Africa60 share','Pooled Africa60 share','Median excluding hosting','Median uploader share'],[[esc(r['family']),r['objects'],r['top20_objects'],percent(r['median_share']),percent(r['pooled_share']),percent(r['median_nonhosting_share']),percent(r['median_uploader_share'])] for r in m['genre_summary']])
        text += '''A median gives each sampled object equal weight; a pooled share divides summed Africa60 weights by summed world weights and gives large swarms more influence. Neither is a deduplicated audience across titles. Genre tags are descriptive, non-exclusive and source-dependent; a large family count does not establish its causal effect.

## The named romance examples

'''
        text += table('Lovebirds, Queen Charlotte and every sampled Bridgerton object',['Object','Rank / 382','Days','Africa60 weight','World export weight','Africa60 share','Excluding hosting','Uploader share'],[[self.object(k),self.o[k]['africa60_rank'],self.o[k]['sample_days'],number(self.metric(self.o[k])['count']),number(self.o[k]['world']['downloaders']['size']),self.share(self.o[k]),self.share(self.o[k],nonhosting=True),self.share(self.o[k],role='uploaders')] for k in m['named_romance_keys']])
        text += '''Bridgerton 02 ranks **31st** (10.32%), while season-four parts rank **321st and 335th** (1.64% and 1.52%). The season-four Africa60 weights are larger than season two's, but their worldwide denominators grew much faster. “Popular” by absolute observed weight and “high African share” answer different questions.

## Does the association survive other views?

'''
        labels={'all':'All objects','at_least_49_days':'At least 49 sample days','days_56_to_112':'56–112 sample days','films':'Metadata film stratum','serials':'Metadata non-film / serial stratum','africa_ex_south_africa':'Africa60 excluding South Africa'}
        rows=[]
        for name,v in m['romance_comparison'].items():
            a,b=v['romance'],v['other_tagged']
            rows.append([labels[name],f"{a['objects']} / {b['objects']}",percent(a['median_share']),percent(b['median_share']),f"{a['median_share']-b['median_share']:+.2f}"])
        text += table('Romance versus other tagged objects',['Comparison','Objects: romance / other','Romance median','Other median','Difference (pp)'],rows)
        text += '''The film stratum favors romance (**13.08% versus 6.60%**), but the non-film/serial stratum does not (**3.20% versus 3.60%**). Excluding South Africa nearly removes the overall median difference (**2.58% versus 2.53%**). The 56–112-day subset is strongly positive but contains only nine romance objects and selects a different mix of titles. These checks support a concentrated, format-sensitive association rather than a universal romance effect.

Collapsing repeated samples gives **13 romance canonical works versus 204 others**, with median work-level shares **4.64% versus 3.70%**. Excluding hosting raises both object-level medians to **4.86% versus 4.22%**. These are descriptive robustness checks, not statistical significance tests; the curated sample and correlated objects do not justify treating 382 rows as independent random draws.

'''
        overlap=len(set(keys)&set(m['top20_nonhosting']))
        text += f"**{overlap} of 20** top-ranked objects remain in the top 20 after hosting exclusion. The complete alternative ranking and role/network values are in the ledger.\n\n"
        text += '''## Hypotheses to test

1. Relationship stories and prominent Black leads may encourage discovery or identification across national settings. Testing this needs audience and language-edition evidence; swarm geography cannot reveal motivation or demographic identity.
2. A few romantic comedies, period romances and musical crossovers may drive the apparent genre effect. The stronger film result and South Africa sensitivity make country-by-format comparisons more informative than a single continental genre average.
3. Availability, subtitles/dubs, platform access, release timing and which torrents were collected may shape both the numerator and denominator. Compare these factors before interpreting lower season-four Bridgerton shares as declining African interest.

'''
        text += disclosure('Every object, rank, sample window and genre family',table('Complete Black-led ranking',['Rank','Object','Sample dates','Days','Africa60 weight','World export weight','Africa60 share','Genre families'],[[self.o[k]['africa60_rank'],self.object(k),self.o[k]['dates'].replace('-to-',' to '),self.o[k]['sample_days'],number(self.metric(self.o[k])['count']),number(self.o[k]['world']['downloaders']['size']),self.share(self.o[k]),esc('; '.join(self.o[k]['genre_families']))] for k in m['ranked_keys']]))
        return text+self.methods(keys,weekly=False)

    def wakanda(self):
        keys=self.d['m4']['keys']; a,b,c,e=keys
        text=header('wakanda-forever',PAGES[3][1])
        text+='''**The sequel grows in Africa60 share; the two later serials have much lower shares.** Full-window share rises from **9.72% Black Panther to 11.20% Wakanda Forever**, then is **1.72% Ironheart and 1.32% Eyes of Wakanda**. The sequel's increase and the serials' lower shares persist in matched elapsed windows. These observations describe sampled swarm circulation; they cannot establish growth or loss of individual fans.

## Four objects, three forms, unequal full windows

The first two objects are live-action feature films, Ironheart is a live-action television season, and Eyes of Wakanda is an animated television season. All have reviewed USA production. The original film has 52 sampled days; the other three have 182. Treating those full cumulative counts as equal-exposure measurements would be misleading. First-seven-week checks below align the elapsed sample clock, with separate coverage checks.

'''
        text+=self.samples(keys)
        text+=table('Africa60 circulation in the full cumulative exports',['Object','Africa60 weight','Africa60 / world','Africa60 excluding hosting','Africa60 uploader share','Africa60 except South Africa'],[[self.object(k),number(self.metric(self.o[k])['count']),self.share(self.o[k]),self.share(self.o[k],nonhosting=True),self.share(self.o[k],role='uploaders'),self.share(self.o[k],'africa_ex_zaf')] for k in keys])
        text+='''Wakanda Forever has 3,405,102 Africa60 weight versus 1,326,273 for Black Panther, but its window is 3.5 times as long. Ironheart's 1,414,228 is slightly above the original film's full count despite a far lower regional share and a much longer sample. This is why both count and share, with window length, are necessary.

## Matching the elapsed observation window

'''
        text+=figure('wakanda-forever','Wakanda Forever exceeds Black Panther in Africa60 share in all three windows; Ironheart and Eyes of Wakanda are lower.','Full cumulative share, summed weeks 1–7 share, and common unflagged weeks 2, 3, 4, 6, 7. Each uses its own matching world denominator; counts across window types are not interchangeable.')
        rows=[]
        for k in keys:
            for label,r in [('Weeks 1–7',self.d['weekly'][k]['first_seven_sum']),('Common weeks 2, 3, 4, 6, 7',self.d['m4']['common_full_weeks'][k])]:
                rows.append([self.object(k),label,number(self.metric(r)['count']),number(r['world']['downloaders']['size']),self.share(r),self.share(r,nonhosting=True),self.share(r,role='uploaders')])
        text+=table('Equal elapsed windows: sums of interval observations',['Object','Window','Africa60 interval weight','World interval weight','Africa60 share','Excluding hosting','Uploader share'],rows)
        text+='''Over weeks 1–7, Africa60 share rises **10.37% → 14.43%** from the first film to the sequel. Africa60 interval weight rises **1,603,650 → 2,926,901**. In common unflagged weeks 2, 3, 4, 6 and 7, shares are **10.42%, 14.79%, 3.35% and 2.04%**, respectively. Removing hosting leaves the same ordering. Uploader shares show a much smaller separation and do not reproduce the downloader sequel increase in every window; the “growth” finding is specific to the downloader measure.

'''
        text+=self.coverage(keys)
        text+='## Which countries gained?\n\nChanges below are **percentage points of worldwide downloader weight**, not percent growth within a country. Ranking requires both objects to have an emitted country observation; no unreported country is treated as zero.\n\n'
        def country_changes(x,y):
            shared=set(self.d['africa60'])&x['countries'].keys()&y['countries'].keys()
            return sorted([(code,self.metric(y,code)['share']-self.metric(x,code)['share']) for code in shared],key=lambda z:(-z[1],z[0]))
        rows=[]
        x=self.d['weekly'][a]['first_seven_sum']; y=self.d['weekly'][b]['first_seven_sum']
        for code,delta in country_changes(x,y)[:8]:
            rows.append([esc(self.country(code)),self.share(x,code),self.share(y,code),f'{delta:+.3f}',number(self.metric(y,code)['count']-self.metric(x,code)['count']),f"{self.metric(self.o[b],code)['share']-self.metric(self.o[a],code)['share']:+.3f}"])
        text+=table('Largest first-seven-week share gains: Black Panther to Wakanda Forever',['Country','Black Panther share','Wakanda Forever share','Change (pp)','Interval weight change','Full-window change (pp)'],rows)
        text+='''South Africa leads the matched-window increase (**+4.19 percentage points**), followed by Nigeria (+1.03), Kenya (+0.43), Botswana (+0.42) and Ghana (+0.38). In full-window shares, South Africa and Nigeria still lead, while Ethiopia and Mozambique move higher in the gain ranking. The result depends partly on when circulation is observed.

The full-window Africa60 share **outside South Africa falls from 8.27% to 7.21%** between the films, even as the Africa60 total rises. A claim of uniform continental expansion would conceal this concentration. Algeria, Morocco, Côte d'Ivoire and Senegal lose world share between the films; see the Francophone comparison for those values.

Relative to Wakanda Forever, Ironheart's largest shared-country full-window share gain is a small **+0.006 pp in DR Congo**, while its largest raw full-count gain is in Morocco (+47,358), where world share falls. In weeks 1–7, Republic of the Congo instead leads the positive differences (+0.061 pp, +16,642 interval weight). **DR Congo (COD) and Republic of the Congo (COG) are different countries.** No shared Africa60 country gains world share from Wakanda Forever to Eyes of Wakanda in either the full or first-seven-week view.

'''
        rows=[]
        for k in [c,e]:
            y=self.d['weekly'][k]['first_seven_sum']; x=self.d['weekly'][b]['first_seven_sum']
            for code,delta in country_changes(x,y):
                rows.append([self.object(k),esc(self.country(code)),self.share(x,code),self.share(y,code),f'{delta:+.4f}',number(self.metric(y,code)['count']-self.metric(x,code)['count'])])
        text+=disclosure('All shared-country changes from Wakanda Forever to each serial',table('First-seven-week changes from Wakanda Forever',['Later object','Country','Wakanda Forever share','Later share','Change (pp)','Interval weight change'],rows))
        text+='''## Observations and next questions

1. Wakanda Forever's Africa60 downloader expansion is geographically concentrated, especially in South Africa and Nigeria. Track those countries separately from Francophone Africa and compare edition/torrent inventories.
2. Film, live-action serial and animation differ here, but format is confounded with title, year, release pattern and sampling. One animated season cannot identify an animation effect. A wider matched franchise study would be needed.
3. Use “circulation share increased” rather than “the fandom grew.” Repeated torrent participation, network location, platform availability and differing observation stages prevent an inference about unique fans or their retention across releases.

'''
        if self.weekly_m4:
            from mellon_7_7_weekly_report import render_weekly
            section = render_weekly(self, self.weekly_m4, self.graphs, table, figure, disclosure, number, title)
            text = text.replace('## Matching the elapsed observation window', section+'## Matching the elapsed observation window')
        return text+self.methods(keys)

    def charts(self):
        plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'svg.fonttype':'none','svg.hashsalt':'mellon-7.7','axes.spines.top':False,'axes.spines.right':False})
        keys=self.d['m1']['keys']; fig,ax=plt.subplots(figsize=(10,4.2))
        inside=[self.metric(self.o[k],'francophone_africa60')['share'] for k in keys]
        outside=[self.metric(self.o[k],'francophone_nonafrica')['share'] for k in keys]
        ax.barh(range(4),inside,color=BLUE,label='Francophone Africa60')
        ax.barh(range(4),outside,left=inside,color=ORANGE,label='Other Francophone countries')
        for i,(x,y) in enumerate(zip(inside,outside)):ax.text(x+y+.15,i,f'{x+y:.2f}%',va='center')
        ax.set(yticks=range(4),yticklabels=[title(k) for k in keys],xlim=(0,15.5),xlabel='Share of worldwide cumulative downloader weight (%)',title='Francophone share: Lupin and Black Panther')
        ax.invert_yaxis();ax.legend(loc='upper center',bbox_to_anchor=(.5,-.22),ncol=2,frameon=False);ax.grid(axis='x',alpha=.2);ax.set_axisbelow(True)
        save_figure(self.site,fig,'francophone','Francophone share by object','Four full cumulative samples; exact values and dates in the companion table.')
        keys=[p[v] for p in self.d['m2']['selected_pairs'] for v in ['nonusa','usa']];fig,ax=plt.subplots(figsize=(10,5.8))
        for off,g,color,label in [(-.18,'anglophone_ex_usa',BLUE,'Anglophone except USA'),(.18,'usa',ORANGE,'USA')]:
            values=[self.metric(self.o[k],g)['share'] for k in keys]
            ax.barh([i+off for i in range(6)],values,height=.32,color=color,label=label)
            for i,v in enumerate(values):ax.text(v+.35,i+off,f'{v:.2f}%',va='center',fontsize=9)
        ax.set(yticks=range(6),yticklabels=[title(k)+(' · non-USA' if i%2==0 else ' · USA') for i,k in enumerate(keys)],xlim=(0,46),xlabel='Share of worldwide cumulative downloader weight (%)',title='Three pairs matched on duration and world volume')
        ax.invert_yaxis();ax.legend(loc='upper center',bbox_to_anchor=(.5,-.14),ncol=2,frameon=False);ax.grid(axis='x',alpha=.2);ax.set_axisbelow(True)
        save_figure(self.site,fig,'anglophone','Anglophone and USA shares for matched objects','Alternating rows are non-USA and USA productions. Each pair has equal sample length.')
        keys=self.d['m3']['top20'];fig,ax=plt.subplots(figsize=(10,9))
        values=[self.metric(self.o[k])['share'] for k in keys]
        ax.barh(range(20),values,color=[ORANGE if 'Romance' in self.o[k]['genre_families'] else BLUE for k in keys])
        for i,v in enumerate(values):ax.text(v+.25,i,f'{v:.2f}%',va='center',fontsize=10)
        ax.set(yticks=range(20),yticklabels=[f'{i+1}. {k}' for i,k in enumerate(keys)],xlim=(0,33.5),xlabel='Africa60 / worldwide cumulative downloader weight (%)',title='Top 20 of 382 confirmed Black-led objects')
        ax.invert_yaxis();ax.grid(axis='x',alpha=.2);ax.set_axisbelow(True)
        from matplotlib.patches import Patch
        ax.legend(handles=[Patch(color=ORANGE,label='Any romance tag'),Patch(color=BLUE,label='Other tagged object')],loc='upper center',bbox_to_anchor=(.5,-.09),ncol=2,frameon=False)
        save_figure(self.site,fig,'romance-genre','Africa60 top 20 of 382 Black-led objects','Ranked by full cumulative downloader share. Five objects carry a romance tag; all values appear in the adjacent table.')
        keys=self.d['m4']['keys'];fig,ax=plt.subplots(figsize=(10,4.7))
        windows=[('Full cumulative',self.o,BLUE,'o',-.22),('Weeks 1–7',{k:self.d['weekly'][k]['first_seven_sum'] for k in keys},ORANGE,'s',0),('Common weeks 2, 3, 4, 6, 7',self.d['m4']['common_full_weeks'],GRAY,'^',.22)]
        for label,records,color,marker,off in windows:
            values=[self.metric(records[k])['share'] for k in keys]
            ax.scatter(values,[i+off for i in range(4)],label=label,color=color,marker=marker,s=65)
            for i,v in enumerate(values):ax.text(v+.2,i+off,f'{v:.2f}%',va='center',fontsize=9)
        ax.set(yticks=range(4),yticklabels=[title(k) for k in keys],xlim=(0,17),xlabel='Africa60 share of matching worldwide downloader weight (%)',title='Black Panther universe: compare within each window')
        ax.invert_yaxis();ax.legend(loc='upper center',bbox_to_anchor=(.5,-.18),frameon=False,ncol=1);ax.grid(axis='x',alpha=.2);ax.set_axisbelow(True)
        save_figure(self.site,fig,'wakanda-forever','Africa60 shares across the four Black Panther universe objects','The sequel exceeds the first film in all three downloader windows. Both later serials have lower shares.')


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--input',type=Path,required=True);ap.add_argument('--site',type=Path,required=True)
    ap.add_argument('--language-config',type=Path,required=True);ap.add_argument('--genre-config',type=Path,required=True)
    ap.add_argument('--country-names',type=Path,required=True)
    ap.add_argument('--weekly-m4',type=Path)
    ap.add_argument('--izzi',type=Path)
    args=ap.parse_args();raw=args.input.read_bytes();data=json.loads(gzip.decompress(raw) if args.input.suffix=='.gz' else raw)
    names={v['alpha-3']:v['name'] for v in json.loads(args.country_names.read_text())}
    for folder in ['docs','resources','data']:(args.site/folder).mkdir(exist_ok=True)
    weekly_path=args.weekly_m4 or args.site/'data/mellon-7.7-wakanda-weekly.json'
    weekly=json.loads(weekly_path.read_text()) if weekly_path.exists() else None
    graphs=None
    if weekly:
        if not args.izzi:ap.error('--izzi is required to render weekly M4 graphs')
        from izzi_weekly_graphs import IzziWeeklyGraphs
        graphs=IzziWeeklyGraphs(args.izzi)
    reports=Reports(data,names,json.loads(args.genre_config.read_text()),args.site,weekly,graphs)
    reports.charts()
    for (name,_),method in zip(PAGES,[reports.francophone,reports.anglophone,reports.romance,reports.wakanda]):
        (args.site/'docs'/f'{name}.md').write_text(method().rstrip()+'\n')
    if graphs:
        graphs.save_ledger(args.site/'data/mellon-7.7-weekly-graphs.json')
        (args.site/'data/mellon-7.7-wakanda-weekly.json').write_text(json.dumps(weekly,ensure_ascii=False,separators=(',',':'))+'\n')
        (args.site/'data/itu-2026-provisional-7.7.json').write_text(json.dumps(weekly['itu_policy'],indent=2)+'\n')
        for filename in ['extend-mellon-7-7-weekly.py','mellon_7_7_weekly_report.py','izzi_weekly_graphs.py','izzi-weekly-graphs.cc']:
            shutil.copyfile(Path(__file__).with_name(filename),args.site/'resources'/filename)
    css='''/* Mellon 7.7 analytical pages; existing site typography remains in use. */
main { overflow-wrap: anywhere; }
main code { white-space: normal; overflow-wrap: anywhere; }
.analysis-table-scroll { overflow-x: auto; max-width: 100%; margin: 1.5rem 0; }
.analysis-table-scroll table { width: 100%; min-width: 720px; margin: 0; border-collapse: collapse; }
.analysis-table-scroll caption { text-align: left; font-weight: 700; margin-bottom: .6rem; }
.analysis-table-scroll th, .analysis-table-scroll td { padding: .6rem; text-align: left; vertical-align: top; border-bottom: 1px solid #d0d7de; }
.analysis-table-scroll thead { background: #f1f4f7; }
.analysis-table-scroll tbody th { font-weight: 400; }
.analysis-table-scroll tbody tr:nth-child(even) { background: #f8f9fa; }
.analysis-figure { margin: 2rem 0; }
.analysis-chart-scroll { overflow-x: auto; max-width: 100%; }
.analysis-chart-scroll img { display: block; width: 100%; height: auto; min-width: 700px; }
.analysis-figure figcaption { margin-top: .7rem; line-height: 1.5; }
.analysis-table-scroll:focus-visible, .analysis-chart-scroll:focus-visible, summary:focus-visible { outline: 3px solid #175b8c; outline-offset: 2px; }
details { margin: 1.3rem 0; }
'''
    (args.site/'resources/mellon-7.7-analysis.css').write_text(css)
    payload=json.dumps(data,ensure_ascii=False,separators=(',',':')).encode()+b'\n'
    (args.site/'data/mellon-7.7-analysis.json.gz').write_bytes(gzip.compress(payload,mtime=0))
    compact={'slice_definition':data['slice_definition'],'slice_source':data['slice_source'],'unit':data['unit'],'denominator':data['denominator'],'groups':data['groups'],
             'objects':{k:{f:r[f] for f in ['key','label','year','sample_days','dates','canonical_work_key','media_type','usa_production','in_african_global','genres','genre_families','africa60_rank','metrics','source_world','world','sources']} for k,r in data['objects'].items()},
             'm3':data['m3'],'m2_matching_rule':data['m2']['rule']}
    (args.site/'data/mellon-7.7-summary.json').write_text(json.dumps(compact,ensure_ascii=False,separators=(',',':'))+'\n')
    for p in [args.language_config,args.genre_config]:shutil.copyfile(p,args.site/'data'/p.name)
    for name in ['analyze','calculate','render','check']:
        filename=f'{name}-mellon-7-7-black.py';source=Path(__file__).with_name(filename)
        if source.exists():shutil.copyfile(source,args.site/'resources'/filename)
    index=args.site/'index.md';content=index.read_text()
    content=content.replace('## Black-led\n\nDefinition:', '## Historical curated Black-led roster\n\nThe definition and list in this section describe the original curated roster. The Round 3 analyses below use the current published slice definitions.\n\nDefinition:')
    block='<!-- BEGIN mellon-7.7 -->\n\n### Round 3 analyses — Mellon 7.7\n\nThese four studies use the [current Round 3 Black-led and African-led-global slices](https://alpha60-devops.github.io/alpha60-results/docs/slices.html). M3 covers all 382 confirmed Black-led media objects, a broader cohort than the historical curated roster above.\n\n'
    block+='\n'.join(f'- [{heading}](docs/{name}.html)' for name,heading in PAGES)+'\n\n<!-- END mellon-7.7 -->\n'
    if '<!-- BEGIN mellon-7.7 -->' in content:content=re.sub(r'<!-- BEGIN mellon-7.7 -->.*?<!-- END mellon-7.7 -->\n',block,content,flags=re.S)
    else:content=content.replace('- [Black-Led](docs/black.html)\n','- [Black-Led](docs/black.html)\n\n'+block)
    index.write_text(content)
    print(f'Rendered four reports, {5 if graphs else 4} SVG charts, JSON evidence, and index links.')


if __name__=='__main__':main()
