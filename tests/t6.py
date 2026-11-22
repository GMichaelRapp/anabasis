import asyncio, json
from playwright.async_api import async_playwright
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from env import URL, HTTP, OUT, FX, AXE
async def main():
  async with async_playwright() as p:
    b=await p.chromium.launch()
    ctx=await b.new_context(viewport={'width':1440,'height':900}, accept_downloads=True)
    await ctx.add_init_script("try{if(!localStorage.getItem('commonplace.prefs'))localStorage.setItem('commonplace.prefs',JSON.stringify({startHome:false}))}catch(e){}")
    pg=await ctx.new_page(); errs=[]
    pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('console', lambda m: errs.append(m.text) if m.type=='error' else None)
    await pg.add_init_script("delete window.showSaveFilePicker; delete window.showOpenFilePicker;")
    await pg.goto(URL); await pg.wait_for_timeout(600)
    await pg.select_option('#docStyle','osint'); await pg.wait_for_timeout(300)
    print('\n'.join(await pg.eval_on_selector_all('#refs p.note','e=>e.map(x=>x.textContent)')))
    print('bib?', await pg.locator('#refs .bib').count())
    # regression: generator samples -> list file -> import -> compare
    res = await pg.evaluate("""()=>{
      const T=OSINT_DATA.TYPES; const sources=Object.keys(T).map(k=>({id:k,fields:Object.assign({type:k,titleStyle:T[k].style},T[k].sample)}));
      const before=P.sources.length; importOsintList({app:'OSINT Citation Generator',format:2,name:'samples',sources});
      const out=[]; Object.keys(T).forEach((k,i)=>{ const s=P.sources[before+i]; const f=sources[i].fields;
        const want=OSINT.toPlain(OSINT.build(Object.assign({},f,{volatile:!!T[k].volatile,live:!!T[k].live,dayDate:!!T[k].dayDate,ai:!!T[k].ai})).seg);
        const loc=f.locator? {locator:f.locator}:{};
        const got=OSINT.toPlain(OSINT.build(osintState(s,loc)).seg);
        out.push([k, want===got, want, got]); });
      return out; }""")
    for k,ok,w,g in res:
      print(('OK  ' if ok else 'DIFF'), k, '' if ok else '\n   want: '+w+'\n   got:  '+g)
    # source panel UI
    await pg.click('.tabs button[data-tab=sources]')
    await pg.click('#sourceList li:has-text("Kofman")'); await pg.wait_for_timeout(300)
    await pg.select_option('#osintBox [data-o=relA]','C'); await pg.select_option('#osintBox [data-o=rel1]','3')
    await pg.click('#osintBox summary:has-text("Qualifiers")'); await pg.check('#osintBox [data-oq="sponsored"]')
    await pg.check('#osintBox [data-oa="paywalled"]'); await pg.wait_for_timeout(600)
    print('preview:', await pg.inner_text('#osintPreview'))
    await pg.locator('#osintBox').scroll_into_view_if_needed(); await pg.screenshot(path='o1.png')
    await pg.evaluate("document.getElementById('osintPreview').scrollIntoView()"); await pg.screenshot(path='o1.png')
    # cite dialog with Cited in prefix in OSINT doc
    await pg.click('#editor p >> nth=1'); await pg.keyboard.press('End')
    await pg.click('#btnCite'); await pg.fill('#citeSearch','Kofman'); await pg.click('#citePick li[data-id]')
    await pg.fill('#citeCluster [data-k=prefix]','Cited in'); await pg.fill('#citeCluster .loc','12-14'); await pg.wait_for_timeout(300)
    print('cite preview:', await pg.inner_text('#citePreview'))
    await pg.click('#citeOk'); await pg.wait_for_timeout(300)
    await pg.click('#btnCite'); await pg.fill('#citeSearch','Kofman'); await pg.click('#citePick li[data-id]'); await pg.fill('#citeCluster .loc','20'); await pg.click('#citeOk'); await pg.wait_for_timeout(300)
    print('\n'.join(await pg.eval_on_selector_all('#refs p.note','e=>e.map(x=>x.textContent)')))
    # export list & reimport roundtrip
    await pg.click('#btnExport')
    async with pg.expect_download() as d: await pg.click('[data-x=osintlist]')
    dl=await d.value; await dl.save_as('osint-list.json'); j=json.load(open('osint-list.json'))
    print('list', j['app'], j['format'], len(j['sources'])); print(j['sources'][-1]['footnote'] if False else [s['footnote'] for s in j['sources'] if 'Kofman' in s['footnote']])
    # save project & reload: osint kept?
    async with pg.expect_download() as d: await pg.click('#btnSave')
    dl=await d.value; await dl.save_as('proj2.json'); pj=json.load(open('proj2.json'))
    print('osint saved', [s.get('osint') for s in pj['sources'] if 'Kofman' in json.dumps(s)])
    await pg.set_input_files('#fileOpen','proj2.json'); await pg.wait_for_timeout(500)
    print('after reopen', (await pg.eval_on_selector_all('#refs p.note','e=>e.map(x=>x.textContent)'))[-2:])
    # PDF
    await pg.evaluate("window.print=()=>{}"); await pg.click('#btnExport'); await pg.click('[data-x=pdf]'); await pg.wait_for_timeout(4000); await pg.emulate_media(media='print'); await pg.pdf(path='osint.pdf'); await pg.emulate_media(media='screen')
    print(errs)
    await b.close()
asyncio.run(main())
