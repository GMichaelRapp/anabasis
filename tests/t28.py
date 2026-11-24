#!/usr/bin/env python3
"""Typing-latency profile: how long the page freezes while you type in each part of Anabasis,
on a 120,000-word project with 300 sources and 600 notes.

    python tests/run_tests.py t28     as part of the suite: fails if typing anywhere freezes the page too long
    python tests/t28.py --report      just print the tables

For each field it types a short phrase the way a person does (a key every 90 ms, with pauses),
and records the browser's long tasks: any stretch over 50 ms when the page can't respond.
"Blocking" is the total of those stretches beyond 50 ms; "worst" is the longest single freeze.
"""
import argparse, asyncio, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from env import URL, OUT
from playwright.async_api import async_playwright

ns = {'__file__': os.path.join(os.path.dirname(os.path.abspath(__file__)), 't26.py')}  # reuse t26's big-project generator
_src = open(ns['__file__']).read()
exec(_src[:_src.index('async def main')], ns)
build = ns['build']

WORST_BUDGET = 250   # ms: no single freeze longer than this while typing (generous, for slower CI machines)
PHRASE = 'Ten Thousand '

# name, setup JS (run before typing), selector to type into
SCENARIOS = [
    ('Document text', "switchTab('docs'); openDoc(P.docs[3].id)", '#editor p:nth-of-type(4)'),
    ('Document title', "0", '#docTitle'),
    ('Project title', "0", '#projTitle'),
    ('Source form: title', "switchTab('sources'); openSource(P.sources[5].id)", '#panelBody input[data-f="title"]'),
    ('Source form: a source this chapter cites', "switchTab('sources'); openSource(markerItems(editor.querySelector('.cite'))[0].id)", '#panelBody input[data-f="title"]'),
    ('Source form: author', "switchTab('sources'); openSource(P.sources[6].id)", '#people .prow [data-p="family"]'),
    ('Source form: OSINT field', "switchTab('sources'); openSource(P.sources[7].id); setTimeout(() => { $('#osintBox').open = true }, 100)", '#panelBody [data-o="descDetails"]'),
    ('Source annotation', "switchTab('sources'); openSource(P.sources[8].id)", '#srcAnnot'),
    ('Search sources', "closePanel(); switchTab('sources')", '#qSources'),
    ('Note text', "switchTab('notes'); openNote(P.notes[3].id)", '#panelBody textarea'),
    ('Note title', "switchTab('notes'); openNote(P.notes[4].id)", '#panelBody input[data-f="title"], #panelBody input'),
    ('Search notes', "closePanel(); switchTab('notes')", '#qNotes'),
    ('Search documents', "switchTab('docs')", '#qDocs'),
    ('Citation search', "openCite()", '#citeSearch'),
    ('Citation note text', "0", '#citeNote'),
    ('Find in all documents', "$('#citeDlg').close(); openFindAll(); $('#frFind').value=''", '#frFind'),
    ('Map place search', "$('#frDlg').close(); openMap()", '#mpSearch'),
    ('Chart data', "$('#mpDlg').close(); openChart()", '#chData'),
    ('Plan item synopsis', "$('#chDlg').close(); openPlan(); const it = P.plan.items[0] || plNewItem(); renderPlan(); openPlanItem(it.id)", '#panelBody textarea[data-p="synopsis"]'),
]


async def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--report', action='store_true'); a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, 'big.json'); json.dump(build(), open(path, 'w'))
    rows, bad = [], []
    async with async_playwright() as pw:
        b = await pw.chromium.launch()
        ctx = await b.new_context(viewport={'width': 1440, 'height': 900})
        await ctx.add_init_script("delete window.showSaveFilePicker; delete window.showOpenFilePicker; localStorage.setItem('commonplace.prefs',JSON.stringify({startHome:false,toured:true,seenVersion:'99.0.0'}))")
        pg = await ctx.new_page(); errs = []
        pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto(URL); await pg.wait_for_timeout(1000)
        await pg.set_input_files('#fileOpen', path)
        await pg.wait_for_function("P && P.title === 'Big book'", timeout=60000); await pg.wait_for_timeout(2500)
        await pg.evaluate("""window.__lt = []; new PerformanceObserver(l => l.getEntries().forEach(e => window.__lt.push(e.duration))).observe({ type: 'longtask', buffered: false });""")
        for name, setup, sel in SCENARIOS:
            try:
                await pg.evaluate(f"(()=>{{ {setup} }})()"); await pg.wait_for_timeout(1500)
                el = pg.locator(sel).first
                await el.click(); await pg.keyboard.press('End')
                await pg.evaluate("window.__lt = []")
                for i, ch in enumerate(PHRASE * 2):
                    await pg.keyboard.type(ch); await pg.wait_for_timeout(90 if i % 7 else 450)   # a pause every few keys
                await pg.wait_for_timeout(1500)
                lt = await pg.evaluate("window.__lt")
                block = round(sum(max(0, d - 50) for d in lt)); worst = round(max(lt) if lt else 0)
                rows.append((name, block, worst, len(lt)))
                if worst > WORST_BUDGET: bad.append(name)
            except Exception as e:
                rows.append((name, -1, -1, 0)); bad.append(name + ' (could not run: ' + str(e).split('\n')[0][:80] + ')')
        # one-off actions: time from click to settled, and the longest freeze
        ACTIONS = [
            ('Open Notes tab', "closePanel(); document.querySelectorAll('dialog[open]').forEach(d => d.close()); closePlan && closePlan(); switchTab('notes')"),
            ('Open Sources tab', "switchTab('sources')"),
            ('Open Outline tab', "switchTab('outline')"),
            ('Switch chapter', "openDoc(P.docs[20].id)"),
            ('Open project home', "openHome()"),
            ('Open notes board', "closeHome(); openBoard()"),
            ('Open plan', "closeBoard(); openPlan()"),
            ('Open drafts', "closePlan(); openDrafts()"),
            ('Relationship map', "closeDrafts(); openRel()"),
            ('Open checkpoints', "closeRel(); openCheckpoints()"),
            ('Insert a citation', "$('#cpDlg').close(); const p = editor.querySelector('p'); const r = document.createRange(); r.selectNodeContents(p); r.collapse(false); getSelection().removeAllRanges(); getSelection().addRange(r); saveSelectionNow(); insertHTMLAtCursor(citeHTML([{ id: P.sources[9].id }]))"),
            ('Change citation style', "$('#docStyle').value = 'apa'; $('#docStyle').dispatchEvent(new Event('change'))"),
        ]
        rows2 = []
        for name, js in ACTIONS:
            await pg.evaluate("window.__lt = []")
            t = await pg.evaluate(f"(async () => {{ const a = performance.now(); {js}; await new Promise(r => requestAnimationFrame(() => setTimeout(r, 0))); return Math.round(performance.now() - a); }})()")
            await pg.wait_for_timeout(1800)
            lt = await pg.evaluate("window.__lt")
            rows2.append((name, t, round(max(lt) if lt else 0)))
        await b.close()
    print(f"{'Action':28} {'to settle ms':>12} {'worst ms':>9}")
    for n, t, w in rows2: print(f'{n:28} {t:>12} {w:>9}')
    print()
    print(f"{'Field':28} {'blocking ms':>12} {'worst ms':>9} {'long tasks':>11}")
    for n, bl, w, c in rows: print(f'{n:28} {bl:>12} {w:>9} {c:>11}')
    if bad: print('OVER BUDGET:', ', '.join(bad))
    print('ERRS', errs)
    sys.exit(0 if a.report or not (bad or errs) else 1)


if __name__ == '__main__':
    asyncio.run(main())
