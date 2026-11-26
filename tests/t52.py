"""2.8.0: special characters by name, contents and lists, paragraph and line numbers, the précis, and editing marks."""
import asyncio, base64, io, zipfile
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from env import URL
from playwright.async_api import async_playwright

DOC = ('<h1>Rivers of the High Plains</h1><p>The Canadian River crosses the Llano Estacado from west to east. It was surveyed in 1853 by a small party.</p>'
       '<h2>Sources of water</h2><p>Springs feed the upper river, and the Ogallala aquifer lies under most of the plain.</p>'
       '<figure><img src="data:image/gif;base64,R0lGODlhAQABAAAAACw=" alt=""><figcaption>The river near Tucumcari</figcaption></figure>'
       '<h2>Uses of the river</h2><p>Farmers took water for irrigation, and towns grew along the railroad.</p>'
       '<figure class="tbl"><table><tbody><tr><td>1900</td><td>12</td></tr></tbody></table><figcaption>Towns on the river</figcaption></figure>'
       '<figure><img src="data:image/gif;base64,R0lGODlhAQABAAAAACw=" alt=""><figcaption>A windmill and tank</figcaption></figure>'
       '<p>There were 7 wells in the county and the the water was hard.</p>')


async def main():
    ok = True
    def check(name, cond, extra=''):
        nonlocal ok
        print(('PASS ' if cond else 'FAIL ') + name, extra if not cond else ''); ok = ok and bool(cond)
    errs = []
    async with async_playwright() as pw:
        b = await pw.chromium.launch()
        ctx = await b.new_context(viewport={'width': 1440, 'height': 950})
        await ctx.add_init_script("delete window.showSaveFilePicker; localStorage.setItem('commonplace.prefs',JSON.stringify({startHome:false,toured:true,seenVersion:'99.0.0',myName:'Ada Ferro',orcDay:new Date().toISOString().slice(0,10)}))")
        pg = await ctx.new_page()
        pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.on('console', lambda m: errs.append('console: ' + m.text) if m.type == 'error' and 'Failed to load resource' not in m.text else None)
        await pg.goto(URL); await pg.wait_for_timeout(1500)
        await pg.evaluate("() => { dirtyFile = false; return openStarter('thesis'); }"); await pg.wait_for_timeout(1300)
        await pg.evaluate("() => document.querySelectorAll('dialog[open]').forEach(d => d.close())")
        await pg.evaluate("(h) => { const d = newDoc('Rivers', h); addDoc(d); renderDocList(); openDoc(d.id); }", DOC); await pg.wait_for_timeout(400)

        # ---- special characters, found by name
        await pg.evaluate("() => { const p = editor.querySelector('p'); const r = document.createRange(); r.setStart(p.firstChild, 3); r.collapse(true); editor.focus(); getSelection().removeAllRanges(); getSelection().addRange(r); openChars(editor); }")
        await pg.fill('#spcQ', 'integral'); await pg.wait_for_timeout(100)
        r = await pg.evaluate("[...document.querySelectorAll('#spcGrid .chb')].map(b => b.dataset.ch)")
        check('the character palette finds characters by name', r[:3] == ['∫', '∬', '∮'], r)
        await pg.press('#spcQ', 'Enter'); await pg.wait_for_timeout(150)
        r = await pg.evaluate("editor.querySelector('p').textContent.slice(0, 12)")
        check('…and Enter inserts the first one where the cursor was', r.startswith('The∫ '), r)
        r = await pg.evaluate("(() => { const out = {}; for (const [q, want] of [['subscript 2', '₂'], ['equilibrium', '⇌'], ['therefore', '∴'], ['thin space', '\\u2009'], ['angstrom', 'Å']]) { $('#spcQ').value = q; chRender(); out[q] = $('#spcGrid .chb')?.dataset.ch === want; } return out; })()")
        check('…math, logic, scripts, units and scholarly sets all have names', all(r.values()), r)
        check('…invisible spaces show a visible stand-in', await pg.evaluate("chShow('\\u2009') === '␣' && chShow('\\u200b') === 'ZW'"))
        await pg.evaluate("() => { document.execCommand('undo'); $('#spcDlg').close(); }")

        # ---- contents and lists
        await pg.evaluate("() => { const h = editor.querySelector('h1'); const r = document.createRange(); r.setStartAfter(h); r.collapse(true); editor.focus(); getSelection().removeAllRanges(); getSelection().addRange(r); INSERT_EXTRA.toc(); }")
        await pg.evaluate("() => { const p = editor.lastElementChild; const r = document.createRange(); r.selectNodeContents(p); r.collapse(false); getSelection().removeAllRanges(); getSelection().addRange(r); INSERT_EXTRA.lofig(); INSERT_EXTRA.lotab(); }")
        await pg.wait_for_timeout(300)
        r = await pg.evaluate("""(() => ({ toc: $$('nav.toc li', editor).map(l => [l.className, l.textContent]), fig: $$('nav.lof[data-k=fig] li', editor).map(l => l.textContent), tbl: $$('nav.lof[data-k=tbl] li', editor).map(l => l.textContent), ce: editor.querySelector('nav.toc').getAttribute('contenteditable') }))()""")
        check('Insert → Contents lists the headings, by level', r['toc'] == [['nav-lv1', 'Rivers of the High Plains'], ['nav-lv2', 'Sources of water'], ['nav-lv2', 'Uses of the river']] and r['ce'] == 'false', r)
        check('…a list of figures and a list of tables, each numbered in its own series', r['fig'] == ['Figure 1. The river near Tucumcari', 'Figure 2. A windmill and tank'] and r['tbl'] == ['Table 1. Towns on the river'], r)
        await pg.evaluate("() => { const h = document.createElement('h2'); h.textContent = 'Floods'; editor.querySelector('figure.tbl').before(h); editor.dispatchEvent(new Event('input')); }"); await pg.wait_for_timeout(400)
        check('…the contents update as the writing changes', await pg.evaluate("$$('nav.toc li', editor).map(l => l.textContent).includes('Floods')"))
        await pg.evaluate("() => { const g = $$('nav.toc [data-go]', editor)[3]; g.click(); }"); await pg.wait_for_timeout(100)
        check('…a click goes to the heading', await pg.evaluate("$$('h2', editor).find(h => h.textContent === 'Floods').classList.contains('nav-flash')"))
        r = await pg.evaluate("(() => { syncEditor(); const x = buildExport(curDoc(), 'html'); const t = document.createElement('div'); t.innerHTML = x.body; return { links: $$('nav.toc a', t).map(a => [a.getAttribute('href'), a.textContent, !!t.querySelector(a.getAttribute('href'))]), lof: $$('nav.lof', t).length, edit: t.querySelector('nav[contenteditable]') ? 1 : 0 }; })()")
        check('…in exports the contents are links to each heading', len(r['links']) == 4 and all(l[2] for l in r['links']) and r['links'][0][1] == 'Rivers of the High Plains' and r['edit'] == 0, r)
        md = await pg.evaluate("exportMarkdown(curDoc())")
        check('…and Markdown keeps the contents', 'Sources of water' in md.split('Rivers of the High Plains', 1)[-1][:400], md[:400])

        # ---- paragraph and line numbers
        await pg.evaluate("setNumbering('para', true)"); await pg.wait_for_timeout(400)
        r = await pg.evaluate("$$('#lnLayer .pnum').map(s => s.textContent)")
        check('Paragraph numbers show beside each paragraph', r[:4] == ['¶1', '¶2', '¶3', '¶4'], r)
        r = await pg.evaluate("(() => { const t = document.createElement('div'); t.innerHTML = buildExport(curDoc(), 'html').body; return $$('span.pn', t).map(s => s.textContent); })()")
        check('…and in the exported page', r[:3] == ['1', '2', '3'], r)
        md = await pg.evaluate("exportMarkdown(curDoc())")
        check('…and as [n] in Markdown', '[1] The' in md and '[2] Springs' in md, md[:500])
        await pg.evaluate("setNumbering('line', true)"); await pg.wait_for_timeout(400)
        r = await pg.evaluate("({ ln: $$('#lnLayer .ln').length, first: $('#lnLayer .ln')?.textContent, right: $$('#lnLayer .pnum.r').length })")
        check('Line numbers count every line, and paragraph numbers move to the right', r['ln'] >= 5 and r['first'] == '1' and r['right'] >= 4, r)
        dx = await pg.evaluate("(async () => { const b = await exportDocx(curDoc(), { returnBlob: true }); const u = new Uint8Array(await b.arrayBuffer()); let s = ''; for (let i = 0; i < u.length; i += 32768) s += String.fromCharCode.apply(null, u.subarray(i, i + 32768)); return btoa(s); })()")
        z = zipfile.ZipFile(io.BytesIO(base64.b64decode(dx))); xml = z.read('word/document.xml').decode('utf8')
        check('Word gets line numbering, paragraph numbers and a Contents field', 'w:lnNumType' in xml and '[1] ' in xml and 'TOC \\o' in xml, [x for x in ['w:lnNumType', '[1] ', 'TOC \\o'] if x not in xml])
        check('…which Word fills in when the file opens', 'updateFields' in z.read('word/settings.xml').decode('utf8'))
        await pg.evaluate("setNumbering('line', false); setNumbering('para', false)"); await pg.wait_for_timeout(200)
        check('…and both turn off', await pg.evaluate("!$('#lnLayer') && !curDoc().layout.paraNums && !curDoc().layout.lineNums"))

        # ---- the rhetorical précis
        sid = await pg.evaluate("P.sources[0].id")
        await pg.evaluate("(id) => openPrecis(id)", sid); await pg.wait_for_timeout(200)
        await pg.fill('#prcCred', 'a historian'); await pg.select_option('#prcVerb', 'contends')
        await pg.fill('#prcThesis', 'armies are shaped by what they eat.'); await pg.fill('#prcMethod', 'tracing supply records')
        await pg.fill('#prcPurpose', 'show that logistics drove strategy'); await pg.fill('#prcAim', 'correct the usual story')
        await pg.fill('#prcAudience', 'military historians'); await pg.fill('#prcTone', 'measured'); await pg.wait_for_timeout(100)
        r = await pg.evaluate("({ out: $('#prcOut').textContent, left: $('#prcLeft').textContent, who: prcAuthor(P.sources[0]) })")
        sents = [s for s in r['out'].split('. ') if s]
        check('The précis is four sentences in Woodworth’s order', len(sents) == 4 and ', a historian, in the ' in r['out'] and 'contends that armies are shaped by what they eat.' in r['out']
              and f"{r['who']['last']} supports this claim by tracing supply records." in r['out'] and 'purpose is to show that logistics drove strategy in order to correct the usual story.' in r['out']
              and r['out'].endswith('writes for military historians, in a measured tone.'), r)
        check('…with nothing left to fill in', 'Still to fill in' not in r['left'], r['left'])
        await pg.click('#prcSave'); await pg.wait_for_timeout(200)
        r = await pg.evaluate("(id) => { const n = P.notes.find(x => x.precis && x.sourceId === id); return n && { kind: n.kind, tags: n.tags, title: n.title, body: n.body.slice(0, 60), cred: n.precis.cred }; }", sid)
        check('…it is saved as a summary note on the source, tagged précis', r and r['kind'] == 'summary' and 'précis' in r['tags'] and r['title'].startswith('Précis: ') and r['cred'] == 'a historian', r)
        n = await pg.evaluate("P.docs.length")
        await pg.evaluate("precisCollection()"); await pg.wait_for_timeout(500)
        r = await pg.evaluate("({ n: P.docs.length, t: curDoc().title, e: $$('.ab-entry', editor).length, p: $$('.ab-note', editor).map(x => x.textContent.slice(0, 40)) })")
        check('…and every précis can become one document under its sources', r['n'] == n + 1 and r['t'] == 'Précis' and r['e'] == 1 and len(r['p']) == 1, r)
        await pg.evaluate("normalize(JSON.parse(JSON.stringify(P)))")
        check('…the précis fields survive saving and reopening', await pg.evaluate("normalize(JSON.parse(JSON.stringify(P))).notes.find(n => n.precis).precis.thesis === 'armies are shaped by what they eat.'"))

        # ---- editing marks
        await pg.evaluate("openDoc(P.docs.find(d => d.title === 'Rivers').id)"); await pg.wait_for_timeout(300)
        mark = """async ([words, kind, answer]) => { const p = [...editor.querySelectorAll('p,h2')].find(e => e.textContent.includes(words)); const w = document.createTreeWalker(p, NodeFilter.SHOW_TEXT); let t; while ((t = w.nextNode())) if (t.data.includes(words)) break;
            const a = t.data.indexOf(words), r = document.createRange(); r.setStart(t, a); r.setEnd(t, a + words.length);
            const done = addEditMark(kind, r); await new Promise(z => setTimeout(z, 60)); const d = document.querySelector('#askDlg[open], dialog[open]');
            if (d && answer !== null) { const i = d.querySelector('input'); if (i) i.value = answer; d.querySelector('button.primary, #askOk')?.click(); }
            await done; return $$('span.edm', editor).filter(s => s.textContent && words.includes(s.textContent)).map(s => s.dataset.ek); }"""
        cases = [('Canadian River', 'lc', None), ('west to east', 'tr', None), ('the the', 'del', None), ('7', 'sp', 'seven'),
                 ('small party', 'ital', None), ('Uses of the river', 'cap', None), ('Llano Estacado', 'chk', ''), ('1853', 'aq', 'Is 1853 right? The survey records say 1852.')]
        for w, k, a in cases:
            await pg.evaluate("(a) => { window.__m = (" + mark + ")(a); }", [w, k, a]); await pg.wait_for_timeout(250)
        r = await pg.evaluate("[...new Set($$('span.edm', editor).map(s => s.dataset.ek))]")
        check('Editing marks go on the words: lowercase, transpose, delete, spell out, italic, capitalize, verify, query', sorted(r) == sorted([c[1] for c in cases]), r)
        r = await pg.evaluate("(() => { renderEditMarks(); const s = editor.querySelector('span.edm[data-ek=aq]'); return { list: $$('#emList li').length, head: !$('#emHead').classList.contains('hidden'), by: s.dataset.by, t: s.dataset.t, sym: s.dataset.sym }; })()")
        check('…each one is listed in the Outline, signed with the editor’s name', r['list'] == 8 and r['head'] and r['by'] == 'Ada Ferro' and r['t'].startswith('Is 1853 right') and r['sym'] == 'AQ', r)
        r = await pg.evaluate("(() => { const t = document.createElement('div'); t.innerHTML = buildExport(curDoc(), 'html').body; return { edm: t.querySelectorAll('.edm').length, text: t.textContent.includes('Canadian River') }; })()")
        check('…exports leave the marks out and the words as they were', r == {'edm': 0, 'text': True}, r)
        await pg.evaluate("$('#emAll').click()"); await pg.wait_for_timeout(300)
        r = await pg.evaluate("""(() => { const t = editor.innerText; return { lc: t.includes('The canadian river crosses'), tr: t.includes('from east to west'), del: t.includes('and water was hard') && !t.includes('the the'),
            sp: t.includes('There were seven wells'), ital: !!$$('i', editor).find(i => i.textContent === 'small party'), cap: $$('h2', editor).some(h => h.textContent === 'Uses Of The River'),
            left: [...new Set($$('span.edm', editor).map(s => s.dataset.ek))].sort() }; })()""")
        check('Make every change: each mark’s change is made', all(r[k] for k in ['lc', 'tr', 'del', 'sp', 'ital', 'cap']), r)
        check('…queries and checks are left for the author', r['left'] == ['aq', 'chk'], r['left'])
        await pg.evaluate("() => { openEdmPop(editor.querySelector('span.edm[data-ek=aq]')); $('#edmAns').value = 'Yes: 1853, per the field notes.'; $('.edm-pop [data-x=ok]').click(); }"); await pg.wait_for_timeout(200)
        r = await pg.evaluate("({ aq: !!editor.querySelector('span.edm[data-ek=aq]'), c: curDoc().comments.map(c => c.text), cmt: !!editor.querySelector('span.cmt') })")
        check('…answering a query resolves it and keeps the exchange as a comment', not r['aq'] and r['cmt'] and any('A: Yes: 1853' in c for c in r['c']), r)
        await pg.evaluate("() => { const id = editor.querySelector('span.edm[data-ek=chk]').dataset.edm; edmReject(id); onEdit(); renderEditMarks(); }")
        check('…and with none left the Outline section hides', await pg.evaluate("!editor.querySelector('span.edm') && $('#emHead').classList.contains('hidden')"))
        r = await pg.evaluate("""(() => { editor.innerHTML = '<p>The cat sat on the mat.</p><p>Second paragraph here.</p><p>its done</p>'; const ids = [];
            const mk = (txt, k, t) => { const p = $$('p', editor).find(e => e.textContent.includes(txt)); const n = [...p.childNodes].find(x => x.nodeType === 3 && x.data.includes(txt)), a = n.data.indexOf(txt), r = document.createRange(); r.setStart(n, a); r.setEnd(n, a + txt.length); const s = edmWrap(r, { 'data-edm': uid('em'), 'data-ek': k, 'data-t': t || '' }); ids.push(s[0].dataset.edm); };
            mk('sat', 'ins', 'lay'); mk('on the', 'para'); mk('Second', 'runin'); mk('its', 'ins', 'it’s'); ids.forEach(edmApply); return $$('p', editor).map(p => p.textContent); })()""")
        check('Replace, new paragraph and run in reshape the text', r == ['The cat lay ', 'on the mat. Second paragraph here.', 'it’s done'], r)
        r = await pg.evaluate("[spellNum('7'), spellNum('42'), spellNum('100'), spellNum('1,000')]")
        check('Spelling out numbers', r == ['seven', 'forty-two', 'one hundred', ''], r)
        await pg.evaluate("() => { editor.innerHTML = '<p>Read <i>the long book</i> today.</p>'; const n = editor.querySelector('i').firstChild, r = document.createRange(); r.setStart(n, 4); r.setEnd(n, 8); const s = edmWrap(r, { 'data-edm': 'x1', 'data-ek': 'rom' }); edmApply('x1'); }")
        check('Roman takes the italics off just the marked words', await pg.evaluate("editor.innerHTML") == '<p>Read <i>the </i>long<i> book</i> today.</p>', await pg.evaluate("editor.innerHTML"))

        bad = [e for e in errs if 'favicon' not in e]
        check('no page errors', not bad, bad[:5])
        await b.close()
    print('ALL PASS' if ok else 'SOME FAILED'); _sys.exit(0 if ok else 1)

asyncio.run(main())
