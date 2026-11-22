import asyncio, json
from playwright.async_api import async_playwright
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from env import URL, HTTP, OUT, FX, AXE
APP=HTTP + 'anabasis.html'
CIT=[{"itemType":"newspaperArticle","title":"Ukraine war: drone strikes hit refinery","publicationTitle":"BBC News","date":"2025-03-14","url":"https://www.bbc.com/news/x","accessDate":"2026-11-21","author":[["Jane","Smith"],["Ali","Khan"]],"language":"en"}]
async def main():
  async with async_playwright() as p:
    b=await p.chromium.launch()
    ctx=await b.new_context(viewport={'width':1440,'height':900}, accept_downloads=True)
    await ctx.add_init_script("try{if(!localStorage.getItem('commonplace.prefs'))localStorage.setItem('commonplace.prefs',JSON.stringify({startHome:false}))}catch(e){}")
    await ctx.route('https://en.wikipedia.org/**', lambda r: r.fulfill(status=200, headers={'access-control-allow-origin':'*','content-type':'application/json'}, body=json.dumps(CIT)))
    errs=[]
    A=await ctx.new_page(); A.on('pageerror', lambda e: errs.append('A '+str(e))); A.on('console', lambda m: errs.append('A '+m.text) if m.type=='error' else None)
    await A.goto(APP); await A.wait_for_timeout(800)
    print('window.name', await A.evaluate('window.name'))
    # --- URL via Citoid
    await A.click('.tabs button[data-tab=sources]'); await A.fill('#quickId','https://www.bbc.com/news/x'); await A.click('#btnQuickId'); await A.wait_for_timeout(800)
    print('citoid source:', await A.evaluate("JSON.stringify(P.sources[P.sources.length-1].csl)"))
    print('toast:', await A.inner_text('#toast'))
    # --- clipper: run bookmarklet on article page in another tab
    art=await ctx.new_page(); await art.goto(HTTP + 'article.html')
    code=await A.evaluate('clipperSource()')
    await art.evaluate("""()=>{const p=document.getElementById('p1');const r=document.createRange();r.selectNodeContents(p);const s=getSelection();s.removeAllRanges();s.addRange(r);}""")
    async with ctx.expect_page() as newp:
      await art.evaluate(code)
    np=await newp.value; np.on('pageerror', lambda e: errs.append('N '+str(e)))
    await A.wait_for_timeout(2000)
    print('handoff tab closed itself:', np.is_closed())
    await A.wait_for_timeout(300)
    print('clip in A:', await A.evaluate("JSON.stringify({src:P.sources[P.sources.length-1].csl, note:(({title,body,kind})=>({title,body,kind}))(P.notes[0])})"))
    print('toast A:', await A.inner_text('#toast'))
    # second clip, same page, no selection -> dedupe
    await art.evaluate("getSelection().removeAllRanges()")
    async with ctx.expect_page() as newp: await art.evaluate(code)
    np2=await newp.value; await A.wait_for_timeout(1500)
    print('sources count after dup clip:', await A.evaluate("P.sources.length"), '| toast:', await A.inner_text('#toast'))
    # --- second tab warning
    B=await ctx.new_page(); await B.goto(APP); await B.wait_for_timeout(1200)
    print('tab warning B:', await B.is_visible('#tabBar'), '| A:', await A.is_visible('#tabBar'))
    await B.close()
    # --- clipper dialog + settings storage
    await A.click('#btnClipper'); await A.wait_for_timeout(200)
    print('clip href starts:', (await A.get_attribute('#clipLink','href'))[:40], '| local warn visible:', await A.is_visible('#clipLocal'))
    await A.screenshot(path='c1.png'); await A.click('#clipClose')
    await A.click('#btnSettings'); await A.wait_for_timeout(400); print('storage:', await A.inner_text('#stStorage')); await A.screenshot(path='c2.png'); await A.click('#stCancel')
    print('ERRS', errs)
    # fresh context: clip with no app tab open
    ctx2=await b.new_context(viewport={'width':1440,'height':900})
    await ctx2.add_init_script("try{if(!localStorage.getItem('commonplace.prefs'))localStorage.setItem('commonplace.prefs',JSON.stringify({startHome:false}))}catch(e){}")
    await ctx2.route('https://en.wikipedia.org/**', lambda r: r.fulfill(status=500, body='x'))
    C=await ctx2.new_page(); C.on('pageerror', lambda e: errs.append('C '+str(e)))
    clip={"v":1,"url":"https://example.org/report","title":"Annual Threat Assessment | ODNI","titleFromDoc":True,"site":"ODNI","authors":[],"date":"2025-03-18","sel":"China remains the top threat."}
    await C.goto(APP+'#clip='+json.dumps(clip).replace(' ','%20')); await C.wait_for_timeout(1500)
    print('fresh clip:', await C.evaluate("JSON.stringify({t:P.sources[P.sources.length-1].csl.title, site:P.sources[P.sources.length-1].csl['container-title'], note:P.notes[0].body, hash:location.hash})"))
    print('ERRS', errs)
    await b.close()
asyncio.run(main())
