import asyncio, json, re
from playwright.async_api import async_playwright
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from env import URL, HTTP, OUT, FX, AXE
URL=URL
SRT = """1
00:00:01,000 --> 00:00:04,200
<v Col. Petrenko>We moved the battery at night,

2
00:00:04,200 --> 00:00:07,000
<v Col. Petrenko>before the drones came over.

3
00:00:08,500 --> 00:00:11,000
<v Interviewer>How many times did you move it?

4
00:00:11,500 --> 00:00:15,000
<v Col. Petrenko>Every second night. Sometimes every night near Kharkiv.
"""
async def m():
  async with async_playwright() as p:
    b=await p.chromium.launch()
    ctx=await b.new_context(viewport={'width':1440,'height':900}, accept_downloads=True)
    await ctx.add_init_script("delete window.showSaveFilePicker; localStorage.setItem('commonplace.prefs',JSON.stringify({startHome:false,seenVersion:'99.0.0'}))")
    pg=await ctx.new_page(); errs=[]
    pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('console', lambda m: errs.append('console:'+m.text) if m.type=='error' else None)
    await pg.goto(URL); await pg.wait_for_timeout(1200)
    # ---------- sources with ratings, a document with citations
    await pg.evaluate("""(()=>{
      const a=addSource({type:'article-newspaper',title:'Strikes on Odesa port',author:[{family:'Kovalenko'}],issued:{'date-parts':[[2025]]}}); a.osint={rating:'B2'};
      const b=addSource({type:'webpage',title:'Telegram channel post',author:[{literal:'Rybar'}],issued:{'date-parts':[[2025]]}}); b.osint={rating:'E5'};
      const c=addSource({type:'report',title:'Black Sea assessment',author:[{family:'ISW'}],issued:{'date-parts':[[2025]]}}); c.osint={rating:'A1'};
      window.S={a:a.id,b:b.id,c:c.id};
      const ci=id=>citeHTML([{id}]);
      const html=`<h1>Ports under fire</h1><h3>Background</h3><p>Russia struck the port of Kiev twice in March, damaging 3 grain terminals and killing 5 people according to local officials and port workers. ${ci(a.id)}</p><p>A channel claimed that 40 % of the berths were out of action, a figure nobody else repeated or confirmed in the days that followed. ${ci(b.id)}</p><p>The U.S. and Britain condemned the strikes , and the navy  withdrew. ${ci(a.id)} ${ci(c.id)}</p><p>The strike came on 24 February 2025, a year after Kovalenko's first "warning" -- one the ministry ignored... ${ci(a.id)} ${ci(a.id)}</p><p>Details are <a href="https://example.org/x">here</a>.</p><figure class="tbl"><table><tbody><tr><td>Port</td><td>Berths</td></tr><tr><td>Odesa</td><td>12</td></tr></tbody></table><figcaption>Berths</figcaption></figure>`;
      addDoc(newDoc('Ports brief', html));
      const d2=newDoc('Second part', '<p>Kiev and Kharkov again. Kiev is the capital.</p>'); addDoc(d2); openDoc(P.docs.find(d=>d.title==='Ports brief').id);
    })()""")
    await pg.wait_for_timeout(500)
    await pg.evaluate("switchTab('outline'); PREFS.corrOn=true; renderCorroboration(); renderHouse(); renderA11y()"); await pg.wait_for_timeout(300)
    # ---------- 3 corroboration
    cor = await pg.evaluate("(()=>{const c=corroboration(); return {items:c.items.map(i=>i.sev+':'+i.msg), weight:c.weight.map(w=>srcShort(w.s)+' '+Math.round(w.share*100)), total:c.total, lean:!!document.querySelector('.cor-lean')}})()")
    print('corroboration:', json.dumps(cor))
    # ---------- 4 house style
    await pg.evaluate("Object.assign(hsCfg(),{numbers:'ap',percent:'word',us:'US',serial:'on',dates:'us',dash:'closed',ellipsis:'char'}); renderHouse()")
    hs = await pg.evaluate("HS.map(x=>x.rule.id+': '+x.from+' → '+x.to)")
    print('house style issues:', len(hs)); [print('   ', h) for h in hs]
    await pg.screenshot(path='y1-outline.png')
    for _ in range(14):
      lbl = await pg.evaluate("HS.length?HS[0].rule.label:null")
      if not lbl: break
      await pg.click(f'#hsList [data-hsall="{lbl}"]'); await pg.wait_for_timeout(120)
    print('after fix-all:', await pg.evaluate("HS.map(x=>x.rule.id+':'+x.from)"))
    print('text now:', (await pg.evaluate("[...editor.querySelectorAll('p')].slice(0,4).map(p=>p.textContent).join(' | ')"))[:600])
    # ---------- 10 accessibility (figure without alt)
    await pg.evaluate("""(()=>{const asset='a'+Date.now(); const c=document.createElement('canvas'); c.width=40;c.height=20; P.assets[asset]={data:c.toDataURL(),w:40,h:20,type:'image/png'}; editor.insertAdjacentHTML('beforeend',`<figure class="fig" contenteditable="false"><img data-asset="${asset}"><figcaption contenteditable="true">Figure 1. Port damage, March 2025</figcaption></figure>`); hydrateImages && hydrateImages(editor); onEdit(); renderA11y();})()""")
    print('a11y:', await pg.evaluate("A11Y.map(a=>a.msg)"))
    await pg.click('#a11yList [data-afix]'); await pg.wait_for_timeout(200)
    print('alt prefill:', await pg.input_value('#askInput')); await pg.click('#askOk'); await pg.wait_for_timeout(200)
    i = await pg.evaluate("A11Y.findIndex(a=>a.fix==='head')"); await pg.click(f'#a11yList [data-afix="{i}"]'); await pg.wait_for_timeout(200)
    print('a11y after fixes:', await pg.evaluate("A11Y.map(a=>a.msg)"), '| th:', await pg.evaluate("editor.querySelectorAll('figure.tbl th').length"))
    await pg.click('#btnExport')
    async with pg.expect_download() as dl: await pg.click('#exportMenu [data-x=html]')
    await pg.wait_for_timeout(1200); print('export toast:', await pg.evaluate("[...document.querySelectorAll('.toast')].map(t=>t.textContent).join(' / ')"))
    # ---------- 5 find & replace across documents
    await pg.evaluate("openFindAll()"); await pg.fill('#frFind','Kiev'); await pg.check('#frWord'); await pg.wait_for_timeout(400)
    print('fr:', await pg.text_content('#frSum'))
    await pg.fill('#frRepl','Kyiv'); await pg.click('#frGo'); await pg.wait_for_timeout(300)
    print('fr after:', await pg.text_content('#frSum'), '|', await pg.evaluate("P.docs.find(d=>d.title==='Second part').html"), '| safety:', await pg.evaluate("P.docs.map(d=>d.snapshots.filter(s=>s.kind==='safety').length)"))
    await pg.fill('#frFind','Khar(kov|kiv)'); await pg.check('#frRe'); await pg.fill('#frRepl','Kharkiv'); await pg.wait_for_timeout(400); print('regex:', await pg.text_content('#frSum'))
    await pg.screenshot(path='y2-find.png'); await pg.click('#frClose')
    # ---------- 6 transcript from .srt
    await pg.evaluate("openTranscript(S.a)"); await pg.wait_for_timeout(200)
    open(OUT + '/int.srt','w').write(SRT)
    await pg.set_input_files('#fileTranscript',OUT + '/int.srt'); await pg.wait_for_timeout(700)
    print('transcript text:', json.dumps(await pg.input_value('#trText')))
    print('lines:', await pg.evaluate("trLines.map(l=>l.ts+'|'+l.sp+'|'+l.text)"))
    await pg.fill('#trFind','kharkiv'); await pg.wait_for_timeout(100); print('filter:', await pg.text_content('#trFindN'))
    await pg.screenshot(path='y3-transcript.png'); await pg.click('#trClose')
    # ---------- 7 promo kit
    await pg.evaluate("editor.insertAdjacentHTML('beforeend','<h2>Why ports</h2><p>Grain exports are the economy’s lifeline and Russia knows it.</p><h2>What next</h2><p>Expect more strikes before the harvest season reaches its peak in July.</p>'); onEdit()")
    await pg.evaluate("openPromo()"); await pg.fill('#pkLink','https://example.substack.com/p/ports'); await pg.dispatch_event('#pkLink','change'); await pg.wait_for_timeout(200)
    posts = await pg.evaluate("$$('#pkPosts textarea').map(t=>t.value)"); print('thread:', len(posts), [len(x) for x in posts]); [print('   ', x) for x in posts]
    await pg.screenshot(path='y4-thread.png')
    await pg.click('#pkTabs [data-t=sub]'); print('sub:', await pg.input_value('#pkSub'), '|', await pg.text_content('#pkDescN'))
    await pg.click('#pkTabs [data-t=card]'); await pg.select_option('#pkTheme','navy'); await pg.fill('#pkHandle','globalwarning.substack.com'); await pg.wait_for_timeout(300)
    await pg.screenshot(path='y5-card.png')
    async with pg.expect_download() as dl: await pg.click('#pkDl')
    d=await dl.value; await d.save_as(OUT + '/card.png'); print('card:', d.suggested_filename)
    await pg.click('#pkClose')
    # ---------- 8 checkpoints
    await pg.evaluate("openCheckpoints()"); await pg.fill('#cpName','Before restructure'); await pg.click('#cpSave'); await pg.wait_for_timeout(400)
    await pg.click('#cpClose')
    await pg.evaluate("editor.insertAdjacentHTML('beforeend','<p>An added paragraph after the checkpoint with several new words in it.</p>'); onEdit(); addDoc(newDoc('Brand new doc','<p>Fresh.</p>')); openDoc(P.docs.find(d=>d.title==='Ports brief').id)")
    await pg.evaluate("openCheckpoints()"); await pg.wait_for_timeout(300)
    await pg.click('#cpList [data-a=cmp]'); await pg.wait_for_timeout(400)
    print('compare:', await pg.evaluate("$('#cpList .cp-diff').innerText"))
    await pg.screenshot(path='y6-checkpoints.png')
    await pg.click('#cpList [data-cmpdoc]'); await pg.wait_for_timeout(600)
    print('drafts compare:', await pg.evaluate("[dfLeft, $('#dfSum').textContent.slice(0,120)]"))
    await pg.click('#dfBack'); await pg.wait_for_timeout(300)
    await pg.evaluate("openCheckpoints()"); await pg.wait_for_timeout(300)
    await pg.click('#cpList li:not(.cp-auto) [data-a=restore]'); await pg.wait_for_timeout(200); await pg.click('#askOk'); await pg.wait_for_timeout(800)
    print('restored:', await pg.evaluate("[P.docs.map(d=>d.title), P.checkpoints.map(c=>c.name), editor.textContent.includes('An added paragraph')]"))
    # ---------- 2 charts
    await pg.evaluate("openChart()"); await pg.fill('#chData','Year\tUkraine\tRussia\tBelarus\n2013\t45\t2000\t30\n2015\t60\t2100\t28\n2018\t80\t2400\t26\n2021\t100\t2600\t25\n2024\t160\t3200\t24')
    await pg.fill('#chEvents','2014–2015 | Minsk agreements\n2022 | Full-scale invasion'); await pg.select_option('#chType','line'); await pg.wait_for_timeout(500)
    await pg.screenshot(path='y7-events.png')
    await pg.select_option('#chType','multi'); await pg.wait_for_timeout(900); await pg.screenshot(path='y8-multiples.png')
    await pg.click('#chOk'); await pg.wait_for_timeout(1200)
    print('multi figure:', await pg.evaluate("(()=>{const f=$$('figure.fig',editor).pop(); const a=P.assets[f.querySelector('img').dataset.asset]; return [a.spec.kind,a.w,a.h,Math.round(a.data.length/1024)+'KB']})()"))
    await pg.evaluate("openChart()"); await pg.fill('#chData','Month\tStrikes\nJan\t12\nFeb\t18\nMar\t31\nApr\t22\nMay\t27'); await pg.select_option('#chType','area'); await pg.fill('#chEvents','Mar | Port campaign'); await pg.wait_for_timeout(500); await pg.screenshot(path='y9-area.png'); await pg.click('#chCancel')
    # ---------- 1 & 9 maps
    await pg.evaluate("openMap()"); await pg.wait_for_timeout(500)
    await pg.check('#mpProv'); await pg.check('#mpRivers'); await pg.check('#mpRiverNames'); await pg.wait_for_timeout(600)
    await pg.click('#mpTools [data-m=shade]')
    pt = await pg.evaluate("(()=>{const q=mpProj([36.25,49.99]); const r=$('#mpStage svg').getBoundingClientRect(); return [r.left+q[0]*r.width/MP.w, r.top+q[1]*r.height/MP.h]})()")
    await pg.mouse.click(pt[0],pt[1]); await pg.wait_for_timeout(300)
    await pg.click('#mpKeys [data-k=h]')
    pt = await pg.evaluate("(()=>{const q=mpProj([34.1,45.3]); const r=$('#mpStage svg').getBoundingClientRect(); return [r.left+q[0]*r.width/MP.w, r.top+q[1]*r.height/MP.h]})()")
    await pg.mouse.click(pt[0],pt[1]); await pg.wait_for_timeout(300)
    await pg.fill('#mpSearch','zapor'); await pg.wait_for_timeout(300)
    print('search:', await pg.evaluate("$$('#mpResults button').map(b=>b.textContent)"))
    await pg.click('#mpResults [data-region]'); await pg.wait_for_timeout(300)
    print('regions:', await pg.evaluate("MP.regions"))
    print('svg:', await pg.evaluate("(()=>{const s=$('#mpStage svg'); return {regions:s.querySelectorAll('[data-r]').length, rivers:[...s.querySelectorAll('path[stroke=\"#7fa7c4\"]')].length, riverNames:[...s.querySelectorAll('text[fill=\"#3f6f93\"]')].map(t=>t.textContent), scale:[...s.querySelectorAll('text')].map(t=>t.textContent).filter(t=>/km/.test(t)), locator:!!s.querySelector('#lc')}})()"))
    await pg.screenshot(path='y10-map.png')
    await pg.evaluate("MP.view={center:[37.6,47.1],scale:9000}; mpRender()"); await pg.wait_for_timeout(300); await pg.screenshot(path='y11-mapzoom.png')
    print('zoomed scale:', await pg.evaluate("[...$('#mpStage svg').querySelectorAll('text')].map(t=>t.textContent).filter(t=>/km/.test(t))"))
    await pg.click('#mpOk'); await pg.wait_for_timeout(1500)
    print('map figure:', await pg.evaluate("(()=>{const f=$$('figure.fig',editor).pop(); const a=P.assets[f.querySelector('img').dataset.asset]; return [a.spec.type,!!a.spec.provinces,Object.keys(a.spec.regions).length,Math.round(a.data.length/1024)+'KB']})()"))
    # save & reload persists house rules and checkpoints
    print('house persists:', await pg.evaluate("JSON.parse(projectJSON()).house.us"))
    print('ERRS', errs)
    await b.close()
asyncio.run(m())
