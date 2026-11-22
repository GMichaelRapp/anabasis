import asyncio, json
from playwright.async_api import async_playwright
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from env import URL, HTTP, OUT, FX, AXE
APP=HTTP + 'anabasis.html'
async def main():
  async with async_playwright() as p:
    b=await p.chromium.launch()
    ctx=await b.new_context(viewport={'width':1440,'height':900})
    await ctx.add_init_script("try{if(!localStorage.getItem('commonplace.prefs'))localStorage.setItem('commonplace.prefs',JSON.stringify({startHome:false}))}catch(e){}")
    pg=await ctx.new_page(); errs=[]
    pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('console', lambda m: errs.append(m.text) if m.type=='error' else None)
    await pg.goto(APP); await pg.wait_for_timeout(700)
    # add a few notes
    await pg.evaluate("""()=>{ const mk=(t,b,tags,k)=>{const n=newNote(); Object.assign(n,{title:t,body:b,tags,kind:k}); P.notes.push(n); return n;};
      mk('Counterpoint: logistics','Russian rail logistics limited advance depth. See [[Plans outrun politics]].',['war plans'],'idea');
      mk('Force design','BTG structure lacked infantry.',['force design'],'paraphrase');
      mk('Stray thought','Compare with [[Missing card]].',[],'idea'); renderNoteList(); }""")
    await pg.click('.tabs button[data-tab=notes]'); await pg.click('#btnBoard'); await pg.wait_for_timeout(300)
    await pg.click('#bdNewPile'); await pg.fill('#askInput','Chapter 3'); await pg.click('#askOk'); await pg.wait_for_timeout(200)
    await pg.click('#bdNewPile'); await pg.fill('#askInput','Maybe'); await pg.click('#askOk'); await pg.wait_for_timeout(200)
    cols = await pg.eval_on_selector_all('.bd-col .bd-col-h b','e=>e.map(x=>x.textContent)'); print('columns:', cols)
    # drag first card of Unsorted into Chapter 3 using mouse (pointer events)
    async def drag(src, dst, dy=0):
      s=await pg.locator(src).bounding_box(); d=await pg.locator(dst).bounding_box()
      await pg.mouse.move(s['x']+40, s['y']+15); await pg.mouse.down()
      await pg.mouse.move(s['x']+60, s['y']+30, steps=3)
      await pg.mouse.move(d['x']+60, d['y']+20+dy, steps=12); await pg.wait_for_timeout(100); await pg.mouse.up(); await pg.wait_for_timeout(300)
    await drag('.bd-col[data-key=""] .card >> nth=0', '.bd-col:has-text("Chapter 3") .bd-cards')
    await drag('.bd-col[data-key=""] .card >> nth=0', '.bd-col:has-text("Chapter 3") .bd-cards', 200)
    await drag('.bd-col[data-key=""] .card >> nth=0', '.bd-col:has-text("Chapter 3") .bd-cards')  # should go to top
    c3 = await pg.eval_on_selector_all('.bd-col:has-text("Chapter 3") .card .card-title','e=>e.map(x=>x.textContent)'); print('chapter 3 order:', c3)
    print('piles in data:', await pg.evaluate("P.notes.filter(n=>n.pile).length"))
    await pg.screenshot(path='b1.png')
    # reorder within column: move last card to top
    await drag('.bd-col:has-text("Chapter 3") .card >> nth=2', '.bd-col:has-text("Chapter 3") .card >> nth=0', -15)
    print('after reorder:', await pg.eval_on_selector_all('.bd-col:has-text("Chapter 3") .card .card-title','e=>e.map(x=>x.textContent)'))
    # multi-select two cards in chapter 3 and merge
    await pg.click('.bd-col:has-text("Chapter 3") .card >> nth=0', modifiers=['Shift']); await pg.click('.bd-col:has-text("Chapter 3") .card >> nth=1', modifiers=['Shift'])
    print('sel bar:', await pg.inner_text('#bdSelN'))
    await pg.click('#bdSel .sw.c-yellow'); await pg.wait_for_timeout(200)
    print('colored:', await pg.evaluate("P.notes.filter(n=>n.color==='yellow').length"))
    print('still selected after color:', await pg.inner_text('#bdSelN'))
    n0 = await pg.evaluate("P.notes.length")
    await pg.click('#bdSel [data-b=merge]'); await pg.wait_for_timeout(200); await pg.click('#askOk'); await pg.wait_for_timeout(300)
    print('merged: notes', n0, '->', await pg.evaluate("P.notes.length"))
    await pg.screenshot(path='b2.png')
    # group by tag, drag between tags
    await pg.select_option('#bdGroup','tag'); await pg.wait_for_timeout(300)
    print('tag cols:', await pg.eval_on_selector_all('.bd-col .bd-col-h b','e=>e.map(x=>x.textContent)'))
    await drag('.bd-col[data-key="force design"] .card >> nth=0', '.bd-col[data-key="war plans"] .bd-cards')
    print('force design note tags:', await pg.evaluate("JSON.stringify(P.notes.find(n=>n.title==='Force design')?.tags)"))
    # canvas
    await pg.select_option('#bdGroup','canvas'); await pg.wait_for_timeout(300)
    before = await pg.evaluate("(()=>{const n=P.notes[0]; return [n.x,n.y]})()")
    card = pg.locator(f'.canvas-in .card[data-id="{await pg.evaluate("P.notes[0].id")}"]')
    bb = await card.bounding_box(); await pg.mouse.move(bb['x']+50,bb['y']+10); await pg.mouse.down(); await pg.mouse.move(bb['x']+300,bb['y']+250, steps=10); await pg.mouse.up(); await pg.wait_for_timeout(200)
    print('canvas moved:', before, '->', await pg.evaluate("[P.notes[0].x,P.notes[0].y]"))
    await pg.screenshot(path='b3.png')
    # links & backlinks + split
    await pg.select_option('#bdGroup','pile'); await pg.wait_for_timeout(200)
    await pg.evaluate("openNote(P.notes.find(n=>n.title==='Plans outrun politics').id)"); await pg.wait_for_timeout(200)
    print('backlinks:', await pg.inner_text('#noteLinks'))
    await pg.evaluate("openNote(P.notes.find(n=>n.title==='Stray thought').id)"); await pg.wait_for_timeout(200)
    await pg.click('#noteLinks a'); await pg.wait_for_timeout(200); print('create prompt:', await pg.inner_text('#askTitle')); await pg.click('#askOk'); await pg.wait_for_timeout(200)
    print('created linked note:', await pg.evaluate("P.notes.some(n=>n.title==='Missing card')"))
    nid = await pg.evaluate("P.notes.find(n=>n.title==='Plans outrun politics').id")
    await pg.evaluate(f"openNote('{nid}')"); await pg.wait_for_timeout(100)
    await pg.evaluate("(()=>{const ta=document.querySelector('#panelBody [data-n=body]'); ta.focus(); const i=ta.value.indexOf('Mobilization'); ta.setSelectionRange(i,i);})()")
    await pg.click('#panelFoot [data-a=split]'); await pg.wait_for_timeout(300)
    print('split:', await pg.evaluate("JSON.stringify(P.notes.filter(n=>n.title.startsWith('Plans outrun')).map(n=>[n.title,n.body.slice(0,30)]))"))
    # draft from selection
    await pg.click('.card >> nth=0', modifiers=['Shift']); await pg.click('.card >> nth=1', modifiers=['Shift'])
    await pg.click('#bdSel [data-b=draft]'); await pg.wait_for_timeout(500)
    print('draft doc:', await pg.input_value('#docTitle'), '| board hidden:', await pg.is_hidden('#board'), '| cites:', await pg.eval_on_selector_all('#editor .cite','e=>e.length'))
    # drag note from sidebar into editor (HTML5 DnD)
    await pg.click('.tabs button[data-tab=notes]')
    n_before = await pg.eval_on_selector_all('#editor > *','e=>e.length')
    await pg.drag_and_drop('#noteList li >> nth=0', '#editor > * >> nth=0')
    await pg.wait_for_timeout(300)
    print('editor blocks after drop:', n_before, '->', await pg.eval_on_selector_all('#editor > *','e=>e.length'))
    # save/load roundtrip keeps piles/colors
    j = await pg.evaluate("projectJSON()"); d=json.loads(j); print('saved piles:', [x['name'] for x in d['piles']], '| colored notes:', sum(1 for n in d['notes'] if n.get('color')))
    await pg.set_viewport_size({'width':390,'height':844})
    await pg.evaluate("openBoard()"); await pg.wait_for_timeout(300); await pg.screenshot(path='b4.png')
    print('ERRS', errs)
    await b.close()
asyncio.run(main())
