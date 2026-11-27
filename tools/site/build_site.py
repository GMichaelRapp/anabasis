"""Build the hosted copy for GitHub Pages: the app, plus what lets it install as an app.

    python tools/site/build_site.py            # after python build.py; writes site/

site/
  index.html, anabasis.html   the app (the same single file you can download)
  manifest.webmanifest        name, icons, colors: "Add to Home Screen" / "Install"
  sw.js                       a small service worker so the installed app opens offline
  icon-*.png, apple-touch-icon.png

The hosted copies carry a <meta name="anabasis-installable"> marker; the app registers
sw.js only when it sees that marker and is served over HTTPS (or localhost), so the
downloaded file behaves exactly as before.
"""
import json, re, shutil, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / 'site'
ICONS = Path(__file__).resolve().parent / 'icons'


def main(out=SITE, app=None, version=None):
    app = app or ROOT / 'dist' / 'anabasis.html'
    if not app.exists(): sys.exit('Build first: python build.py')
    if not version:
        m = re.search(r"const APP_VERSION = '([^']+)'", (ROOT / 'src' / 'app.js').read_text(encoding='utf-8'))
        version = m.group(1) if m else 'dev'
    if out.exists(): shutil.rmtree(out)
    out.mkdir(parents=True)
    html = app.read_text(encoding='utf-8')
    marked = html.replace('<meta charset="utf-8">', '<meta charset="utf-8">\n<meta name="anabasis-installable" content="1">', 1)
    assert marked != html, 'could not mark the hosted copy'
    for name in ('index.html', 'anabasis.html'): (out / name).write_text(marked, encoding='utf-8')
    for f in ICONS.glob('*.png'): shutil.copy(f, out / f.name)
    (out / '.nojekyll').write_text('')
    manifest = {
        'name': 'Anabasis', 'short_name': 'Anabasis',
        'description': 'A word processor, notebook and citation manager for nonfiction, in one offline file.',
        'id': './', 'start_url': './', 'scope': './', 'display': 'standalone', 'orientation': 'any',
        'background_color': '#E7EBE4', 'theme_color': '#24456E', 'lang': 'en',
        'icons': [
            {'src': 'icon-192.png', 'sizes': '192x192', 'type': 'image/png', 'purpose': 'any'},
            {'src': 'icon-512.png', 'sizes': '512x512', 'type': 'image/png', 'purpose': 'any'},
            {'src': 'icon-maskable-512.png', 'sizes': '512x512', 'type': 'image/png', 'purpose': 'maskable'},
        ],
        'categories': ['productivity', 'education'],
    }
    (out / 'manifest.webmanifest').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    files = ['./', './index.html', './anabasis.html', './manifest.webmanifest'] + [f'./{f.name}' for f in sorted(ICONS.glob('*.png'))]
    (out / 'sw.js').write_text(SW.replace('__VERSION__', version).replace('__FILES__', json.dumps(files)), encoding='utf-8')
    print(f'site/ for Anabasis {version}: {", ".join(sorted(p.name for p in out.iterdir()))}')


# Network first, so a new release arrives as soon as you're online; the cached copy
# opens the app when you're not. Only this site's own files are cached: citation
# lookups and GitHub backups go to the network as usual and are never stored.
SW = """/* Anabasis __VERSION__ service worker: lets the installed app open offline. */
const CACHE = 'anabasis-__VERSION__';
const FILES = __FILES__;
self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(FILES)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k.startsWith('anabasis-') && k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', e => {
  const req = e.request, url = new URL(req.url);
  // only the app's own files: nothing from other sites, nothing elsewhere on this one
  if (req.method !== 'GET' || url.origin !== self.location.origin || !url.pathname.startsWith(new URL(self.registration.scope).pathname)) return;
  e.respondWith(fetch(req).then(res => {
    if (res.ok && res.type === 'basic') { const copy = res.clone(); caches.open(CACHE).then(c => c.put(req, copy)); }
    return res;
  }).catch(() => caches.match(req, { ignoreSearch: true }).then(hit => hit || (req.mode === 'navigate' ? caches.match('./index.html') : Response.error()))));
});
"""

if __name__ == '__main__':
    main()
