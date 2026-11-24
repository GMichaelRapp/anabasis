"""1.2: adaptive bars on every screen width, customizable toolbar, shortcut sheet, writing view,
undo for research marks, the sidebar toggle, phone layouts, and the installable hosted copy."""
import asyncio, functools, http.server, os, subprocess, sys, threading
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from env import URL, OUT
from playwright.async_api import async_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOD = 'Meta' if sys.platform == 'darwin' else 'Control'


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
    def end_headers(self):
        self.send_header('Cache-Control', 'no-store'); super().end_headers()


async def main():
    ok = True
    def check(name, cond, extra=''):
        nonlocal ok
        print(('PASS ' if cond else 'FAIL ') + name, extra if not cond else ''); ok = ok and bool(cond)
    errs = []
    async with async_playwright() as pw:
        b = await pw.chromium.launch()

        async def page(w, h, mobile=False, prefs="{startHome:false,toured:true,seenVersion:'99.0.0'}"):
            ctx = await b.new_context(viewport={'width': w, 'height': h}, is_mobile=mobile, has_touch=mobile)
            await ctx.add_init_script(f"delete window.showSaveFilePicker; localStorage.setItem('commonplace.prefs',JSON.stringify({prefs}))")
            pg = await ctx.new_page()
            pg.on('pageerror', lambda e: errs.append(f'{w}: {e}'))
            await pg.goto(URL); await pg.wait_for_timeout(1300)
            return ctx, pg

        # ---- adaptive bars at every width: nothing overflows, nothing is out of reach
        for w, h, mob in [(1440, 900, False), (1180, 820, False), (1024, 768, False), (820, 1100, True), (600, 900, True), (390, 844, True), (320, 640, True)]:
            ctx, pg = await page(w, h, mob)
            r = await pg.evaluate("""() => {
              const over = ['#topBar', '#docBar', '#toolbar'].map(s => { const e = $(s); return [s, e.scrollWidth - e.clientWidth]; }).filter(x => x[1] > 1);
              const page = document.documentElement.scrollWidth - innerWidth;
              const hiddenTb = $$('#toolbar [data-tb].pb-off').map(e => e.dataset.label);
              TB_PB.open(); const inMenu = $$('#tbMore [data-pbi] > span:not(.pb-glyph)').map(s => s.textContent); $('#tbMore').classList.remove('open');
              const hiddenDoc = $$('#docBar .pb-off[data-label]').filter(e => !('nomenu' in e.dataset)).map(e => e.dataset.label);
              DOC_PB.open && DOC_PB.layout(); DOC_PB.fill(); const docMenu = $$('#docMore [data-pbi] > span:not(.pb-glyph)').map(s => s.textContent);
              const hiddenTop = $$('#topBar .pb-off[data-label]').map(e => e.dataset.label); TOP_PB.fill(); const topMenu = $$('#topMore [data-pbi] > span:not(.pb-glyph)').map(s => s.textContent);
              const visible = s => { const e = $(s); return !!e && !e.classList.contains('pb-off') && e.offsetParent !== null; };
              return { over, page, hiddenTb, inMenu, hiddenDoc, docMenu, hiddenTop, topMenu, cite: visible('#btnCite'), save: visible('#btnSave'), more: visible('#btnTbMore'), side: getComputedStyle($('#sidebar')).position };
            }""")
            check(f'{w}px: no bar overflows', not r['over'] and r['page'] <= 1, r['over'])
            check(f'{w}px: hidden toolbar buttons are all in the ⋯ menu', r['hiddenTb'] == r['inMenu'], (r['hiddenTb'], r['inMenu']))
            check(f'{w}px: hidden document-bar buttons are in its ⋯ menu', r['hiddenDoc'] == r['docMenu'], (r['hiddenDoc'], r['docMenu']))
            check(f'{w}px: hidden top-bar buttons are in its ⋯ menu', [x.replace('&amp;', '&') for x in r['hiddenTop']] == r['topMenu'], (r['hiddenTop'], r['topMenu']))
            check(f'{w}px: Cite, Save and ⋯ always on screen', r['cite'] and r['save'] and r['more'])
            if w <= 600:
                d = await pg.evaluate("() => { $('#settingsDlg').showModal(); const r = $('#settingsDlg').getBoundingClientRect(); $('#settingsDlg').close(); return [r.width, r.height, innerWidth, innerHeight]; }")
                check(f'{w}px: dialogs open full screen', abs(d[0] - d[2]) <= 1 and abs(d[1] - d[3]) <= 1, d)
                fr = await pg.evaluate("() => getComputedStyle($('#page')).boxShadow")
                check(f'{w}px: the page fills the screen, no frame', fr == 'none', fr)
            if w <= 820:
                check(f'{w}px: sidebar is a drawer', r['side'] == 'fixed')
                await pg.click('#btnSide'); await pg.wait_for_timeout(300)
                opened = await pg.evaluate("() => document.body.classList.contains('side-open')")
                await pg.mouse.click(w - 8, h // 2); await pg.wait_for_timeout(300)
                check(f'{w}px: drawer opens, and a tap beside it closes it', opened and not await pg.evaluate("() => document.body.classList.contains('side-open')"))
            if w == 390:
                # reach Drafts and Record through the document ⋯ menu, Mark through the toolbar ⋯ menu if hidden
                await pg.click('#btnDocMore'); await pg.wait_for_timeout(200)
                labels = await pg.locator('#docMore [data-pbi]').all_inner_texts()
                check('phone: Drafts and Record are one tap away', any('Drafts' in x for x in labels) and any('Record' in x for x in labels), labels)
                await pg.locator('#docMore [data-pbi]', has_text='Drafts').click(); await pg.wait_for_timeout(500)
                check('phone: Drafts opens from the ⋯ menu', await pg.evaluate("() => draftsOn"))
                await pg.evaluate("() => closeDrafts()")
            await ctx.close()

        # ---- proxied buttons open their menus beside the ⋯ button
        ctx, pg = await page(600, 900, True)
        await pg.evaluate("() => { PREFS.tbHidden = ['mark', 'figure']; TB_PB.layout(); }")
        await pg.click('#btnTbMore'); await pg.locator('#tbMore [data-pbi]', has_text='Mark').click(); await pg.wait_for_timeout(250)
        r = await pg.evaluate("() => { const m = $('#markMenu').getBoundingClientRect(), b = $('#btnTbMore').getBoundingClientRect(); return { open: $('#markMenu').classList.contains('open'), near: Math.abs(m.top - b.bottom) < 12 && m.right <= innerWidth }; }")
        check('Mark opened from the ⋯ menu appears beside it', r['open'] and r['near'], r)
        await pg.keyboard.press('Escape'); await pg.mouse.click(300, 600)
        await pg.click('#btnTbMore'); await pg.locator('#tbMore [data-pbi]', has_text='Figure').click(); await pg.wait_for_timeout(250)
        check('Figure menu from the ⋯ menu stays on screen', await pg.evaluate("() => { const p = $('.fig-menu'); if (!p) return false; const r = p.getBoundingClientRect(); return r.left >= 0 && r.right <= innerWidth && r.top > 0; }"))
        await ctx.close()

        # ---- customize toolbar, shortcut sheet, writing view, sidebar toggle, undo for marks
        ctx, pg = await page(1440, 900)
        await pg.click('#btnTbMore'); await pg.locator('#tbMore button', has_text='Customize toolbar').click(); await pg.wait_for_timeout(200)
        check('customize dialog lists every toolbar button', await pg.locator('#tbcList input').count() == await pg.locator('#toolbar [data-tb]').count())
        await pg.uncheck('#tbcList input[data-tb=footnote]'); await pg.uncheck('#tbcList input[data-tb=lens]'); await pg.click('#tbcOk'); await pg.wait_for_timeout(200)
        r = await pg.evaluate("() => ({ hid: PREFS.tbHidden, vis: !!$('#btnFootnote').offsetParent, saved: JSON.parse(localStorage.getItem('commonplace.prefs')).tbHidden })")
        check('hidden buttons leave the toolbar and are remembered', r['hid'] == ['footnote', 'lens'] and not r['vis'] and r['saved'] == ['footnote', 'lens'], r)
        await pg.click('#btnTbMore'); items = await pg.locator('#tbMore [data-pbi]').all_inner_texts()
        check('…and wait in the ⋯ menu', any('Footnote' in x for x in items) and any('Revision lens' in x for x in items), items)
        await pg.locator('#tbMore [data-pbi]', has_text='Footnote').click(); await pg.wait_for_timeout(400)
        check('a hidden button still works from the menu', await pg.evaluate("() => !!document.querySelector('dialog[open]') || editor.querySelectorAll('.fn').length > 0"))
        await pg.keyboard.press('Escape')
        await pg.evaluate("() => { $$('dialog[open]').forEach(d => d.close()); PREFS.tbHidden = []; savePrefs(); TB_PB.layout(); }")
        # shortcut sheet: ? when not typing, never while typing
        await pg.evaluate("() => { document.activeElement.blur(); }"); await pg.keyboard.press('?'); await pg.wait_for_timeout(200)
        check('? opens the keyboard shortcuts', await pg.evaluate("() => $('#keysDlg').open"))
        check('shortcut sheet has every group', await pg.locator('#keysBody h4').count() == 4)
        await pg.click('#keysClose')
        await pg.evaluate("() => { const p = editor.querySelector('p'); const r = document.createRange(); r.selectNodeContents(p); r.collapse(false); const s = getSelection(); s.removeAllRanges(); s.addRange(r); editor.focus(); }")
        await pg.keyboard.type('?'); await pg.wait_for_timeout(150)
        check('typing ? in the draft types a question mark', not await pg.evaluate("() => $('#keysDlg').open") and await pg.evaluate("() => editor.querySelector('p').textContent.endsWith('?')"))
        await pg.keyboard.press('Backspace')
        # writing view outside focus mode
        await pg.click('#btnTbMore'); await pg.locator('#tbMore [data-x=tw]').click(); await pg.wait_for_timeout(100)
        await pg.click('#btnTbMore'); await pg.locator('#tbMore [data-x=dim]').click(); await pg.wait_for_timeout(100)
        await pg.evaluate("() => { const p = editor.querySelectorAll('p')[2]; const r = document.createRange(); r.setStart(p.firstChild, 3); r.collapse(true); const s = getSelection(); s.removeAllRanges(); s.addRange(r); editor.focus(); }"); await pg.wait_for_timeout(500)
        r = await pg.evaluate("() => ({ tw: document.body.classList.contains('tw-on'), dim: document.body.classList.contains('dim'), cur: editor.querySelectorAll('[data-cp-current]').length, op: getComputedStyle(editor.querySelectorAll('p')[0]).opacity, saved: (syncEditor(), curDoc().html.includes('data-cp-current')), prefs: [PREFS.twAlways, PREFS.dimAlways] })")
        check('typewriter scrolling and dimming work outside focus mode', r['tw'] and r['dim'] and r['cur'] == 1 and float(r['op']) < 0.6 and r['prefs'] == [True, True], r)
        check('the current-paragraph mark never reaches the saved file', not r['saved'])
        await pg.click('#btnTbMore'); await pg.locator('#tbMore [data-x=tw]').click(); await pg.click('#btnTbMore'); await pg.locator('#tbMore [data-x=dim]').click(); await pg.wait_for_timeout(150)
        check('…and turn off again', await pg.evaluate("() => !document.body.classList.contains('dim') && !document.body.classList.contains('tw-on') && !editor.querySelector('[data-cp-current]')"))
        # sidebar toggle on a wide screen
        await pg.click('#btnSide'); await pg.wait_for_timeout(200)
        r = await pg.evaluate("() => ({ gone: getComputedStyle($('#sidebar')).display === 'none', pref: PREFS.sideHidden, tb: $('#toolbar').clientWidth })")
        await pg.click('#btnSide'); await pg.wait_for_timeout(200)
        check('the sidebar can be put away and brought back', r['gone'] and r['pref'] is True and await pg.evaluate("() => getComputedStyle($('#sidebar')).display !== 'none' && !PREFS.sideHidden"), r)
        # undo for marks
        sel = """([i, a, z]) => { const p = editor.querySelectorAll('p')[i]; const w = document.createTreeWalker(p, NodeFilter.SHOW_TEXT); const ns = []; let n; while ((n = w.nextNode())) if (!n.parentElement.closest('.cite,.fn')) ns.push(n);
          const at = o => { for (const x of ns) { if (o <= x.data.length) return [x, o]; o -= x.data.length; } };
          const [sn, so] = at(a), [en, eo] = at(z); const r = document.createRange(); r.setStart(sn, so); r.setEnd(en, eo); const s = getSelection(); s.removeAllRanges(); s.addRange(r); savedRange = r.cloneRange(); editor.focus(); }"""
        html0 = await pg.evaluate("() => (syncEditor(), curDoc().html)")
        await pg.evaluate(sel, [0, 0, 30]); await pg.evaluate("() => markClaim()"); await pg.wait_for_timeout(200)
        check('toast offers Undo after marking', await pg.locator('#toast .toast-act').count() == 1)
        await pg.keyboard.press(f'{MOD}+z'); await pg.wait_for_timeout(250)
        r = await pg.evaluate("h => ({ spans: editor.querySelectorAll('.rm').length, claims: P.claims.length, same: (syncEditor(), curDoc().html === h) })", html0)
        check('⌘/Ctrl+Z takes a claim mark back, text and register', r == {'spans': 0, 'claims': 0, 'same': True}, r)
        await pg.keyboard.press(f'{MOD}+Shift+z'); await pg.wait_for_timeout(250)
        check('⌘/Ctrl+Shift+Z puts it back', await pg.evaluate("() => editor.querySelectorAll('.rm[data-k=cl]').length > 0 && P.claims.length === 1"))
        await pg.evaluate("() => removeMark('cl', P.claims[0].id)"); await pg.wait_for_timeout(200)
        await pg.click('#toast .toast-act'); await pg.wait_for_timeout(250)
        check('the toast’s Undo brings back a removed mark', await pg.evaluate("() => editor.querySelectorAll('.rm[data-k=cl]').length > 0 && P.claims.length === 1"))
        await pg.evaluate("() => $('#toolbar [data-cmd=undo]').click()"); await pg.wait_for_timeout(250)
        check('the toolbar Undo button undoes marks too', await pg.evaluate("() => !editor.querySelector('.rm[data-k=cl]') && P.claims.length === 0"))
        # a thread with two passages, deleted and undeleted in one step
        await pg.evaluate(sel, [1, 0, 20]); await pg.evaluate("() => { const t = newThread('Undo me'); thRange = savedRange.cloneRange(); thAddTo(t.id); }"); await pg.wait_for_timeout(200)
        await pg.evaluate(sel, [2, 0, 20]); await pg.evaluate("() => { thRange = savedRange.cloneRange(); thAddTo(P.threads[0].id); }"); await pg.wait_for_timeout(200)
        await pg.evaluate("() => { const t = P.threads[0]; rmOp('delete a thread', () => { rmAll('th').filter(p => p.ref === t.id).forEach(p => removeMark('th', p.pid, true)); P.threads = P.threads.filter(x => x.id !== t.id); }); rmRefresh(); }")
        gone = await pg.evaluate("() => P.threads.length === 0 && !editor.querySelector('.rm')")
        await pg.keyboard.press(f'{MOD}+z'); await pg.wait_for_timeout(250)
        check('deleting a whole thread is one undo', gone and await pg.evaluate("() => P.threads.length === 1 && rmAll('th').length === 2"))
        # typing after a mark: undo goes to the typing first (the browser’s own history)
        await pg.evaluate(sel, [3, 0, 10]); await pg.evaluate("() => markClaim()"); await pg.wait_for_timeout(200)
        await pg.evaluate("() => { const p = editor.querySelectorAll('p')[3]; const r = document.createRange(); r.selectNodeContents(p); r.collapse(false); const s = getSelection(); s.removeAllRanges(); s.addRange(r); editor.focus(); }")
        await pg.keyboard.type(' xyz'); await pg.wait_for_timeout(500)
        check('after typing, the mark can’t be undone out from under the new text', not await pg.evaluate("() => rmCanUndo()"))
        await ctx.close()

        # ---- installable hosted copy
        subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'site', 'build_site.py')], check=True, capture_output=True)
        srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Quiet, directory=os.path.join(ROOT, 'site')))
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        site = f'http://127.0.0.1:{srv.server_address[1]}/'
        ctx = await b.new_context(viewport={'width': 1200, 'height': 800})
        await ctx.add_init_script("localStorage.setItem('commonplace.prefs',JSON.stringify({startHome:false,toured:true,seenVersion:'99.0.0'}))")
        pg = await ctx.new_page(); pg.on('pageerror', lambda e: errs.append(f'site: {e}'))
        await pg.goto(site); await pg.wait_for_timeout(1500)
        await pg.evaluate("() => navigator.serviceWorker.ready"); await pg.wait_for_timeout(300)
        r = await pg.evaluate("() => ({ man: !!document.querySelector('link[rel=manifest]'), inst: document.documentElement.classList.contains('installable') })")
        mf = await (await pg.request.get(site + 'manifest.webmanifest')).json()
        check('hosted copy links a manifest and registers its service worker', r['man'] and r['inst'], r)
        check('manifest: standalone app with maskable icon', isinstance(mf, dict) and mf.get('display') == 'standalone' and any(i.get('purpose') == 'maskable' for i in mf.get('icons', [])), mf)
        await pg.reload(); await pg.wait_for_timeout(1200)
        check('service worker controls the page after a reload', await pg.evaluate("() => !!navigator.serviceWorker.controller"))
        await ctx.set_offline(True)
        await pg.reload(); await pg.wait_for_timeout(1800)
        check('the installed app opens offline', await pg.evaluate("() => typeof APP_VERSION === 'string' && !!document.querySelector('#editor')"))
        await ctx.set_offline(False); await ctx.close(); srv.shutdown()
        # the downloaded file: none of that
        ctx, pg = await page(1200, 800)
        check('opened as a file: no manifest, no service worker', await pg.evaluate("() => !document.querySelector('link[rel=manifest]') && !document.documentElement.classList.contains('installable')"))
        await ctx.close()
        await b.close()
    errs = [e for e in errs if 'net::ERR_INTERNET_DISCONNECTED' not in e]
    print('ERRS', errs)
    return ok and not errs

if __name__ == '__main__':
    sys.exit(0 if asyncio.run(main()) else 1)
