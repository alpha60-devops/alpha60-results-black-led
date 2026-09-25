"""Render the Black Panther weekly extension with Izzi, from its numeric ledger."""
from izzi_weekly_graphs import point, series


def render_weekly(report, weekly, graphs, table, figure, disclosure, number, title):
    keys=list(weekly['objects']);panels=[]
    for role in ['downloaders','uploaders']:
        for region in ['world','africa60']:
            label='Worldwide' if region=='world' else 'Africa60'
            panels.append({'title':label+' '+role,'unit':'weight','ylabel':'2026 adjusted weight','series':[
                series(title(k),i,[point(w['week'],w['adjusted'][region][role]['size'],
                    f"{title(k)} · {label} {role} · week {w['week']} · {w['dates']} · raw {w[region][role]['size']:,} · 2026 adjusted {w['adjusted'][region][role]['size']:,.2f}")
                    for w in weekly['objects'][k]['weeks']]) for i,k in enumerate(keys)]})
    spec={'title':'Black Panther universe · weekly circulation',
          'subtitle':'Provisional 2026 Internet-user scale · available weeks 1–26 · panel scales differ',
          'description':'Four Izzi line panels: world and Africa60, downloaders and uploaders. Black Panther stops at week seven; no missing intervals are imputed.',
          'columns':2,'xmin':1,'xmax':26,'ticks':[[n,str(n)] for n in [1,5,10,15,20,26]],
          'xlabel':'Elapsed sampling week','panels':panels}
    graphs.render(report.site,'mellon-7.7-wakanda-weekly-itu-2026',spec,inline=False)
    text='''## Weekly circulation at the 2026 scale

The graph uses **weeks 1–26**, plotting available complete seven-day calendar
bins. **Black Panther stops at week 7**: its 52-day sample has seven full weeks
and a three-day trailing bin, which is omitted. The other three objects have
26 full weeks. Lines stop at observed coverage; missing weeks are not zeros.
This available-coverage view does not extend the original film's matched window.

**2026 adjusted weight = raw weekly weight × 6.1 / sample-start-year global
Internet users (billions).** The **6.1-billion 2026 reference is a provisional
project estimate**, not an official ITU 2026 observation. Each object's factor
is constant across its intervals, including samples that cross a calendar year.
This adjusts global Internet-user growth; country penetration, media scope,
torrent inventory and missing collection hours remain unadjusted. Shares and
network-flag rates are unchanged by the multiplier.

'''
    text+=figure('wakanda-weekly-itu-2026',spec['description'],
                 'Native Izzi weekly line graphs. Worldwide and Africa60 weights for downloaders and uploaders; each panel has its own vertical scale. Markers identify observed weeks. The 2026 reference is provisional.')
    rows=[]
    for k in keys:
        r=weekly['objects'][k];first,last=r['weeks'][0],r['weeks'][-1]
        flags=', '.join(str(w['week']) for w in r['weeks'] if w['partial']) or 'None'
        rows.append([title(k),r['year'],r['source_users_billions'],f"{r['factor']:.6f}",
                     f"1–{last['week']}",first['dates'][:10]+' to '+last['dates'].removesuffix('-partial')[-10:],flags])
    text+=table('Weekly coverage and ITU factors',['Object','Sample year','Internet users (billions)','2026 factor','Plotted weeks','Calendar extent','Partial export flags'],rows)
    text+='''Full-length calendar bins can carry partial export flags or contain
sampling gaps. The flags above are retained in the graph; they do not quantify
missing hours. The exact dates, source audit notes and source-file hashes are in
the weekly ledger. The earlier seven-week coverage sensitivity follows below.

Sources: [ITU 2018: 3.9 billion](https://www.itu.int/en/mediacentre/pages/2018-pr40.aspx),
[ITU 2023: 5.4 billion](https://www.itu.int/en/mediacentre/Pages/PR-2023-11-27-facts-and-figures-measuring-digital-development.aspx),
[ITU 2025: 6.0 billion](https://www.itu.int/en/mediacentre/Pages/PR-2025-11-17-Facts-and-Figures.aspx).
The [ITU publication index](https://www.itu.int/en/ITU-D/Statistics/pages/facts/default.aspx)
still lists 2025 as its latest release when checked on September 25, 2026.
Historical values retain their as-published vintages.

'''
    rows=[]
    for k in keys:
        for w in weekly['objects'][k]['weeks']:
            rows.append([title(k),w['week'],w['dates']]+[
                number(v) for role in ['downloaders','uploaders'] for region in ['world','africa60']
                for v in [w[region][role]['size'],w['adjusted'][region][role]['size']]])
    text+=disclosure('Weekly graph values: raw and 2026 adjusted',table('Weekly weights underlying the Izzi graph',
        ['Object','Week','Dates']+[f'{region} {role} {kind}' for role in ['downloaders','uploaders']
                                 for region in ['World','Africa60'] for kind in ['raw','adjusted']],rows))
    text+='''The graph reads top-level weekly aggregate GeoJSON interval features,
with H3 resolution 5 and minimum swarm size 3. Nested by-BTIH features and
companion weekly JSON cumulative prefixes are not added again. Repeated weekly
swarm weights are not unique people, viewers or completed downloads.

Download the [weekly numeric ledger](../data/mellon-7.7-wakanda-weekly.json),
[graph inputs and Izzi provenance](../data/mellon-7.7-weekly-graphs.json),
[ITU policy](../data/itu-2026-provisional-7.7.json) and
[weekly reducer](../resources/extend-mellon-7-7-weekly.py).
The [C++ graph renderer](../resources/izzi-weekly-graphs.cc) and
[Python wrapper](../resources/izzi_weekly_graphs.py) are also available.
Run the reducer beside the existing collector with `--input mellon-7.7-analysis.json.gz
--source-root /path/to/checkouts --itu-config itu-2026-provisional-7.7.json
--output weekly.json --weeks 26`. The report renderer accepts `--weekly-m4 weekly.json
--izzi /path/to/izzi`; the graph ledger pins the Izzi revision and renderer digest.

'''
    return text
