#!/usr/bin/env python3
"""Build Anabasis into one self-contained, offline HTML file.

    python build.py            writes dist/anabasis.html
    python build.py --check    also verifies every vendored file against vendor/manifest.json

Needs only the Python standard library. Every third-party file is committed under vendor/, data/ and
assets/ with its version, license and SHA-256 recorded in vendor/manifest.json, so the build never
touches the network and the same commit always produces the same file.
"""
import argparse, base64, hashlib, html.parser, json, pathlib, re, sys, urllib.parse

ROOT = pathlib.Path(__file__).resolve().parent
SRC, VJ, CSL, DATA, ASSETS, DIST = (ROOT / d for d in ('src', 'vendor/js', 'vendor/csl', 'data', 'assets', 'dist'))
BUDGET = 50 * 1024 * 1024  # the whole app must stay under 50 MB
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
    lazy += '<script type="text/plain" id="data-oracle">' + read(DATA / 'oracle.txt').replace('<', '&lt;') + '</script>\n'
    lazy += '<script type="text/plain" id="data-socrates">' + read(DATA / 'socrates.txt').replace('<', '&lt;') + '</script>\n'
    lazy += '<script type="text/plain" id="data-proof">' + read(DATA / 'proofread.txt').replace('<', '&lt;') + '</script>\n'
    lazy += '<script type="text/plain" id="data-guide">' + read(DATA / 'guide.txt').replace('<', '&lt;') + '</script>\n'
    lazy += '<script type="application/json" id="data-admin1">' + safe(read(DATA / 'admin1.json')) + '</script>\n'
    lazy += '<script type="application/json" id="data-rivers">' + safe(read(DATA / 'rivers.json')) + '</script>\n'
    lazy += '<script type="text/plain" id="lib-math">/*! MathJax 3.2.2 | Apache-2.0 | (c) The MathJax Consortium | mathjax.org */' + safe(read(VJ / 'mathjax-tex-svg-full.js')) + '</script>\n'
    # 2.7: offline OCR (Tesseract.js, its WebAssembly core, and the English model), read only when used
    OCR = ROOT / 'vendor' / 'ocr'
    lazy += '<script type="text/plain" id="lib-ocr">/*! Tesseract.js 7.0.0 | Apache-2.0 | github.com/naptha/tesseract.js */' + safe(read(OCR / 'tesseract.min.js')) + '</script>\n'
    lazy += '<script type="text/plain" id="lib-ocr-worker">/*! Tesseract.js worker 7.0.0 | Apache-2.0 */' + safe(read(OCR / 'worker.min.js')) + '</script>\n'
    lazy += '<script type="text/plain" id="lib-ocr-core">/*! tesseract.js-core 6.1.2 (Tesseract OCR, simd-lstm) | Apache-2.0 */' + safe(read(OCR / 'tesseract-core-simd-lstm.wasm.js')) + '</script>\n'
    lazy += '<script type="text/plain" id="lib-ocr-eng">' + base64.b64encode((OCR / 'eng.traineddata.gz').read_bytes()).decode() + '</script>\n'
    # 2.12: Excalidraw for sketches, with React, run only inside the sketch frame. Its fonts come with it as data,
    # and the bundle's own font addresses are pointed at them, so drawing never reaches the network.
    EX = ROOT / 'vendor' / 'excalidraw'
    exc = read(EX / 'excalidraw.production.min.js')
    for f in ('Virgil', 'Cascadia', 'Assistant-Regular', 'Assistant-Medium', 'Assistant-SemiBold', 'Assistant-Bold'):
        ref = f'n.p+"excalidraw-assets/{f}.woff2"'
        if exc.count(ref) != 1: sys.exit(f'Excalidraw bundle changed shape: {ref}')
        exc = exc.replace(ref, '"data:font/woff2;base64,' + base64.b64encode((EX / f'{f}.woff2').read_bytes()).decode() + '"')
    nocmt = lambda t: safe(t).replace('<!--', '\\x3c!--')
    # the app holds no keys: refuse a build if a vendored file brings one in (a Google API key, as Excalidraw's bundle once did)
    for name, t in (('excalidraw', exc), ('excalidraw vendor chunk', read(EX / 'excalidraw-vendor.js'))):
        if re.search(r'AIza[0-9A-Za-z_-]{35}|"apiKey"\s*:\s*"[^"]+"', t): sys.exit(f'{name} carries an API key; empty it in vendor/ (see vendor/manifest.json)')
    lazy += '<script type="text/plain" id="lib-excal-shim">' + safe(read(SRC / 'sketch' / 'shim.js')) + '</script>\n'
    lazy += '<script type="text/plain" id="lib-excal-boot">' + safe(read(SRC / 'sketch' / 'boot.js')) + '</script>\n'
    lazy += '<script type="text/plain" id="lib-react">/*! React 18.3.1 | MIT | (c) Meta Platforms, Inc. */' + nocmt(read(EX / 'react.production.min.js')) + '</script>\n'
    lazy += '<script type="text/plain" id="lib-react-dom">/*! ReactDOM 18.3.1 | MIT | (c) Meta Platforms, Inc. */' + nocmt(read(EX / 'react-dom.production.min.js')) + '</script>\n'
    lazy += '<script type="text/plain" id="lib-excal-vendor">/*! Excalidraw 0.17.6 (vendor chunk) | MIT | excalidraw.com */' + nocmt(read(EX / 'excalidraw-vendor.js')) + '</script>\n'
    lazy += '<script type="text/plain" id="lib-excal">/*! Excalidraw 0.17.6 | MIT | excalidraw.com; fonts Virgil, Cascadia Code, Assistant | SIL OFL 1.1 */' + nocmt(exc) + '</script>\n'
    lazy += '<script type="text/plain" id="lib-paged">/*! Paged.js 0.4.3 | MIT | pagedjs.org */' + read(VJ / 'paged.min.js') + '</script>\n'
    lazy += f'<script type="text/plain" id="csl-locale">{read(CSL / "locales-en-US.xml")}</script>\n'
    for f in sorted(CSL.glob('locales-*.xml')):  # 2.7: citation terms for documents written in other languages
        code = f.stem[len('locales-'):]
        if code != 'en-US': lazy += f'<script type="text/plain" id="csl-locale-{code}">{read(f)}</script>\n'
    vendor = '\n'.join(read(VJ / f) for f in EAGER)
    for name, chunk in (('vendor', vendor), ('app', app)):
        if '</script' in chunk.lower(): sys.exit(f'{name} code contains "</script", which would break the page')
    shell = shell.replace('/*@FONTS@*/', fonts_css())
    return (shell.replace('/*@DOCCSS@*/', '</style><style id="docCss">' + doc_css + '</style><style>')
                 .replace('<!--@CSL@-->', lazy).replace('/*@VENDOR@*/', vendor).replace('/*@APP@*/', app))


class _Scripts(html.parser.HTMLParser):
    """The scripts a browser would run, read the way the browser reads them (not by pattern, since the app's own
    code holds the text '<script>' in strings)."""
    def __init__(self):
        super().__init__(convert_charrefs=False); self.found, self._cur = [], None
    def handle_starttag(self, tag, attrs):
        if tag != 'script': return
        a = dict(attrs); t = (a.get('type') or '').lower()
        # a library kept as text until it's needed, then run by useLib(): its exact text may run too
        lazy = t == 'text/plain' and (a.get('id') or '').startswith('lib-')
        self._cur = [] if ((not t or t in ('text/javascript', 'module')) and 'src' not in a) or lazy else None
    def handle_data(self, data):
        if self._cur is not None: self._cur.append(data)
    def handle_endtag(self, tag):
        if tag == 'script' and self._cur is not None: self.found.append(''.join(self._cur)); self._cur = None


def pin_scripts(html):
    """Swap 'unsafe-inline' in the page's script-src for the SHA-256 of each script it runs.

    The browser then runs the app's own scripts and nothing else: a script slipped into the page by a crafted file
    is refused. Blocks of data (type="text/plain", "application/json") don't run, so they aren't listed."""
    p = _Scripts(); p.feed(html); p.close()
    hashes = ["'sha256-" + base64.b64encode(hashlib.sha256(t.encode('utf-8')).digest()).decode() + "'" for t in p.found]
    if not hashes: sys.exit('no inline scripts found to pin')
    before = "script-src 'unsafe-inline'"
    if html.count(before) != 1: sys.exit('the content security policy has changed shape: expected exactly one ' + before)
    return html.replace(before, 'script-src ' + ' '.join(dict.fromkeys(hashes)), 1)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--check', action='store_true', help='verify vendored files against vendor/manifest.json')
    ap.add_argument('--out', default=str(DIST / 'anabasis.html'))
    a = ap.parse_args()
    if a.check: check_manifest()
    out = pin_scripts(build())
    size = len(out.encode('utf-8'))
    if size > BUDGET: sys.exit(f'dist is {size / 1048576:.2f} MB, over the {BUDGET / 1048576:.0f} MB budget')
    version = re.search(r"const APP_VERSION = '([^']+)'", read(SRC / 'app.js')).group(1)
    p = pathlib.Path(a.out); p.parent.mkdir(parents=True, exist_ok=True); p.write_text(out, encoding='utf-8')
    print(f'Anabasis {version}: {p.relative_to(ROOT) if p.is_relative_to(ROOT) else p} ({size / 1048576:.2f} MB of {BUDGET / 1048576:.0f} MB)')
    print('sha256', hashlib.sha256(out.encode('utf-8')).hexdigest())


if __name__ == '__main__':
    main()
