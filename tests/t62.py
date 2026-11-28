"""2.12 load test: a project far bigger than a real one (300,000 words in 60 chapters, 1,500 sources, 3,000 notes)
carrying every 2.12 feature in bulk: drafting colors through every chapter, 120 code snippets, a task list on every
chapter and section (about 780 lists, 2,500 tasks), and 25 sketches of 400 shapes each. It must open, save, reopen,
switch chapters, show Project home with its task card, and take typing without long freezes."""
import asyncio, json, os, random, sys, time
from playwright.async_api import async_playwright
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from env import URL, OUT

random.seed(12)
WORDS = ('the army moved east along the river while the ministry argued about supply lines and the press reported heavy losses near the border towns '
         'where artillery and drones changed how commanders planned each operation officials may have expected a shorter campaign but reserves proved decisive').split()
INKS = 'bgarps'
OPEN_BUDGET = 60_000   # ms to open the file (CI machines are slow; a fast laptop takes a fraction of this)
WORST_BUDGET = 300     # ms: no single freeze longer than this while typing
SAVE_BUDGET = 15_000   # ms to serialize the project


def para(n):
    w = [random.choice(WORDS) for _ in range(n)]; w[0] = w[0].capitalize()
    # a colored passage in about one paragraph in four
    if random.random() < 0.25:
        a = random.randint(1, max(1, n - 6)); w[a] = f'<span class="ink ink-{random.choice(INKS)}">' + w[a]; w[a + 4] = w[a + 4] + '</span>'
    return ' '.join(w) + '.'


def build():
    sources = [{'id': f's{i}', 'csl': {'type': 'book', 'title': f'Study {i}', 'author': [{'family': f'Author{i}', 'given': 'A.'}], 'issued': {'date-parts': [[1950 + i % 70]]}}} for i in range(1500)]
    docs, tasks, sketches = [], [], {}
    for c in range(60):
        html, words, sec = f'<h1 data-task="tc{c}">Chapter {c + 1}</h1>', 0, 0
        tasks.append({'id': f'tl{c}', 'docId': f'd{c}', 'anchor': f'tc{c}', 'title': f'Chapter {c + 1}', 'items': [{'id': f'ti{c}_{k}', 't': f'Check claim {k} in chapter {c + 1}', 'done': k % 3 == 0, 'due': '2026-12-0' + str(1 + k % 9), 'at': '2026-11-01T00:00:00Z'} for k in range(5)]})
        while words < 5000:
            if words // 400 > sec:
                sec += 1; html += f'<h2 data-task="ts{c}_{sec}">Section {sec}</h2>'
                tasks.append({'id': f'tl{c}_{sec}', 'docId': f'd{c}', 'anchor': f'ts{c}_{sec}', 'title': f'Section {sec}', 'items': [{'id': f'ti{c}_{sec}_{k}', 't': f'Rewrite paragraph {k}', 'done': False, 'due': '', 'at': '2026-11-01T00:00:00Z'} for k in range(3)]})
            n = random.randint(60, 140); words += n
            html += f'<p>{para(n)}<span class="cite" contenteditable="false" data-items=\'[{{"id":"s{random.randrange(1500)}","locator":"{random.randint(1, 300)}","label":"page"}}]\'></span></p>'
            if c % 2 == 0 and words % 2500 < 140: html += '<pre class="code" data-lang="Python" contenteditable="false"><code>def supply(days):\n    return days * 12  # rations</code></pre>'
        if c < 25:
            sid = f'sk{c}'; html += f'<figure class="fig" data-sketch="{sid}" contenteditable="false"><img data-asset="i{c}" alt=""><figcaption>Sketch {c}</figcaption></figure>'
            sketches[sid] = {'elements': [{'id': f'e{c}_{k}', 'type': random.choice(['rectangle', 'ellipse', 'arrow', 'text']), 'x': k * 7, 'y': k * 5, 'width': 40, 'height': 30, 'text': 'Label' if k % 4 == 3 else None, 'version': 1, 'versionNonce': k, 'isDeleted': False, 'strokeColor': '#1e1e1e'} for k in range(400)], 'files': {}, 'appState': {'viewBackgroundColor': '#ffffff'}}
        docs.append({'id': f'd{c}', 'title': f'Chapter {c + 1}', 'html': html, 'style': 'chicago-notes-bibliography', 'order': c})
    png = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=='
    assets = {f'i{c}': {'name': 'Sketch', 'type': 'image/png', 'data': png, 'w': 1, 'h': 1} for c in range(25)}
    notes = [{'id': f'n{i}', 'title': f'Note {i}', 'body': ' '.join(random.choice(WORDS) for _ in range(60)), 'kind': 'quote', 'tags': ['tag' + str(i % 30)], 'sourceId': f's{i % 1500}', 'pinned': i % 200 == 0} for i in range(3000)]
    return {'app': 'Anabasis', 'format': 2, 'id': 'p_load', 'title': 'Load test', 'docs': docs, 'notes': notes, 'sources': sources, 'tasks': tasks, 'sketches': sketches, 'assets': assets, 'inkKey': {'b': 'rewrite', 'a': 'check'}}


async def main():
    os.makedirs(OUT, exist_ok=True)
    data = build(); path = os.path.join(OUT, 'load.json'); json.dump(data, open(path, 'w'))
    words = sum(len(d['html'].split()) for d in data['docs'])
    print('file MB', round(os.path.getsize(path) / 1e6, 1), '| about', words, 'words |', len(data['tasks']), 'task lists |', sum(len(l['items']) for l in data['tasks']), 'tasks')
    ok = True
    def check(name, cond, extra=''):
        nonlocal ok
        print(('PASS ' if cond else 'FAIL ') + name, extra if not cond else ''); ok = ok and bool(cond)
    async with async_playwright() as pw:
        b = await pw.chromium.launch()
        ctx = await b.new_context(viewport={'width': 1440, 'height': 900})
        await ctx.add_init_script("delete window.showSaveFilePicker; delete window.showOpenFilePicker; try { localStorage.setItem('commonplace.prefs',JSON.stringify({startHome:false,toured:true,seenVersion:'99.0.0',homeCards:[{k:'tasks'},{k:'pinned'},{k:'resume'}]})) } catch (e) {}")
        pg = await ctx.new_page(); errs = []
        pg.on('pageerror', lambda e: errs.append(str(e)[:300]))
        await pg.goto(URL); await pg.wait_for_timeout(1000)
        t = time.time()
        await pg.set_input_files('#fileOpen', path)
        await pg.wait_for_function("() => (P && P.title === 'Load test')", timeout=OPEN_BUDGET)
        opened = round((time.time() - t) * 1000); print('open ms', opened)
        check('the load-test project opens within budget', opened < OPEN_BUDGET, opened)
        await pg.wait_for_timeout(2500)
        r = await pg.evaluate("({ docs: P.docs.length, tasks: P.tasks.length, items: P.tasks.reduce((n, l) => n + l.items.length, 0), sketches: Object.keys(P.sketches).length, notes: P.notes.length, colored: (P.docs[0].html.match(/class=\"ink ink-/g) || []).length })")
        check('everything survived opening', r['docs'] == 60 and r['tasks'] == len(data['tasks']) and r['sketches'] == 25 and r['notes'] == 3000 and r['colored'] > 3, r)
        await pg.evaluate("""window.__lt = []; new PerformanceObserver(l => l.getEntries().forEach(e => window.__lt.push(e.duration))).observe({ type: 'longtask', buffered: false });""")
        # one-off actions
        for name, js, budget in [('switch chapter', "openDoc(P.docs[40].id)", 3000), ('Project home with the task card', "openHome()", 4000), ('all open tasks', "closeHome(); openTaskAll()", 3000),
                                 ('a chapter’s tasks', "$('#taskAllDlg').close(); openTasks({ anchor: '' })", 1500), ('drafting-color menu counts', "$('#taskDlg').close(); openInk()", 4000),
                                 ('save (serialize)', "closePop(); projectJSON().length", SAVE_BUDGET), ('Markdown export of a chapter', "buildExport(P.docs[40], 'md').body.length", 5000)]:
            ms = await pg.evaluate(f"(async () => {{ const a = performance.now(); {js}; await new Promise(r => requestAnimationFrame(() => setTimeout(r, 0))); return Math.round(performance.now() - a); }})()")
            print(f'  {name}: {ms} ms'); check(f'{name} within {budget} ms', ms < budget, ms)
        # typing in a colored chapter, with headings carrying task counts
        await pg.evaluate("openDoc(P.docs[2].id)"); await pg.wait_for_timeout(1500)
        await pg.locator('#editor p').nth(3).click(); await pg.keyboard.press('End')
        await pg.evaluate("window.__lt = []")
        for i, ch in enumerate('The supply column halted at dusk. ' * 2):
            await pg.keyboard.type(ch); await pg.wait_for_timeout(90 if i % 7 else 400)
        await pg.wait_for_timeout(1500)
        lt = await pg.evaluate("window.__lt"); worst = round(max(lt) if lt else 0)
        print('typing: worst freeze', worst, 'ms,', len(lt), 'long tasks')
        check(f'typing never freezes the page longer than {WORST_BUDGET} ms', worst <= WORST_BUDGET, worst)
        # save, reopen, nothing lost
        text = await pg.evaluate("projectJSON()")
        r = await pg.evaluate("t => { const p = normalize(JSON.parse(t)); return { tasks: p.tasks.length, sketches: Object.keys(p.sketches).length, typed: p.docs[2].html.includes('supply column halted') }; }", text)
        check('a save reads back whole', r['tasks'] == len(data['tasks']) and r['sketches'] == 25 and r['typed'], r)
        print('ERRS', json.dumps(errs[:5]))
        await b.close()
    return ok and not errs

if __name__ == '__main__':
    sys.exit(0 if asyncio.run(main()) else 1)
