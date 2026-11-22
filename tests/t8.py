import asyncio, json, subprocess
from playwright.async_api import async_playwright
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from env import URL, HTTP, OUT, FX, AXE
async def main():
  async with async_playwright() as p:
    b=await p.chromium.launch()
    ctx=await b.new_context(viewport={'width':1440,'height':900}, accept_downloads=True)
    await ctx.add_init_script("try{if(!localStorage.getItem('commonplace.prefs'))localStorage.setItem('commonplace.prefs',JSON.stringify({startHome:false}))}catch(e){}")
    pg=await ctx.new_page(); errs=[]
    pg.on('pageerror', lambda e: errs.append('PAGEERR '+str(e))); pg.on('console', lambda m: errs.append(m.text) if m.type=='error' else None)
    await pg.add_init_script("delete window.showSaveFilePicker; delete window.showOpenFilePicker;")
    await pg.goto(URL); await pg.wait_for_timeout(800)
    async def dl(sel, path, menu=True):
      if menu: await pg.click('#btnExport')
      async with pg.expect_download() as d: await pg.click(sel)
      f=await d.value; await f.save_as(path); return path
    # ---- flags & outline
    await pg.click('#editor p >> nth=1'); await pg.keyboard.press('End')
    await pg.keyboard.press('Control+Shift+K'); await pg.wait_for_timeout(200)
    await pg.fill('#flagNote','tonnage of Liaoning'); await pg.click('#flagOk'); await pg.wait_for_timeout(200)
    await pg.keyboard.type(' More text TK here.'); await pg.wait_for_timeout(700)
    await pg.click('.tabs button[data-tab=outline]'); await pg.wait_for_timeout(300)
    print('outline:', await pg.inner_text('#outlineList'))
    print('flags:', await pg.inner_text('#flagList'), '| badge', await pg.inner_text('#tabOutlineBadge'))
    print('uncited:', await pg.inner_text('#uncitedList'))
    await pg.check('#showUncited'); await pg.wait_for_timeout(200)
    print('marked uncited in DOM:', await pg.eval_on_selector_all('#editor [data-cp-uncited]','e=>e.length'), '| saved html has attr:', await pg.evaluate("curDoc().html.includes('data-cp')"))
    await pg.screenshot(path='n1.png')
    # ---- find & replace
    await pg.keyboard.press('Control+f'); await pg.fill('#findQ','Tuchman'); await pg.wait_for_timeout(200)
    print('find count:', await pg.inner_text('#findCount'))
    await pg.fill('#replQ','TUCHMAN'); await pg.click('#replAll'); await pg.wait_for_timeout(500)
    print('after replace, has TUCHMAN:', await pg.evaluate("editor.textContent.includes('TUCHMAN')"), await pg.inner_text('#findCount'))
    await pg.click('#editor h1'); await pg.keyboard.press('Control+z'); await pg.wait_for_timeout(400)
    print('after undo, TUCHMAN count:', await pg.evaluate("(editor.textContent.match(/TUCHMAN/g)||[]).length"))
    await pg.keyboard.press('Escape')
    # ---- palette
    await pg.keyboard.press('Control+k'); await pg.fill('#palQ','proxies'); await pg.wait_for_timeout(200)
    print('palette:', (await pg.inner_text('#palList')).replace('\n',' | ')[:300])
    await pg.screenshot(path='n2.png')
    await pg.keyboard.press('Escape')
    # ---- capture
    await pg.evaluate("""()=>{const p=[...editor.querySelectorAll('p')].find(x=>x.textContent.startsWith('Proxy')); const r=document.createRange(); r.setStart(p.firstChild,0); r.setEnd(p.firstChild,30); const s=getSelection(); s.removeAllRanges(); s.addRange(r);}""")
    await pg.keyboard.press('Control+Shift+E'); await pg.wait_for_timeout(400)
    print('captured note:', await pg.evaluate("JSON.stringify((({title,body,kind,sourceId,locator,tags})=>({title,body,kind,src:!!sourceId,locator,tags}))(P.notes[0]))"))
    # ---- binder
    await pg.click('.tabs button[data-tab=docs]')
    await pg.click('#btnNewPart'); await pg.fill('#askInput','Part I: Proxies'); await pg.click('#askOk')
    await pg.click('#btnNewDoc'); await pg.fill('#docTitle','Chapter 2'); 
    await pg.evaluate("""()=>{ editor.innerHTML='<p>Second chapter cites Tuchman again.'+citeHTML([{id:P.sources[0].id,locator:'50'}])+' And Mumford.'+citeHTML([{id:P.sources[1].id,locator:'44'}])+'</p>'; editor.dispatchEvent(new Event('input')); }""")
    await pg.wait_for_timeout(600)
    pid = await pg.evaluate("P.parts[0].id")
    for t in ['Welcome','Chapter 2']:
      li = pg.locator(f'#docList li.doc:has-text("{t}")'); await li.hover(); await li.locator('[data-a=move]').click(); await pg.fill('#askInput','Part I: Proxies'); await pg.click('#askOk'); await pg.wait_for_timeout(200)
    print('binder:', (await pg.inner_text('#docList')).replace('\n',' | '))
    # reorder via drag: drag Chapter 2 before Welcome
    await pg.drag_and_drop('#docList li.doc:has-text("Chapter 2")', '#docList li.doc:has-text("Welcome")'); await pg.wait_for_timeout(200)
    print('after drag:', await pg.eval_on_selector_all('#docList li.doc .t','e=>e.map(x=>x.textContent)'))
    await pg.hover('#docList li.doc:has-text("Welcome")'); await pg.click('#docList li.doc:has-text("Welcome") [data-a=up]')
    print('after up:', await pg.eval_on_selector_all('#docList li.doc .t','e=>e.map(x=>x.textContent)'))
    await pg.screenshot(path='n3.png')
    # ---- docx export (single doc, chicago)
    await pg.click('#docList li.doc:has-text("Welcome")'); await pg.wait_for_timeout(300)
    await dl('[data-x=docx]','welcome.docx')
    # osint docx
    await pg.select_option('#docStyle','osint'); await pg.wait_for_timeout(200); await dl('[data-x=docx]','welcome-osint.docx')
    await pg.select_option('#docStyle','apa'); await pg.wait_for_timeout(200); await dl('[data-x=docx]','welcome-apa.docx')
    await pg.select_option('#docStyle','chicago-notes-bibliography')
    # ---- manuscript
    await pg.click('#btnManuscript'); await pg.wait_for_timeout(200)
    print('ms list:', (await pg.inner_text('#msList')).replace('\n',' | '), '|', await pg.inner_text('#msCount'))
    await pg.screenshot(path='n4.png')
    async with pg.expect_download() as d: await pg.click('#msOk')
    f=await d.value; await f.save_as('ms.docx')
    await pg.click('#btnManuscript'); await pg.select_option('#msFormat','doc'); await pg.click('#msOk'); await pg.wait_for_timeout(500)
    print('ms doc notes:', await pg.eval_on_selector_all('#refs p.note','e=>e.map(x=>x.textContent.slice(0,70))'))
    # ---- focus mode
    await pg.click('#docList li.doc:has-text("Welcome")'); await pg.wait_for_timeout(200)
    await pg.click('#editor p >> nth=2'); await pg.keyboard.press('Control+Shift+F'); await pg.wait_for_timeout(500)
    print('focus:', await pg.evaluate("document.body.className"), await pg.inner_text('#focusStat'))
    await pg.screenshot(path='n5.png')
    await pg.keyboard.press('Escape'); await pg.wait_for_timeout(200)
    print('after esc:', await pg.evaluate("document.body.className"))
    # ---- reminders
    await pg.evaluate("dirtyFile=true; dirtySince=Date.now()-20*60000; checkReminder()")
    print('remind:', await pg.is_visible('#remindBar'), await pg.inner_text('#remindText'))
    await pg.screenshot(path='n6.png')
    await pg.click('#remindLater'); print('after later:', await pg.is_visible('#remindBar'))
    # ---- save, edit, reopen file -> newer-copy prompt
    await pg.evaluate("snoozeUntil=0")
    async with pg.expect_download() as d: await pg.click('#btnSave')
    f=await d.value; await f.save_as('p3.json')
    print('after save remind visible:', await pg.is_visible('#remindBar'))
    await pg.click('#editor h1'); await pg.keyboard.type(' EDITED'); await pg.wait_for_timeout(1500)
    await pg.click('#btnOpen'); await pg.wait_for_timeout(200)
    if await pg.is_visible('#askDlg'): await pg.click('#askOk')
    await pg.set_input_files('#fileOpen','p3.json'); await pg.wait_for_timeout(600)
    print('newer prompt:', await pg.is_visible('#askDlg'), await pg.inner_text('#askTitle'))
    await pg.click('#askOk'); await pg.wait_for_timeout(400)
    print('kept edit:', await pg.evaluate("P.docs.some(d=>d.html.includes('EDITED'))"))
    # settings
    await pg.click('#btnSettings'); await pg.screenshot(path='n7.png'); await pg.click('#stCancel')
    print(errs)
    await b.close()
asyncio.run(main())
