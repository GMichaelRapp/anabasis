#!/usr/bin/env python3
"""Build Anabasis into one self-contained, offline HTML file.

    python build.py            writes dist/anabasis.html
    python build.py --check    also verifies every vendored file against vendor/manifest.json

Needs only the Python standard library. Every third-party file is committed under vendor/, data/ and
assets/ with its version, license and SHA-256 recorded in vendor/manifest.json, so the build never
touches the network and the same commit always produces the same file.
"""
import argparse, base64, hashlib, json, pathlib, re, sys, urllib.parse

ROOT = pathlib.Path(__file__).resolve().parent
SRC, VJ, CSL, DATA, ASSETS, DIST = (ROOT / d for d in ('src', 'vendor/js', 'vendor/csl', 'data', 'assets', 'dist'))
BUDGET = 25 * 1024 * 1024  # the whole app must stay under 25 MB
STYLES = sorted(p.stem for p in (ROOT / 'vendor/csl').glob('*.csl'))  # every vendored CSL style is bundled
EAGER = ['purify.min.js', 'citeproc.min.js', 'marked.min.js', 'turndown.min.js', 'osint.js', 'docx.min.js', 'mammoth.min.js', 'diff.min.js']


def read(p): return p.read_text(encoding='utf-8')
def safe(t): return t.replace('</script', '<\\/script')  # keep inline data from closing its <script> early


def check_manifest():
    bad = []
    for e in json.loads(read(ROOT / 'vendor/manifest.json')):
        f = ROOT / e['file']
        if not f.exists(): bad.append(f'missing: {e["file"]}'); continue
        h = hashlib.sha256(f.read_bytes()).hexdigest()
        if h != e['sha256']: bad.append(f'changed: {e["file"]} (expected {e["sha256"][:12]}…, got {h[:12]}…)')
    if bad:
        sys.exit('Vendored files do not match vendor/manifest.json:\n  ' + '\n  '.join(bad) +
                 '\nIf you updated a library on purpose, update its version and sha256 in the manifest.')
    print('vendor manifest: all files verified')


def fonts_css():
    faces = ''
    ranges = {
        'latin': 'U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD',
        'latin-ext': 'U+0100-02BA,U+02BD-02C5,U+02C7-02CC,U+02CE-02D7,U+02DD-02FF,U+0304,U+0308,U+0329,U+1D00-1DBF,U+1E00-1E9F,U+1EF2-1EFF,U+2020,U+20A0-20AB,U+20AD-20C0,U+2113,U+2C60-2C7F,U+A720-A7FF',
    }
    for w, st in ((400, 'normal'), (500, 'normal'), (700, 'normal'), (400, 'italic'), (700, 'italic')):
        for sub, rng in ranges.items():
            f = ASSETS / 'fonts' / f'atkinson-hyperlegible-next-{sub}-{w}-{st}.woff2'
            if f.exists():
                faces += (f"@font-face{{font-family:'Atkinson Hyperlegible Next';font-style:{st};font-weight:{w};font-display:swap;"
                          f"src:url(data:font/woff2;base64,{base64.b64encode(f.read_bytes()).decode()}) format('woff2');unicode-range:{rng}}}\n")
    for w, st in ((500, 'normal'), (700, 'normal'), (500, 'italic')):  # display face for titles and headings
        for sub, rng in ranges.items():
            f = ASSETS / 'fonts' / f'alegreya-{sub}-{w}-{st}.woff2'
            if f.exists():
                faces += (f"@font-face{{font-family:'Alegreya';font-style:{st};font-weight:{w};font-display:swap;"
                          f"src:url(data:font/woff2;base64,{base64.b64encode(f.read_bytes()).decode()}) format('woff2');unicode-range:{rng}}}\n")
    svg = lambda p: 'url("data:image/svg+xml,' + urllib.parse.quote(read(p), safe=" =:/,.'-") + '")'
    contour = ':root{--contour-light:' + svg(ASSETS / 'contour-light.svg') + ';--contour-dark:' + svg(ASSETS / 'contour-dark.svg') + '}'
    return '/*! Atkinson Hyperlegible Next | SIL Open Font License 1.1 | Braille Institute of America */\n/*! Alegreya | SIL Open Font License 1.1 | Juan Pablo del Peral, Huerta Tipográfica */\n' + faces + contour


def build():
    shell, doc_css, app = read(SRC / 'shell.html'), read(SRC / 'doc.css'), read(SRC / 'app.js')
    lazy = ''.join(f'<script type="text/plain" id="csl-{s}">{read(CSL / (s + ".csl"))}</script>\n' for s in STYLES)
    lazy += '<script type="text/plain" id="lib-pdfjs">/*! PDF.js 6.5.438 | Apache-2.0 | (c) Mozilla Foundation | github.com/mozilla/pdf.js */' + read(VJ / 'pdf.min.mjs') + '</script>\n'
    lazy += ('<script type="text/plain" id="lib-pdfworker">/*! PDF.js 6.5.438 worker | Apache-2.0 */' +
             read(VJ / 'pdf.worker.min.mjs').replace('export{WorkerMessageHandler};', '').replace('import.meta.url', 'self.location.href') + '</script>\n')
    lazy += '<script type="text/plain" id="lib-chart">/*! Chart.js 4.6.1 | MIT | chartjs.org */' + safe(read(VJ / 'chart.umd.min.js')) + '</script>\n'
    lazy += ('<script type="text/plain" id="lib-geo">/*! d3-array 3.2.5, d3-geo 3.1.2 | ISC | Mike Bostock */' + safe(read(VJ / 'd3-array.min.js')) + '\n' +
             safe(read(VJ / 'd3-geo.min.js')) + '\n/*! topojson-client 3.1.0 | ISC | Mike Bostock */' + safe(read(VJ / 'topojson-client.min.js')) + '</script>\n')
    lazy += '<script type="application/json" id="data-world">' + read(DATA / 'countries-50m.json') + '</script>\n'
    lazy += '<script type="text/plain" id="data-places">' + read(DATA / 'places.txt').replace('<', '&lt;') + '</script>\n'
    lazy += '<script type="text/plain" id="data-socrates">' + read(DATA / 'socrates.txt').replace('<', '&lt;') + '</script>\n'
    lazy += '<script type="application/json" id="data-admin1">' + safe(read(DATA / 'admin1.json')) + '</script>\n'
    lazy += '<script type="application/json" id="data-rivers">' + safe(read(DATA / 'rivers.json')) + '</script>\n'
    lazy += '<script type="text/plain" id="lib-math">/*! MathJax 3.2.2 | Apache-2.0 | (c) The MathJax Consortium | mathjax.org */' + safe(read(VJ / 'mathjax-tex-svg-full.js')) + '</script>\n'
    lazy += '<script type="text/plain" id="lib-paged">/*! Paged.js 0.4.3 | MIT | pagedjs.org */' + read(VJ / 'paged.min.js') + '</script>\n'
    lazy += f'<script type="text/plain" id="csl-locale">{read(CSL / "locales-en-US.xml")}</script>\n'
    vendor = '\n'.join(read(VJ / f) for f in EAGER)
    for name, chunk in (('vendor', vendor), ('app', app)):
        if '</script' in chunk.lower(): sys.exit(f'{name} code contains "</script", which would break the page')
    shell = shell.replace('/*@FONTS@*/', fonts_css())
    return (shell.replace('/*@DOCCSS@*/', '</style><style id="docCss">' + doc_css + '</style><style>')
                 .replace('<!--@CSL@-->', lazy).replace('/*@VENDOR@*/', vendor).replace('/*@APP@*/', app))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--check', action='store_true', help='verify vendored files against vendor/manifest.json')
    ap.add_argument('--out', default=str(DIST / 'anabasis.html'))
    a = ap.parse_args()
    if a.check: check_manifest()
    out = build()
    size = len(out.encode('utf-8'))
    if size > BUDGET: sys.exit(f'dist is {size / 1048576:.2f} MB, over the {BUDGET / 1048576:.0f} MB budget')
    version = re.search(r"const APP_VERSION = '([^']+)'", read(SRC / 'app.js')).group(1)
    p = pathlib.Path(a.out); p.parent.mkdir(parents=True, exist_ok=True); p.write_text(out, encoding='utf-8')
    print(f'Anabasis {version}: {p.relative_to(ROOT) if p.is_relative_to(ROOT) else p} ({size / 1048576:.2f} MB of {BUDGET / 1048576:.0f} MB)')
    print('sha256', hashlib.sha256(out.encode('utf-8')).hexdigest())


if __name__ == '__main__':
    main()
