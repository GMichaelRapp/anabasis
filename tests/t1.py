import asyncio, json, sys
from playwright.async_api import async_playwright
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from env import URL, HTTP, OUT, FX, AXE
URL=URL
async def main():
  async with async_playwright() as p:
    b=await p.chromium.launch()
    ctx=await b.new_context(viewport={'width':1440,'height':900}, accept_downloads=True)
    await ctx.add_init_script("try{if(!localStorage.getItem('commonplace.prefs'))localStorage.setItem('commonplace.prefs',JSON.stringify({startHome:false,seenVersion:'99.0.0'}))}catch(e){}")
    pg=await ctx.new_page(); errs=[]
    pg.on('console', lambda m: errs.append(m.type+': '+m.text) if m.type in ('error','warning') else None)
    pg.on('pageerror', lambda e: errs.append('PAGEERROR '+str(e)))
    await pg.add_init_script("delete window.showSaveFilePicker; delete window.showOpenFilePicker;")
    await pg.goto(URL); await pg.wait_for_timeout(800)
    print('markers', await pg.eval_on_selector_all('#editor .cite,#editor .fn','els=>els.map(e=>e.className+":"+e.textContent)'))
    print('refs', (await pg.inner_text('#refs'))[:900])
    await pg.screenshot(path=OUT + '/s1.png')
    for st in ['apa','modern-language-association','chicago-author-date']:
      await pg.select_option('#docStyle', st); await pg.wait_for_timeout(300)
      print(st, await pg.eval_on_selector_all('#editor .cite','els=>els.map(e=>e.textContent)'))
    await pg.select_option('#docStyle','chicago-notes-bibliography')
    # insert citation via dialog at end
    await pg.click('#editor p:last-of-type'); await pg.keyboard.press('End')
    await pg.click('#btnCite'); await pg.wait_for_timeout(200)
    await pg.click('#citePick li[data-id] >> nth=1')
    await pg.fill('#citeCluster .loc','99')
    await pg.wait_for_timeout(300)
    print('preview', await pg.inner_text('#citePreview'))
    await pg.screenshot(path=OUT + '/s2.png')
    await pg.click('#citeOk'); await pg.wait_for_timeout(400)
    print('markers2', await pg.eval_on_selector_all('#editor .cite,#editor .fn','els=>els.map(e=>e.getAttribute("contenteditable")+":"+e.textContent+":"+(e.dataset.items||""))'))
    print('notes now', await pg.eval_on_selector_all('#refs p.note','els=>els.map(e=>e.textContent)'))
    # notes tab: insert note
    await pg.click('.tabs button[data-tab=notes]')
    await pg.click('#noteList li >> nth=0'); await pg.wait_for_timeout(200)
    await pg.screenshot(path=OUT + '/s3.png')
    await pg.click('#panelFoot [data-a=ins]'); await pg.wait_for_timeout(400)
    print('after note insert count', await pg.eval_on_selector_all('#editor .cite','e=>e.length'))
    # compile
    await pg.click('#btnCompile'); await pg.wait_for_timeout(200); await pg.select_option('#cmGroup','tag')
    await pg.screenshot(path=OUT + '/s4.png')
    await pg.click('#cmOk'); await pg.wait_for_timeout(500)
    print('compiled html', (await pg.inner_html('#editor'))[:700])
    print('compiled refs', await pg.inner_text('#refs'))
    # sources: new source form
    await pg.click('.tabs button[data-tab=sources]'); await pg.click('#btnNewSource'); await pg.wait_for_timeout(200)
    await pg.fill('#panelBody [data-f=title]','Fighting for Ukraine'); 
    await pg.fill('#people [data-p=family]','Rapp'); await pg.fill('#people [data-p=given]','G. Michael')
    await pg.select_option('#panelBody [data-f=type]','report'); await pg.wait_for_timeout(400)
    await pg.fill('#panelBody [data-f=publisher]','Example Institute'); await pg.fill('#panelBody [data-f=issued]','May 3, 2025'); await pg.fill('#panelBody [data-f=genre]','white paper')
    await pg.wait_for_timeout(600)
    print('src preview', await pg.inner_text('#srcPreview'))
    await pg.screenshot(path=OUT + '/s5.png')
    # save
    async with pg.expect_download() as d: await pg.click('#btnSave')
    dl=await d.value; path=OUT + '/proj.json'; await dl.save_as(path)
    j=json.load(open(path)); print('saved', len(j['docs']), len(j['notes']), len(j['sources']), j['sources'][-1]['csl'])
    # md export
    await pg.click('#btnExport')
    async with pg.expect_download() as d: await pg.click('[data-x=md]')
    dl=await d.value; await dl.save_as(OUT + '/doc.md'); 
    await pg.click('.tabs button[data-tab=docs]'); await pg.click('#docList li:has-text("Welcome")'); await pg.wait_for_timeout(300)
    await pg.click('#btnExport')
    async with pg.expect_download() as d: await pg.click('[data-x=md]')
    dl=await d.value; await dl.save_as(OUT + '/welcome.md')
    await pg.click('#btnExport')
    async with pg.expect_download() as d: await pg.click('[data-x=html]')
    dl=await d.value; await dl.save_as(OUT + '/welcome.html')
    # pdf
    await pg.evaluate("window.print=()=>{}")
    await pg.click('#btnExport'); await pg.click('[data-x=pdf]'); await pg.wait_for_timeout(200)
    await pg.emulate_media(media='print')
    await pg.pdf(path=OUT + '/welcome.pdf', prefer_css_page_size=True)
    await pg.emulate_media(media='screen')
    # reload: restore from localStorage? (file:// localStorage works)
    await pg.reload(); await pg.wait_for_timeout(800)
    print('after reload docs', await pg.eval_on_selector_all('#docList li','e=>e.length'), await pg.inner_text('#saveState'))
    # open file
    await pg.set_input_files('#fileOpen', path); await pg.wait_for_timeout(600)
    print('opened', await pg.inner_text('#cntDocs'), await pg.inner_text('#cntSources'))
    # dark + mobile
    await pg.click('#btnTheme'); await pg.screenshot(path=OUT + '/s6.png')
    await pg.set_viewport_size({'width':390,'height':844}); await pg.wait_for_timeout(200); await pg.screenshot(path=OUT + '/s7.png')
    print('ERRS', errs)
    await b.close()
asyncio.run(main())
