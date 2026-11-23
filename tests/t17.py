import asyncio, json
from playwright.async_api import async_playwright
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from env import URL, HTTP, OUT, FX, AXE
APP=HTTP + 'anabasis.html'
async def main():
  async with async_playwright() as p:
    b=await p.chromium.launch()
    pg=await b.new_page(viewport={'width':1500,'height':920}); errs=[]
    await pg.add_init_script("try{if(!localStorage.getItem('commonplace.prefs'))localStorage.setItem('commonplace.prefs',JSON.stringify({startHome:false}))}catch(e){}")
    pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('console', lambda m: errs.append(m.text) if m.type=='error' else None)
    await pg.goto(APP); await pg.wait_for_timeout(700)
    titles = lambda: pg.eval_on_selector_all('#plArea .pl-row','e=>e.map(r=>"  ".repeat(+r.style.getPropertyValue("--d"))+r.querySelector(".pl-title").value)')
    await pg.click('#btnPlan'); await pg.wait_for_timeout(200)
    print('empty:', (await pg.inner_text('#plArea'))[:60])
    # keyboard outlining
    await pg.click('#plAdd'); await pg.keyboard.type('Introduction'); await pg.keyboard.press('Enter'); await pg.keyboard.type('Chapter 1: The march inland')
    await pg.keyboard.press('Enter'); await pg.keyboard.press('Tab'); await pg.keyboard.type('Patronage networks'); await pg.keyboard.press('Enter'); await pg.keyboard.type('Violence as a business')
    await pg.keyboard.press('Enter'); await pg.keyboard.press('Enter'); await pg.keyboard.type('Chapter 2: Proxies')  # empty Enter → outdent
    await pg.keyboard.press('Enter'); await pg.keyboard.type('temp'); await pg.keyboard.press('Control+a'); await pg.keyboard.press('Backspace'); await pg.keyboard.press('Backspace')  # delete empty
    print('outline:', await titles())
    await pg.click('#plArea .pl-row:has(input[value="Violence as a business"]) .pl-title'); await pg.keyboard.press('Alt+ArrowUp'); await pg.wait_for_timeout(100)
    print('after alt-up:', await titles())
    await pg.click('#plArea .pl-row:has(input[value="Chapter 1: The march inland"]) .pl-title'); await pg.keyboard.press('Control+.'); await pg.wait_for_timeout(100)
    print('folded:', await titles())
    await pg.keyboard.press('Control+.')
    # template inside Chapter 2
    await pg.click('#plArea .pl-row:has(input[value="Chapter 2: Proxies"]) .pl-title')
    await pg.click('#plTemplates'); await pg.check('#ptInside'); await pg.click('#ptList [data-pt="Argument essay"]'); await pg.wait_for_timeout(200)
    print('rows after template:', len(await titles()))
    # panel: synopsis, target, link note
    await pg.click('#plArea .pl-row:has(input[value="Chapter 1: The march inland"]) .pl-title'); await pg.wait_for_timeout(100)
    await pg.fill('#panelBody [data-p=synopsis]','Show how autocrats run states like criminal enterprises.'); await pg.fill('#panelBody [data-p=target]','300')
    await pg.select_option('#panelBody [data-add=note]', index=1); await pg.wait_for_timeout(200)
    print('item:', await pg.evaluate("JSON.stringify((({title,synopsis,target,notes})=>({title,synopsis,target,notes:notes.length}))(P.plan.items.find(i=>i.title.startsWith('Chapter 1'))))"))
    # drag note from notes list onto plan row
    await pg.click('.tabs button[data-tab=notes]')
    await pg.drag_and_drop('#noteList li >> nth=0', '#plArea .pl-row:has(input[value="Patronage networks"])'); await pg.wait_for_timeout(200)
    print('synthetic drop:', await pg.evaluate("""()=>{ const dt=new DataTransfer(); dt.setData('application/x-commonplace-note', P.notes[1].id); const row=[...document.querySelectorAll('#plArea .pl-row')].find(r=>r.querySelector('.pl-title').value==='Patronage networks'); const inp=row.querySelector('.pl-title'); inp.dispatchEvent(new DragEvent('dragover',{dataTransfer:dt,bubbles:true,cancelable:true})); inp.dispatchEvent(new DragEvent('drop',{dataTransfer:dt,bubbles:true,cancelable:true})); return P.plan.items.find(i=>i.title==='Patronage networks').notes.length; }"""))
    print('dropped note links:', await pg.evaluate("P.plan.items.find(i=>i.title==='Patronage networks').notes.length"))
    # grip drag: move "Introduction" inside Chapter 2 (drop on right side lower half)
    g=await pg.locator('#plArea .pl-row:has(input[value="Introduction"]) .pl-grip').bounding_box(); t=await pg.locator('#plArea .pl-row:has(input[value="Chapter 2: Proxies"])').bounding_box()
    await pg.mouse.move(g['x']+5,g['y']+5); await pg.mouse.down(); await pg.mouse.move(g['x']+5,g['y']+30, steps=4); await pg.mouse.move(t['x']+300,t['y']+t['height']-4, steps=10); await pg.mouse.up(); await pg.wait_for_timeout(200)
    print('after drag:', (await titles())[:6])
    await pg.screenshot(path='p1.png')
    # check view
    await pg.select_option('#plView','check'); await pg.wait_for_timeout(200)
    print('check:', (await pg.inner_text('#plArea')).replace('\n',' | ')[:400]); await pg.screenshot(path='p2.png')
    # cards view & hoist
    await pg.select_option('#plView','cards'); await pg.wait_for_timeout(200)
    print('cards:', await pg.eval_on_selector_all('.pl-card b','e=>e.map(x=>x.textContent)'))
    await pg.dblclick('.pl-card:has-text("Chapter 1")'); await pg.wait_for_timeout(200)
    print('hoisted crumbs:', await pg.inner_text('#plCrumbs'), '| cards:', await pg.eval_on_selector_all('.pl-card b','e=>e.map(x=>x.textContent)'))
    await pg.screenshot(path='p3.png')
    await pg.click('#plCrumbs [data-h=""]'); await pg.select_option('#plView','outline')
    # build drafts (whole plan) into new part
    await pg.click('#plBuild'); await pg.select_option('#bdScope','all'); await pg.select_option('#bdPart','__new'); await pg.click('#bdOk'); await pg.fill('#askInput','The March of the Ten Thousand'); await pg.click('#askOk'); await pg.wait_for_timeout(500)
    print('docs:', await pg.evaluate("JSON.stringify(P.docs.map(d=>[d.title,(P.parts.find(p=>p.id===d.partId)||{}).name||'',d.target]))"))
    ch1 = await pg.evaluate("P.docs.find(d=>d.title.startsWith('Chapter 1')).html")
    print('chapter 1 html:', ch1[:500])
    print('chapter 2 headings:', await pg.evaluate("(()=>{const t=document.createElement('div'); t.innerHTML=P.docs.find(d=>d.title.startsWith('Chapter 2')).html; return [...t.querySelectorAll('h2,h3')].map(h=>h.nodeName+':'+h.textContent)})()"))
    # coverage: open chapter 1 and write
    await pg.evaluate("openDoc(P.docs.find(d=>d.title.startsWith('Chapter 1')).id)"); await pg.wait_for_timeout(200)
    await pg.evaluate("""()=>{ const h=[...editor.querySelectorAll('h2')].find(x=>x.textContent==='Patronage networks'); const p=document.createElement('p'); p.textContent='Patronage binds elites to the ruler through access to rents, contracts and protection from prosecution, which is the gangster bargain in miniature.'; h.after(p); editor.dispatchEvent(new Event('input')); }"""); await pg.wait_for_timeout(600)
    await pg.click('.tabs button[data-tab=docs]'); await pg.click('#btnPlan'); await pg.wait_for_timeout(200)
    print('coverage:', await pg.eval_on_selector_all('#plArea .pl-row','e=>e.filter(r=>r.querySelector(".pl-cov")).map(r=>r.querySelector(".pl-title").value+" → "+r.querySelector(".pl-cov").textContent)'))
    await pg.screenshot(path='p4.png')
    # freewrite on an item
    await pg.click('#plArea .pl-row:has(input[value="Patronage networks"]) .pl-title'); await pg.click('#panelFoot [data-pa=fw]'); await pg.wait_for_timeout(200)
    await pg.select_option('#fwMins','5'); await pg.check('#fwStrict'); await pg.click('#fwGo'); await pg.keyboard.type('Patronage is the glue. Every ruler buys loyalty'); await pg.keyboard.press('Backspace'); await pg.keyboard.press('Backspace')
    print('fw text (strict, backspace blocked):', await pg.input_value('#fwText'), '|', await pg.inner_text('#fwStat'))
    await pg.screenshot(path='p5.png')
    await pg.click('#fwStop'); await pg.click('#fwSave'); await pg.wait_for_timeout(200)
    print('fw note:', await pg.evaluate("JSON.stringify((({title,tags,body})=>({title,tags,body:body.slice(0,60)}))(P.notes[0]))"), '| linked:', await pg.evaluate("P.plan.items.find(i=>i.title==='Patronage networks').notes.includes(P.notes[0].id)"))
    # structure editor in Outline tab
    await pg.click('#plBack'); await pg.evaluate("openDoc(P.docs.find(d=>d.title.startsWith('Chapter 2')).id)"); await pg.wait_for_timeout(300)
    await pg.click('.tabs button[data-tab=outline]'); await pg.wait_for_timeout(200)
    before = await pg.eval_on_selector_all('#outlineList li.ol-h','e=>e.map(x=>x.querySelector("span:nth-child(2)").textContent)'); print('structure:', before)
    s=await pg.locator('#outlineList li.ol-h:has-text("Conclusion") .ol-grip').bounding_box(); d=await pg.locator('#outlineList li.ol-h >> nth=0').bounding_box()
    await pg.hover('#outlineList li.ol-h:has-text("Conclusion")'); await pg.mouse.move(s['x']+4,s['y']+6); await pg.mouse.down(); await pg.mouse.move(s['x']+4,s['y']-20, steps=4); await pg.mouse.move(d['x']+60,d['y']+6, steps=10); await pg.mouse.up(); await pg.wait_for_timeout(500)
    print('after move:', await pg.eval_on_selector_all('#outlineList li.ol-h','e=>e.map(x=>x.querySelector("span:nth-child(2)").textContent)'), '| editor first h2:', await pg.evaluate("editor.querySelector('h2,h3').textContent"))
    await pg.hover('#outlineList li.ol-h:has-text("Point 1")'); await pg.click('#outlineList li.ol-h:has-text("Point 1") [data-sa=down]'); await pg.wait_for_timeout(300)
    print('demoted:', await pg.evaluate("[...editor.querySelectorAll('h2,h3')].find(h=>h.textContent==='Point 1').nodeName"))
    await pg.click('#olUndo'); await pg.wait_for_timeout(300); print('undo:', await pg.evaluate("[...editor.querySelectorAll('h2,h3')].find(h=>h.textContent==='Point 1').nodeName"))
    await pg.check('#olParas'); await pg.wait_for_timeout(200); print('reverse outline rows:', await pg.eval_on_selector_all('#outlineList li.ol-p','e=>e.length'))
    await pg.screenshot(path='p6.png')
    j=json.loads(await pg.evaluate("projectJSON()")); print('saved plan items:', len(j['plan']['items']), '| with docs:', sum(1 for i in j['plan']['items'] if i['docId']))
    print('ERRS', errs)
    await b.close()
asyncio.run(main())
