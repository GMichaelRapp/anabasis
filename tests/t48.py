"""2.6.2: the calendar on Project home and its .ics export, the scratch pad, the note trash, copy citation,
note templates, the recent switcher (⌘/Ctrl E) and a note resurfaced on Project home."""
import asyncio, json, re
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from env import URL
from playwright.async_api import async_playwright


async def main():
    ok = True
    def check(name, cond, extra=''):
        nonlocal ok
        print(('PASS ' if cond else 'FAIL ') + name, extra if not cond else ''); ok = ok and bool(cond)
    errs = []
    async with async_playwright() as pw:
        b = await pw.chromium.launch()
        ctx = await b.new_context(viewport={'width': 1440, 'height': 950})
        await ctx.grant_permissions(['clipboard-read', 'clipboard-write'])
        await ctx.add_init_script("delete window.showSaveFilePicker; localStorage.setItem('commonplace.prefs',JSON.stringify({startHome:false,toured:true,seenVersion:'99.0.0',orcDay:new Date().toISOString().slice(0,10),dailyGoal:500}))")
        pg = await ctx.new_page()
        pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.on('console', lambda m: errs.append('console: ' + m.text) if m.type == 'error' and 'Failed to load resource' not in m.text else None)
        await pg.goto(URL); await pg.wait_for_timeout(1500)
        await pg.evaluate("() => { dirtyFile = false; return openStarter('thesis'); }"); await pg.wait_for_timeout(1300)
        await pg.evaluate("() => document.querySelectorAll('dialog[open]').forEach(d => d.close())")

        # ---------- calendar ----------
        await pg.evaluate("""() => { window.K = o => { const d = new Date(); d.setDate(d.getDate() + o); return todayKey(d); };
          P.stats.days = {}; P.stats.days[K(-1)] = { a: 600, n: 600 }; P.stats.days[K(-2)] = { a: 120, n: 120 };
          P.docs[0].deadline = K(2); P.docs[0].status = 'drafting'; P.goal.deadline = K(5); jLog('found', 'Muster rolls disagree with the speeches.');
          calMonth = ''; calDay = ''; openHome(); }""")
        await pg.wait_for_timeout(700)
        r = await pg.evaluate("""() => { const c = $('#hmCal'); if (!c) return null; const d = k => c.querySelector(`[data-cal="${k}"]`);
          return { y: d(K(-1))?.className, y2: d(K(-2))?.className, today: d(K(0))?.className, due: d(K(2)) ? !!d(K(2)).querySelector('i.due') : 'other month', jr: !!d(K(0)).querySelector('i.jr'),
                   label: d(K(-1))?.getAttribute('aria-label'), wd: c.querySelectorAll('.cal-wd').length, detail: c.querySelector('.cal-day')?.innerText || '' }; }""")
        check('Project home has a calendar of this month, a cell per day under seven weekday heads', r and r['wd'] == 7 and 'today' in r['today'], r)
        if r and r['y']:
            check('…each day shaded by the words written: the darkest when the daily goal is met', 'lv4' in r['y'] and re.search(r'lv[12]', r['y2'] or ''), [r['y'], r['y2']])
            check('…and the day says so to a screen reader', '600 words' in (r['label'] or ''), r['label'])
        check('…with a mark for what’s due and for journal entries', r['jr'] and r['due'] in (True, 'other month'), r)
        check('…and today’s details open beneath it: words, journal entries, notes made', 'journal' in r['detail'].lower() or 'Journal' in r['detail'], r['detail'][:200])

        # add an item: an archive visit two days on
        await pg.click('#calAdd'); await pg.wait_for_timeout(200)
        await pg.fill('#evName', 'National Archives, Kew'); await pg.evaluate("$('#evDate').value = K(1); $('#evTime').value = '10:30'; $('#evKind').value = 'visit'; $('#evNote').value = 'Boxes 3, 4; bring pencils'")
        await pg.click('#evOk'); await pg.wait_for_timeout(300)
        r = await pg.evaluate("""() => ({ ev: P.events.map(e => [e.title, e.date === K(1), e.time, e.kind]), cell: !!$(`#hmCal [data-cal="${K(1)}"] i.ev.k-visit`) || K(1).slice(0, 7) !== K(0).slice(0, 7),
            sel: $('#hmCal .cal-d.on')?.dataset.cal === K(1), detail: $('#hmCal .cal-day')?.innerText || '' })""")
        check('+ Add to the calendar: a named, dated item with a kind, shown on its day', r['ev'] == [['National Archives, Kew', True, '10:30', 'visit']] and r['cell'] and r['sel'] and 'Kew' in r['detail'], r)
        # edit and remove, with Undo
        await pg.evaluate("openEvent(P.events[0].id)"); await pg.wait_for_timeout(150)
        check('…clicking it opens it to edit, with Remove', await pg.evaluate("$('#evName').value === 'National Archives, Kew' && !$('#evDel').classList.contains('hidden')"))
        await pg.click('#evDel'); await pg.wait_for_timeout(200)
        n0 = await pg.evaluate("P.events.length")
        await pg.evaluate("$('#toast button')?.click()"); await pg.wait_for_timeout(200)
        check('…and Remove can be undone', n0 == 0 and await pg.evaluate("P.events.length") == 1)
        # month navigation and arrow keys
        await pg.evaluate("$('#hmCal [data-calnav=\"1\"]').click()"); await pg.wait_for_timeout(150)
        r = await pg.evaluate("() => { const d = new Date(); d.setDate(1); d.setMonth(d.getMonth() + 1); return [$('#hmCal .cal-nav b').textContent, d.toLocaleDateString([], { month: 'long', year: 'numeric' }), !!$('#hmCal [data-calnav=\"0\"]')]; }")
        check('‹ › move between months, with Today to come back', r[0] == r[1] and r[2], r)
        await pg.evaluate("$('#hmCal [data-calnav=\"0\"]').click()"); await pg.wait_for_timeout(150)
        await pg.focus(f"#hmCal .cal-d.on"); await pg.keyboard.press('ArrowRight'); await pg.wait_for_timeout(150)
        check('…and the arrow keys move between days', await pg.evaluate("$('#hmCal .cal-d.on')?.dataset.cal === K(1) && document.activeElement?.dataset.cal === K(1)"))

        # .ics
        ics = await pg.evaluate("calIcsText().text")
        lines = ics.split('\r\n')
        check('Export .ics: a calendar file with the item, the document deadline and the project deadline',
              ics.startswith('BEGIN:VCALENDAR\r\nVERSION:2.0') and ics.rstrip().endswith('END:VCALENDAR') and ics.count('BEGIN:VEVENT') == 3, ics[:300])
        k1 = await pg.evaluate("K(1).replace(/-/g, '')"); k2 = await pg.evaluate("K(2).replace(/-/g, '')"); k3 = await pg.evaluate("K(3).replace(/-/g, '')")
        check('…a timed item lasts an hour from its start, and commas are escaped',
              f'DTSTART:{k1}T103000' in ics and f'DTEND:{k1}T113000' in ics and 'SUMMARY:National Archives\\, Kew' in ics and 'Boxes 3\\, 4\\; bring pencils' in ics, ics)
        check('…a deadline is an all-day item', f'DTSTART;VALUE=DATE:{k2}' in ics and f'DTEND;VALUE=DATE:{k3}' in ics, ics)
        check('…and no line runs past 75 characters', all(len(l.encode()) <= 75 for l in lines), max(len(l) for l in lines))
        async with pg.expect_download() as dl:
            await pg.click('#calIcs')
        d = await dl.value
        check('…downloaded as a .ics file named for the project', d.suggested_filename.endswith(' - calendar.ics'), d.suggested_filename)

        # ---------- resurfaced note ----------
        r = await pg.evaluate("""() => { P.notes.forEach((n, i) => { n.modified = i < 2 ? new Date(Date.now() - 90 * 864e5).toISOString() : nowISO(); if (i < 2) n.body = n.body.length > 40 ? n.body : n.body + ' and a longer body to resurface here.'; });
          renderHome(); return new Promise(res => setTimeout(() => res({ card: !!$('#hmRs'), t: $('#hmRs .rs-note b')?.textContent, more: !!$('#rsNext') }), 300)); }""")
        old = await pg.evaluate("P.notes.slice(0, 2).map(n => noteTitle(n))")
        check('Project home brings back a note untouched for a month, with Another', r['card'] and r['t'] in old and r['more'], [r, old])
        await pg.click('#rsNext'); await pg.wait_for_timeout(150)
        t2 = await pg.evaluate("$('#hmRs .rs-note b')?.textContent")
        check('…Another shows a different one', t2 in old and t2 != r['t'], [t2, r['t']])
        await pg.click('#hmRs .rs-note'); await pg.wait_for_timeout(300)
        check('…and clicking it opens the note', await pg.evaluate("panelState?.kind === 'note' && noteTitle(P.notes.find(n => n.id === panelState.id)) === " + json.dumps(t2)))
        r = await pg.evaluate("() => { P.notes.forEach(n => n.modified = nowISO()); renderHome(); return new Promise(res => setTimeout(() => res(!!$('#hmRs')), 300)); }")
        check('…with nothing that old, there’s no card', not r)
        await pg.evaluate("closeHome()")

        # ---------- scratch pad ----------
        await pg.keyboard.press('Control+Alt+KeyN'); await pg.wait_for_timeout(200)
        check('⌘/Ctrl Alt N opens the scratch pad, focused', await pg.evaluate("!$('#pad').hidden && document.activeElement === $('#padText')"))
        await pg.keyboard.type('Ask the archivist about the 1919 file #archive #Kew')
        await pg.keyboard.press('Enter'); await pg.keyboard.press('Enter'); await pg.keyboard.type('> the army moved like a town')
        await pg.keyboard.press('Enter'); await pg.keyboard.press('Enter'); await pg.keyboard.type('Call M. about the photos')
        await pg.wait_for_timeout(600)
        check('…what you type is kept with the project', await pg.evaluate("P.scratch.startsWith('Ask the archivist') && P.scratch.includes('> the army') && dirtyFile"))
        # cursor in the second passage → Make a note
        await pg.evaluate("const t = $('#padText'), i = t.value.indexOf('army'); t.setSelectionRange(i, i)")
        n0 = await pg.evaluate("P.notes.length")
        await pg.click('#padNote'); await pg.wait_for_timeout(200)
        r = await pg.evaluate("({ n: P.notes.length, k: P.notes[0].kind, b: P.notes[0].body, pad: P.scratch })")
        check('Make a note takes the passage the cursor is in: a > passage becomes a quotation note',
              r['n'] == n0 + 1 and r['k'] == 'quote' and r['b'] == 'the army moved like a town', r)
        check('…and it leaves the pad, the passages either side closing up', r['pad'] == 'Ask the archivist about the 1919 file #archive #Kew\n\nCall M. about the photos', repr(r['pad']))
        await pg.evaluate("$('#toast button')?.click()"); await pg.wait_for_timeout(200)
        r = await pg.evaluate("({ n: P.notes.length, pad: $('#padText').value })")
        check('…Undo puts the passage back and removes the note', r['n'] == n0 and 'the army moved' in r['pad'], r)
        # split the whole pad
        await pg.evaluate("const t = $('#padText'); t.setSelectionRange(0, 0)")
        await pg.click('#padSplit'); await pg.wait_for_timeout(200)
        r = await pg.evaluate("({ n: P.notes.length, top: P.notes.slice(0, 3).map(n => [n.kind, n.tags, n.body]), pad: P.scratch })")
        check('Split into notes: each passage becomes a note, and the pad empties', r['n'] == n0 + 3 and r['pad'] == '', r)
        check('…#tags become note tags (and leave the text); > lines a quotation', r['top'][0] == ['idea', ['archive', 'kew'], 'Ask the archivist about the 1919 file'] and r['top'][1][0] == 'quote', r['top'])
        # to the journal
        await pg.evaluate("$('#padText').value = 'Pattern: halts follow harvests'; $('#padText').dispatchEvent(new Event('input')); $('#padText').setSelectionRange(3, 3)")
        j0 = await pg.evaluate("jr().log.length")
        await pg.click('#padJournal'); await pg.wait_for_timeout(200)
        r = await pg.evaluate("({ j: jr().log.length, last: jr().log[jr().log.length - 1], pad: P.scratch })")
        check('To the journal: the passage becomes today’s journal entry', r['j'] == j0 + 1 and r['last']['text'] == 'Pattern: halts follow harvests' and r['last']['kind'] == 'idea' and r['pad'] == '', r)
        await pg.keyboard.press('Escape'); await pg.wait_for_timeout(100)
        check('Esc closes the pad', await pg.evaluate("$('#pad').hidden"))
        await pg.evaluate("$('#btnPad').click()"); await pg.wait_for_timeout(100)
        check('…and Notes → Scratch pad opens it again', await pg.evaluate("!$('#pad').hidden"))
        # it stays clear of the side panel, and remembers where you drag it
        await pg.evaluate("padOpen(false); delete PREFS.padPos; openNote(P.notes[0].id); padOpen(true)"); await pg.wait_for_timeout(150)
        r = await pg.evaluate("() => { const a = $('#pad').getBoundingClientRect(), p = $('#panel').getBoundingClientRect(); return [a.right, p.left]; }")
        check('…it opens clear of the side panel', r[0] <= r[1] + 1, r)
        hb = await pg.evaluate("(() => { const r = $('#pad header').getBoundingClientRect(); return [r.left + 40, r.top + 15]; })()")
        await pg.mouse.move(hb[0], hb[1]); await pg.mouse.down(); await pg.mouse.move(hb[0] - 300, hb[1] - 200, steps=5); await pg.mouse.up()
        r = await pg.evaluate("[PREFS.padPos, $('#pad').getBoundingClientRect().left]")
        check('…drag its header to move it; it opens there next time', r[0] and abs(r[0]['x'] - r[1]) < 2, r)
        await pg.evaluate("padOpen(false)")

        # ---------- note trash ----------
        await pg.evaluate("openNote(P.notes[0].id)"); await pg.wait_for_timeout(150)
        gone = await pg.evaluate("P.notes[0].id"); n0 = await pg.evaluate("P.notes.length")
        await pg.click('#panelFoot [data-a=deln]'); await pg.wait_for_timeout(250)
        r = await pg.evaluate(f"({{ dlg: !!document.querySelector('dialog[open]'), n: P.notes.length, t: P.trash.length, tid: P.trash[0]?.note.id, btn: $('#btnTrash').textContent, toast: $('#toast').innerText }})")
        check('Delete moves a note to the trash at once, no question asked', not r['dlg'] and r['n'] == n0 - 1 and r['tid'] == gone and r['btn'] == 'Trash (1)', r)
        check('…with Undo in the message', 'Undo' in r['toast'], r['toast'])
        await pg.evaluate("$('#toast button').click()"); await pg.wait_for_timeout(200)
        check('…Undo brings it back', await pg.evaluate(f"P.notes.some(n => n.id === '{gone}') && P.trash.length === 0"))
        # board delete goes to the trash too
        await pg.evaluate("trashNotes(P.notes.slice(0, 2))"); await pg.wait_for_timeout(150)
        await pg.evaluate("openTrash()"); await pg.wait_for_timeout(150)
        r = await pg.evaluate("({ rows: $$('#trashBody li').length, txt: $('#trashBody').innerText })")
        check('Notes → Trash lists deleted notes with the days they have left', r['rows'] == 2 and '30 days left' in r['txt'], r)
        await pg.click('#trashBody [data-tr=restore]'); await pg.wait_for_timeout(150)
        check('…Restore puts one back', await pg.evaluate("P.trash.length === 1 && $$('#trashBody li').length === 1"))
        await pg.click('#trashBody [data-tr=del]'); await pg.wait_for_timeout(150)
        check('…Delete now removes it for good', await pg.evaluate("P.trash.length === 0 && $('#trashEmpty').disabled"))
        await pg.evaluate("$('#trashDlg').close()")
        # 30 days: older items are dropped when the project loads; the rest survive a save and reopen
        r = await pg.evaluate("""() => { const a = Object.assign(newNote(), { body: 'old' }), b = Object.assign(newNote(), { body: 'recent' });
          const raw = JSON.parse(JSON.stringify(P)); raw.trash = [{ at: new Date(Date.now() - 31 * 864e5).toISOString(), note: a }, { at: new Date(Date.now() - 3 * 864e5).toISOString(), note: b }];
          raw.events = [{ id: 'e1', date: '2027-01-04', title: 'Kew', kind: 'visit' }, { id: 'e2', date: 'soon', title: 'bad' }]; raw.scratch = 'kept';
          const x = normalize(raw); return { t: x.trash.map(t => t.note.body), e: x.events.map(e => [e.id, e.kind, e.time]), s: x.scratch }; }""")
        check('…in the project file, the trash keeps 30 days; the calendar and pad are saved with it',
              r['t'] == ['recent'] and r['e'] == [['e1', 'visit', '']] and r['s'] == 'kept', r)

        # ---------- copy citation ----------
        await pg.evaluate("openSource(sortedSources()[0].id)"); await pg.wait_for_timeout(200)
        await pg.click('#panelFoot [data-a=copycite]'); await pg.wait_for_timeout(300)
        r = await pg.evaluate("({ open: $('#ccDlg').open, style: $('#ccStyle').value, doc: curDoc().style, rows: $$('#ccBody .cc-row').map(x => x.innerText), opt: $('#ccStyle option[selected]')?.textContent })")
        check('Copy citation on a source: its citation and bibliography entry in the document’s style', r['open'] and r['style'] == r['doc'] and len(r['rows']) == 2 and not r['opt'].startswith('chicago-'), r)
        await pg.fill('#ccLoc', '47'); await pg.wait_for_timeout(300)
        check('…with a page if you give one', '47' in await pg.evaluate("$$('#ccBody .cc-out')[0].innerText"))
        await pg.select_option('#ccStyle', 'apa'); await pg.wait_for_timeout(300)
        apa = await pg.evaluate("$$('#ccBody .cc-out').map(x => x.innerText)")
        check('…in any other style', re.search(r'\(.*\d{4}.*47\)', apa[0]) and 'In-text' in await pg.evaluate("$('#ccBody').innerText"), apa)
        await pg.click('#ccBody [data-cc=bib]'); await pg.wait_for_timeout(300)
        clip = await pg.evaluate("navigator.clipboard.readText()")
        check('…Copy puts it on the clipboard', clip.strip() == apa[1].strip() and await pg.evaluate("$('#ccBody [data-cc=bib]').textContent") == 'Copied', [clip, apa[1]])
        await pg.evaluate("$('#ccDlg').close()")

        # ---------- note templates ----------
        await pg.evaluate("switchTab('notes')"); await pg.wait_for_timeout(150)
        r = await pg.evaluate("(() => { const row = $('#btnTrash').parentElement, sb = $('#sidebar').getBoundingClientRect(); return [row.scrollWidth <= row.clientWidth, [...row.children].every(b => b.getBoundingClientRect().right <= sb.right + 0.5), $('#btnNoteTpl').textContent]; })()")
        check('the Notes tab’s Scratch pad, Templates… and Trash buttons fit the sidebar', r[0] and r[1] and r[2] == 'Templates…', r)
        await pg.evaluate("$('#btnNoteTpl').click()"); await pg.wait_for_timeout(150)
        names = await pg.evaluate("$$('#ntList [data-nt] b').map(b => b.textContent)")
        check('Notes → Templates…: interview log, archive visit, source summary, field notes, meeting notes', names == ['Interview log', 'Archive visit', 'Source summary', 'Field notes', 'Meeting notes'], names)
        await pg.click('#ntList [data-nt=interview]'); await pg.wait_for_timeout(250)
        r = await pg.evaluate("({ n: P.notes[0], open: panelState?.id === P.notes[0].id, today: new Date().toLocaleDateString([], { year: 'numeric', month: 'long', day: 'numeric' }) })")
        check('…an interview log: tagged, laid out, today’s date filled in, open to write',
              r['open'] and r['n']['tags'] == ['interview'] and '## Quotations to check against the recording' in r['n']['body'] and r['today'] in r['n']['body'] and r['n']['title'] == 'Interview: ', r['n']['body'][:200])
        await pg.evaluate("openSource(sortedSources()[0].id); openNoteTpls()"); await pg.wait_for_timeout(150)
        await pg.click('#ntList [data-nt=source]'); await pg.wait_for_timeout(250)
        check('…a source summary started from a source is linked to it', await pg.evaluate("P.notes[0].sourceId === sortedSources()[0].id && P.notes[0].kind === 'summary' && P.notes[0].body.includes('## Limits and gaps')"))
        # save your own
        await pg.evaluate("const n = P.notes[0]; n.title = 'Court record'; n.body = '**Case:** \\n**Court:** \\n## Holding\\n'; n.tags = ['court']; openNote(n.id)"); await pg.wait_for_timeout(150)
        await pg.click('#panelFoot [data-a=savetpl]'); await pg.wait_for_timeout(150)
        await pg.evaluate("openNoteTpls()"); await pg.wait_for_timeout(150)
        r = await pg.evaluate("({ names: $$('#ntList [data-nt] b').map(b => b.textContent), saved: JSON.parse(localStorage.getItem('commonplace.prefs')).noteTpls })")
        check('Save as template: your own layout joins the list, kept in this browser for every project', r['names'][-1] == 'Court record' and r['saved'] and r['saved'][0]['tags'] == ['court'], r)
        await pg.click('#ntList [data-ntdel]'); await pg.wait_for_timeout(150)
        check('…and ✕ removes it', await pg.evaluate("$$('#ntList [data-nt]').length === 5 && !PREFS.noteTpls.length"))
        await pg.evaluate("$('#ntDlg').close()")

        # ---------- recent switcher ----------
        await pg.evaluate("openDoc(P.docs[1].id); openNote(P.notes[3].id); openDoc(P.docs[0].id)"); await pg.wait_for_timeout(300)
        await pg.keyboard.press('Control+e'); await pg.wait_for_timeout(200)
        r = await pg.evaluate("({ open: $('#swDlg').open, first: $$('#swList li')[0]?.innerText, on: $('#swList li.on')?.innerText, d1: P.docs[1].title, n3: noteTitle(P.notes[3]), d0: P.docs[0].title })")
        check('⌘/Ctrl E lists what you opened, most recent first, with the one before this ready to open',
              r['open'] and r['d0'] in r['first'] and r['n3'] in r['on'], r)
        await pg.keyboard.press('Enter'); await pg.wait_for_timeout(250)
        check('…Enter opens it', await pg.evaluate("panelState?.kind === 'note' && panelState.id === P.notes[3].id && !$('#swDlg').open"))
        await pg.keyboard.press('Control+e'); await pg.wait_for_timeout(150)
        await pg.keyboard.type(await pg.evaluate("P.docs[1].title.slice(0, 6)")); await pg.keyboard.press('Enter'); await pg.wait_for_timeout(250)
        check('…type to filter', await pg.evaluate("curDocId === P.docs[1].id"))

        # palette, shortcuts sheet
        r = await pg.evaluate("COMMANDS.map(c => c[0]).join('|')")
        check('the command search reaches each of them', all(x in r for x in ['Calendar:', 'Add to the calendar', 'Export the calendar', 'Scratch pad', 'Note trash', 'New note from a template', 'Recent documents']), r[-400:])
        await pg.evaluate("openKeys()"); await pg.wait_for_timeout(100)
        check('…and the shortcuts sheet lists the new keys', await pg.evaluate("/Scratch pad/.test($('#keysBody').innerText) && /Recent documents/.test($('#keysBody').innerText)"))
        check('no errors', not errs, errs[:5])
        await b.close()
    print('ALL PASS' if ok else 'SOME FAILED'); _sys.exit(0 if ok else 1)

asyncio.run(main())
