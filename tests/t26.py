"""Big-project stress test: a 120,000-word book with 300 sources and 600 notes."""
import asyncio, json, os, random, sys, time
from playwright.async_api import async_playwright
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from env import URL, HTTP, OUT, FX, AXE
URL = os.environ.get('ANABASIS_URL', URL)
HERE = OUT
random.seed(7)
WORDS = ('the army moved east along the river while the ministry argued about supply lines and the press reported '
         'heavy losses near the border towns where artillery and drones changed how commanders planned each operation '
         'NATO officials may have expected a shorter campaign but reserves and logistics proved decisive over the winter').split()

def para(n):
    w = [random.choice(WORDS) for _ in range(n)]
    w[0] = w[0].capitalize()
    return ' '.join(w) + '.'

def build():
    sources = [{'id': f's{i}', 'csl': {'type': 'article-journal', 'title': f'Study {i} of the war', 'author': [{'family': f'Author{i}', 'given': 'A.'}], 'container-title': 'Journal', 'issued': {'date-parts': [[2000 + i % 25]]}, 'page': '1–20'},
                'osint': {'rating': random.choice(['A1', 'B2', 'C3', 'D4', 'E5'])}} for i in range(300)]
    docs = []
    for c in range(30):
        html = f'<h1>Chapter {c + 1}</h1>'
        words = 0
        while words < 4000:
            if words % 1200 < 120: html += f'<h2>Section {words // 1200 + 1}</h2>'
            n = random.randint(60, 140); words += n
            ids = random.sample(range(300), random.randint(1, 3))
            cite = '<span class="cite" contenteditable="false" data-items=\'' + json.dumps([{'id': f's{i}', 'locator': str(random.randint(1, 300)), 'label': 'page'} for i in ids]) + '\'></span>'
            html += f'<p>{para(n)}{cite}</p>'
        docs.append({'id': f'd{c}', 'title': f'Chapter {c + 1}', 'html': html, 'style': 'chicago-notes-bibliography', 'order': c})
    notes = [{'id': f'n{i}', 'title': f'Note {i}', 'body': para(50), 'kind': 'quote', 'tags': ['tag' + str(i % 20)], 'sourceId': f's{i % 300}', 'date': f'19{14 + i % 5}-0{1 + i % 9}-1{i % 9}'} for i in range(600)]
    return {'app': 'Anabasis', 'format': 2, 'id': 'p_big', 'title': 'Big book', 'docs': docs, 'notes': notes, 'sources': sources}

async def main():
    path = os.path.join(HERE, 'big.json'); json.dump(build(), open(path, 'w'))
    print('file MB', round(os.path.getsize(path) / 1e6, 2))
    async with async_playwright() as pw:
        b = await pw.chromium.launch()
        ctx = await b.new_context(viewport={'width': 1440, 'height': 900}, accept_downloads=True)
        await ctx.add_init_script("delete window.showSaveFilePicker; delete window.showOpenFilePicker; localStorage.setItem('commonplace.prefs',JSON.stringify({startHome:false,toured:true,seenVersion:'99.0.0'}))")
        pg = await ctx.new_page(); errs = []
        pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto(URL); await pg.wait_for_timeout(1000)
        t = time.time()
        await pg.set_input_files('#fileOpen', path)
        await pg.wait_for_function("() => (P && P.title === 'Big book')", timeout=60000)
        print('open (s)', round(time.time() - t, 2))
        await pg.wait_for_timeout(1500)
        res = await pg.evaluate("""(async()=>{
          const T = {}, time = (k, f) => { const a = performance.now(); f(); T[k] = Math.round(performance.now() - a); };
          T.words = P.docs.reduce((n,d)=>n+wc(docPlain(d.html)),0);
          time('switch chapter', () => openDoc(P.docs[15].id));
          time('render references', () => renderRefs(true));
          time('house style scan', () => renderHouse());
          time('corroboration', () => { PREFS.corrOn = true; renderCorroboration(); });
          time('accessibility', () => renderA11y());
          time('acronyms', () => renderAcronyms());
          time('render all panes', () => renderAll());
          time('project JSON', () => projectJSON());
          time('find in all docs', () => { $('#frFind').value = 'logistics'; frSearch(); });
          T.findHits = FR.hits.length;
          await persistLocal(); time('persist (sync part)', () => persistLocal());
          return T; })()""")
        for k, v in res.items(): print(f'{k:22} {v}')
        # typing latency: time from keydown to the next frame
        await pg.click('#editor p:nth-of-type(3)')
        lat = await pg.evaluate("""(async()=>{ const out=[]; for (let i=0;i<25;i++){ const a=performance.now(); document.execCommand('insertText', false, 'x'); await new Promise(r=>requestAnimationFrame(()=>setTimeout(r,0))); out.push(performance.now()-a);} out.sort((a,b)=>a-b); return {median: Math.round(out[12]), worst: Math.round(out[24])}; })()""")
        print('typing latency ms', lat)
        await pg.evaluate("$('#btnExport').click()")
        t = time.time()
        async with pg.expect_download(timeout=120000) as dl: await pg.click('#exportMenu [data-x=docx]')
        print('Word export (s)', round(time.time() - t, 2))
        print('ERRS', errs)
        await b.close()
        bad = lat['median'] > 50 or res['render references'] > 1500
        sys.exit(1 if errs or bad else 0)
asyncio.run(main())
