# Third-party notices

Anabasis bundles the following open-source software, data and fonts in `dist/anabasis.html`. Exact versions and SHA-256 checksums are in [vendor/manifest.json](vendor/manifest.json). Full license texts are in [licenses/](licenses/).

| Component | Version | Copyright | License | Used for |
|---|---|---|---|---|
| [citeproc-js](https://github.com/Juris-M/citeproc-js) | 2.4.63 | © 2009–2019 Frank Bennett | CPAL-1.0 or AGPL-3.0-or-later (used here under the AGPL) | formatting citations and bibliographies |
| [CSL styles](https://github.com/citation-style-language/styles): Chicago 18th notes-bibliography, shortened notes, author-date; APA 7th; MLA 9th | 2026 snapshot | their respective authors | CC BY-SA 3.0 | citation styles |
| [CSL locale en-US](https://github.com/citation-style-language/locales) | 2026 snapshot | their respective authors | CC BY-SA 3.0 | citation terms |
| [OSINT Citation Generator](https://gmichaelrapp.github.io/OSINT_Cites/) core and OSINT Style Guide | 3.2.1 / 1.5 | © 2026 G. Michael Rapp | MIT (code), CC BY 4.0 (guide content) | OSINT citations |
| [DOMPurify](https://github.com/cure53/DOMPurify) | 3.5.0 | © Cure53 and contributors | Apache-2.0 or MPL-2.0 (used here under Apache-2.0) | cleaning opened files |
| [marked](https://github.com/markedjs/marked) | 15.0.12 | © MarkedJS; © 2011–2018 Christopher Jeffrey | MIT | Markdown to HTML |
| [turndown](https://github.com/mixmark-io/turndown) | 7.2.5 | © 2017+ Dom Christie | MIT | HTML to Markdown |
| [docx](https://github.com/dolanmiu/docx) | 9.16.0 | © 2016 Dolan Miu | MIT | Word export |
| [mammoth.js](https://github.com/mwilliamson/mammoth.js) | 1.13.0 | © 2013 Michael Williamson | BSD-2-Clause | Word import |
| [jsdiff](https://github.com/kpdecker/jsdiff) | 9.0.0 | © 2009–2015 Kevin Decker | BSD-3-Clause | comparing drafts |
| [Paged.js](https://pagedjs.org) | 0.4.3 | © 2018 Adam Hyde, Fred Chasen, Julien Taquet and contributors | MIT | paginated PDF with footnotes |
| [PDF.js](https://github.com/mozilla/pdf.js) | 6.5.438 | © Mozilla Foundation and contributors | Apache-2.0 | PDF reader |
| [Chart.js](https://www.chartjs.org) | 4.6.1 | © 2014–2024 Chart.js contributors | MIT | charts |
| [d3-array](https://github.com/d3/d3-array), [d3-geo](https://github.com/d3/d3-geo) | 3.2.5, 3.1.2 | © Mike Bostock | ISC | map projections |
| [topojson-client](https://github.com/topojson/topojson-client) | 3.1.0 | © Mike Bostock | ISC | map data decoding |
| [world-atlas](https://github.com/topojson/world-atlas) | 2.0.2 | © Mike Bostock | ISC | country outlines (Crimea assigned to Ukraine; see tools/data) |
| [Natural Earth](https://www.naturalearthdata.com) | 2026 snapshot | — | Public domain | countries, provinces, rivers, lakes, populated places |
| [Atkinson Hyperlegible Next](https://www.brailleinstitute.org/freefont/) | 5.3.0 (Fontsource) | © Braille Institute of America | SIL Open Font License 1.1 | interface typeface |

The CSL styles and locale are distributed unmodified under CC BY-SA 3.0. That license covers those files only; it doesn’t extend to the rest of Anabasis.

The test suite (not part of the app) includes [axe-core](https://github.com/dequelabs/axe-core) 4.14.1, © Deque Systems, under MPL-2.0.
