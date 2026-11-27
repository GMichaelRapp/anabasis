"""2.1.0: Socrates (question stems dealt to suit the selection and the kind of writing, handed to the
question dialog and linked to the passage) and the archive export (the whole project as plain files)."""
import asyncio, io, json, re, sys, zipfile
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from env import URL, OUT
from playwright.async_api import async_playwright

PX = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=='


async def main():
    ok = True
    def check(name, cond, extra=''):
        nonlocal ok
        print(('PASS ' if cond else 'FAIL ') + name, extra if not cond else ''); ok = ok and bool(cond)
    errs = []
    async with async_playwright() as pw:
        b = await pw.chromium.launch()
        ctx = await b.new_context(viewport={'width': 1440, 'height': 900}, accept_downloads=True)
        await ctx.add_init_script("delete window.showSaveFilePicker; localStorage.setItem('commonplace.prefs',JSON.stringify({startHome:false,toured:true,seenVersion:'99.0.0'}))")
        pg = await ctx.new_page()
        pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.on('console', lambda m: errs.append('console: ' + m.text) if m.type == 'error' and 'Failed to load resource' not in m.text else None)
        await pg.goto(URL); await pg.wait_for_timeout(1500)

        # ---- the deck itself
        deck = await pg.evaluate("() => socData().map(g => ({ id: g.id, label: g.label, suits: g.suits, n: g.stems.length, bad: g.stems.filter(s => !/[?.][”]?$/.test(s) || (s.match(/___/g) || []).length > 2) }))")
        check('Socrates has 24 kinds of question and 475 stems', len(deck) == 24 and sum(g['n'] for g in deck) == 475, [(g['id'], g['n']) for g in deck])
        check('every stem ends as a question or sentence and has at most two blanks', all(not g['bad'] for g in deck), [g['bad'] for g in deck if g['bad']])
        check('every kind says which selections it suits', all(g['suits'] and all(x in {'term', 'claim', 'number', 'source', 'person', 'event', 'none'} for x in g['suits']) for g in deck))

        # ---- the kind of selection
        kinds = await pg.evaluate("""() => ({ term: socKindOf('logistics'), claim: socKindOf('The blockade caused the famine in the north'), number: socKindOf('42,000 troops'),
            name: socKindOf('Xenophon'), none: socKindOf(''), subj: socSubject('  The army reached the sea. '), long: socSubject('word '.repeat(60)).length })""")
        check('a selection is read as a term, a claim, a number or a name', kinds['term'] == 'term' and kinds['claim'] == 'claim' and kinds['number'] == 'number' and kinds['name'] == 'name' and kinds['none'] == 'none', kinds)
        check('the selection is tidied to sit inside a question', kinds['subj'] == 'the army reached the sea' and kinds['long'] <= 141, kinds)

        # ---- select a sentence, ask Socrates from the Mark menu (Ctrl+Alt+G, then S)
        await pg.evaluate("""() => { editor.innerHTML = '<h1>Supply</h1><p>The blockade caused the famine in the northern provinces.</p><p>Second paragraph.</p>'; syncEditor();
            const t = editor.querySelector('p').firstChild, r = document.createRange(); r.setStart(t, 0); r.setEnd(t, t.data.length); getSelection().removeAllRanges(); getSelection().addRange(r); savedRange = r.cloneRange(); editor.focus(); }""")
        await pg.keyboard.press('Control+Alt+KeyG'); await pg.wait_for_timeout(150); await pg.keyboard.press('s'); await pg.wait_for_timeout(300)
        st = await pg.evaluate("() => ({ open: $('#socDlg').open, about: $('#socAbout').value, kind: socKindNow, groups: socDeal.map(d => d.g.id), cards: $$('#socCards .soc-q').map(x => x.textContent), marks: $$('#socCards mark').length })")
        check('Mark → Ask Socrates opens the panel about the selected sentence', st['open'] and st['about'] == 'the blockade caused the famine in the northern provinces' and st['kind'] == 'claim', st)
        check('three questions, each of a different kind', len(st['groups']) == 3 and len(set(st['groups'])) == 3, st['groups'])
        check('the claim fills the blanks, in quotation marks', st['marks'] >= 1 and any('“the blockade caused the famine' in c for c in st['cards']), st['cards'])
        pool = await pg.evaluate("() => [...new Set(socPool('claim').map(g => g.id))]")
        check('claims draw on evidence, assumptions, alternatives and implications', all(x in pool for x in ['evidence', 'assumptions', 'alternatives', 'implications']) and 'numbers' not in pool, pool)

        # another like this, a chosen kind, a different subject
        before = await pg.evaluate("() => $$('#socCards .soc-q').map(x => x.textContent)")
        await pg.click('[data-soc-more="1"]'); await pg.wait_for_timeout(100)
        after = await pg.evaluate("() => ({ q: $$('#socCards .soc-q').map(x => x.textContent), g: socDeal.map(d => d.g.id) })")
        check('"Another like this" replaces that one question with another of the same kind', after['q'][0] == before[0] and after['q'][2] == before[2] and after['q'][1] != before[1] and after['g'][1] == st['groups'][1], after)
        await pg.select_option('#socKind', 'numbers'); await pg.wait_for_timeout(100)
        lab = await pg.evaluate("() => $$('#socCards .soc-g').map(x => x.textContent)")
        check('picking a kind deals three of that kind', lab == ['Numbers, data and measurement'] * 3, lab)
        await pg.select_option('#socKind', 'auto')
        await pg.fill('#socAbout', 'Xenophon'); await pg.press('#socAbout', 'Enter'); await pg.wait_for_timeout(100)
        nm = await pg.evaluate("() => ({ kind: socKindNow, suits: socDeal.map(d => d.g.suits), q: $$('#socCards .soc-q').map(x => x.textContent) })")
        check('a name gets questions about people and events, unquoted', nm['kind'] == 'name' and all(('person' in s or 'event' in s) for s in nm['suits']) and not any('“Xenophon”' in q for q in nm['q']), nm)
        await pg.fill('#socAbout', 'the blockade caused the famine in the northern provinces'); await pg.press('#socAbout', 'Enter'); await pg.wait_for_timeout(100)
        await pg.select_option('#socKind', 'evidence'); await pg.wait_for_timeout(100)
        q0 = await pg.evaluate("() => socText(socDeal[0].s, $('#socAbout').value.trim())")

        # use it: the question dialog opens, linked to the passage
        await pg.click('[data-soc-use="0"]'); await pg.wait_for_timeout(300)
        qd = await pg.evaluate("() => ({ soc: $('#socDlg').open, open: $('#qDlg').open, title: $('#qDlgTitle').textContent, text: $('#qText').value })")
        check('"Use this question" opens the question dialog with it, to link this passage', not qd['soc'] and qd['open'] and qd['title'] == 'Link this passage to a question' and qd['text'] == q0, qd)
        await pg.click('#qNew'); await pg.wait_for_timeout(300)
        linked = await pg.evaluate("() => { const it = qItems().find(i => i.title === $('#qText').value || i.title.startsWith(%s)); const marks = rmAll('q'); return { n: qItems().length, title: it && it.title, linked: !!it && marks.some(p => p.ref === it.id && /blockade/.test(p.text)), side: $('#rsQs').textContent }; }" % json.dumps(q0[:20]))
        check('the question is saved and the sentence is linked to it', linked['n'] == 1 and linked['title'] == q0 and linked['linked'], linked)
        check('the Research tab lists it', q0[:30] in linked['side'], linked['side'][:200])

        # ---- with nothing selected: from the Research tab, a mix of kinds; the blank is ready to type over
        await pg.evaluate("() => { getSelection().removeAllRanges(); savedRange = null; switchTab('research'); }")
        await pg.click('#rsSoc'); await pg.wait_for_timeout(250)
        mx = await pg.evaluate("() => ({ about: $('#socAbout').value, kind: socKindNow, foot: $('#socFoot').textContent, n: $$('#socCards li').length })")
        check('with nothing selected Socrates deals a mix of kinds', mx['about'] == '' and mx['kind'] == 'none' and mx['n'] == 3 and 'a mix of kinds' in mx['foot'] and '475 questions in 24 kinds' in mx['foot'], mx)
        noblank = await pg.evaluate("() => { let n = 0; for (let i = 0; i < 20; i++) { socShuffle(); n += socDeal.filter(d => d.s.includes('___')).length; } return n; }")
        check('with nothing selected, most questions stand on their own instead of leaving a blank', noblank <= 20, noblank)
        await pg.select_option('#socKind', 'clarify'); await pg.wait_for_timeout(100)
        await pg.evaluate("() => { const g = socData().find(x => x.id === 'clarify'); socDeal[0] = { g, s: 'What exactly do I mean by ___?' }; socRender(); }")
        await pg.click('[data-soc-use="0"]'); await pg.wait_for_timeout(300)
        nq = await pg.evaluate("() => { const q = $('#qText'); return { title: $('#qDlgTitle').textContent, text: q.value, sel: q.value.slice(q.selectionStart, q.selectionEnd) }; }")
        check('a new question, with the blank selected to type over', nq['title'] == 'New research question' and nq['text'] == 'What exactly do I mean by ___?' and nq['sel'] == '___', nq)
        await pg.click('#qCancel')

        # ---- the question dialog offers Socrates; empty states point to it
        await pg.evaluate("() => openQuestionLink(true)"); await pg.wait_for_timeout(150)
        await pg.click('#qSoc'); await pg.wait_for_timeout(200)
        check('the question dialog has Ask Socrates', await pg.evaluate("() => $('#socDlg').open && !$('#qDlg').open"))
        await pg.click('#socClose')
        await pg.evaluate("() => { P.plan.items = PLI().filter(i => i.type !== 'question'); rmRefresh(); renderResearch && renderResearch(); }"); await pg.wait_for_timeout(150)
        emp = await pg.evaluate("() => ({ side: $('#rsQs').textContent, btn: !!$('#rsQs .link-btn') })")
        check('with no questions the Research tab offers Socrates', 'Not sure what to ask?' in emp['side'] and emp['btn'], emp)
        await pg.click('#rsQs .link-btn'); await pg.wait_for_timeout(200)
        check('…and it opens the panel', await pg.evaluate("() => $('#socDlg').open")); await pg.click('#socClose')
        await pg.evaluate("() => openDesk('questions')"); await pg.wait_for_timeout(250)
        dk = await pg.evaluate("() => $$('#deskBody .soc-btn, #deskTools .soc-btn').length")
        check('the research desk Questions view has Ask Socrates', dk >= 2, dk)
        await pg.evaluate("() => closeDesk()")
        pal = await pg.evaluate("() => { openPalette(); $('#palQ').value = 'socrates'; $('#palQ').dispatchEvent(new Event('input')); return $$('#palList li').map(li => li.textContent).join('|'); }")
        check('the command palette finds Ask Socrates', 'Ask Socrates' in pal, pal[:200])
        await pg.keyboard.press('Escape')

        # ---- the kind of writing leans the deal
        lean = await pg.evaluate("() => { PREFS.tipsFor = Object.assign({}, PREFS.tipsFor, { [P.id]: 'brief' }); const a = socPool('claim').filter(g => g.id === 'intel').length; PREFS.tipsFor[P.id] = 'general'; const c = socPool('claim').filter(g => g.id === 'intel').length; return [a, c]; }")
        check('an intelligence brief leans toward intelligence-analysis questions', lean[0] == lean[1] + 2, lean)

        # ---- the archive export, on the thesis example with a figure added
        await pg.evaluate("() => { dirtyFile = false; }")
        await pg.evaluate("() => openStarter('thesis')"); await pg.wait_for_timeout(1500)
        await pg.evaluate("px => { const a = addAsset(px, 'map', 1, 1); editor.insertAdjacentHTML('beforeend', figHTML(a, 'The route north')); syncEditor(); hydrateImages(); renumberFigures(); }", PX)
        await pg.wait_for_timeout(300)
        proj = await pg.evaluate("() => ({ docs: P.docs.length, notes: P.notes.length, sources: P.sources.length, title: P.title, keys: [...citeKeys(P.sources).values()] })")
        await pg.click('#btnExport')
        async with pg.expect_download() as dl:
            await pg.click('#exportMenu [data-x=archive]')
        d = await dl.value
        path = OUT + '/archive.zip'; await d.save_as(path)
        z = zipfile.ZipFile(path); names = z.namelist(); root = names[0].split('/')[0]
        check('the archive is named for the project', d.suggested_filename.endswith(' archive.zip') and root.endswith(' archive'), d.suggested_filename)
        mds = [n for n in names if re.match(re.escape(root) + r'/documents/[^/]+/[^/]+\.md$', n)]
        check('every document is a Markdown file in its own folder', len(mds) == proj['docs'], (len(mds), proj['docs']))
        text = '\n'.join(z.read(n).decode() for n in mds)
        cited = set(re.findall(r'@([A-Za-z][\w:.-]*)', text)) - {'key'}
        bib = z.read(root + '/references.bib').decode()
        check('citations are Pandoc keys found in references.bib', cited and all(('{' + k + ',') in bib for k in cited), (cited, bib[:200]))
        check('documents point to the shared bibliography', 'bibliography: ../../references.bib' in text)
        cj = json.loads(z.read(root + '/references.json'))
        check('sources are also CSL-JSON, with the same keys', len(cj) == proj['sources'] and {x['id'] for x in cj} == set(proj['keys']))
        figs = [n for n in names if '/figures/' in n]
        check('figures sit beside their document and the Markdown points to them', figs and any('](figures/figure-' in z.read(n).decode() for n in mds), figs)
        notes = [n for n in names if n.startswith(root + '/notes/')]
        check('every note is its own Markdown file with its title and tags at the top', len(notes) == proj['notes'] and all(z.read(n).decode().startswith('---\ntitle: ') for n in notes), (len(notes), proj['notes']))
        check('a note from a source names it by key', any('source: "@' in z.read(n).decode() for n in notes))
        check('the research memo comes too', root + '/research memo.md' in names and 'Research memo' in z.read(root + '/research memo.md').decode())
        pj = [n for n in names if n.startswith(root + '/project/') and n.endswith('.json')]
        back = json.loads(z.read(pj[0])) if pj else {}
        check('the project file is in the archive, whole', pj and back.get('title') == proj['title'] and len(back.get('docs', [])) == proj['docs'] and back.get('app') == 'Anabasis')
        rd = z.read(root + '/README.txt').decode()
        check('a README says what is where and how to use it without Anabasis', 'documents/' in rd and 'notes/' in rd and 'references.bib' in rd and 'pandoc' in rd.lower() and 'zerohistory.net/anabasis' in rd, rd[:300])
        check('Markdown has no leftover placeholders', 'ZZC' not in text and 'ZZF' not in text)
        # still the thesis starter, loaded for the archive above
        # 2.3: a person, a place, a claim and your project
        fit = await pg.evaluate("""() => { const out = {}; [['Xenophon', 'person'], ['Cunaxa', 'event']].forEach(([w, want]) => { const k = socNameKind(w); let bad = 0, proj = 0;
            for (let i = 0; i < 40; i++) { openSocrates({ about: w, fresh: true }); socDeal.forEach(d => { const t = SOC_TAG[d.s] || ''; if (k === 'person' && /(had not happened|___ (had )?happen)/.test(d.s)) bad++; if (k !== 'person' && /What did ___ want|had decided the other way/.test(d.s)) bad++; if (/Lee|Engels|Waterfield|Xenophon|Chapter|thread/.test(d.s.replace(w, ''))) proj++; }); }
            out[w] = { k, bad, proj }; }); $('#socDlg').close(); return out; }""")
        check('a name used with "says" is a person, one used with "at" or "left" a place or event', fit['Xenophon']['k'] == 'person' and fit['Cunaxa']['k'] == 'event', fit)
        check('a person never gets a question meant for an event, nor a place one meant for a person', fit['Xenophon']['bad'] == 0 and fit['Cunaxa']['bad'] == 0, fit)
        check('some questions name the project: an author, the chapter, a thread', fit['Xenophon']['proj'] > 0 and fit['Cunaxa']['proj'] > 0, fit)
        tags = await pg.evaluate("() => { const t = Object.values(SOC_TAG); return { p: t.filter(x => x === 'p').length, x: t.filter(x => x === 'x').length, c: t.filter(x => x === 'c').length, leak: socData().some(g => g.stems.some(s => /\\{[pxc]\\}/.test(s))) }; }")
        check('stems carry person, non-person and claim tags, stripped from the text', tags['p'] >= 15 and tags['x'] >= 18 and tags['c'] >= 5 and not tags['leak'], tags)
        short = await pg.evaluate("() => { socKindNow = 'claim'; return socQ('Daily needs ran into many tons of grain for a force of this size and more'); }")
        check('a long claim is quoted by its opening words', short == '“Daily needs ran into many tons of…”', short)
        # 2.4: examining a claim, step by step
        await pg.evaluate("() => openSocrates({ fresh: true, about: 'Markets mattered more than plunder on the march' })"); await pg.wait_for_timeout(200)
        aside = await pg.evaluate("() => $('#socAside').textContent")
        check('Socrates speaks a line of his own above the questions', len(aside) > 10, aside)
        await pg.click('#socExam'); await pg.wait_for_timeout(200)
        st = await pg.evaluate("() => ({ talk: !$('#socTalk').hidden, deck: $('#socDeck').hidden, term: SX.term, step: SX.step, said: htmlToText(SX.log[0].html) })")
        check('Examine a claim starts from what is in About, asking what its key phrase means', st['talk'] and st['deck'] and st['step'] == 'define' and st['term'] in st['said'], st)
        for a in ['I mean that buying food counted for more than taking it', 'It holds, mostly', 'Markets mattered more than plunder where there were markets', 'Xenophon says so in Book V']:
            await pg.fill('#socIn', a); await pg.press('#socIn', 'Enter'); await pg.wait_for_timeout(120)
        dn = await pg.evaluate("() => ({ step: SX.step, form: $('#socForm').hidden, done: !$('#socDone').hidden, sum: $('#socDone').textContent, n: SX.log.length })")
        check('the dialogue runs define, counter, revise, test, and ends with before and after', dn['step'] == 'done' and dn['form'] and dn['done'] and 'Before' in dn['sum'] and 'where there were markets' in dn['sum'] and dn['n'] >= 9, dn)
        nj = await pg.evaluate("() => P.journal.log.length")
        await pg.click('#sxSave'); await pg.wait_for_timeout(120)
        sv = await pg.evaluate("n => { const e = P.journal.log[P.journal.log.length - 1]; return { more: P.journal.log.length - n, kind: e.kind, tags: e.tags, text: e.text }; }", nj)
        check('saving puts the before and after in the journal as an idea', sv['more'] == 1 and sv['kind'] == 'idea' and 'socrates' in sv['tags'] and 'Before: Markets mattered' in sv['text'] and 'After: Markets mattered more than plunder where' in sv['text'], sv)
        await pg.click('#socBack'); await pg.wait_for_timeout(120)
        bk = await pg.evaluate("() => ({ deck: !$('#socDeck').hidden, talk: $('#socTalk').hidden, exam: !$('#socExam').hidden, back: $('#socBack').hidden })")
        check('Back to the questions returns to the cards', all(bk.values()), bk)
        await pg.evaluate("() => $('#socDlg').close()")
        await b.close()
    check('no page errors', not errs, errs[:5])
    print('t42', 'OK' if ok else 'FAILED'); sys.exit(0 if ok else 1)

asyncio.run(main())
