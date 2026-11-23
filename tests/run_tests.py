#!/usr/bin/env python3
"""Run the browser test suite against dist/anabasis.html.

    python tests/run_tests.py                 every suite, in Chromium
    python tests/run_tests.py t20 t23         just these
    python tests/run_tests.py --degraded      as a browser without the File System Access and
                                              CSS Custom Highlight APIs (older Firefox and Safari) would see it

Build first (python build.py). Each suite is a Playwright script; a suite passes when it exits 0,
prints no FAIL lines and records no page errors.
"""
import argparse, functools, http.server, os, pathlib, re, shutil, subprocess, sys, threading, time

T = pathlib.Path(__file__).resolve().parent
ROOT = T.parent
SUITES = {
    't1': 'core editing, citations, saving and reopening, Markdown and HTML export',
    't6': 'OSINT Style Guide citations and the generator list format',
    't8': 'save reminders and the newer-browser-copy prompt',
    't10': 'web clipper hand-off between tabs',
    't11': 'binder, parts and manuscript compile',
    't12': 'BibTeX/RIS import, comments, drafts, paged PDF layout',
    't14': 'PDF reader and index',
    't15': 'PDF reader from a file:// page',
    't17': 'planning board and outline',
    't19': 'project home and goals',
    't20': 'figures, tables, margin notes, Word import, Markdown import, lock, autosave to file',
    't21': 'drafts: save, compare side by side, take changes',
    't22': 'charts, maps, timelines, relationships, acronyms, estimative language, script mode, GitHub backup (mocked)',
    't23': 'map layers, chart events, corroboration, house style, find in all documents, transcripts, promo kit, checkpoints, accessibility check',
    't24': 'hostile and damaged project files, file-format versions, locked-file read-back',
    't25': 'axe-core accessibility audit of the app (WCAG 2.1 A/AA), light and dark',
    't26': 'performance with a 120,000-word project',
    't27': 'note text on citations: note styles, author-date, OSINT, and every export',
    't28': 'typing latency in every field, and one-off actions, on a 120,000-word project',
    't29': 'research marks: threads, claims, review keys, questions, the research desk, clean exports',
    't31': 'citation styles, reference export, Pandoc and LaTeX packages, suggest mode and Word round-trips, starter projects, reading aloud',
    't30': 'adaptive bars at every width, toolbar trimming, shortcut sheet, writing view, undo for marks, phone layouts, installable hosted copy',
    't32': 'research journal: design, hypotheses and evidence, the dated log, the search log, memo and appendix',
    't33': 'picking up on another device from GitHub, weekly review and next steps, design templates, fact-check sheet, getting-started tips',
}
DEGRADED = ['t1', 't10', 't20', 't23', 't24']


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass


def serve(folder, port):
    h = functools.partial(Quiet, directory=str(folder))
    s = http.server.ThreadingHTTPServer(('127.0.0.1', port), h)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s


def verdict(out, code):
    if code != 0: return False, f'exit {code}'
    if re.search(r'^FAIL', out, re.M): return False, 'FAIL lines'
    errs = re.findall(r'ERRS (\[.*\])\s*$', out, re.M)
    last = [l for l in out.strip().split('\n') if l.strip()][-1:] or ['']
    if errs and errs[-1] != '[]': return False, 'page errors ' + errs[-1][:160]
    if not errs and last[0].strip().startswith('[') and last[0].strip() != '[]': return False, 'page errors ' + last[0][:160]
    return True, ''


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('only', nargs='*'); ap.add_argument('--degraded', action='store_true'); ap.add_argument('--port', type=int, default=8765)
    a = ap.parse_args()
    dist = ROOT / 'dist' / 'anabasis.html'
    if not dist.exists(): sys.exit('Build first: python build.py')
    out = T / 'out'; shutil.rmtree(out, ignore_errors=True); out.mkdir()
    shutil.copy(dist, out / 'anabasis.html')
    for f in (T / 'fixtures').iterdir():
        if f.is_file(): shutil.copy(f, out / f.name)
    srv = serve(out, a.port)
    env = dict(os.environ, ANABASIS_OUT=str(out), ANABASIS_URL=(out / 'anabasis.html').as_uri(), ANABASIS_HTTP=f'http://localhost:{a.port}/', PYTHONUNBUFFERED='1')
    names = a.only or (DEGRADED if a.degraded else list(SUITES))
    failed = []
    for n in names:
        cmd = [sys.executable, str(T / 'degraded.py'), str(T / f'{n}.py')] if a.degraded else [sys.executable, str(T / f'{n}.py')]
        t0 = time.time()
        try: p = subprocess.run(cmd, cwd=out, env=env, capture_output=True, text=True, timeout=600); text, code = p.stdout + p.stderr, p.returncode
        except subprocess.TimeoutExpired: text, code = 'timed out', -1
        ok, why = verdict(text, code)
        (out / f'{n}{"-degraded" if a.degraded else ""}.log').write_text(text)
        print(f'{"PASS" if ok else "FAIL"}  {n:4} {time.time() - t0:5.1f}s  {SUITES.get(n, "")}' + ('' if ok else f'\n      {why}; see tests/out/{n}.log'))
        if not ok: failed.append(n)
    srv.shutdown()
    print(f'\n{len(names) - len(failed)} of {len(names)} suites passed' + (f'; failed: {", ".join(failed)}' if failed else ''))
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
