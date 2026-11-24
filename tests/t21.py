import asyncio, json
from playwright.async_api import async_playwright
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from env import URL, HTTP, OUT, FX, AXE
URL=URL
P1='<h2>The raid</h2><p>On the morning of October 1, agents waited in the science fiction section of the Glen Park library.</p><p>Ulbricht sat down at a table near the window and opened his laptop to work on the site.</p><p>The arrest itself took less than a minute, and the laptop never closed.</p><p>Investigators later said the open laptop was the whole case.</p><p>It was the end of a two-year hunt.</p><p>A sixth paragraph that stays the same throughout.</p><p>A seventh paragraph that stays the same as well.</p><p>An eighth paragraph that also stays.</p>'
async def m():
  async with async_playwright() as p:
    b=await p.chromium.launch()
    ctx=await b.new_context(viewport={'width':1440,'height':900}, accept_downloads=True)
    await ctx.add_init_script("delete window.showSaveFilePicker; localStorage.setItem('commonplace.prefs',JSON.stringify({startHome:false,seenVersion:'99.0.0'}))")
    pg=await ctx.new_page(); errs=[]
    pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('console', lambda m: errs.append('console:'+m.text) if m.type=='error' else None)
    await pg.goto(URL); await pg.wait_for_timeout(1200)
    await pg.evaluate(f"addDoc(newDoc('Library arrest', {json.dumps(P1)}))"); await pg.wait_for_timeout(300)
    print('button before:', await pg.inner_text('#btnVersions'))
    # Draft 1 via keyboard shortcut with a note
    await pg.click('#editor p >> nth=0'); await pg.keyboard.press('Control+Alt+KeyD'); await pg.wait_for_timeout(200)
    print('save dlg:', await pg.evaluate("$('#sdDlg').open"), '| info:', await pg.inner_text('#sdInfo'), '| placeholder:', await pg.get_attribute('#sdName','placeholder'))
    await pg.fill('#sdNote','First full pass, before the editor read it'); await pg.press('#sdName','Enter'); await pg.wait_for_timeout(200)
    print('button after:', await pg.inner_text('#btnVersions'))
    # revise: rewrite p2, cut p3, add a new one, move p1 to the end
    await pg.evaluate("""(()=>{const ps=$$('#editor > p');
      ps[1].textContent='Ulbricht chose a table by the window, opened his laptop, and logged in as the site’s administrator.';
      ps[2].remove();
      const n=document.createElement('p'); n.textContent='A librarian later said she had noticed nothing unusual that morning at all.'; ps[4].after(n);
      editor.append(ps[0]);
      onEdit(); syncEditor();})()""")
    await pg.click('#btnVersions'); await pg.wait_for_timeout(400)
    print('drafts open:', await pg.evaluate("draftsOn"), '| head:', await pg.inner_text('#dfHead'))
    print('left/right:', await pg.evaluate("[$('#dfL').selectedOptions[0].text, $('#dfR').selectedOptions[0].text]"))
    print('summary:', (await pg.inner_text('#dfSum')).replace('\n',' '))
    rows = await pg.evaluate("dfRows.map(r=>r.t)")
    print('rows:', rows)
    print('chg diff:', await pg.evaluate("(()=>{const r=$('#dfGrid .df-row.chg'); return r ? [r.querySelectorAll('del').length, r.querySelectorAll('ins').length] : null})()"))
    print('folds:', await pg.evaluate("$$('#dfGrid .df-fold').map(f=>f.textContent)"))
    await pg.click('#dfNext'); await pg.click('#dfNext'); print('nav:', await pg.inner_text('#dfPos'))
    await pg.keyboard.press('j'); print('nav j:', await pg.inner_text('#dfPos'))
    await pg.screenshot(path='d1-light.png')
    # take actions
    await pg.evaluate("$$('.df-take').forEach(b=>b.style.opacity=1)")
    await pg.click('.df-row.del .df-take'); await pg.wait_for_timeout(300)
    print('after put back:', await pg.evaluate("(()=>({rows:dfRows.map(r=>r.t), safety:curDoc().snapshots.filter(v=>v.kind==='safety').map(v=>v.name), hasArrest:curDoc().html.includes('less than a minute')}))()"))
    await pg.evaluate("$$('.df-take').forEach(b=>b.style.opacity=1)")
    await pg.click('.df-row.chg .df-take'); await pg.wait_for_timeout(300)
    await pg.evaluate("$$('.df-take').forEach(b=>b.style.opacity=1)")
    await pg.click('.df-row.add .df-take'); await pg.wait_for_timeout(300)
    print('after use+remove:', await pg.evaluate("({rows:dfRows.map(r=>r.t), safety:curDoc().snapshots.filter(v=>v.kind==='safety').length, librarian:curDoc().html.includes('librarian'), window:curDoc().html.includes('near the window')})"))
    # Draft 2 from the button, then compare Draft 1 vs Draft 2
    await pg.click('#dfSave'); await pg.fill('#sdName','After editor notes'); await pg.click('#sdOk'); await pg.wait_for_timeout(300)
    print('rail:', await pg.evaluate("$$('#dfRail .df-item').map(li=>li.querySelector('.df-it-head').textContent.trim().replace(/\\s+/g,' '))"))
    # undo everything with Restore Draft 1
    await pg.click('#dfRail .df-list > .df-item:nth-child(2)'); await pg.wait_for_timeout(200)
    await pg.click('#dfRail .df-item.on [data-a=restore]'); await pg.click('#askOk'); await pg.wait_for_timeout(400)
    print('restored == draft1:', await pg.evaluate("(()=>{const d=curDoc(); const v=d.snapshots.find(v=>v.n===1); return d.html===v.html})()"), '| editor matches:', await pg.evaluate("editor.innerHTML.includes('less than a minute')"))
    # copy to new doc
    await pg.click('#dfRail .df-item.on [data-a=copy]'); await pg.wait_for_timeout(300)
    print('copy:', await pg.evaluate("[curDoc().title, draftsOn, P.docs.length]"))
    # compare against another document
    await pg.evaluate("openDoc(P.docs.find(d=>d.title==='Library arrest').id)"); await pg.click('#btnVersions'); await pg.wait_for_timeout(300)
    await pg.select_option('#dfR', label='Library arrest (Draft 1)'); await pg.wait_for_timeout(300)
    print('vs other doc:', (await pg.inner_text('#dfSum')).replace('\n',' '), '| take buttons:', await pg.evaluate("$$('.df-take').length"))
    await pg.select_option('#dfR', value='current'); await pg.wait_for_timeout(200)
    # download
    async with pg.expect_download() as dl: await pg.click('#dfDl')
    d=await dl.value; path=OUT + '/compare.html'; await d.save_as(path); h=open(path).read()
    print('download:', d.suggested_filename, '| rows:', h.count('class="df-row'), '| buttons left:', h.count('<button'))
    # show unchanged
    await pg.check('#dfAll'); print('all rows shown:', await pg.evaluate("$$('#dfGrid .df-row').length === dfRows.length"))
    await pg.uncheck('#dfAll')
    # persistence & migration of old versions
    await pg.evaluate("persistLocal()"); await pg.wait_for_timeout(400); await pg.reload(); await pg.wait_for_timeout(1300)
    print('after reload:', await pg.evaluate("(()=>{const d=P.docs.find(d=>d.title==='Library arrest'); return d.snapshots.map(v=>v.kind+':'+(v.n||'')+':'+v.name)})()"))
    mig = await pg.evaluate("""(()=>{const x=normalize({docs:[{id:'d1',title:'Old',html:'<p>a</p>',snapshots:[{id:'v3',name:'Before restoring “Sent”',date:'2026-01-03',html:'<p>c</p>',words:1},{id:'v2',name:'Sent to editor',date:'2026-01-02',html:'<p>b</p>',words:1},{id:'v1',name:'First',date:'2026-01-01',html:'<p>a</p>',words:1}]}],notes:[],sources:[]}); return x.docs[0].snapshots.map(v=>v.kind+':'+(v.n||'')+':'+v.name)})()""")
    print('migration:', mig)
    # dark + phone screenshots
    await pg.evaluate("openDoc(P.docs.find(d=>d.title==='Library arrest').id); document.documentElement.dataset.theme='dark'; openDrafts()"); await pg.wait_for_timeout(400)
    await pg.evaluate("(()=>{const d=curDoc(); dfLeft='v:'+d.snapshots.find(v=>v.n===2).id; dfRight='v:'+d.snapshots.find(v=>v.n===1).id; renderDrafts();})()"); await pg.wait_for_timeout(300)
    await pg.screenshot(path='d2-dark.png')
    await pg.set_viewport_size({'width':390,'height':844}); await pg.wait_for_timeout(400); await pg.screenshot(path='d3-phone.png')
    print('ERRS', [e for e in errs if 'Failed to load resource' not in e])
    await b.close()
asyncio.run(m())
