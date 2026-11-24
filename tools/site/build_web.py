"""Build the product site for Netlify: the front page, with the app behind it.

    python tools/site/build_web.py           # needs dist/anabasis.html (python build.py, or a release download)

site/
  index.html                 the front page (web/index.html, with version and size filled in)
  anabasis.html              the app as a download (served with Content-Disposition: attachment)
  app/                       the hosted, installable app (tools/site/build_site.py)
  fonts/, img/               the page's own fonts and images: it loads nothing from elsewhere
  _headers, _redirects       Netlify settings

On Netlify, netlify.toml first downloads the latest release into dist/, so the hosted app
always matches the published release while the front page follows main.
"""
import re, shutil, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_site  # noqa: E402

SITE = ROOT / 'site'
FONTS = ['alegreya-latin-500-normal', 'alegreya-latin-700-normal', 'alegreya-latin-500-italic',
         'atkinson-hyperlegible-next-latin-400-normal', 'atkinson-hyperlegible-next-latin-400-italic',
         'atkinson-hyperlegible-next-latin-700-normal']
SHOTS = ['editor-light', 'editor-dark', 'phone']  # the detail crops live in web/img

HEADERS = """/*
  X-Content-Type-Options: nosniff
  Referrer-Policy: strict-origin-when-cross-origin
  Permissions-Policy: interest-cohort=()

/
  Content-Security-Policy: default-src 'none'; style-src 'unsafe-inline'; img-src 'self'; font-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'
  X-Frame-Options: DENY

/index.html
  Content-Security-Policy: default-src 'none'; style-src 'unsafe-inline'; img-src 'self'; font-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'
  X-Frame-Options: DENY

/anabasis.html
  Content-Disposition: attachment; filename="anabasis.html"
  Cache-Control: public, max-age=0, must-revalidate

/app/sw.js
  Cache-Control: no-cache

/fonts/*
  Cache-Control: public, max-age=31536000, immutable
"""

REDIRECTS = """/download        /anabasis.html                                        302
/source          https://github.com/gmichaelrapp/anabasis              302
/changelog       https://github.com/gmichaelrapp/anabasis/blob/main/CHANGELOG.md   302
/quick-start     https://github.com/gmichaelrapp/anabasis/blob/main/docs/quick-start.md   302
/privacy         https://github.com/gmichaelrapp/anabasis/blob/main/docs/privacy.md   302
/file-format     https://github.com/gmichaelrapp/anabasis/blob/main/docs/file-format.md   302
"""


def main(out=SITE):
    app = ROOT / 'dist' / 'anabasis.html'
    if not app.exists(): sys.exit('Build first (python build.py), or download a release into dist/anabasis.html')
    html = app.read_text(encoding='utf-8')
    m = re.search(r"const APP_VERSION = '([^']+)'", html)
    version = m.group(1) if m else 'dev'
    size = f'{app.stat().st_size / 1e6:.1f} MB'
    if out.exists(): shutil.rmtree(out)
    build_site.main(out / 'app', app=app, version=version)
    shutil.copy(app, out / 'anabasis.html')
    page = (ROOT / 'web' / 'index.html').read_text(encoding='utf-8')
    page = page.replace('{{VERSION}}', version).replace('{{SIZE}}', size)
    assert '{{' not in page, 'unfilled placeholder in web/index.html'
    (out / 'index.html').write_text(page, encoding='utf-8')
    (out / 'fonts').mkdir()
    for f in FONTS: shutil.copy(ROOT / 'assets' / 'fonts' / f'{f}.woff2', out / 'fonts')
    (out / 'img').mkdir()
    for s in SHOTS: shutil.copy(ROOT / 'docs' / 'screenshots' / f'{s}.png', out / 'img')
    for f in (ROOT / 'web' / 'img').glob('*.png'): shutil.copy(f, out / 'img')
    for f in ('contour-light.svg', 'contour-dark.svg', 'icon.svg'): shutil.copy(ROOT / 'assets' / f, out / 'img')
    (out / '_headers').write_text(HEADERS, encoding='utf-8')
    (out / '_redirects').write_text(REDIRECTS, encoding='utf-8')
    print(f'site/ for Anabasis {version} ({size}): front page, app/, download, {len(FONTS)} fonts, {len(SHOTS)} screenshots')


if __name__ == '__main__':
    main()
