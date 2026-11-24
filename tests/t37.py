"""1.7: split view (notes, sources, the research desk or another document beside the writing) and
pop-out windows kept in step with the main window."""
import asyncio, json, sys
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from env import URL, OUT
from playwright.async_api import async_playwright


async def main():
    ok = True
    def check(name, cond, extra=''):
        nonlocal ok
        print(('PASS ' if cond else 'FAIL ') + name, extra if not cond else ''); ok = ok and bool(cond)
    errs = []
    async with async_playwright() as pw:
        b = await pw.chromium.launch()
        ctx = await b.new_context(viewport={'width': 1440, 'height': 900})
        await ctx.add_init_script("delete window.showSaveFilePicker; localStorage.setItem('commonplace.prefs',JSON.stringify({startHome:false,toured:true,seenVersion:'99.0.0'}))")
        pg = await ctx.new_page()
        pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.on('console', lambda m: errs.append('console: ' + m.text) if m.type == 'error' else None)
        await pg.goto(URL); await pg.wait_for_timeout(1500)
        await pg.evaluate("async () => { dirtyFile = false; await openStarter('thesis'); }"); await pg.wait_for_timeout(800)

        # ---- split view
        await pg.evaluate("() => editor.focus()"); await pg.keyboard.press('Control+Backslash'); await pg.wait_for_timeout(300)
        r = await pg.evaluate("() => ({ on: SPLIT.on, v: SPLIT.view, list: !!$('#spBody #noteList'), page: getComputedStyle($('#scroller')).display !== 'none', stub: !!$('#sidebar .sp-stub[data-pane=notes]') })")
        check('Ctrl+\\ puts notes beside the writing', r == {'on': True, 'v': 'notes', 'list': True, 'page': True, 'stub': True}, r)
        await pg.evaluate("() => switchTab('notes')")
        check('the sidebar says where the notes went, and still shows the list beside the writing', 'open beside the writing' in await pg.inner_text('#sidebar .sp-stub') and await pg.locator('#spBody #noteList li').count() == 3)
        await pg.evaluate("() => { editor.focus(); const r = document.createRange(); r.selectNodeContents(editor); r.collapse(false); getSelection().removeAllRanges(); getSelection().addRange(r); saveSelectionNow(); $$('#spBody #noteList li')[1].querySelector('button[data-a=ins]').click(); }"); await pg.wait_for_timeout(300)
        check('insert a note into the draft from beside it', 'Engels works out daily needs' in await pg.inner_text('#editor'))
        await pg.click('#spTabs [data-sv=sources]'); await pg.wait_for_timeout(200)
        check('switch to sources; notes go home', await pg.locator('#spBody #sourceList li').count() == 4 and await pg.locator('#sidebar #noteList').count() == 1 and await pg.locator('#sidebar .sp-stub[data-pane=sources]').count() == 1)
        await pg.click('#spTabs [data-sv=desk]'); await pg.wait_for_timeout(400)
        r = await pg.evaluate("() => ({ inSplit: !!$('#spBody #desk'), deskOn, deskInSplit, bodyDesk: document.body.classList.contains('desk-on'), page: getComputedStyle($('#scroller')).display !== 'none' })")
        check('the research desk beside the writing, with the page still there', r == {'inSplit': True, 'deskOn': True, 'deskInSplit': True, 'bodyDesk': False, 'page': True}, r)
        await pg.click('#spBody #deskTabs [data-dv=journal]'); await pg.wait_for_timeout(300)
        await pg.evaluate("() => journalDoc('memo')"); await pg.wait_for_timeout(500)
        check('making a document from the desk opens it in the writing, desk still beside it', await pg.evaluate("() => curDoc().title.startsWith('Research memo') && SPLIT.view === 'desk' && deskOn"))
        await pg.click('#spTabs [data-sv=doc]'); await pg.wait_for_timeout(400)
        other = await pg.evaluate("() => $('#spDocSel').value")
        check('another document, read only, beside the writing', other != await pg.evaluate("() => curDocId") and await pg.evaluate("() => !$('#spBody [contenteditable=true]') && $('#spBody .sp-page').textContent.length > 20"))
        await pg.select_option('#spDocSel', await pg.evaluate("() => curDocId")); await pg.wait_for_timeout(200)
        await pg.evaluate("() => { editor.focus(); document.execCommand('insertText', false, ' Zebra-marker.'); }"); await pg.wait_for_timeout(1800)
        check('showing the document being edited keeps up with the writing', 'Zebra-marker' in await pg.inner_text('#spBody .sp-page'))
        check('the desk is back home after switching away', await pg.evaluate("() => $('#main #desk') !== null && !deskInSplit && !deskOn"))
        # swap, wide, resize, keyboard
        await pg.click('#spSwap'); await pg.wait_for_timeout(100)
        check('swap sides', await pg.evaluate("() => document.body.classList.contains('split-left') && $('#split').getBoundingClientRect().left < $('#main').getBoundingClientRect().left"))
        await pg.keyboard.press('Control+Shift+Backslash'); await pg.wait_for_timeout(100)
        check('…and back with Ctrl+Shift+\\', await pg.evaluate("() => !document.body.classList.contains('split-left')"))
        await pg.click('#spMax'); await pg.wait_for_timeout(100)
        check('wide: the side panel takes the whole width', await pg.evaluate("() => getComputedStyle($('#main')).display === 'none' && $('#split').getBoundingClientRect().width > 1000"))
        await pg.click('#spMax')
        await pg.focus('#spResize'); await pg.keyboard.press('ArrowLeft'); await pg.keyboard.press('ArrowLeft'); await pg.wait_for_timeout(100)
        w = await pg.evaluate("() => [PREFS.splitW, $('#split').offsetWidth]")
        check('resize with the keyboard, remembered', w[0] == w[1] and w[0] > 600, w)
        await pg.keyboard.press('F6'); await pg.wait_for_timeout(100)
        f1 = await pg.evaluate("() => document.activeElement === editor")
        await pg.keyboard.press('F6'); await pg.wait_for_timeout(100)
        check('F6 moves between the writing and the side panel', f1 and await pg.evaluate("() => $('#split').contains(document.activeElement)"))
        await pg.keyboard.press('Control+Backslash'); await pg.wait_for_timeout(200)
        check('Ctrl+\\ again closes it, and everything is back in place', await pg.evaluate("() => !SPLIT.on && $('#split').classList.contains('hidden') && !!$('#sidebar #noteList') && !!$('#sidebar #sourceList') && !$('.sp-stub')"))
        # phones: switch between writing and the side panel
        await pg.set_viewport_size({'width': 390, 'height': 844}); await pg.wait_for_timeout(300)
        await pg.evaluate("() => splitOpen('notes')"); await pg.wait_for_timeout(300)
        check('on a phone the side panel fills the screen, with a switch back to the writing', await pg.evaluate("() => $('#split').getBoundingClientRect().width === innerWidth && getComputedStyle($('#spToggle')).display !== 'none'"))
        await pg.click('#spToggle'); await pg.wait_for_timeout(200)
        check('…and the switch goes back to the writing', await pg.evaluate("() => getComputedStyle($('#split')).display === 'none' && SPLIT.on"))
        await pg.click('#spToggle'); await pg.wait_for_timeout(200)
        check('…and to the notes again', await pg.evaluate("() => getComputedStyle($('#split')).display !== 'none'"))
        await pg.evaluate("() => splitClose()"); await pg.set_viewport_size({'width': 1440, 'height': 900}); await pg.wait_for_timeout(300)

        # ---- pop-out windows
        async with ctx.expect_page() as np: await pg.evaluate("() => popOut('notes')")
        pop = await np.value
        pop.on('pageerror', lambda e: errs.append('POP ' + str(e)))
        pop.on('console', lambda m: errs.append('POP console: ' + m.text) if m.type == 'error' else None)
        await pop.wait_for_function("() => typeof popReady !== 'undefined' && popReady", timeout=8000)
        r = await pop.evaluate("() => ({ notes: $$('#spBody #noteList li').length, title: $('#spPTitle').textContent, top: getComputedStyle($('.topbar')).display })")
        check('a pop-out window shows the notes on their own', r['notes'] == 3 and r['title'].startswith('Notes · Supply and Survival') and r['top'] == 'none', r)
        check('the pop-out doesn’t trigger the “open in another tab” warning', await pg.evaluate("() => $('#tabBar').classList.contains('hidden')"))
        # edit in the pop-out -> main
        await pop.click('#noteList li >> nth=1'); await pop.wait_for_timeout(200)
        await pop.fill('#panelBody [data-n=title]', 'Edited in the window'); await pop.wait_for_timeout(1200)
        check('a change in the pop-out reaches the main window', 'Edited in the window' in await pg.evaluate("() => P.notes.map(n => n.title).join('|')") and 'Edited in the window' in await pg.inner_text('#noteList'))
        check('…which marks the project unsaved there (the main window keeps the work)', await pg.evaluate("() => dirtyFile"))
        # edit in main -> pop-out (deferred while typing there)
        await pg.evaluate("() => { const n = P.notes.find(n => n.title === 'Camp followers'); n.title = 'Edited in main'; n.modified = nowISO(); renderNoteList(); markDirty(); }"); await pg.wait_for_timeout(1200)
        mid = await pop.evaluate("() => P.notes.map(n => n.title).join('|')")
        await pop.evaluate("() => document.activeElement.blur()"); await pop.wait_for_timeout(300)
        check('a change in the main window reaches the pop-out', 'Edited in main' in mid and 'Edited in main' in await pop.inner_text('#noteList'), mid)
        check('…without losing the pop-out’s own edit', 'Edited in the window' in await pop.evaluate("() => P.notes.map(n => n.title).join('|')"))
        # both change different notes at the same moment
        await pop.evaluate("() => { const n = P.notes[0]; n.tags = n.tags.concat('from-pop'); n.modified = nowISO(); markDirty(); }")
        await pg.evaluate("() => { const n = P.notes[2]; n.tags = n.tags.concat('from-main'); n.modified = nowISO(); markDirty(); }")
        await pg.wait_for_timeout(1500)
        r1 = await pg.evaluate("() => P.notes.flatMap(n => n.tags).filter(t => /^from-/.test(t)).sort().join()")
        r2 = await pop.evaluate("() => P.notes.flatMap(n => n.tags).filter(t => /^from-/.test(t)).sort().join()")
        check('changes made in both windows at once are both kept', r1 == r2 == 'from-main,from-pop', [r1, r2])
        # a new note in the pop-out, a deleted note in main
        await pop.click('#btnPanelClose'); await pop.click('#btnNewNote'); await pop.fill('#panelBody [data-n=title]', 'Born in the pop-out'); await pop.wait_for_timeout(1200)
        await pg.evaluate("() => { P.notes = P.notes.filter(n => n.title !== 'Read me first'); renderNoteList(); markDirty(); }"); await pg.wait_for_timeout(1500)
        await pop.evaluate("() => document.activeElement.blur()"); await pop.wait_for_timeout(300)
        r1 = await pg.evaluate("() => P.notes.map(n => n.title).sort().join('|')"); r2 = await pop.evaluate("() => P.notes.map(n => n.title).sort().join('|')")
        check('new notes and deletions travel both ways', r1 == r2 and 'Born in the pop-out' in r1 and 'Read me first' not in r1, [r1, r2])
        # actions that touch the draft are done by the main window
        await pop.click('#btnPanelClose'); await pop.evaluate("() => [...$$('#noteList li')].find(l => l.textContent.includes('Edited in main')).querySelector('button[data-a=ins]').click()"); await pop.wait_for_timeout(600)
        check('“Insert” in the pop-out inserts in the main window’s draft', 'Lee argues the non-combatant' in await pg.inner_text('#editor'))
        check('…and the pop-out never saves on its own', await pop.evaluate("() => { let called = false; const o = idb.set; idb.set = () => { called = true; }; persistLocal(); idb.set = o; return !called; }"))
        # a research desk window
        async with ctx.expect_page() as np2: await pg.evaluate("() => popOut('desk', { dv: 'claims' })")
        dk = await np2.value; dk.on('pageerror', lambda e: errs.append('DESK ' + str(e)))
        await dk.wait_for_function("() => typeof popReady !== 'undefined' && popReady", timeout=8000); await dk.wait_for_timeout(500)
        check('the research desk in its own window', await dk.evaluate("() => deskView === 'claims' && $$('#spBody .cl-row, #spBody tr').length > 1"))
        await dk.evaluate("() => { const id = P.claims[0].id; setClaimStatus(id, 'disp'); }"); await dk.wait_for_timeout(1200)
        check('a claim’s status set in the desk window reaches the main window', await pg.evaluate("() => P.claims[0].status === 'disp'"))
        await dk.close(); await pop.close(); await pg.wait_for_timeout(700)
        check('closing pop-outs tidies up', await pg.evaluate("() => { popSync(); return true; }"))
        # opened without Anabasis behind it
        lone = await ctx.new_page(); await lone.goto(URL + '#popout=notes'); await lone.wait_for_timeout(800)
        check('a pop-out opened on its own explains itself and does nothing else', 'Open this from Anabasis' in await lone.inner_text('#popWait'))
        await b.close()
    print('ERRS', errs)
    return ok and not errs

if __name__ == '__main__':
    sys.exit(0 if asyncio.run(main()) else 1)
