---
layout: default
title: "Black-Led"
author: "Benjamin De Kosnik <bkoz@gnu.org>"
description: "Analysis of Black-Led peer-to-peer distribution"
---

{::nomarkdown}
<img src="resources/a60-logo-block-gray.simple.svg?sanitize=true" height="50" width="100">

<div style="height: 50px;">
</div>
{:/}


## About

These are results from sampling peer swarms associated with *media objects*
being *shared* on the internet. Here, *media objects* are instances of media
that represent a specific film, television series or episode, or recorded
event as a file or archive. *Sharing* means the BitTorrent peer-to-peer file
sharing protocol. This is part of the long-term [Alpha60](https://alpha60.co/)
project.

## Black-led

Definition: Texts produced by US production companies (co-productions are acceptable as long as one major partner is a US company) that feature African American characters, actors, creators, and/or storylines. A text does not need all four (Black characters, actors, creators, and/or storylines) to qualify.

This excludes: texts that are not produced by US production companies (regardless of African American involvement otherwise); texts that exclusively feature non-US Black characters, actors, creators, and/or storylines (e.g. a Black British actor would not be counted).

Edge cases to consider: Queen Charlotte. English characters, English actors, US creators. And so while a text doesn’t need to meet all four Black criteria, it likely has to meet more than one…


Sample dates: 2017 to 2026

<div style="height: 50px;"></div>
{% include black-led-media-objects-list.html %}
<div style="height: 50px;"></div>


## Results, Commentary
- [Black-Led](docs/black.html)
<div style="height: 50px;"></div>


## Data

### Forms

The files below are this group's published measurements. The itemized links
above open annual sample-cache audits, which may describe newer exports or
different observation windows. Check the sample dates when comparing sources.

Replace `<collection-key>` with a key from the group list above. Each form
links to an example from this group's `data/` directory.

- [Cumulative measurements (JSON)](data/abbott-elementary-113-cumulative.json)
  - `<collection-key>-cumulative.json` — Collection totals and cumulative summaries.
- [Cumulative BTIH and media-object measurements (JSON)](data/abbott-elementary-113-cumulative-btiha-media-objects.json)
  - `<collection-key>-cumulative-btiha-media-objects.json` — Torrent/media inventory and per-BTIH cumulative measurements.
- [Cumulative network classifications (JSON)](data/abbott-elementary-113-cumulative-ip-swarm.json)
  - `<collection-key>-cumulative-ip-swarm.json` — IP-swarm and network summaries.
- [Weekly measurements (JSON)](data/abbott-elementary-113-week.json)
  - `<collection-key>-week.json` — Weekly collection, BTIH, and country measurements.
- [Geographic observations (GeoJSON)](data/abbott-elementary-113-cumulative.geojson)
  - `<collection-key>-cumulative.geojson` — Cumulative downloader and uploader geography.
- [Canonical media-object metadata (repository access required)](https://github.com/alpha60-devops/alpha60-swarm-metadata/tree/main/metadata)
  - `<collection-key>.json` — Descriptive source metadata.
- [JSON field documentation](docs/data-json.2026.html)

### [Source](https://github.com/alpha60-devops/alpha60-results-black-led/tree/main/data)


<!-- - [analysis notebook](/notebooks/analysis_2025.ipynb) -->

{::nomarkdown}
<svg width="100" height=100>
    <circle cx="20" cy="50" r="10" fill="black"/>
</svg>
{:/}
