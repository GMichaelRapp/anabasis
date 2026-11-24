"""1.3: 55 citation styles, BibTeX/RIS/CSL-JSON export, Pandoc and LaTeX packages, suggest mode with
Word tracked changes and comments both ways, starter projects, and reading aloud."""
import asyncio, io, json, os, re, shutil, subprocess, sys, tempfile, zipfile
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from env import URL, OUT
from playwright.async_api import async_playwright

MOD = 'Meta' if sys.platform == 'darwin' else 'Control'
STUB = """window.__said = []; const fake = { getVoices(){ return [{ name: 'Test Voice', lang: 'en-US', voiceURI: 't1', localService: true }]; }, addEventListener(){}, cancel(){ this.cur = null; },
  speak(u){ window.__said.push(u.text); this.cur = u; setTimeout(() => { if (this.cur === u && u.onend) u.onend(); }, 60); } };
Object.defineProperty(window, 'speechSynthesis', { value: fake, configurable: true }); window.SpeechSynthesisUtterance = function (t) { this.text = t; };"""


async def main():
    ok = True
    def check(name, cond, extra=''):
        nonlocal ok
        print(('PASS ' if cond else 'FAIL ') + name, extra if not cond else ''); ok = ok and bool(cond)
    errs = []
    async with async_playwright() as pw:
        b = await pw.chromium.launch()
        ctx = await b.new_context(viewport={'width': 1440, 'height': 900}, accept_downloads=True)
        await ctx.add_init_script("delete window.showSaveFilePicker; localStorage.setItem('commonplace.prefs',JSON.stringify({startHome:false,toured:true,seenVersion:'99.0.0',myName:'Ed Itor'}))")
        await ctx.add_init_script(STUB)
        pg = await ctx.new_page()
        pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.on('console', lambda m: errs.append('console: ' + m.text) if m.type == 'error' else None)
        await pg.goto(URL); await pg.wait_for_timeout(1500)
        async def dl(js):
            async with pg.expect_download() as d: await pg.evaluate(js)
            return await (await d.value).path()

        # ---- citation styles
        r = await pg.evaluate("""() => { const d = curDoc(), out = {}; for (const k of Object.keys(STYLES)) { try { d.style = k; lastSig = ''; renderRefs(true);
            out[k] = { cite: (editor.querySelector('.cite') || {}).textContent || '', refs: ($('#refs').innerText || '').length }; } catch (e) { out[k] = { err: e.message }; } }
            d.style = DEFAULT_STYLE; lastSig = ''; renderRefs(true); return out; }""")
        bad = {k: v for k, v in r.items() if v.get('err') or not v['cite'].strip() or v['refs'] < 20}
        check(f'all {len(r)} citation styles format the sample without errors', len(r) >= 55 and not bad, bad)
        g = await pg.evaluate("() => [...$('#docStyle').querySelectorAll('optgroup')].map(o => [o.label, o.children.length])")
        check('style picker is grouped by field', [x[0] for x in g] == ['Most used', 'Humanities & history', 'Social sciences', 'Law', 'Sciences & medicine', 'Engineering & standards'] and sum(x[1] for x in g) == len(r), g)

        # ---- references out, and back in
        bib = open(await dl("() => { openRefExport(); $('#refExpDlg [data-re=bib]').click(); }"), encoding='utf-8').read()
        ris = open(await dl("() => { openRefExport(); $('#refExpDlg [data-re=ris]').click(); }"), encoding='utf-8').read()
        cj = json.load(open(await dl("() => { openRefExport(); $('#refExpDlg [data-re=json]').click(); }"), encoding='utf-8'))
        check('BibTeX export: readable keys and fields', '@book{tuchman1962guns,' in bib and 'pages = {40--61}' in bib and 'doi = {10.1080/00396338.2013.784469}' in bib, bib[:300])
        check('RIS export: one record per source', ris.count('TY  - ') == 2 and ris.count('ER  - ') == 2 and 'AU  - Tuchman, Barbara W.' in ris)
        check('CSL-JSON export carries the same keys', sorted(x['id'] for x in cj) == ['mumford2013why', 'tuchman1962guns'])
        back = await pg.evaluate("""([bib, ris]) => { const a = parseBibTeX(bib), b = parseRIS(ris); return [a.map(x => [x.type, x.title, x.author && x.author[0].family, x.page || '']), b.map(x => [x.type, x.title, x.author && x.author[0].family, x.page || ''])]; }""", [bib, ris])
        check('exported BibTeX and RIS import back the same sources', sorted(map(tuple, back[0])) == sorted(map(tuple, back[1])) and len(back[0]) == 2 and ('article-journal', 'Why States Act through Proxies', 'Mumford', '40–61') in map(tuple, back[0]), back)
        await pg.evaluate("() => { openRefExport(); $('#reCited').click(); }")
        check('export can be limited to sources cited in the document', await pg.evaluate("() => $('#reCount').textContent") == '2')
        await pg.evaluate("() => $('#refExpDlg').close()")

        # ---- Pandoc and LaTeX packages
        z = zipfile.ZipFile(await dl("() => $('#exportMenu [data-x=pandoc]').click()"))
        names = z.namelist(); md = z.read([n for n in names if n.endswith('.md')][0]).decode()
        check('Pandoc package: text, bibliography, style, readme', any(n.endswith('references.bib') for n in names) and any(n.endswith('chicago-notes-bibliography.csl') for n in names) and any(n.endswith('README.txt') for n in names), names)
        check('Pandoc text cites by key with locators, and keeps text footnotes', '[@tuchman1962guns, p. 3]' in md and '[@mumford2013why, p. 41–42]' in md and '^[This is a text footnote' in md and 'bibliography: references.bib' in md, md[:400])
        if shutil.which('pandoc'):
            d = tempfile.mkdtemp(); z.extractall(d); root = os.path.join(d, os.path.dirname(names[0]))
            out = subprocess.run(['pandoc', os.path.basename([n for n in names if n.endswith('.md')][0]), '--citeproc', '-t', 'plain'], cwd=root, capture_output=True, text=True, timeout=120)
            check('pandoc --citeproc renders the package', out.returncode == 0 and 'Tuchman, Barbara W. The Guns of August' in out.stdout, out.stderr[:300])
        z = zipfile.ZipFile(await dl("() => $('#exportMenu [data-x=latex]').click()"))
        tex = z.read([n for n in z.namelist() if n.endswith('main.tex')][0]).decode()
        check('LaTeX package: biblatex citations, footnotes, tables', '\\autocite[3]{tuchman1962guns}' in tex and '\\footnote{This is a text footnote' in tex and '\\begin{tabular}{lll}' in tex and '\\addbibresource{references.bib}' in tex and 'biblatex-chicago' in tex)

        # ---- suggest mode
        await pg.click('#btnSuggest')
        await pg.evaluate("""() => { const p = [...editor.querySelectorAll('p')].find(p => p.textContent.startsWith('Plans built')); const t = p.firstChild; const r = document.createRange(); r.setStart(t, t.data.indexOf(' can')); r.collapse(true); const s = getSelection(); s.removeAllRanges(); s.addRange(r); editor.focus(); }""")
        for _ in range(5): await pg.keyboard.press('Backspace')
        await pg.keyboard.type('haste'); await pg.wait_for_timeout(300)
        p = await pg.evaluate("() => { const p = [...editor.querySelectorAll('p')].find(p => p.textContent.startsWith('Plans')); return { ins: [...p.querySelectorAll('ins.sg')].map(e => e.textContent + '|' + e.dataset.by), del: [...p.querySelectorAll('del.sg')].map(e => e.textContent + '|' + e.dataset.by) }; }")
        check('suggest mode: deleting marks text, typing inserts it, both signed', p == {'ins': ['haste|Ed Itor'], 'del': ['speed|Ed Itor']}, p)
        await pg.keyboard.press('Backspace'); await pg.keyboard.press('Backspace'); await pg.wait_for_timeout(150)
        check('deleting your own suggested text removes it outright', await pg.evaluate("() => [...editor.querySelectorAll('ins.sg')].map(e => e.textContent).join() === 'has'"))
        await pg.keyboard.type('te'); await pg.wait_for_timeout(200)
        check('word count leaves out suggested deletions', await pg.evaluate("() => { const c = editor.cloneNode(true); c.querySelectorAll('.cite,.fn,.flag,del.sg').forEach(x => x.remove()); return parseInt($('#wordCount').textContent.replace(/,/g, ''), 10) === c.innerText.trim().split(/\\s+/).filter(Boolean).length; }"))
        html = await pg.evaluate("() => buildExport(curDoc(), 'html').body")
        check('other exports show suggestions as accepted', 'Plans built for haste can crowd out diplomacy' in re.sub('<[^>]+>', '', html) and 'speed' not in re.sub('<[^>]+>', '', html).split('Plans built')[1][:40])
        z = zipfile.ZipFile(await dl("() => $('#exportMenu [data-x=docx]').click()")); xml = z.read('word/document.xml').decode()
        check('Word export keeps suggestions as tracked changes', '<w:ins ' in xml and '<w:del ' in xml and 'w:author="Ed Itor"' in xml and '<w:delText' in xml)
        await pg.keyboard.press(f'{MOD}+z'); await pg.wait_for_timeout(200)
        check('undo takes back suggested typing and deleting', await pg.evaluate("() => !editor.querySelector('.sg') && editor.textContent.includes('Plans built for speed can')"))
        await pg.keyboard.press(f'{MOD}+Shift+z'); await pg.wait_for_timeout(200)
        await pg.click('#sgToggle'); await pg.wait_for_timeout(100)
        el = await pg.evaluate("() => { const d = editor.querySelector('del.sg'); const r = d.getClientRects()[0]; return [r.left + 5, r.top + r.height / 2]; }")
        await pg.mouse.click(*el); await pg.wait_for_timeout(200)
        check('clicking a suggestion offers Accept and Reject', await pg.locator('.sg-pop button', has_text='Accept').count() == 1)
        await pg.click('.sg-pop button:has-text("Reject")'); await pg.wait_for_timeout(200)
        check('rejecting a deletion restores the text', await pg.evaluate("() => !editor.querySelector('del.sg') && editor.textContent.includes('Plans built for hastespeed can') "))
        await pg.click('[data-sga=accall]'); await pg.wait_for_timeout(200)
        check('accept all leaves clean text', await pg.evaluate("() => !editor.querySelector('.sg') && editor.textContent.includes('for hastespeed can') && $('#sgBar').classList.contains('hidden')"))
        # Word in: tracked changes and comments
        await pg.evaluate("""() => { const p = editor.querySelectorAll('p')[1]; const r = document.createRange(); r.setStart(p.firstChild, 0); r.setEnd(p.firstChild, 8); getSelection().removeAllRanges(); getSelection().addRange(r); savedRange = r.cloneRange(); }""")
        await pg.evaluate("() => addComment()"); await pg.wait_for_timeout(200)
        await pg.evaluate("() => { const c = curDoc().comments[curDoc().comments.length - 1]; c.text = 'Is this true of every browser?'; c.author = 'Ed Itor'; syncEditor(); }")
        await pg.click('#btnSuggest'); await pg.evaluate("""() => { const p = editor.querySelectorAll('p')[2]; const t = p.firstChild; const r = document.createRange(); r.setStart(t, 5); r.collapse(true); getSelection().removeAllRanges(); getSelection().addRange(r); editor.focus(); }""")
        await pg.keyboard.type('NEW '); await pg.click('#sgToggle'); await pg.wait_for_timeout(200)
        wp = await dl("() => $('#exportMenu [data-x=docx]').click()")
        await pg.set_input_files('#fileDocx', wp); await pg.wait_for_timeout(2500)
        r = await pg.evaluate("() => ({ sg: [...editor.querySelectorAll('ins.sg,del.sg')].map(e => e.nodeName + ':' + e.textContent + ':' + e.dataset.by), cm: curDoc().comments.map(c => c.text + '|' + c.author), span: (editor.querySelector('.cmt') || {}).textContent, toast: $('#toast').textContent })")
        check('Word import: tracked changes come in as suggestions', r['sg'] == ['INS:NEW :Ed Itor'], r)
        check('Word import: comments become margin notes on their text', r['cm'] == ['Is this true of every browser?|Ed Itor'] and r['span'] == 'This sam' and 'comment' in r['toast'], r)

        # ---- starter projects
        for k in ['thesis', 'article', 'whitepaper', 'proposal', 'investigation']:
            await pg.evaluate("() => { dirtyFile = false; }")
            await pg.evaluate(f"() => openStarter('{k}')"); await pg.wait_for_timeout(700)
            r = await pg.evaluate("() => ({ docs: P.docs.length, src: P.sources.length, read: P.notes.some(n => n.pinned && n.title === 'Read me first'), th: rmAll('th').length, rv: rmAll('rv').length, q: rmAll('q').length, plan: PLI().filter(i => i.type === 'section').length, raw: P.docs.some(d => /⟪|⟫|\\{c:|\\{fn:/.test(d.html)), orphan: P.claims.filter(c => !rmAll('cl').some(p => p.pid === c.id)).length, cites: P.docs.flatMap(d => [...d.html.matchAll(/data-items=\"([^\"]*)\"/g)].map(m => JSON.parse(m[1].replace(/&quot;/g, '\"')))).flat().every(it => P.sources.some(s => s.id === it.id)) })")
            check(f'starter “{k}” is complete', r['docs'] >= 1 and r['src'] >= 1 and r['read'] and r['th'] >= 1 and r['rv'] == 1 and r['q'] >= 1 and r['plan'] >= 4 and not r['raw'] and r['orphan'] == 0 and r['cites'], r)
        saved = await pg.evaluate("() => projectJSON()")
        await pg.evaluate("t => loadProjectText(t, null, 'x.json')", saved); await pg.wait_for_timeout(600)
        check('a starter saves and reopens intact', await pg.evaluate("() => P.title.startsWith('Investigation') && rmAll('cl').length === 3"))

        # ---- reading aloud
        await pg.evaluate("() => { PREFS.ttsCites = true; dirtyFile = false; openStarter('article'); }"); await pg.wait_for_timeout(600)
        await pg.evaluate("() => { const r = document.createRange(); r.setStart(editor.querySelector('h1'), 0); r.collapse(true); getSelection().removeAllRanges(); getSelection().addRange(r); }")
        await pg.click('#btnListen'); await pg.wait_for_timeout(40)
        hl = await pg.evaluate("() => !!(CSS.highlights && CSS.highlights.get('tts'))")
        await pg.wait_for_timeout(2500)
        said = await pg.evaluate("window.__said")
        check('Listen reads sentence by sentence, highlighting each', hl and said[0] == 'The Wire That Shrank the World.' and len(said) >= 6, (hl, len(said)))
        check('…with note numbers when asked, never the marker text itself', any(s.endswith(', note 1.') for s in said) and not any('[cite]' in s for s in said), said)
        check('…and stops at the end', await pg.evaluate("() => !TTS.on && $('#ttsBar').classList.contains('hidden') && !(CSS.highlights && CSS.highlights.get('tts'))"))
        await pg.evaluate("() => { window.__said = []; const p = editor.querySelectorAll('p')[1]; const r = document.createRange(); r.setStart(p, 0); r.collapse(true); getSelection().removeAllRanges(); getSelection().addRange(r); ttsStart(true); }"); await pg.wait_for_timeout(60)
        first = await pg.evaluate("window.__said[0]")
        check('Listen starts from the cursor', first.startswith('Within a decade'), first)
        await pg.evaluate("() => openDoc(P.docs[0].id)"); await pg.wait_for_timeout(100)
        check('switching documents stops reading', await pg.evaluate("() => !TTS.on"))
        await b.close()
    print('ERRS', errs)
    return ok and not errs

if __name__ == '__main__':
    sys.exit(0 if asyncio.run(main()) else 1)
