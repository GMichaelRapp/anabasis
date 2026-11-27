"""2.10.2 security: Trusted Types and the strict script policy, Work offline, the idle lock and password checks,
encrypted PDFs, photos and GitHub token in a locked project, the public-repository guard, photos without their
metadata, saved pages with their own policy, and refusing to run inside another site's page."""
import asyncio, base64, io, json, re
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from env import URL, HTTP
from playwright.async_api import async_playwright


def jpeg(orientation=1):
    from PIL import Image
    im = Image.new('RGB', (60, 40), (180, 40, 40)); ex = Image.Exif()
    ex[0x010F] = 'CameraCo'; ex[0x0110] = 'Model X'; ex[0x0112] = orientation; ex[0x8825] = {1: 'N', 2: (35.0, 10.0, 5.0), 3: 'W', 4: (103.0, 12.0, 1.0)}
    b = io.BytesIO(); im.save(b, 'JPEG', exif=ex.tobytes(), comment=b'secret comment'); return 'data:image/jpeg;base64,' + base64.b64encode(b.getvalue()).decode()


async def main():
    ok = True
    def check(name, cond, extra=''):
        nonlocal ok
        print(('PASS ' if cond else 'FAIL ') + name, extra if not cond else ''); ok = ok and bool(cond)
    errs, gh = [], []
    async with async_playwright() as pw:
        b = await pw.chromium.launch()
        ctx = await b.new_context(viewport={'width': 1440, 'height': 900})
        await ctx.add_init_script("delete window.showSaveFilePicker; localStorage.setItem('commonplace.prefs',JSON.stringify({startHome:false,toured:true,seenVersion:'99.0.0'}))")
        pg = await ctx.new_page(); pg.on('pageerror', lambda e: errs.append(str(e)[:200]))
        async def github(r):
            gh.append(r.request.method + ' ' + r.request.url)
            if r.request.url.rstrip('/').endswith('/repos/someone/public-notes'):
                await r.fulfill(status=200, headers={'access-control-allow-origin': '*', 'content-type': 'application/json'}, body=json.dumps({'full_name': 'someone/public-notes', 'private': False, 'permissions': {'push': True}}))
            else: await r.fulfill(status=500, headers={'access-control-allow-origin': '*'}, body='{}')
        await ctx.route('https://api.github.com/**', github)
        await pg.goto(URL); await pg.wait_for_timeout(1200)

        # ---- the page itself: only its own scripts, and nothing written in as HTML can carry one
        r = await pg.evaluate("""(() => { const out = {};
          const s = document.createElement('script'); try { s.textContent = 'window.RAN1 = 1'; document.head.appendChild(s); } catch (e) { out.text = 'refused'; }
          const d = document.createElement('div'); d.innerHTML = '<img src="data:image/png;base64,iVBORw0KGgo=" onerror="window.RAN2=1"><a href="javascript:window.RAN3=1">x</a><b data-ch=" ">kept</b>';
          out.markup = [d.querySelector('img').hasAttribute('onerror'), d.querySelector('a').hasAttribute('href'), d.querySelector('b').dataset.ch];
          try { setTimeout('window.RAN4 = 1', 0); } catch (e) { out.timer = 'refused'; }
          out.csp = document.querySelector('meta[http-equiv=Content-Security-Policy]').content;
          return out; })()""")
        await pg.wait_for_timeout(300)
        ran = await pg.evaluate("[window.RAN1, window.RAN2, window.RAN3, window.RAN4]")
        check('a script made from text is refused', r.get('text') == 'refused' and ran[0] is None, r)
        check('HTML written into the page loses handlers and javascript: links, keeps spaces in data', r['markup'] == [False, False, ' '], r['markup'])
        # eval and Function, tried from code the page itself runs (a blob: script, the one kind it may make)
        fn = await pg.evaluate("""() => new Promise(res => { window.FN = null; const s = document.createElement('script');
          s.src = URL.createObjectURL(new Blob(["try { new Function('return 1')(); window.FN = 'ran'; } catch (e) { window.FN = 'refused'; } try { eval('1'); window.EV = 'ran'; } catch (e) { window.EV = 'refused'; }"], { type: 'text/javascript' }));
          s.onload = () => res([window.FN, window.EV]); document.head.appendChild(s); })""")
        check('timers, eval and Function from strings are refused', r.get('timer') == 'refused' and ran[3] is None and fn == ['refused', 'refused'], [r.get('timer'), fn])
        check('the policy pins scripts by hash, with no unsafe-inline', "'unsafe-inline'" not in r['csp'].split('style-src')[0] and r['csp'].count("'sha256-") >= 3 and 'require-trusted-types-for' in r['csp'], r['csp'][:200])
        check('nothing ran', ran == [None, None, None, None], ran)

        # ---- password strength
        r = await pg.evaluate("[pwWeak('short'), pwWeak('password123'), pwWeak('aaaaaaaaaaaa'), pwWeak('correct horse battery')]")
        check('weak passwords are refused with a reason, a phrase passes', r[0] and r[1] and r[2] and r[3] == '', r)

        # ---- lock the project; stored files, the token and the idle lock
        await pg.evaluate("""async () => { const salt = crypto.getRandomValues(new Uint8Array(16)); LOCK = { key: await deriveKey('correct horse battery', salt), salt, iter: ITER }; document.body.classList.add('locked');
          P.sources.push({ id: 'srcx', csl: { title: 'A source' }, photos: [] }); }""")
        r = await pg.evaluate("""async () => {
          await pdfStore.set('srcx', { name: 'secret-report.pdf', buf: new Uint8Array([37, 80, 68, 70, 1, 2, 3]).buffer, kind: 'pdf' });
          const raw = await idbReq('readonly', st => st.get('pdf:srcx'));
          const back = await pdfStore.get('srcx');
          const k = LOCK; LOCK = null; const without = await pdfStore.get('srcx'); LOCK = k;
          await resealStored(LOCK.key, null); const plain = await idbReq('readonly', st => st.get('pdf:srcx'));
          await resealStored(null, LOCK.key); const again = await idbReq('readonly', st => st.get('pdf:srcx'));
          return { sealed: raw.sealed === 1 && !JSON.stringify(raw).includes('secret-report'), back: back && back.name === 'secret-report.pdf' && new Uint8Array(back.buf)[1] === 80,
                   without, plain: !plain.sealed && plain.name === 'secret-report.pdf', again: again.sealed === 1 }; }""")
        check('a PDF stored for a locked project is encrypted, name and all', r['sealed'], r)
        check('…opens while the project is unlocked', r['back'], r)
        check('…and not without its key', r['without'] is None, r)
        check('taking the lock off decrypts it; locking again encrypts it', r['plain'] and r['again'], r)
        r = await pg.evaluate("""async () => { ghCfg().remember = true; ghTokenMem = 'github_pat_TESTTOKEN'; await ghStoreToken('github_pat_TESTTOKEN');
          const plain = localStorage.getItem(GH_TOKEN_KEY), sealed = localStorage.getItem(ghSealKey());
          ghTokenMem = ''; await ghUnsealToken(); return { plain, sealed: !!sealed && !sealed.includes('TESTTOKEN'), back: ghTokenMem }; }""")
        check('a remembered token is encrypted with the locked project, and comes back on unlock', r['plain'] is None and r['sealed'] and r['back'] == 'github_pat_TESTTOKEN', r)

        await pg.evaluate("() => { idleLockNow('Locked for the test.'); }"); await pg.wait_for_timeout(300)
        r = await pg.evaluate("({ hid: document.body.classList.contains('idle-locked'), dlg: $('#pwDlg').open, cancel: !$('#pwCancel').classList.contains('hidden'), vis: getComputedStyle($('#editor')).visibility, title: document.title })")
        check('stepping away hides the project behind the password', r['hid'] and r['dlg'] and not r['cancel'] and r['vis'] == 'hidden' and r['title'] == 'Anabasis (locked)', r)
        await pg.keyboard.press('Escape'); await pg.wait_for_timeout(200)
        check('…Escape doesn’t get past it', await pg.evaluate("$('#pwDlg').open && document.body.classList.contains('idle-locked')"))
        await pg.fill('#pw1', 'not the password'); await pg.click('#pwOk'); await pg.wait_for_timeout(1500)
        check('…nor a wrong password', await pg.evaluate("$('#pwDlg').open && document.body.classList.contains('idle-locked')"), await pg.inner_text('#pwMsg'))
        await pg.fill('#pw1', 'correct horse battery'); await pg.click('#pwOk'); await pg.wait_for_timeout(1500)
        check('…the right one brings it back', await pg.evaluate("!$('#pwDlg').open && !document.body.classList.contains('idle-locked') && getComputedStyle($('#editor')).visibility === 'visible'"))
        check('the lock settings offer the time and Lock now', await pg.evaluate("(() => { openLockSettings(); const v = $('#lockIdle').value; $('#lockDlg').close(); return v === '15' && !!$('#lockNow'); })()"))

        # ---- Work offline
        r = await pg.evaluate("""async () => { PREFS.offline = true; let e1 = ''; try { await netFetch('https://doi.org/10.1000/x'); } catch (e) { e1 = e.message; }
          const n = performance.getEntriesByType('resource').filter(x => /doi\\.org/.test(x.name)).length; PREFS.offline = false; return { e1, n }; }""")
        check('Work offline: nothing goes online, with a reason', 'offline' in r['e1'] and r['n'] == 0, r)
        check('Work offline is in Settings', await pg.evaluate("!!$('#stOffline')"))

        # ---- GitHub: a public repository
        gh.clear()
        r = await pg.evaluate("""async () => { LOCK = null; ghCfg().repo = 'someone/public-notes'; ghTokenMem = 'github_pat_X'; try { await ghBackup(false); } catch (e) {} return $('#ghStatus') ? $('#ghStatus').textContent : ''; }""")
        check('an automatic backup never goes to a public repository', 'public' in r and not [x for x in gh if x.startswith(('PUT', 'POST', 'PATCH'))], [r, gh])
        await pg.evaluate("() => { window.BK = ghBackup(true).catch(e => 'ERR ' + e.message); }")
        try: await pg.wait_for_function("() => $('#askDlg').open", timeout=5000)
        except Exception: pass
        asked = await pg.evaluate("$('#askDlg').open ? $('#askTitle').textContent : ($('#ghStatus') || {}).textContent")
        if await pg.evaluate("$('#askDlg').open"): await pg.click('#askCancel')
        await pg.evaluate("window.BK")
        check('a manual one asks first, and stops if you say no', asked == 'This repository is public' and not [x for x in gh if x.startswith(('PUT', 'POST', 'PATCH'))], [asked, gh])

        # ---- pictures lose their metadata
        for o, label in [(1, 'kept as it was'), (6, 'redrawn upright')]:
            src = jpeg(o)
            r = await pg.evaluate("""async src => { const r = await normalizeImage(src, 'image/jpeg', src.length * 0.75); const bin = atob(r.data.split(',')[1]);
              return { exif: bin.includes('Exif'), cam: bin.includes('CameraCo'), note: bin.includes('secret comment'), w: r.w, h: r.h }; }""", src)
            check(f'a photo loses its GPS, camera and comment ({label})', not r['exif'] and not r['cam'] and not r['note'], r)
        check('…and a turned one comes out upright', r['w'] == 40 and r['h'] == 60, r)

        # ---- saved pages carry their own policy, and their own scripts still run
        html = await pg.evaluate("pageCSP('<!DOCTYPE html><html><head><title>t</title></head><body><p id=p>x</p><img src=x onerror=\"document.title=\\'bad\\'\"><script>document.getElementById(\\'p\\').textContent=\\'ran\\'</script></body></html>')")
        p2 = await ctx.new_page(); await p2.set_content(html); await p2.wait_for_timeout(400)
        r = await p2.evaluate("({ p: document.getElementById('p').textContent, title: document.title })")
        check('a saved page runs its own script and nothing else', r == {'p': 'ran', 'title': 't'}, r)
        await p2.close()
        dash = await pg.evaluate("pageCSP('<!DOCTYPE html><html><head></head><body><iframe src=\"https://www.youtube-nocookie.com/embed/abcdefghijk\"></iframe></body></html>')")
        check('a dashboard with a video tile may frame that player only', "frame-src https://www.youtube-nocookie.com;" in dash and 'vimeo' not in dash, dash[:300])

        # ---- not inside another site's page
        if HTTP.startswith('http'):
            p3 = await ctx.new_page()
            await p3.set_content(f'<iframe src="{HTTP}anabasis.html" width="800" height="600"></iframe>'); await p3.wait_for_timeout(3000)
            fr = [f for f in p3.frames if 'anabasis.html' in f.url]
            r = await fr[0].evaluate("getComputedStyle(document.documentElement).display") if fr else 'navigated'
            check('framed by another site, Anabasis shows nothing (or takes the whole window)', r in ('none', 'navigated') and (fr or p3.url.startswith(HTTP)), [r, p3.url])
            await p3.close()
        await b.close()
    print('ERRS', json.dumps(errs))
    _sys.exit(0 if ok and not errs else 1)

asyncio.run(main())
