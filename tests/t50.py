"""2.7: the translation workspace, search inside sources, my library, the review round-trip, submissions,
and offline OCR."""
import asyncio, json
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
        ctx = await b.new_context(viewport={'width': 1440, 'height': 950}, accept_downloads=True)
        await ctx.grant_permissions(['clipboard-read', 'clipboard-write'])
        await ctx.add_init_script("delete window.showSaveFilePicker; localStorage.setItem('commonplace.prefs',JSON.stringify({startHome:false,toured:true,seenVersion:'99.0.0',myName:'G. Author',orcDay:new Date().toISOString().slice(0,10)}))")
        pg = await ctx.new_page()
        pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.on('console', lambda m: errs.append('console: ' + m.text) if m.type == 'error' and 'Failed to load resource' not in m.text else None)
        await pg.goto(URL); await pg.wait_for_timeout(1500)
        await pg.evaluate("() => { dirtyFile = false; return openStarter('thesis'); }"); await pg.wait_for_timeout(1300)
        await pg.evaluate("() => document.querySelectorAll('dialog[open]').forEach(d => d.close())")

        # ---------- translation workspace ----------
        await pg.evaluate("() => { const T = trj(); T.from = 'grc'; T.glossary.push({ id: 'g1', term: 'ἐπιμελητής', lang: 'grc', render: 'quartermaster', avoid: ['steward'], note: '', translit: '', created: nowISO() }); openDesk('translate'); }")
        await pg.wait_for_timeout(300)
        check('Research desk → Translate starts with a form for the original', await pg.evaluate("!!$('#twnText') && $('#deskTabs [data-dv=translate]').classList.contains('on')"))
        await pg.fill('#twnTitle', 'Anabasis 4.5'); await pg.select_option('#twnFrom', 'grc')
        await pg.fill('#twnText', 'ἐνταῦθα ἔμειναν ἡμέρας τρεῖς.\n\nὁ δὲ ἐπιμελητὴς ἦλθεν.\n\nἐντεῦθεν ἐπορεύθησαν σταθμοὺς δύο.')
        await pg.click('#twnGo'); await pg.wait_for_timeout(400)
        r = await pg.evaluate("({ segs: P.trw[0].segs.map(s => [s.o, s.p, s.st]), focus: document.activeElement.dataset.twt === P.trw[0].segs[0].id, tl: $('.tw-tl')?.textContent })")
        check('…a segment per paragraph, the first ready to type in, with its transliteration', len(r['segs']) == 3 and r['segs'][1][1] == 1 and r['focus'] and r['tl'] == 'entautha emeinan hēmeras treis.', r)
        await pg.keyboard.type('There they stayed three days.'); await pg.keyboard.press('Control+Enter'); await pg.wait_for_timeout(200)
        await pg.keyboard.type('And the steward came.'); await pg.wait_for_timeout(400)
        r = await pg.evaluate("({ st: P.trw[0].segs.map(s => s.st), hint: $$('.tw-h').map(h => h.className + '|' + h.textContent), head: $('.tw-head').innerText, pct: $('.desk-side li.on em').textContent })")
        check('…⌘/Ctrl Enter marks it done and moves on; typing makes a draft', r['st'] == ['done', 'draft', ''], r)
        check('…the glossary term is found whatever its accents, and flagged when the translation avoids it', any('bad' in h and 'not “steward”' in h for h in r['hint']), r['hint'])
        check('…progress: segments and words done', '1 of 3 segments done' in r['head'] and r['pct'] == '33%', r)
        await pg.evaluate("[...$$('.tw-t')][1].value = 'And the quartermaster came.'; [...$$('.tw-t')][1].dispatchEvent(new Event('input'))"); await pg.wait_for_timeout(200)
        check('…and turns green when it follows it', await pg.evaluate("$$('.tw-h')[0].classList.contains('ok')"))
        await pg.evaluate("$$('[data-twst]')[1].click()"); await pg.wait_for_timeout(100)
        await pg.select_option('#twFilter', 'todo'); await pg.wait_for_timeout(200)
        check('…filter to what’s left', await pg.evaluate("$$('#twSegs .tw-seg').length") == 1)
        await pg.select_option('#twFilter', 'all'); await pg.wait_for_timeout(200)
        await pg.evaluate("$$('[data-twmerge]')[1].click()"); await pg.wait_for_timeout(200)
        check('…Join next merges two segments', await pg.evaluate("P.trw[0].segs.length") == 2)
        await pg.evaluate("$$('[data-twnote]')[0].click()"); await pg.wait_for_timeout(200)
        r = await pg.evaluate("({ k: P.notes[0].kind, o: P.notes[0].orig, b: P.notes[0].body, l: P.notes[0].origLang })")
        check('…Note makes a translation note from a segment', r == {'k': 'translation', 'o': 'ἐνταῦθα ἔμειναν ἡμέρας τρεῖς.', 'b': 'There they stayed three days.', 'l': 'grc'}, r)
        await pg.evaluate("P.trw[0].segs.push({ id: 'sx', o: 'ἐντεῦθεν ἐπορεύθησαν σταθμοὺς δύο.', t: '', st: '', n: '', p: 2 }); $$('#deskTools [data-j]').find(b => b.textContent === 'Make a document').click()"); await pg.wait_for_timeout(400)
        r = await pg.evaluate("({ t: curDoc().title, h: editor.innerHTML })")
        check('Make a document: the translation, untranslated segments highlighted', r['t'] == 'Anabasis 4.5' and 'There they stayed three days.' in r['h'] and 'And the quartermaster came.' in r['h'] and '<mark>' in r['h'] and 'σταθμοὺς' in r['h'], r['h'][:300])
        await pg.evaluate("openDesk('translate'); $$('#deskTools [data-j]').find(b => b.textContent === 'Side by side').click()"); await pg.wait_for_timeout(400)
        check('Side by side: a two-column table, the original marked as Greek', await pg.evaluate("!!editor.querySelector('table td span[lang=grc]') && editor.querySelector('th').textContent === 'Greek (ancient)'"))

        # ---------- search inside sources ----------
        await pg.evaluate("() => showReader(true)")
        await pg.set_input_files('#filePdf', FIX); await pg.wait_for_timeout(2500)
        sid = await pg.evaluate("sortedSources()[0].id")
        await pg.evaluate(f"() => {{ $('#rdSource').value = '{sid}'; $('#rdSource').dispatchEvent(new Event('change')); }}"); await pg.wait_for_timeout(800)
        await pg.evaluate("""() => { showReader(false); const s = sortedSources()[1]; s.transcript = '00:01:10 We met the colonel at dawn.\\n00:02:05 He said the railway was cut.'; s.photos = [{ id: 'ph1', name: 'IMG_1.jpg', box: '3', folder: '12', item: '4', text: 'Letter about the railway at Mons.' }]; }""")
        await pg.evaluate("$('#srcMoreMenu [id=btnFtx]').click()"); await pg.wait_for_timeout(2500)
        await pg.fill('#ftxQ', 'railway'); await pg.wait_for_timeout(400)
        r = await pg.evaluate("({ st: $('#ftxStatus').innerText, list: $('#ftxList').innerText, where: $$('.ftx-where').map(x => x.textContent) })")
        check('Sources → Search inside sources: PDF pages, photo transcriptions and transcripts', '1 PDF' in r['st'] and '3 places in 2 sources' in r['list'] and set(r['where']) >= {'p. 2', 'box 3, folder 12, item 4', '00:02:05'}, r)
        await pg.fill('#ftxQ', 'MOLTKE'); await pg.wait_for_timeout(400)
        check('…capitals and accents don’t matter', '1 place in 1 source' in await pg.evaluate("$('#ftxList').innerText"))
        await pg.click('#ftxList .ftx-hit'); await pg.wait_for_timeout(1500)
        check('…a hit opens the PDF at its page', await pg.evaluate(f"!$('#reader').classList.contains('hidden') && $('#rdPage').value === '3' && R.sourceId === '{sid}'"))
        r = await pg.evaluate(f"ftxStore.get('{sid}').then(v => ({{ n: v && v.pages && v.pages.length, keys: v && Object.keys(v), inP: JSON.stringify(P).includes(v.pages[1].slice(5, 40)) }}))")
        check('…the text is kept in this browser, not the project file', r['n'] and r['n'] >= 2 and not r['inP'], r)

        # ---------- offline OCR ----------
        await pg.evaluate("""async () => { const c = document.createElement('canvas'); c.width = 1400; c.height = 300; const x = c.getContext('2d'); x.fillStyle = '#fff'; x.fillRect(0, 0, 1400, 300); x.fillStyle = '#111'; x.font = '44px Georgia'; x.fillText('The railway at Mons was cut on 23 August.', 40, 120);
            const blob = await new Promise(r => c.toBlob(r, 'image/png')), buf = await blob.arrayBuffer(), s = sortedSources()[1]; s.photos = [{ id: 'phx', name: 'IMG_9.png', box: '3', folder: '12', item: '1', text: '' }];
            await photoStore.set('phx', { buf, type: 'image/png' }, 'data:image/png;base64,iVBORw0KGgo='); showReader(false); openPhotos(s.id); }""")
        await pg.wait_for_timeout(800)
        await pg.click('#phOcr')
        for _ in range(120):
            await pg.wait_for_timeout(500)
            if await pg.evaluate("!$('#phOcr').disabled"): break
        await pg.wait_for_timeout(500)
        r = await pg.evaluate("({ t: $('#phText').value, saved: sortedSources()[1].photos[0].text })")
        check('Archive photos → Read the text: OCR on this computer fills the transcription', r['t'] == 'The railway at Mons was cut on 23 August.' and r['saved'] == r['t'], r)
        await pg.evaluate("$('#phDlg').close()")
        r = await pg.evaluate("ocrRead((() => { const c = document.createElement('canvas'); c.width = 900; c.height = 120; const x = c.getContext('2d'); x.fillStyle = '#fff'; x.fillRect(0, 0, 900, 120); x.fillStyle = '#000'; x.font = '40px Georgia'; x.fillText('Send forage to the second division.', 20, 70); return c; })())")
        check('…the same reader works on a page image (scanned PDFs, in the reader)', r == 'Send forage to the second division.', r)

        # ---------- my library ----------
        await pg.evaluate(f"openSource('{sid}')"); await pg.wait_for_timeout(200)
        await pg.click('#panelFoot [data-a=savelib]'); await pg.wait_for_timeout(500)
        r = await pg.evaluate("libLoad().then(L => L.items.map(i => [i.from, i.notes.length > 0, !!i.csl.title]))")
        check('Save to library on a source keeps it, with its notes, in this browser', r == [['Supply and Survival: The March of the Ten Thousand', True, True]], r)
        await pg.evaluate("libAdd([P.sources.find(s => s.id === '" + sid + "')])"); await pg.wait_for_timeout(300)
        check('…saving it again updates it rather than doubling it', await pg.evaluate("libLoad().then(L => L.items.length)") == 1)
        saved = await pg.evaluate("JSON.parse(JSON.stringify(P))")
        await pg.evaluate("() => { P.sources = []; P.notes = []; srcVersion++; renderSourceList(); renderNoteList(); openLibrary(); }"); await pg.wait_for_timeout(400)
        check('Sources → My library lists it in another project', await pg.evaluate("$$('#libList li').length === 1 && !$('#libList [data-libadd]').disabled"))
        await pg.evaluate("$('#libList [data-lib]').click()"); await pg.wait_for_timeout(100)
        await pg.click('#libAddSel'); await pg.wait_for_timeout(300)
        r = await pg.evaluate("({ s: P.sources.length, n: P.notes.filter(n => n.sourceId === P.sources[0].id).length, here: $('#libList li').classList.contains('here') })")
        check('…Add copies it into the project with its notes, and marks it as here', r['s'] == 1 and r['n'] >= 1 and r['here'], r)
        async with pg.expect_download() as dl:
            await pg.click('#libExport')
        d = await dl.value; await d.save_as(OUT + '/lib.json'); j = json.load(open(OUT + '/lib.json'))
        check('…Export saves the shelf as a file', j['app'] == 'Anabasis library' and len(j['items']) == 1)
        await pg.evaluate("() => { LIB.items = []; return libSave(); }")
        await pg.set_input_files('#libFile', OUT + '/lib.json'); await pg.wait_for_timeout(500)
        check('…and Import puts it back', await pg.evaluate("LIB.items.length") == 1)
        await pg.evaluate("$('#libDlg').close()")
        await pg.evaluate("raw => { P = normalize(raw); renderAll(); }", saved); await pg.wait_for_timeout(800)

        # ---------- submissions ----------
        await pg.evaluate("openSubs()"); await pg.wait_for_timeout(200)
        await pg.click('#subAdd'); await pg.wait_for_timeout(200)
        await pg.fill('#subList tr [data-sf=outlet]', 'Parameters'); await pg.press('#subList tr [data-sf=outlet]', 'Tab'); await pg.wait_for_timeout(150)
        r = await pg.evaluate("({ x: P.subs[0], due: (() => { const d = new Date(); d.setDate(d.getDate() + 14); return todayKey(d); })() })")
        check('Submissions → Add: the open document, sent today, a follow-up in two weeks', r['x']['outlet'] == 'Parameters' and r['x']['docId'] == await pg.evaluate("curDocId") and r['x']['status'] == 'sent' and r['x']['followUp'] == r['due'], r)
        await pg.evaluate("() => { const x = P.subs[0]; x.followUp = todayKey(); P.subs.push({ id: 'sb2', docId: '', outlet: 'War on the Rocks', editor: '', kind: 'pitch', sent: todayKey(), status: 'accepted', followUp: '', fee: 300, notes: '', created: nowISO(), modified: nowISO() }); subsRender(); }")
        r = await pg.evaluate("$('#subSum').innerText")
        check('…a summary: out, accepted, fees, the next follow-up', '1 out' in r and '1 accepted' in r and '$300' in r and 'Parameters' in r, r)
        await pg.evaluate("$('#subDlg').close(); calMonth = ''; calDay = todayKey(); openHome()"); await pg.wait_for_timeout(600)
        r = await pg.evaluate("({ cal: $('#hmCal .cal-day').innerText, card: $('#hmSubs')?.innerText || '', ics: calIcsText().text })")
        check('…follow-ups are on the calendar, Project home and the .ics file', 'Follow up: Parameters' in r['cal'] and 'follow up today' in r['card'] and 'SUMMARY:Follow up: Parameters' in r['ics'], r['card'])
        r = await pg.evaluate("() => { const raw = JSON.parse(JSON.stringify(P)); raw.subs.push({ status: 'bogus', fee: -5, sent: 'soon' }); return normalize(raw).subs.slice(-1)[0]; }")
        check('…kept in the project file; bad values cleaned', r['status'] == 'sent' and r['fee'] == 0 and r['sent'] == '', r)
        await pg.evaluate("closeHome()")

        # ---------- review round-trip ----------
        await pg.evaluate("openDoc(P.docs.find(d => /Army/.test(d.title)).id)"); await pg.wait_for_timeout(500)
        await pg.evaluate("openReviewSend()"); await pg.wait_for_timeout(150)
        async with pg.expect_download() as dl:
            await pg.click('#rvsGo')
        d = await dl.value; rpath = OUT + '/review.html'; await d.save_as(rpath)
        check('Export → For a reviewer: one HTML file', d.suggested_filename.endswith(' - for review.html'))
        rp = await ctx.new_page(); rp.on('pageerror', lambda e: errs.append('review page: ' + str(e)))
        answers = []
        async def on_dialog(dg): await dg.accept(answers.pop(0) if dg.type == 'prompt' and answers else '')
        rp.on('dialog', lambda dg: asyncio.ensure_future(on_dialog(dg)))
        await rp.goto('file://' + rpath); await rp.wait_for_timeout(500)
        sel = """([n, a, z]) => { const el = [...document.querySelectorAll('[data-b]')].filter(e => e.tagName === 'P' && e.textContent.length > 120)[n]; const w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT); let t;
            while ((t = w.nextNode())) if (t.data.trim().length > 30 && !t.parentElement.closest('.cite,.rv-c,.rv-tag,.rv-ins')) break; const r = document.createRange(); r.setStart(t, a); r.setEnd(t, z); getSelection().removeAllRanges(); getSelection().addRange(r); return r.toString(); }"""
        q1 = await rp.evaluate(sel, [0, 0, 9])
        answers[:] = ['Say which histories.', 'Maria Lopez']; await rp.click('#rvComment'); await rp.wait_for_timeout(200)
        q2 = await rp.evaluate(sel, [1, 0, 9])
        answers[:] = ['Xenophon’s account']; await rp.click('#rvChange'); await rp.wait_for_timeout(200)
        r = await rp.evaluate("({ n: document.getElementById('rvN').textContent, list: document.getElementById('rvList').innerText })")
        check('The reviewer selects words to comment on or change, in any browser', r['n'] == '2 notes' and 'Say which histories.' in r['list'] and f'Change “{q2}” to “Xenophon’s account”' in r['list'], [r, q1, q2])
        await rp.wait_for_timeout(500); await rp.close()
        rp = await ctx.new_page(); rp.on('pageerror', lambda e: errs.append('review page: ' + str(e))); rp.on('dialog', lambda dg: asyncio.ensure_future(on_dialog(dg)))
        await rp.goto('file://' + rpath); await rp.wait_for_timeout(600)
        r = await rp.evaluate("[document.getElementById('rvN').textContent, Object.keys(localStorage).filter(k => k.startsWith('anabasis-review')), location.href, Object.keys(localStorage).map(k => k + ':' + localStorage.getItem(k).length)]")
        check('…their notes survive closing the page', r[0] == '2 notes', r)
        async with rp.expect_download() as dl2:
            await rp.click('#rvSave')
        d2 = await dl2.value; jpath = OUT + '/review.json'; await d2.save_as(jpath); rev = json.load(open(jpath))
        check('…Save my review makes a small file to send back', rev['app'] == 'Anabasis review' and rev['reviewer'] == 'Maria Lopez' and len(rev['ops']) == 2 and 'review by Maria Lopez' in d2.suggested_filename, d2.suggested_filename)
        await rp.close(); await pg.bring_to_front()
        await pg.evaluate("() => { const p = [...editor.children].find(e => e.tagName === 'P' && e.textContent.length > 120); p.insertAdjacentHTML('afterbegin', 'New opening words. '); syncEditor(); }")
        snaps = await pg.evaluate("curDoc().snapshots.length")
        await pg.set_input_files('#rviFile', jpath); await pg.wait_for_timeout(1200)
        r = await pg.evaluate("({ toast: $('#toast').innerText, cm: curDoc().comments.slice(-1)[0], cmt: (() => { const c = curDoc().comments.slice(-1)[0]; return [...editor.querySelectorAll('.cmt')].filter(e => e.dataset.cmt === c.id).map(e => e.textContent).join(''); })(), sg: [...editor.querySelectorAll('ins.sg,del.sg')].map(e => e.tagName + ':' + e.textContent + ':' + e.dataset.by), snaps: curDoc().snapshots.length })")
        check('Import a review: comments in the margin, changes as suggestions by the reviewer, found even after the text moved',
              '1 comment and 1 suggested change' in r['toast'] and r['cm']['author'] == 'Maria Lopez' and r['cm']['text'] == 'Say which histories.' and r['cmt'] == q1 and f'DEL:{q2}:Maria Lopez' in r['sg'] and 'INS:Xenophon’s account:Maria Lopez' in r['sg'], r)
        check('…after saving a draft to go back to', r['snaps'] == snaps + 1, r['snaps'])
        await pg.evaluate("() => { $$('ins.sg,del.sg', editor).forEach(e => e.remove()); [...editor.children].find(e => e.tagName === 'P' && e.textContent.length > 120).textContent = 'Completely different text now.'; syncEditor(); }")
        await pg.set_input_files('#rviFile', jpath); await pg.wait_for_timeout(1000)
        r = await pg.evaluate("({ toast: $('#toast').innerText, info: $('#infoDlg').open ? $('#infoDlg').innerText : '' })")
        check('…notes whose text has gone are listed, so nothing is lost', 'couldn’t be placed' in r['toast'] and 'Say which histories.' in r['info'], r)
        await pg.evaluate("$('#infoDlg').close()")

        r = await pg.evaluate("COMMANDS.map(c => c[0]).join('|')")
        check('the command search reaches all of it', all(x in r for x in ['Translate:', 'Search inside sources', 'My library', 'Submissions', 'Send for review', 'Import a review', 'Read the text of a scanned PDF']), r[-600:])
        check('no errors', not errs, errs[:5])
        await b.close()
    print('ALL PASS' if ok else 'SOME FAILED'); _sys.exit(0 if ok else 1)

asyncio.run(main())
