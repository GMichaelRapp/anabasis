import asyncio, json
from playwright.async_api import async_playwright
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from env import URL, HTTP, OUT, FX, AXE
URL=URL
async def m():
  async with async_playwright() as p:
    b=await p.chromium.launch()
    ctx=await b.new_context(viewport={'width':1440,'height':900}, accept_downloads=True)
    pg=await ctx.new_page(); errs=[]
    await pg.add_init_script("delete window.showSaveFilePicker; delete window.showOpenFilePicker;")
    await pg.add_init_script("try{if(!localStorage.getItem('commonplace.prefs'))localStorage.setItem('commonplace.prefs',JSON.stringify({toured:true,seenVersion:'99.0.0'}))}catch(e){}")
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.on('console', lambda m: errs.append('console:'+m.text) if m.type=='error' else None)
    await pg.goto(URL); await pg.wait_for_timeout(1200)
    print('home on boot:', await pg.evaluate("homeOn && !document.querySelector('#home').classList.contains('hidden')"))
    print('next step:', await pg.inner_text('.hm-next span'))
    await pg.screenshot(path='h1-sample.png', full_page=False)
    # resume -> draft, brand -> home
    await pg.click('#hmResume'); await pg.wait_for_timeout(300)
    print('after resume homeOn:', await pg.evaluate('homeOn'), 'editor visible:', await pg.is_visible('#editor'))
    await pg.click('#btnHome'); await pg.wait_for_timeout(300)
    print('brand opens home:', await pg.evaluate('homeOn'))
    # new project: series
    await pg.click('#hmNew'); await pg.wait_for_timeout(200)
    await pg.click('#npKinds [data-k=series]')
    await pg.fill('#npTitle', 'A Four-Part Series')
    print('series defaults:', await pg.evaluate("[$('#npStyle').value, $('#npTarget').value, !!$('#npDeadline').value, $('#npPlan').checked]"))
    await pg.click('#npOk'); await pg.wait_for_timeout(400)
    if await pg.is_visible('#askDlg'):
        await pg.click('#askDlg .primary'); await pg.wait_for_timeout(400)
    st = await pg.evaluate("({title:P.title, goal:P.goal, items:P.plan.items.length, top:plKids('').map(i=>i.title), docs:P.docs.length, style:P.docs[0].style, home:homeOn})")
    print('new project:', json.dumps(st)[:400])
    print('next step:', await pg.inner_text('.hm-next span'))
    # build drafts via next-step button
    await pg.click('#hmNextBtn'); await pg.wait_for_timeout(300)
    print('build dlg open:', await pg.evaluate("$('#buildDlg').open"))
    await pg.click('#bdOk'); await pg.wait_for_timeout(500)
    print('docs after build:', await pg.evaluate("P.docs.map(d=>d.title).join(' | ')"))
    # add writing with flags and an uncited paragraph to a doc
    await pg.evaluate("""(() => { const d=P.docs.find(x=>x.title==='Part 2'); openDoc(d.id);
      editor.innerHTML += '<p>Ross Ulbricht ran the market under a pseudonym for years before investigators connected the handle to a real person, using a careless forum post and a Gmail address that he had left behind in the early days of the site. TK on the date.</p><p>The server was in Iceland.' + flagHTML('cite','which agency?') + '</p>';
      onEdit(); syncEditor(); })()""")
    await pg.click('#btnHome'); await pg.wait_for_timeout(400)
    groups = await pg.evaluate("[...document.querySelectorAll('.hm-group summary')].map(s=>s.textContent)")
    print('loose ends:', groups)
    # click a flag -> jumps into doc
    await pg.evaluate("document.querySelector('#hmFlags').open=true")
    await pg.click('#hmFlags li >> nth=0'); await pg.wait_for_timeout(400)
    print('jumped to:', await pg.evaluate("[curDoc().title, homeOn, !!document.querySelector('#editor .hm-flash')]"))
    # goal editing
    await pg.click('#btnHome'); await pg.wait_for_timeout(300)
    await pg.fill('#hmTarget', '10000'); await pg.press('#hmTarget', 'Tab'); await pg.wait_for_timeout(300)
    await pg.evaluate("(()=>{const d=new Date(Date.now()+10*864e5); const v=todayKey(d); const i=$('#hmDeadline'); i.value=v; i.dispatchEvent(new Event('change',{bubbles:true}));})()")
    await pg.wait_for_timeout(300)
    # fake some writing days so pace shows
    await pg.evaluate("(()=>{for(let i=1;i<6;i++){const d=new Date(Date.now()-i*864e5); P.stats.days[todayKey(d)]={a:300+i*40,n:300}} renderHome();})()")
    await pg.wait_for_timeout(300)
    print('goal:', await pg.evaluate("JSON.stringify(P.goal)"), '| pace:', await pg.inner_text('.hm-pace'))
    print('inbox count:', await pg.inner_text('.hm-card:has(h5:text("Notes inbox")) .count'))
    await pg.screenshot(path='h2-series.png', full_page=True)
    # save (download fallback) then recent list; reopen sample via file input
    async with pg.expect_download() as dl:
        await pg.click('#hmSave')
    d = await dl.value; path=OUT + '/series.json'; await d.save_as(path)
    await pg.wait_for_timeout(300)
    print('recent after save:', await pg.evaluate("recentList().then(l=>l.map(r=>r.title+'|'+r.name))"))
    # palette commands exist
    print('palette:', await pg.evaluate("palItems.length>=0 && typeof openNewProject"))
    # settings toggle off -> boot to draft
    await pg.evaluate("PREFS.startHome=false; savePrefs()")
    await pg.reload(); await pg.wait_for_timeout(1200)
    print('reload with pref off -> homeOn:', await pg.evaluate('homeOn'), 'title:', await pg.evaluate('P.title'))
    await pg.evaluate("PREFS.startHome=true; savePrefs()")
    await pg.reload(); await pg.wait_for_timeout(1200)
    print('reload with pref on -> homeOn:', await pg.evaluate('homeOn'))
    # dark mode screenshot
    await pg.evaluate("document.documentElement.dataset.theme='dark'"); await pg.wait_for_timeout(200)
    await pg.screenshot(path='h3-dark.png')
    # mobile
    mp = await ctx.new_page(); await mp.set_viewport_size({'width':390,'height':844})
    mp.on('pageerror', lambda e: errs.append('m:'+str(e)))
    await mp.goto(URL); await mp.wait_for_timeout(1200)
    print('mobile topbar scrollW:', await mp.evaluate("document.querySelector('.topbar').scrollWidth"), 'title w:', await mp.evaluate("$('#projTitle').offsetWidth"))
    await mp.screenshot(path='h4-mobile.png', full_page=False)
    print('ERRS', [e for e in errs if 'Failed to load resource' not in e])
    await b.close()
asyncio.run(m())
