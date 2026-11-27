"""2.5.0: Proofread (misspellings, mixed-up words, a and an, doubled words, spacing, capitals; fix, show, ignore),
the abstract and keywords (a form by kind of piece, suggestions from the draft, keywords, in every export), and
reading a PDF with a note pad beside it."""
import asyncio, io, json, re, sys, zipfile
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from env import URL, OUT
from playwright.async_api import async_playwright

FIX = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'fixtures', 'sample.pdf')


async def main():
    ok = True
    def check(name, cond, extra=''):
        nonlocal ok
        print(('PASS ' if cond else 'FAIL ') + name, extra if not cond else ''); ok = ok and bool(cond)
    errs = []
    async with async_playwright() as pw:
        b = await pw.chromium.launch()
        ctx = await b.new_context(viewport={'width': 1440, 'height': 900}, accept_downloads=True)
        await ctx.add_init_script("delete window.showSaveFilePicker; localStorage.setItem('commonplace.prefs',JSON.stringify({startHome:false,toured:true,seenVersion:'99.0.0',orcDay:new Date().toISOString().slice(0,10)}))")
        pg = await ctx.new_page()
        pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.on('console', lambda m: errs.append('console: ' + m.text) if m.type == 'error' and 'Failed to load resource' not in m.text else None)
        await pg.goto(URL); await pg.wait_for_timeout(1500)
        await pg.evaluate("() => { dirtyFile = false; return openStarter('thesis'); }"); await pg.wait_for_timeout(1300)

        # ---- Proofread: the checks
        scan = lambda t: pg.evaluate("t => pfScan(t).map(f => [f.kind, t.slice(f.at, f.at + f.len), f.fix])", t)
        r = await scan('Teh army recieved alot of grain, wich was more then it needed.')
        check('common misspellings are found, with the fix', ['Spelling', 'Teh', 'The'] in r and ['Spelling', 'recieved', 'received'] in r and ['Spelling', 'alot', 'a lot'] in r and ['Spelling', 'wich', 'which'] in r, r)
        check('"more then" is "more than"', ['Word', 'then', 'than'] in r, r)
        r = await scan('Xenophon would of agreed, but its not clear. Your welcome to check. Their is no record.')
        check('"would of", "its not", "your welcome", "their is"', ['Phrase', 'would of', 'would have'] in r and ['Word', 'its', 'it’s'] in r and ['Word', 'Your', 'You’re'] in r and ['Word', 'Their', 'There'] in r, r)
        r = await scan('It was a honest mistake by an general at an FBI briefing and a hour later a unit and a European left.')
        check('a and an go by sound: an honest, a general, an FBI, an hour, a unit, a European', [x[1:] for x in r] == [['a', 'an'], ['an', 'a'], ['a', 'an']], r)
        r = await scan('The the soldiers marched ,and then stopped.After that,they rested  for a while.')
        check('doubled words, spaces before and after punctuation, two spaces', ['Repeated', 'The the', 'The'] in r and any(x[0] == 'Spacing' for x in r) and len(r) >= 4, r)
        r = await scan('He paused. then he went on, e.g. at Trapezus, i.e. later. Lee et al. argue otherwise, and i agree.')
        check('a capital after a full stop, but not after e.g., i.e. or et al.; "i" is "I"', ['Capital', 't', 'T'] in r and ['Capital', 'i', 'I'] in r and len(r) == 2, r)
        r = await scan('The calvary charged the infantry and it had an affect on morale; for all intensive purposes it was over (as Lee says.')
        check('calvary near horse soldiers, "an affect on", stock phrases, an unclosed bracket', ['Word', 'calvary', 'cavalry'] in r and ['Word', 'affect', 'effect'] in r and ['Phrase', 'for all intensive purposes', 'for all intents and purposes'] in r and any(x[0] == 'Unclosed' for x in r), r)
        clean = await pg.evaluate("""() => { let n = 0; const keep = P; Object.keys(STARTERS).forEach(k => { buildStarter(k); const p = P; (p.docs || []).forEach(d => { const t = document.createElement('div'); t.innerHTML = d.html; [...t.children].forEach(el => { n += pfScan(pfText(el).t).length; }); }); }); P = keep; return n; }""")
        check('nothing is flagged in any of the starter projects', clean == 0, clean)
        # ---- Proofread: the dialog
        await pg.evaluate("() => { const p = document.createElement('p'); p.innerHTML = 'Teh army recieved <i>alot</i> of grain, wich was more then it needed. Xenophon would of agreed.'; editor.insertBefore(p, editor.children[2]); syncEditor(); }")
        await pg.keyboard.press('F7'); await pg.wait_for_timeout(250)
        s = await pg.evaluate("() => ({ open: $('#proofDlg').open, sum: $('#proofSum').textContent, n: $$('#proofList li').length })")
        check('F7 opens Proofread with what it found', s['open'] and s['n'] == 6 and '4 spelling' in s['sum'], s)
        await pg.click('#proofFixAll'); await pg.wait_for_timeout(150)
        await pg.click('[data-pf-fix]'); await pg.wait_for_timeout(150)
        await pg.click('[data-pf-fix]'); await pg.wait_for_timeout(150)
        h = await pg.evaluate("() => editor.children[2].innerHTML")
        check('Fix all spellings and Fix mend the text, keeping its italics', h == 'The army received <i>a lot</i> of grain, which was more than it needed. Xenophon would have agreed.', h)
        await pg.evaluate("() => { editor.children[2].innerHTML = 'The wether was cold. Teh end.'; syncEditor(); }")
        await pg.click('#proofAgain'); await pg.wait_for_timeout(120)
        await pg.click('[data-pf-ign]'); await pg.wait_for_timeout(150)
        ig = await pg.evaluate("() => ({ list: P.proofIgnore, left: pfList.map(f => f.word) })")
        check('Ignore keeps a word out of Proofread for the whole project', 'wether' in ig['list'] and ig['left'] == ['Teh'], ig)
        await pg.click('#proofClose')
        await pg.click('#btnTbMore'); await pg.click('#tbMore [data-x=proof]'); await pg.wait_for_timeout(200)
        check('Proofread is in the toolbar’s ⋯ menu too', await pg.evaluate("() => $('#proofDlg').open"))
        await pg.click('#proofClose')
        await pg.evaluate("() => { editor.children[2].remove(); syncEditor(); }")

        # ---- Abstract and keywords
        await pg.click('#btnExport'); await pg.click('#exportMenu [data-x="abstract"]'); await pg.wait_for_timeout(250)
        check('Export → Abstract and keywords opens the form, with parts for the kind of piece', await pg.evaluate("() => $('#absDlg').open && $$('#absParts textarea').length === 5"))
        await pg.click('#absSuggest'); await pg.wait_for_timeout(150)
        a = await pg.evaluate("() => { const a = curDoc().meta.abstract; return { parts: Object.values(a.parts).filter(Boolean).length, text: a.text, count: $('#absCount').textContent, arg: a.parts.argument }; }")
        check('Suggest from the draft fills the parts with the draft’s own sentences, and the abstract follows', a['parts'] >= 4 and 'negotiation with hunger' in a['arg'] and a['text'].startswith('Histories of the retreat') and 'of 250 words' in a['count'], a)
        await pg.select_option('#absLimit', '100'); await pg.wait_for_timeout(50)
        check('the count turns red over the limit', await pg.evaluate("() => $('#absCount').classList.contains('over') === (wc($('#absText').value) > 100)"))
        await pg.fill('#absText', 'Supply, not courage, set the route and pace of the Ten Thousand. Reading Xenophon’s halts against modern estimates of rations, this chapter argues the march was a long negotiation with hunger.')
        await pg.click('#absKwSug'); await pg.wait_for_timeout(120)
        kw = await pg.evaluate("() => [...$$('#absKwPick button')].map(b => b.dataset.kwAdd)")
        check('suggested keywords are the document’s own names and terms, not everyday words', 'Xenophon' in kw and 'grain' in kw and not any(x in kw for x in ['argued', 'several', 'turn', 'army’s']), kw)
        await pg.click('#absKwPick [data-kw-add="Xenophon"]'); await pg.click('#absKwPick [data-kw-add="grain"]')
        await pg.fill('#absKwIn', 'ancient logistics'); await pg.press('#absKwIn', 'Enter')
        await pg.click('#absDone')
        ab = await pg.evaluate("() => curDoc().meta.abstract")
        check('the abstract and keywords are kept with the document', ab['keywords'] == ['Xenophon', 'grain', 'ancient logistics'] and ab['text'].startswith('Supply, not courage') and ab['include'], ab)
        x = await pg.evaluate("() => buildExport(curDoc(), 'html').title")
        check('exports carry the abstract under the title, with its keywords', '<section class="abstract"><p class="ab-h">Abstract</p><p class="ab-t">Supply, not courage' in x and 'Keywords:</i> Xenophon; grain; ancient logistics' in x, x[:200])
        pk = await pg.evaluate("""() => { let got = []; const z = zipStore, d = download; zipStore = files => { got = got.concat(files); return new Uint8Array(1); }; download = () => {}; try { exportLatex(curDoc()); exportPandoc(curDoc()); } finally { zipStore = z; download = d; } return got.filter(f => /\\.(tex|md)$/.test(f.name)).map(f => typeof f.data === 'string' ? f.data : new TextDecoder().decode(f.data)).join('\\n=====\\n'); }""")
        check('LaTeX gets an abstract environment with the keywords, Pandoc an abstract and keywords in its front matter', '\\begin{abstract}' in pk and '\\textit{Keywords:} Xenophon; grain; ancient logistics' in pk and 'abstract: "Supply, not courage' in pk and 'keywords: ["Xenophon", "grain", "ancient logistics"]' in pk, pk[:600])
        await pg.evaluate("() => { curDoc().meta.abstract.include = false; }")
        check('with Include off, exports leave it out', await pg.evaluate("() => !buildExport(curDoc(), 'html').title.includes('abstract')"))
        await pg.evaluate("() => { curDoc().meta.abstract.include = true; }")
        norm = await pg.evaluate("() => { const p = JSON.parse(JSON.stringify(P)); p.docs[0].meta.abstract = { text: 5, keywords: 'x', limit: 'big', shape: 'nope' }; const q = normalize(p); return q.docs[0].meta.abstract; }")
        check('a damaged abstract in a file is mended on opening', norm['text'] == '5' and norm['keywords'] == [] and norm['limit'] == 0 and norm['shape'] == 'humanities', norm)

        # ---- Read and take notes
        await pg.evaluate("localStorage.removeItem('commonplace.rdat')")  # open at the first page, not where an earlier step left off
        await pg.set_input_files('#filePdf', FIX); await pg.wait_for_timeout(2500)
        await pg.click('#rdNotes'); await pg.wait_for_timeout(500)
        await pg.wait_for_function("() => document.querySelectorAll('#rdPages .rd-page .textLayer span').length > 6", timeout=30000)  # slow machines: wait for the text layer
        lay = await pg.evaluate("() => ({ on: document.body.classList.contains('rr-on'), main: getComputedStyle($('#main')).display, pane: !$('#rrPane').classList.contains('hidden'), left: $('#reader').getBoundingClientRect().left < $('#rrPane').getBoundingClientRect().left })")
        check('Take notes puts the PDF on the left and a note pad on the right, the writing set aside', lay['on'] and lay['main'] == 'none' and lay['pane'] and lay['left'], lay)
        await pg.fill('#rrText', 'Timetables made the plan rigid.'); await pg.fill('#rrTags', 'war plans')
        await pg.press('#rrText', 'Control+Enter')
        await pg.wait_for_function("() => $('#rrText').value === ''", timeout=10000)
        sel = await pg.evaluate("""() => { const sp = [...document.querySelectorAll('#rdPages .rd-page .textLayer span')].filter(s => s.textContent.trim().length > 20)[2]; if (!sp) return ''; const r = document.createRange(); r.selectNodeContents(sp); const s = getSelection(); s.removeAllRanges(); s.addRange(r); return sp.textContent.trim(); }""")
        await pg.wait_for_timeout(350)
        await pg.click('#rdSelBar [data-k="quote"]'); await pg.wait_for_timeout(200)
        pad = await pg.evaluate("() => ({ t: $('#rrText').value, k: $('#rrKind').value, p: $('#rrPage').value })")
        check('a passage selected in the PDF goes to the pad as a quote, with its page, to comment on first', sel and pad['t'] == f'“{sel}”' and pad['k'] == 'quote' and pad['p'], pad)
        await pg.click('#rrSave'); await pg.wait_for_timeout(300)
        ns = await pg.evaluate("() => P.notes.filter(n => n.sourceId && n.sourceId === R.sourceId).map(n => ({ k: n.kind, p: n.locator, tags: n.tags, b: n.body }))")
        check('saved notes go to the PDF’s source, with the page and tags; quotes without their quotation marks', len(ns) == 2 and any(n['k'] == 'idea' and n['tags'] == ['war plans'] for n in ns) and any(n['k'] == 'quote' and n['b'] == sel for n in ns), ns)
        check('the pad lists this source’s notes in page order', await pg.evaluate("() => $$('#rrList li').length === 2"))
        await pg.click('#rrList [data-rr-ed]'); await pg.wait_for_timeout(100)
        await pg.fill('#rrList textarea', 'Timetables made the plan rigid, and fast.'); await pg.click('#rrText'); await pg.wait_for_timeout(150)
        check('clicking a note edits it in place', await pg.evaluate("() => P.notes.some(n => n.body === 'Timetables made the plan rigid, and fast.')"))
        await pg.click('#rrDone'); await pg.wait_for_timeout(200)
        back = await pg.evaluate("() => ({ on: document.body.classList.contains('rr-on'), main: getComputedStyle($('#main')).display, reader: readerOpen() })")
        check('Back to writing restores the writing beside the reader', not back['on'] and back['main'] != 'none' and back['reader'], back)

        # ---- 2.5.1: research process prompts in the journal
        await pg.evaluate("() => { curDoc().style = 'apa'; }")
        await pg.click('#rsToday'); await pg.wait_for_timeout(400)
        n0 = await pg.evaluate("() => ({ n: $$('[data-jp]').length, txt: $('.j-prompts p').textContent })")
        check('the journal offers twelve research-process stages above the log', n0['n'] == 12 and 'of 12 stages' in n0['txt'], n0)
        await pg.click('[data-jp="3"]'); await pg.wait_for_timeout(80)
        st = await pg.evaluate("() => ({ t: $('#jText').value, tags: $('#jTags').value, kind: document.querySelector('#jForm input[name=jkind]:checked').value })")
        check('a stage starts the entry with its question, its kind and its tag', st['t'].startswith('Research question: What one question') and st['tags'] == 'research question' and st['kind'] == 'question', st)
        await pg.keyboard.type('Did supply set the route?'); await pg.keyboard.press('Control+Enter'); await pg.wait_for_timeout(300)
        await pg.click('[data-jp="6"]'); await pg.wait_for_timeout(80)
        sid = await pg.evaluate("() => P.sources.find(s => (s.csl.author || [])[0]?.family === 'Lee').id")
        await pg.select_option('#jPSrcSel', sid); await pg.wait_for_timeout(120)
        await pg.keyboard.type('A moving community.'); await pg.keyboard.press('Control+Enter'); await pg.wait_for_timeout(300)
        e = await pg.evaluate("() => jr().log[jr().log.length - 1]")
        check('notes on a source carry the APA citation and link the source', e['text'].startswith('Source: Lee, J. W. I. (2007). A Greek Army on the March') and e['text'].endswith('Notes: A moving community.') and e['links'] == [{'k': 'src', 'id': sid}] and e['tags'] == ['source notes'], e)
        dn = await pg.evaluate("() => ({ done: $$('[data-jp].done').length, txt: $('.j-prompts p').textContent })")
        check('a tick marks the stages written about', dn['done'] == 2 and '2 of 12' in dn['txt'], dn)

        check('no errors', not errs, errs[:5])
        await b.close()
    print('t44', 'OK' if ok else 'FAILED')
    sys.exit(0 if ok else 1)

asyncio.run(main())
