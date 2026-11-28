// Contrast of emphasized text, the way it is drawn: the editor's highlights (which accessibility checkers can't see,
// because they are painted, not elements), drafting colors, code snippets and task badges, against the page they
// sit on in the current theme. Returns the pairs under 4.5:1.
(() => {
  const out = [], probe = document.createElement('div'); document.body.appendChild(probe);
  const rgba = c => { probe.style.color = ''; probe.style.color = c; const v = getComputedStyle(probe).color, m = (v.match(/[\d.]+/g) || [0, 0, 0]).map(Number); return [m[0], m[1], m[2], m.length > 3 ? m[3] : 1]; };
  const L = ([r, g, b]) => [r, g, b].map(v => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; }).reduce((s, v, i) => s + v * [0.2126, 0.7152, 0.0722][i], 0);
  const cr = (a, b) => { const x = L(a), y = L(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
  const over = (t, b) => [0, 1, 2].map(i => t[i] * t[3] + b[i] * (1 - t[3])).concat(1);
  const cs = getComputedStyle(document.documentElement), v = n => cs.getPropertyValue(n).trim();
  const page = rgba(v('--page')), ink = rgba(v('--page-ink'));
  // painted highlights in the editor
  for (const sh of document.styleSheets) { let rules; try { rules = sh.cssRules; } catch (e) { continue; }
    for (const r of rules) {
      const sel = r.selectorText || ''; if (!/^(:root\[data-theme="dark"\] )?::highlight\(cp-(find|cur|name|close|gloss)\)$/.test(sel)) continue;
      if (/data-theme="dark"/.test(sel) !== (document.documentElement.dataset.theme === 'dark')) continue;
      const bg = (r.style.backgroundColor || r.style.background || '').replace(/var\(--([\w-]+)\)/g, (m, n) => v('--' + n)); if (!bg) continue;
      const fg = r.style.color && r.style.color !== 'inherit' ? rgba(r.style.color) : ink, ratio = cr(fg, over(rgba(bg), page));
      if (ratio < 4.5) out.push([sel, +ratio.toFixed(2)]);
    } }
  // elements drawn on the page: colors, snippets, a badge
  const pg = document.createElement('article'); pg.className = 'page docbody'; pg.id = 'contrastProbe'; pg.style.cssText = 'position:fixed;left:-9999px;top:0;width:600px';
  pg.innerHTML = 'bgarps'.split('').map(c => `<span class="ink ink-${c}">x</span>`).join('') + '<pre class="code" data-lang="Python"><code>x</code></pre>';
  document.getElementById('editor').appendChild(pg);
  const eff = el => { let bg = [0, 0, 0, 0], n = el; const layers = []; while (n && n.nodeType === 1) { const c = rgba(getComputedStyle(n).backgroundColor); if (c[3] > 0) layers.push(c); if (c[3] >= 1) break; n = n.parentElement; } let base = page; layers.reverse().forEach(l => { base = over(l, base); }); return base; };
  pg.querySelectorAll('.ink, pre.code').forEach(el => { const r = cr(rgba(getComputedStyle(el).color), eff(el)); if (r < 4.5) out.push([el.className, +r.toFixed(2)]); });
  pg.remove();
  const badge = cr(rgba(v('--accent')), over(rgba(v('--accent-soft')), page)); if (badge < 4.5) out.push(['task badge', +badge.toFixed(2)]);
  probe.remove();
  return out;
})()
