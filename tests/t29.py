"""Research marks: threads, claims, review keys, questions, the research desk, and exports that leave no trace of them."""
import asyncio, json, os, re, sys, zipfile
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from env import URL, OUT
from playwright.async_api import async_playwright

MOD = 'Meta' if sys.platform == 'darwin' else 'Control'


async def main():
    ok = True
    def check(name, cond, extra=''):
        nonlocal ok
        print(('PASS ' if cond else 'FAIL ') + name, extra); ok = ok and bool(cond)
    async with async_playwright() as pw:
        b = await pw.chromium.launch()
        ctx = await b.new_context(viewport={'width': 1400, 'height': 900}, accept_downloads=True)
        await ctx.add_init_script("delete window.showSaveFilePicker; localStorage.setItem('commonplace.prefs',JSON.stringify({startHome:false,toured:true,seenVersion:'99.0.0'}))")
        await ctx.grant_permissions(['clipboard-read', 'clipboard-write'])
        pg = await ctx.new_page(); errs = []
        pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.on('console', lambda m: errs.append('console:' + m.text) if m.type == 'error' else None)
        await pg.goto(URL); await pg.wait_for_timeout(1500)
        await pg.evaluate("""() => {
          const a = addSource({ type: 'book', title: 'Anabasis', author: [{ family: 'Xenophon' }], issued: { 'date-parts': [[1897]] } }); a.osint = { rating: 'B2' };
          const w = addSource({ type: 'webpage', title: 'A forum post', author: [{ family: 'Anon' }] }); w.osint = { rating: 'E5' };
          window.SA = a.id; window.SW = w.id;
          P.entities.push({ id: 'e1', name: 'Trapezus', kind: 'place', variants: ['Trebizond', 'Trabzon'], note: 'Greek colony on the Black Sea' });
          addDoc(newDoc('Chapter one', '<h1>Chapter one</h1><p id="p1">The army marched north through the mountains of the Carduchians for seven days.' + citeHTML([{ id: SA, locator: 'IV.1', label: 'page' }]) + ' Supplies ran short.</p><p id="p2">Morale fell as the snow deepened, and many men were lost.</p><p id="p3">At last they saw the sea from Mount Theches.' + citeHTML([{ id: SW }]) + '</p><p id="p4">They reached Trebizond in the spring.</p>'));
          window.D1 = curDoc().id;
        }""")
        sel = """([a, ao, z, zo]) => { const f = (id, o) => { const p = editor.querySelector('#' + id); const w = document.createTreeWalker(p, NodeFilter.SHOW_TEXT); let n, left = o; while ((n = w.nextNode())) { if (n.parentElement.closest('.cite')) continue; if (left <= n.data.length) return [n, left]; left -= n.data.length; } return [p, p.childNodes.length]; };
          const at = (id, o) => typeof o === 'number' ? o : (t => t.indexOf(o) + o.length)([...editor.querySelector('#' + id).childNodes].filter(n => !(n.nodeType === 1 && n.matches('.cite'))).map(n => n.textContent).join(''));
          const [sn, so] = f(a, at(a, ao)), [en, eo] = f(z, at(z, zo)); const r = document.createRange(); r.setStart(sn, so); r.setEnd(en, eo); const s = getSelection(); s.removeAllRanges(); s.addRange(r); savedRange = r.cloneRange(); editor.focus(); }"""
        # ---- thread across two paragraphs, through the Mark menu
        await pg.evaluate(sel, ['p1', 0, 'p2', 30])
        await pg.click('#btnMark'); await pg.click('#markMenu [data-m=th]'); await pg.wait_for_timeout(200)
        check('thread dialog opens', await pg.is_visible('#thDlg'))
        await pg.fill('#thName', 'Logistics'); await pg.click('#thColors [data-c="#2A9D8F"]'); await pg.click('#thNew'); await pg.wait_for_timeout(400)
        r = await pg.evaluate("""() => { const s = [...editor.querySelectorAll('.rm[data-k=th]')]; return { n: s.length, paras: [...new Set(s.map(x => x.closest('p').id))], ids: [...new Set(s.map(x => x.dataset.rm))].length, citeWrapped: !!editor.querySelector('.rm .cite, .cite .rm'), thread: P.threads[0], text: rmAll('th')[0] && rmAll('th')[0].text } }""")
        check('thread passage spans both paragraphs as one passage', r['paras'] == ['p1', 'p2'] and r['ids'] == 1, r)
        check('citations are stepped around, not wrapped', not r['citeWrapped'])
        check('thread saved with name and color', r['thread'] and r['thread']['name'] == 'Logistics' and r['thread']['color'] == '#2A9D8F')
        check('passage text reads across the citation', r['text'] and r['text'].startswith('The army marched') and 'Supplies ran short. Morale fell' in r['text'], r['text'])
        # ---- a second passage in the thread, in another document
        await pg.evaluate("""() => { addDoc(newDoc('Chapter two', '<h1>Chapter two</h1><p id="q1">Food came from the villages they passed, by purchase or by force.</p><p id="q2">Xenophon worried about Trapezus and its harbor.</p>')); window.D2 = curDoc().id; }""")
        await pg.evaluate(sel, ['q1', 0, 'q1', 40])
        await pg.keyboard.press(f'{MOD}+Alt+KeyG'); await pg.wait_for_timeout(150)
        check('Ctrl/Cmd+Alt+G opens the Mark menu', await pg.is_visible('#markMenu'))
        await pg.keyboard.press('t'); await pg.wait_for_timeout(200)
        await pg.click('#thPickList [data-th]'); await pg.wait_for_timeout(300)
        r = await pg.evaluate("() => rmAll('th').map(p => p.docId === D1 ? 1 : 2)")
        check('thread runs across documents in manuscript order', r == [1, 2], r)
        # stepping: from chapter two, next wraps to chapter one
        await pg.evaluate("() => rmStep('th', P.threads[0].id, 1, rmAll('th')[1].pid)"); await pg.wait_for_timeout(400)
        check('stepping a thread crosses documents', await pg.evaluate("() => curDocId === D1"))
        # ---- claims
        await pg.evaluate(sel, ['p1', 0, 'p1', 'days.'])  # the marching sentence, cited after
        await pg.keyboard.press(f'{MOD}+Alt+KeyG'); await pg.keyboard.press('c'); await pg.wait_for_timeout(400)
        await pg.evaluate(sel, ['p2', 0, 'p2', 40])  # morale: no citation
        await pg.evaluate("() => markClaim()"); await pg.wait_for_timeout(300)
        await pg.evaluate(sel, ['p3', 0, 'p3', 'Theches.'])  # the sea, cited to a weak source
        await pg.evaluate("() => markClaim()"); await pg.wait_for_timeout(300)
        r = await pg.evaluate("() => rmAll('cl').map(p => ({ cites: p.cites, iss: claimIssues(p), text: p.text }))")
        check('three claims registered', len(r) == 3 and len(await pg.evaluate("() => P.claims")) == 3, r)
        check('citation right after a claim is found', r[0]['cites'] == [await pg.evaluate('SA')], r[0])
        check('uncited claim is flagged', 'No citation' in r[1]['iss'], r[1])
        check('claim resting only on a low-rated source is flagged', 'Only low-rated sources' in r[2]['iss'], r[2])
        # the popover: set status from the draft
        await pg.evaluate("() => { const s = editor.querySelector('.rm[data-k=cl]'); const b = s.getBoundingClientRect(); s.scrollIntoView({ block: 'center' }); }"); await pg.wait_for_timeout(200)
        box = await pg.evaluate("() => { const s = [...editor.querySelectorAll('.rm[data-k=cl]')][0]; const r = s.getClientRects()[0]; return [r.left + 20, r.top + r.height / 2]; }")
        await pg.mouse.click(box[0], box[1]); await pg.wait_for_timeout(250)
        check('clicking a marked passage shows its marks', await pg.is_visible('.rm-pop') and await pg.locator('.rm-pop .rp-row').count() == 2, await pg.locator('.rm-pop').inner_text() if await pg.is_visible('.rm-pop') else '')
        await pg.select_option('.rm-pop select[data-a=status]', 'ok'); await pg.wait_for_timeout(300)
        r = await pg.evaluate("() => P.claims[0]")
        check('status set from the popover; checked text stored', r['status'] == 'ok' and r['checkedText'].startswith('The army'), r)
        await pg.keyboard.press('Escape')
        await pg.evaluate("() => { const s = editor.querySelector('.rm[data-k=cl]'); s.firstChild.data = s.firstChild.data.replace('seven', 'eight'); onEdit(); }"); await pg.wait_for_timeout(600)
        r = await pg.evaluate("() => claimIssues(rmAll('cl')[0])")
        check('editing a supported claim flags it as changed', 'Changed since you marked it supported' in r, r)
        # ---- review key due today, and a question
        await pg.evaluate(sel, ['p4', 0, 'p4', 20])
        await pg.evaluate("() => openReviewKey()"); await pg.wait_for_timeout(200)
        await pg.select_option('#rvReason', 'Check a quote'); await pg.evaluate("() => { $('#rvDue').value = todayISO(); }"); await pg.fill('#rvNote', 'Confirm the city name')
        await pg.click('#rvOk'); await pg.wait_for_timeout(300)
        r = await pg.evaluate("() => ({ k: P.reviewKeys, badge: $('#tabResearchBadge').textContent, keys: $('#rsKeys').innerText })")
        check('review key saved', len(r['k']) == 1 and r['k'][0]['reason'] == 'Check a quote' and r['k'][0]['note'] == 'Confirm the city name', r['k'])
        check('due key counts in the Research tab', r['badge'] and int(r['badge']) >= 1 and 'today' in r['keys'], r)
        await pg.evaluate(sel, ['p4', 0, 'p4', 33])
        await pg.evaluate("() => openQuestionLink()"); await pg.wait_for_timeout(200)
        await pg.fill('#qText', 'When did they reach the coast?'); await pg.click('#qNew'); await pg.wait_for_timeout(300)
        r = await pg.evaluate("() => ({ q: PLI().filter(i => i.type === 'question').map(i => i.title), linked: rmAll('q').length, nested: !!editor.querySelector('.rm[data-k=rv] .rm[data-k=q], .rm[data-k=q] .rm[data-k=rv]') })")
        check('question created in the plan and the passage linked', r['q'] == ['When did they reach the coast?'] and r['linked'] == 1, r)
        check('overlapping marks nest', r['nested'])
        # ---- project home
        await pg.evaluate("() => openHome()"); await pg.wait_for_timeout(500)
        txt = await pg.inner_text('#hmArea')
        check('home shows due review keys and claims to check', 'Due for review' in txt and 'Claims to check' in txt and 'When did they reach the coast?' in txt)
        await pg.evaluate("() => closeHome()")
        # ---- the research desk, every view
        for v in ['threads', 'claims', 'grid', 'review', 'questions', 'about']:
            await pg.evaluate(f"() => openDesk('{v}')"); await pg.wait_for_timeout(250)
            body = await pg.inner_text('#deskBody')
            if v == 'threads': check('desk: thread reads in order across chapters', 'Chapter one' in body and 'Chapter two' in body and body.index('Chapter one') < body.index('Chapter two'))
            if v == 'claims': check('desk: claims register lists all three with problems', await pg.locator('.cl-table tbody tr').count() == 3 and 'No citation' in body)
            if v == 'grid': check('desk: evidence grid has claims by sources with ratings', await pg.locator('table.eg tbody tr').count() == 4 and 'B2' in body and 'E5' in body, body[:300])
            if v == 'review': check('desk: review shows the due key', 'Check a quote' in body and 'today' in body)
            if v == 'questions': check('desk: question shows its linked passage', 'They reached Trebizond' in body)
        await pg.fill('#abQ', 'Trapezus'); await pg.press('#abQ', 'Enter'); await pg.wait_for_timeout(400)
        body = await pg.inner_text('#deskBody')
        check('everything about X searches the name’s other spellings', 'Trebizond' in body and 'Trapezus' in body and 'In your documents' in body, body[:300])
        # filters and the register edits
        await pg.evaluate("() => openDesk('claims')"); await pg.click('.cl-filters button:has-text(\"Needs attention\")'); await pg.wait_for_timeout(200)
        check('register filter: needs attention', await pg.locator('.cl-table tbody tr').count() == 3)
        await pg.fill('.cl-table tbody tr:nth-child(2) textarea', 'Ask the editor'); await pg.press('.cl-table tbody tr:nth-child(2) textarea', 'Tab')
        check('register note saved', await pg.evaluate("() => P.claims.some(c => c.note === 'Ask the editor')"))
        async with pg.expect_download() as dl: await pg.click('#deskTools button:has-text(\"Fact-check sheet\")')
        f = await (await dl.value).path(); sheet = open(f, encoding='utf-8').read()
        check('fact-check sheet lists claims with full citations', 'Xenophon' in sheet and 'Morale fell' in sheet and '<table>' in sheet and 'B2' in sheet)
        async with pg.expect_download() as dl: await pg.click('#deskTools button:has-text(\"CSV\")')
        csv = open(await (await dl.value).path(), encoding='utf-8-sig', newline='').read()
        check('claims CSV', csv.startswith('"Claim","Document"') and csv.count('\r\n') == 3, csv[:200])
        await pg.evaluate("() => openDesk('threads')"); await pg.click('#deskTools button:has-text(\"New document from thread\")'); await pg.wait_for_timeout(500)
        check('new document from a thread', await pg.evaluate("() => curDoc().title === 'Thread: Logistics' && editor.querySelectorAll('blockquote').length === 2"))
        # ---- exports leave no trace; saved file keeps the marks
        await pg.evaluate("() => openDoc(D1)"); await pg.wait_for_timeout(300)
        r = await pg.evaluate("""() => { const d = P.docs.find(x => x.id === D1); const out = {}; ['html', 'md', 'docx', 'epub', 'paged', 'substack'].forEach(m => { const x = buildExport(d, m); out[m] = /class="rm"|data-rm|data-k=/.test(JSON.stringify(x)); }); return out; }""")
        check('no research marks in any export', not any(r.values()), r)
        txt = await pg.evaluate("() => buildExport(P.docs.find(x => x.id === D1), 'html').body")
        check('export text intact around unwrapped marks', 'The army marched north through the mountains of the Carduchians for eight days.' in re.sub('<[^>]+>', '', txt))
        saved = await pg.evaluate("() => projectJSON()")
        await pg.evaluate("t => loadProjectText(t, null, 'r.json')", saved); await pg.wait_for_timeout(800)
        r = await pg.evaluate("() => ({ th: rmAll('th').length, cl: rmAll('cl').length, rv: rmAll('rv').length, q: rmAll('q').length, threads: P.threads.length, claims: P.claims.map(c => c.status), keys: P.reviewKeys.length })")
        check('marks and records survive save and reopen', r == {'th': 2, 'cl': 3, 'rv': 1, 'q': 1, 'threads': 1, 'claims': ['ok', 'open', 'open'], 'keys': 1}, r)
        # ---- copy duplicates nothing; cut and paste keeps the mark
        await pg.evaluate("() => openDoc(D1)")
        await pg.evaluate(sel, ['p2', 0, 'p2', 20])
        await pg.keyboard.press(f'{MOD}+c'); await pg.evaluate("() => { const p = editor.querySelector('#p4'); const r = document.createRange(); r.selectNodeContents(p); r.collapse(false); const s = getSelection(); s.removeAllRanges(); s.addRange(r); }")
        await pg.keyboard.press(f'{MOD}+v'); await pg.wait_for_timeout(300)
        r = await pg.evaluate("() => [...new Set([...editor.querySelectorAll('.rm')].map(s => s.dataset.rm))].map(id => editor.querySelectorAll(`.rm[data-rm='${id}']`).length)")
        n_before = await pg.evaluate("() => editor.querySelectorAll('#p4 .rm').length")
        check('pasting a copy does not duplicate a mark', await pg.evaluate("() => !editor.querySelector('#p4 .rm[data-k=th]')"), n_before)
        await pg.evaluate("() => { const q = editor.querySelector('#p4 .rm[data-k=q]'); const r = document.createRange(); r.selectNodeContents(q); const s = getSelection(); s.removeAllRanges(); s.addRange(r); }")
        await pg.keyboard.press(f'{MOD}+x'); await pg.wait_for_timeout(100)
        await pg.evaluate("() => { const p = editor.querySelector('#p3'); const r = document.createRange(); r.selectNodeContents(p); r.collapse(false); const s = getSelection(); s.removeAllRanges(); s.addRange(r); }")
        await pg.keyboard.press(f'{MOD}+v'); await pg.wait_for_timeout(300)
        check('cut and paste moves a mark with its passage', await pg.evaluate("() => !!editor.querySelector('#p3 .rm[data-k=q]') || [...editor.querySelectorAll('.rm[data-k=q]')].length === 1"))
        # ---- removing marks, hiding a thread, hiding all marks
        await pg.evaluate("() => removeMark('cl', P.claims[1].id)"); await pg.wait_for_timeout(200)
        check('removing a claim unwraps it and drops its record', await pg.evaluate("() => P.claims.length === 2 && rmAll('cl').length === 2"))
        await pg.evaluate("() => { P.threads[0].hidden = true; rmStyle(); }")
        bg = await pg.evaluate("() => getComputedStyle(editor.querySelector('.rm[data-k=th]')).backgroundColor")
        check('a hidden thread loses its highlight', bg in ('rgba(0, 0, 0, 0)', 'transparent'), bg)
        await pg.evaluate("() => { P.threads[0].hidden = false; PREFS.marksOff = true; rmStyle(); }")
        bg = await pg.evaluate("() => getComputedStyle(editor.querySelector('.rm[data-k=th]')).backgroundColor")
        check('Show marks off hides every mark', bg in ('rgba(0, 0, 0, 0)', 'transparent'), bg)
        await pg.evaluate("() => { PREFS.marksOff = false; rmStyle(); }")
        # ---- hostile research fields don't break loading
        bad = json.dumps({'app': 'Anabasis', 'format': 2, 'title': 'x', 'docs': [{'id': 'd1', 'title': 'D', 'html': '<p><span class="rm" data-rm="m1" data-k="th" data-ref="nope" onclick="alert(1)">hi</span></p>'}],
                          'threads': [None, 5, {'id': 't1', 'name': {'x': 1}, 'color': 'red;}body{display:none'}], 'claims': [{'id': 'c1', 'status': '__proto__'}], 'reviewKeys': [{'id': 'r1', 'due': '<script>'}]})
        await pg.evaluate("t => loadProjectText(t, null, 'bad.json')", bad); await pg.wait_for_timeout(800)
        r = await pg.evaluate("() => ({ t: P.threads, c: P.claims[0].status, d: P.reviewKeys[0].due, oc: !!editor.querySelector('[onclick]'), shown: getComputedStyle(document.body).display })")
        check('hostile research fields are cleaned', r['t'][0]['color'] == '#E0A526' and r['t'][0]['name'] == 'Thread' and r['c'] == 'open' and r['d'] == '' and not r['oc'] and r['shown'] != 'none', r)
        await pg.evaluate("() => { openDesk('threads'); openDesk('grid'); openDesk('claims'); closeDesk(); }")
        await b.close()
    print('ERRS', errs)
    return ok and not errs

if __name__ == '__main__':
    sys.exit(0 if asyncio.run(main()) else 1)
