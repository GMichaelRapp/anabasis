/*! OSINT Citation Generator 3.2.1 core — (c) 2026 G. Michael Rapp — MIT License (code); OSINT Style Guide content CC BY 4.0 — https://gmichaelrapp.github.io/OSINT_Cites/ */
var OSINT = (function () {
  'use strict';
  var MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
  var REL = { A: 'Highly Reliable', B: 'Usually Reliable', C: 'Fairly Reliable', D: 'Not Usually Reliable', E: 'Unreliable', F: 'Unknown' };
  var CRED = { 1: 'Confirmed', 2: 'Probable', 3: 'Possible', 4: 'Doubtful', 5: 'Improbable', 6: 'Unknown' };
  var ZROWS = ['GGGYYX', 'GGYYOX', 'YYYOOX', 'OOOORX', 'RRRRRX', 'XXXXXX'];
  var ZNAME = { G: 'Green', Y: 'Yellow', O: 'Orange', R: 'Red', X: 'Gray' };
  var HANDLING = {
    G: 'May be used as core evidence.',
    Y: 'Usable with framing and corroboration. Say in the text that the claim is not confirmed.',
    O: 'Weak. Use only where necessary, with the caveat stated in a footnote.',
    R: 'Likely misleading or false. Cite only to identify and challenge the claim, never to support one.',
    X: 'Unverifiable. May show that a claim is circulating; may never be the sole support for a judgment.'
  };
  var SHORTENERS = ['bit.ly', 'tinyurl.com', 't.co', 'goo.gl', 'ow.ly', 'buff.ly', 'is.gd', 'lnkd.in', 'shorturl.at', 'rb.gy', 'tiny.cc', 'cutt.ly', 'trib.al', 'dlvr.it'];
  var VOLATILE = ['x.com', 'twitter.com', 't.me', 'telegram.me', 'discord.com', 'discord.gg', 'facebook.com', 'instagram.com', 'tiktok.com', 'reddit.com', 'bsky.app', 'threads.net', 'vk.com', 'weibo.com', 'truthsocial.com', 'mastodon.social', 'medium.com', 'blogspot.com', 'wordpress.com'];
  var ORG = /\b(Staff|Department|Ministry|Institute|Institution|University|Corporation|Council|Bureau|Service|Office|Agency|Labs?|PBC|Inc|LLC|Ltd|News|Organization|Bank|Fund|Union|Commission|Court|House|Congress|Parliament|Foundation|Center|Centre|Nations|Reserve|Government|Press|Group|Project|Analysts|Endowment|Command|Force|Navy|Army|accounts)\b/i;

  function straight(s) { return String(s == null ? '' : s).replace(/[“”]/g, '"').replace(/[‘’]/g, "'"); }
  function clean(s) { return straight(s).replace(/\s+/g, ' ').trim(); }
  function lines(s) { return String(s == null ? '' : s).split(/[\n;]+/).map(clean).filter(Boolean); }
  function listJoin(a) {
    if (a.length <= 1) return a[0] || '';
    if (a.length === 2) return a[0] + ' and ' + a[1];
    return a.slice(0, -1).join(', ') + ', and ' + a[a.length - 1];
  }
  function authorBlock(a) { return a.length >= 4 ? a.slice(0, 3).join(', ') + ', et al.' : listJoin(a); }
  var ROLE_TAG = /\s*\((eds?|trans|contr)\.\)$/i;
  // Editors, translators and contributors each have their own field. Lists saved before 3.1 kept
  // all three in one box (st.contribs), tagged by hand or given one default role; those still read correctly.
  function splitPeople(st) {
    var out = { ed: lines(st.editors), trans: lines(st.translators), contr: lines(st.contributors) };
    lines(st.contribs).forEach(function (n) {
      var m = n.match(ROLE_TAG), role = m ? m[1].toLowerCase().replace('eds', 'ed') : (st.contribRole || 'ed');
      (out[role] || out.ed).push(n);
    });
    function tidy(a) { return a.map(function (n) { return n.replace(ROLE_TAG, ''); }).filter(Boolean); }
    return { ed: tidy(out.ed), trans: tidy(out.trans), contr: tidy(out.contr) };
  }
  function roleList(st) {
    var p = splitPeople(st);
    return p.ed.map(function (n) { return n + ' (ed.)'; })
      .concat(p.trans.map(function (n) { return n + ' (trans.)'; }), p.contr.map(function (n) { return n + ' (contr.)'; }));
  }
  // 'en': in English. 'foreign': in another language. 'published': an English translation someone published.
  function langModeOf(st) {
    if (st.langMode === 'en' || st.langMode === 'foreign' || st.langMode === 'published') return st.langMode;
    return (clean(st.transTitle) || clean(st.origLang) || st.transBy) ? 'foreign' : 'en';
  }
  // Bring a source saved by an earlier version up to the current fields.
  function upgradeState(st) {
    var out = {}, k, p = splitPeople(st);
    for (k in st) if (Object.prototype.hasOwnProperty.call(st, k) && k !== 'contribs' && k !== 'contribRole') out[k] = st[k];
    out.editors = p.ed.join('\n'); out.translators = p.trans.join('\n'); out.contributors = p.contr.join('\n');
    out.langMode = langModeOf(st);
    return out;
  }
  function pad2(n) { return (n < 10 ? '0' : '') + n; }
  function monthIndex(name) {
    var n = String(name).toLowerCase().replace(/\.$/, '');
    if (n.length < 3) return -1;
    for (var i = 0; i < 12; i++) if (MONTHS[i].toLowerCase().indexOf(n) === 0) return i;
    return -1;
  }
  function normDate(raw) {
    var s = clean(raw), m, mi, d;
    if (!s) return { text: '', level: 'none' };
    if (/^n\.?\s?d\.?$/i.test(s)) return { text: 'n.d.', level: 'none' };
    if (/^\d{4}$/.test(s)) return { text: s, level: 'year' };
    function full(y, mo, da) {
      mo = +mo; da = +da;
      if (mo < 1 || mo > 12 || da < 1 || da > 31) return { text: s, level: 'raw' };
      return { text: pad2(da) + ' ' + MONTHS[mo - 1] + ' ' + y, level: 'day' };
    }
    if ((m = s.match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/))) return full(m[1], m[2], m[3]);
    if ((m = s.match(/^(\d{4})-(\d{1,2})$/)) && +m[2] >= 1 && +m[2] <= 12) return { text: MONTHS[+m[2] - 1] + ' ' + m[1], level: 'month' };
    if ((m = s.match(/^(\d{1,2})[\/.](\d{1,2})[\/.](\d{4})$/))) {
      return (+m[1] > 12 && +m[2] <= 12) ? full(m[3], m[2], m[1]) : full(m[3], m[1], m[2]);
    }
    if ((m = s.match(/^(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]{3,9})\.?,?\s+(\d{4})$/)) && (mi = monthIndex(m[2])) >= 0) return full(m[3], mi + 1, m[1]);
    if ((m = s.match(/^([A-Za-z]{3,9})\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})$/)) && (mi = monthIndex(m[1])) >= 0) return full(m[3], mi + 1, m[2]);
    if ((m = s.match(/^([A-Za-z]{3,9})\.?,?\s+(\d{4})$/)) && (mi = monthIndex(m[1])) >= 0) return { text: MONTHS[mi] + ' ' + m[2], level: 'month' };
    return { text: s, level: 'raw' };
  }
  function normLocator(raw) {
    var s = clean(raw).replace(/\.$/, ''), m, body;
    if (!s) return '';
    var PAGES = /^[\divxlcdm\s,–—-]+$/i;
    body = s;
    if ((m = s.match(/^pp?\.?\s*(.+)$/i)) && PAGES.test(m[1])) body = m[1];
    if (PAGES.test(body) && /[\divxlcdm]/i.test(body)) {
      var p = body.replace(/\s*[-–—]\s*/g, '–').replace(/\s*,\s*/g, ', ');
      return (/[–,]/.test(p) ? 'pp. ' : 'p. ') + p;
    }
    return s.replace(/(\d)\s*[-–—]\s*(?=\d)/g, '$1–');
  }
  function hostOf(u) {
    var m = String(u).match(/^[a-z]+:\/\/([^\/?#:]+)/i);
    return m ? m[1].toLowerCase().replace(/^www\./, '') : '';
  }
  function hostIn(h, list) {
    for (var i = 0; i < list.length; i++) if (h === list[i] || h.slice(-(list[i].length + 1)) === '.' + list[i]) return true;
    return false;
  }
  function normUrl(raw) {
    var s = String(raw == null ? '' : raw).trim(), doi = false;
    if (!s) return { url: '', doi: false };
    s = s.replace(/^doi:\s*/i, '');
    if (/^10\.\d{4,9}\/\S+$/.test(s)) return { url: 'https://doi.org/' + s, doi: true };
    if (/^(https?:\/\/)?(dx\.)?doi\.org\//i.test(s)) {
      var fixed = 'https://doi.org/' + s.replace(/^(https?:\/\/)?(dx\.)?doi\.org\//i, '');
      return { url: fixed, doi: fixed !== s };
    }
    if (!/^[a-z][a-z0-9+.-]*:\/\//i.test(s) && /^[\w-]+(\.[\w-]+)+(\/|$|\?|#)/.test(s)) s = 'https://' + s;
    return { url: s, doi: doi };
  }
  function cleanTitle(raw, style) {
    var s = clean(raw), m = s.match(/^"(.*)"$/);
    if (m && m[1].indexOf('"') === -1) s = m[1];
    s = s.replace(/,$/, '');
    if (style === 'quotes') s = s.replace(/"/g, "'");
    return s;
  }
  function zoneOf(r) {
    if (!/^[A-F][1-6]$/.test(r || '')) return '';
    return ZROWS[+r[1] - 1]['ABCDEF'.indexOf(r[0])];
  }
  function words(s) { return s ? s.split(/\s+/).filter(Boolean).length : 0; }
  function surname(n) {
    var w = n.split(' ');
    if (w.length > 3 || w.length < 2 || /\d/.test(n) || ORG.test(n)) return n;
    return w[w.length - 1];
  }
  function deriveName(authors) {
    var s = authors.map(surname);
    if (s.length >= 4) return s[0] + ' et al.';
    return listJoin(s);
  }
  function deriveShortTitle(t) {
    var q = t.match(/^(.+?[?!])\s/);
    if (q) return q[1];
    var i = t.indexOf(':');
    return (i > 0 ? t.slice(0, i) : t).trim();
  }

  function accessOf(st) {
    var raw = Array.isArray(st.access) ? st.access : (st.access ? [st.access] : []);
    var out = [];
    raw.forEach(function (a) {
      var v = a === 'other' ? clean(st.accessNote) : clean(a);
      if (v && out.indexOf(v) === -1) out.push(v);
    });
    return out;
  }
  function has(list, x) { return list.indexOf(x) !== -1; }
  var REVIEW_Q = ['peer-reviewed', 'editor-reviewed', 'student-edited', 'not peer-reviewed', 'review status unclear'];
  var UNI_PRESS = /\buniversity press\b/i;
  var TRADE_HOUSE = /\b(penguin|random house|harpercollins|simon (&|and) schuster|hachette|knopf|doubleday|farrar, straus|norton|basic books|publicaffairs|little, brown|viking|scribner|st\. martin's|henry holt)\b/i;

  function build(st) {
    var seg = [], checks = [], slots = {};
    function push(s, i) { if (!s) return; var l = seg[seg.length - 1]; if (l && l.i === !!i) l.s += s; else seg.push({ s: s, i: !!i }); }
    function tail() { return seg.length ? seg[seg.length - 1].s.slice(-1) : ''; }
    function sp() { if (seg.length && tail() !== ' ') push(' '); }
    function add(level, msg) { checks.push({ level: level, msg: msg }); }

    var style = st.titleStyle || 'quotes';
    var authors = lines(st.authors), contribs = roleList(st), mode = langModeOf(st);
    var who = authorBlock(authors), cb = listJoin(contribs);
    if (who && cb) who += '; ' + cb; else if (cb) who = cb;
    var title = cleanTitle(st.title, style), trans = mode === 'foreign' ? cleanTitle(st.transTitle, style) : '';
    var rawLoc = clean(st.location), loc = rawLoc, locSame = false;
    if (loc && title && loc.toLowerCase() === title.toLowerCase()) { loc = ''; locSame = true; }

    var type = clean(st.descType), items = [];
    if (type) items.push(type);
    lines(st.descDetails).forEach(function (x) { items.push(x); });
    var quals = Array.isArray(st.quals) ? st.quals.map(clean).filter(Boolean) : [];
    quals.forEach(function (q) { items.push(q); });
    var lang = mode === 'en' ? '' : clean(st.origLang), transBy = mode === 'foreign' ? st.transBy : '';
    if (mode === 'published') { if (lang) items.push('translated from ' + lang); }
    else if (transBy === 'machine') { items.push('machine translation'); if (lang) items.push('original in ' + lang); }
    else { if (lang) items.push('original in ' + lang); if (transBy === 'own') items.push('translation by author'); }
    var accessList = accessOf(st);
    accessList.forEach(function (a) { items.push(a); });
    var access = accessList.length > 0;
    var descWords = words(items.join(' ').replace(/[;,]/g, ' '));
    var rating = /^[A-F][1-6]$/.test(st.rating || '') ? st.rating : '';
    if (rating) items.push(rating);

    var pub = clean(st.publisher), pubSame = false;
    if (pub && rawLoc && pub.toLowerCase() === rawLoc.toLowerCase()) { pub = ''; pubSame = true; }
    var d = normDate(st.date), acc = normDate(st.accessed);
    var u = normUrl(st.url), au = normUrl(st.archiveUrl), ad = normDate(st.archiveDate);
    var locator = normLocator(st.locator), note = clean(st.note), lead = clean(st.lead);

    var empty = !who && !title && !loc && !items.length && !pub && !d.text && !u.url && !locator;
    if (empty) return { seg: [], checks: [], slots: {}, empty: true, rating: '', zone: '' };

    if (lead) push(lead + ' ');
    if (who) { push(who); if (title || loc) push(', '); }
    var endP = /[?!]$/.test(title);
    if (title) {
      if (style === 'quotes') {
        if (trans) { push('"' + title + '" ["' + trans + '"]'); if (loc) push(', '); }
        else { push('"' + title + (loc && !endP ? ',' : '') + '"'); if (loc) push(' '); }
      } else if (style === 'italics') {
        push(title, true);
        if (trans) { push(' ['); push(trans, true); push(']'); }
        if (loc) push(endP && !trans ? ' ' : ', ');
      } else {
        push(title + (trans ? ' [' + trans + ']' : ''));
        if (loc) push(', ');
      }
    }
    if (loc) push(loc, true);
    if (items.length) { sp(); push('[' + items.join('; ') + ']'); }

    var dateText = d.text || 'n.d.';
    if ((st.dateKind === 'updated' || st.dateKind === 'captured') && d.text && d.text !== 'n.d.') dateText = st.dateKind + ' ' + dateText;
    if (acc.text) dateText += ', accessed ' + acc.text;
    sp(); push('(' + (pub ? pub + ': ' : '') + dateText + ')');
    if (u.url) { sp(); push(u.url); }
    if (locator) push(': ' + locator);
    if (!/[.?!]$/.test(tail()) || (u.url && !locator)) push('.');
    if (au.url) push(' Archived: ' + au.url + (ad.text ? ' (captured ' + ad.text + ')' : '') + '.');
    if (note) push(' ' + note + (/[.?!]$/.test(note) ? '' : '.'));

    slots.author = who ? 'filled' : 'dropped';
    slots.title = title ? 'filled' : 'missing';
    slots.location = loc ? 'filled' : 'dropped';
    slots.description = type ? 'filled' : 'missing';
    slots.publisher = pub ? 'filled' : 'dropped';
    slots.date = (d.text && d.text !== 'n.d.') ? 'filled' : 'nd';
    slots.url = u.url ? 'filled' : 'dropped';
    slots.locator = locator ? 'filled' : 'dropped';

    if (!title) add('fix', 'No title. Where a source has none, write a plain description in the title slot and set it as a plain description.');
    if (!type) add('fix', 'The description bracket is empty. It is the one slot that is never dropped.');
    if (st.ai && rating !== 'F6') add('check', 'AI model output is rated F6 by default.');
    var h = hostOf(u.url);
    if (h && hostIn(h, SHORTENERS)) add('fix', 'That is a link shortener. Give the full URL.');
    if (u.url && /[?&](utm_[a-z]+|fbclid|gclid|mc_cid|igshid)=/i.test(u.url)) add('check', 'The URL carries tracking parameters. Trim them so the link is the stable one.');
    if ((st.volatile || (h && hostIn(h, VOLATILE))) && !au.url) add('check', 'Volatile source with no archive link. Archive it now and add the link and capture date.');
    if (au.url && !ad.text) add('check', 'The archive link has no capture date.');
    if (st.live && !acc.text) add('check', 'A continuously updated source needs an access date.');
    if (st.dayDate && (d.level === 'year' || d.level === 'month')) add('check', 'This kind of source takes the full date: DD Month YYYY.');
    var z = zoneOf(rating);
    if (z && z !== 'G') add('check', rating + ' sits in the ' + ZNAME[z] + ' zone. ' + HANDLING[z]);
    if (rating === 'C1') add('note', 'C1 is the weakest of the Green blocks. Say so when leaning on it.');
    if (words(rawLoc) > 10 && st.type !== 'chapter') add('check', 'Location runs ' + words(rawLoc) + ' words. The guide asks for ten or fewer.');
    if (!who && title) add('note', 'No author, so the footnote opens with the title. Use the organization if there is one, or the outlet plus Staff.');
    if (authors.length >= 4) add('note', authors.length + ' authors: the first three are named, then et al.');
    if (locSame) add('note', 'Location repeats the title, so it is dropped.');
    if (pubSame) add('note', 'Publisher repeats the location, so it is dropped.');
    if (!d.text) add('note', 'No date given, so the parenthetical reads n.d. If you can establish one, put [ca. YYYY] in the description and say how.');
    if (d.level === 'raw') add('note', 'Date left as typed. House form is DD Month YYYY, or the year alone for books and journal articles.');
    if (u.doi) add('note', 'DOI rewritten in resolvable form.');
    if (descWords > 10) add('note', 'Description runs ' + descWords + ' words against a target of ten. Archival detail and imagery metadata often need the room.');
    if (/^(cited|quoted) in$/i.test(lead)) add('note', 'A secondary citation inherits the weaker of the two ratings and is never stronger than the intermediary.');
    if (mode === 'foreign' && !lang) add('check', 'This source is marked as not in English, but no language is given.');
    if (mode === 'foreign' && title && !trans) add('note', 'Add the title in English so a reader can tell what the source is.');
    if (mode === 'published' && !contribs.some(function (c) { return /\(trans\.\)$/.test(c); })) add('note', 'A published translation credits its translator. Add the name under Translators.');
    if (transBy === 'machine') add('note', 'Check any quotation against the original before it is used as a quotation.');
    if (access) add('note', 'Access is restricted, so some readers cannot check this source. Where a free version exists, such as a preprint or an official release, cite that instead or alongside.');
    var tl = type.toLowerCase();
    if (/unverified|suspected synthetic|suspected inauthentic|manipulated media|ai-generated/.test(tl) || has(quals, 'provenance unverified') || has(quals, 'suspected synthetic') || has(quals, 'AI-generated') || has(quals, 'digitally altered')) add('check', 'Unverified or synthetic material. Say in the commentary what was checked, what was not, and why it is cited at all.');
    if (has(quals, 'retracted')) add('check', 'Retracted work. Cite it only to discuss the retraction, and say so in the commentary.');
    if (/state media|party newspaper/.test(tl)) add('note', 'State or party media: evidence of official messaging first, of fact second.');
    if (/^leaked|captured document|leak site|hacktivist/.test(tl) || has(quals, 'leaked') || has(quals, 'captured')) add('note', 'Leaked or captured material. Say how its authenticity was established, and rate the information on its own merits.');
    if (/^(preprint paper|working paper)$/.test(tl) || has(quals, 'preprint') || has(quals, 'not peer-reviewed')) add('note', 'Not peer-reviewed. Say so in the text wherever the claim is load-bearing.');
    var rq = quals.filter(function (q) { return has(REVIEW_Q, q); });
    if (rq.length > 1) add('check', 'More than one review status is ticked (' + rq.join(', ') + '). Keep the one that fits.');
    if (tl === 'journal article' && !rq.length) add('check', 'Journal Article says nothing about review. Set the review status, or mark it review status unclear if the journal does not say.');
    if (tl === 'peer-reviewed article' && rq.some(function (q) { return q !== 'peer-reviewed'; })) add('check', 'The description says peer-reviewed and a qualifier says otherwise. Use Journal Article with the qualifier.');
    if (tl === 'peer-reviewed article' && rq.length === 1 && rq[0] === 'peer-reviewed') add('note', 'Peer-Reviewed Article already says it, so the peer-reviewed qualifier can go.');
    if (has(quals, 'review status unclear')) add('note', 'Review status not established. Treat the article as unreviewed until the journal\'s own statement says otherwise.');
    var rawPub = clean(st.publisher);
    if (tl === 'trade book' && UNI_PRESS.test(rawPub)) add('note', 'Trade Book from a university press. University presses publish both kinds. If it argues one thesis for specialists, with notes and a bibliography, Monograph fits better.');
    if (tl === 'monograph' && TRADE_HOUSE.test(rawPub)) add('note', 'Monograph from a commercial publisher. Books from trade houses are usually Trade Books, even when a scholar wrote them. Keep Monograph only if it is written for specialists.');
    if (st.type === 'social' && style !== 'plain' && words(title) > 15) add('note', 'The post title runs ' + words(title) + ' words. The opening words, about a dozen, are enough to identify the post. End with an ellipsis where you stop.');
    if (type && !LIB_INDEX[tl]) add('note', 'That description is not in the library. Fine if it fits in ten words; send a note so it can be added.');
    if (st.ai) add('note', 'Keep the prompt and transcript on file, and disclose the use in the piece itself as well as here.');
    if (!rating && !st.ai) add('note', 'No rating. Optional, but expected on any source a reader might question.');

    var order = { fix: 0, check: 1, note: 2 };
    checks.sort(function (a, b) { return order[a.level] - order[b.level]; });
    return { seg: seg, checks: checks, slots: slots, empty: false, rating: rating, zone: z };
  }

  function shortForms(st) {
    var style = st.titleStyle || 'quotes';
    var authors = lines(st.authors);
    var name = clean(st.shortName) || deriveName(authors);
    var full = cleanTitle(st.title, style);
    var t = cleanTitle(st.shortTitle, style) || deriveShortTitle(full);
    var useT = (st.shortUseTitle !== false || !name) && !!t;
    var L = normLocator(st.locator);
    var s = [], i = [];
    function push(x, it) { if (!x) return; var l = s[s.length - 1]; if (l && l.i === !!it) l.s += x; else s.push({ s: x, i: !!it }); }
    if (name) push(name);
    if (useT) {
      if (name) push(', ');
      if (style === 'quotes') {
        var endP = /[?!]$/.test(t);
        push('"' + t + (endP ? '' : (L ? ',' : '.')) + '"');
        if (L) push(' ' + L + '.');
      } else {
        push(t, style === 'italics');
        push(L ? ', ' + L + '.' : '.');
      }
    } else if (name) {
      push(L ? ', ' + L + '.' : (/\.$/.test(name) ? '' : '.'));
    }
    i.push({ s: 'Ibid.' + (L ? ', ' + L + '.' : ''), i: false });
    return { short: s, ibid: i, name: deriveName(authors), title: deriveShortTitle(full) };
  }

  function esc(s) { return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }
  function toHTML(seg, mode) {
    var t = mode === 'u' ? 'u' : 'i';
    return seg.map(function (x) { return x.i ? '<' + t + '>' + esc(x.s) + '</' + t + '>' : esc(x.s); }).join('');
  }
  function toMarkdown(seg) { return seg.map(function (x) { return x.i ? '*' + x.s + '*' : x.s; }).join(''); }
  function toPlain(seg) { return seg.map(function (x) { return x.s; }).join(''); }
  function joinSources(list) {
    var out = [];
    list.forEach(function (seg, n) {
      var copy = seg.map(function (x) { return { s: x.s, i: x.i }; });
      if (copy.length && n < list.length - 1) copy[copy.length - 1].s = copy[copy.length - 1].s.replace(/\.$/, '');
      if (n > 0) out.push({ s: '; ', i: false });
      out = out.concat(copy);
    });
    return out;
  }

  // ---- list files and exports ----
  var CRC_T = null;
  function crc32(b) {
    var n, k, c, i, crc = 0xFFFFFFFF;
    if (!CRC_T) { CRC_T = []; for (n = 0; n < 256; n++) { c = n; for (k = 0; k < 8; k++) c = (c & 1) ? (0xEDB88320 ^ (c >>> 1)) : (c >>> 1); CRC_T[n] = c >>> 0; } }
    for (i = 0; i < b.length; i++) crc = CRC_T[(crc ^ b[i]) & 0xFF] ^ (crc >>> 8);
    return (crc ^ 0xFFFFFFFF) >>> 0;
  }
  function utf8(s) { return new TextEncoder().encode(s); }
  function zipStore(files) {
    var parts = [], central = [], offset = 0, cdSize = 0, total = 0, pos = 0, out;
    function u16(n) { return [n & 255, (n >>> 8) & 255]; }
    function u32(n) { return [n & 255, (n >>> 8) & 255, (n >>> 16) & 255, (n >>> 24) & 255]; }
    files.forEach(function (f) {
      var name = utf8(f.name), crc = crc32(f.data), size = f.data.length;
      var local = [].concat(u32(0x04034b50), u16(20), u16(0x0800), u16(0), u16(0), u16(0x21), u32(crc), u32(size), u32(size), u16(name.length), u16(0));
      parts.push(new Uint8Array(local), name, f.data);
      central.push([new Uint8Array([].concat(u32(0x02014b50), u16(20), u16(20), u16(0x0800), u16(0), u16(0), u16(0x21), u32(crc), u32(size), u32(size), u16(name.length), u16(0), u16(0), u16(0), u16(0), u32(0), u32(offset))), name]);
      offset += local.length + name.length + size;
    });
    central.forEach(function (c) { parts.push(c[0], c[1]); cdSize += c[0].length + c[1].length; });
    parts.push(new Uint8Array([].concat(u32(0x06054b50), u16(0), u16(0), u16(files.length), u16(files.length), u32(cdSize), u32(offset), u16(0))));
    parts.forEach(function (p) { total += p.length; });
    out = new Uint8Array(total);
    parts.forEach(function (p) { out.set(p, pos); pos += p.length; });
    return out;
  }
  function xesc(s) { return String(s).replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F]/g, '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }
  function docxBytes(title, segLists, mode) {
    var FONT = '<w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:cs="Times New Roman"/>';
    function run(text, it, bold, sz) {
      sz = sz || 24;
      return '<w:r><w:rPr>' + FONT + (bold ? '<w:b/>' : '') + (it && mode !== 'u' ? '<w:i/>' : '') + '<w:sz w:val="' + sz + '"/><w:szCs w:val="' + sz + '"/>' + (it && mode === 'u' ? '<w:u w:val="single"/>' : '') + '</w:rPr><w:t xml:space="preserve">' + xesc(text) + '</w:t></w:r>';
    }
    var body = '';
    if (title) body += '<w:p><w:pPr><w:spacing w:after="240"/></w:pPr>' + run(title, false, true, 28) + '</w:p>';
    segLists.forEach(function (seg, n) {
      body += '<w:p><w:pPr><w:spacing w:after="160"/><w:ind w:left="432" w:hanging="432"/></w:pPr>' + run((n + 1) + '. ', false) + seg.map(function (x) { return run(x.s, x.i); }).join('') + '</w:p>';
    });
    var head = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n';
    var doc = head + '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>' + body + '<w:sectPr><w:pgSz w:w="12240" w:h="15840"/><w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" w:header="720" w:footer="720" w:gutter="0"/></w:sectPr></w:body></w:document>';
    var ct = head + '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>';
    var rels = head + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>';
    return zipStore([{ name: '[Content_Types].xml', data: utf8(ct) }, { name: '_rels/.rels', data: utf8(rels) }, { name: 'word/document.xml', data: utf8(doc) }]);
  }
  function mdText(title, segLists) {
    return (title ? '# ' + title + '\n\n' : '') + segLists.map(function (s, n) { return (n + 1) + '. ' + toMarkdown(s); }).join('\n') + '\n';
  }
  function csvCell(v) { v = String(v == null ? '' : v); return /[",\n\r]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v; }
  function csvText(states, typeLabels) {
    var rows = [['No.', 'Footnote', 'Short form', 'Source type', 'Authors', 'Editors', 'Translators', 'Contributors', 'Title', 'Title in English', 'Location', 'Kind of source', 'Details', 'Qualifiers', 'Original language', 'Access', 'Rating', 'Publisher', 'Date', 'Accessed', 'URL', 'Archive link', 'Archive captured', 'Locator', 'Commentary']];
    states.forEach(function (st, n) {
      var d = normDate(st.date), ppl = splitPeople(st);
      rows.push([n + 1, toPlain(build(st).seg), toPlain(shortForms(st).short), (typeLabels && typeLabels[st.type]) || st.type || '',
        lines(st.authors).join('; '), ppl.ed.join('; '), ppl.trans.join('; '), ppl.contr.join('; '), cleanTitle(st.title, 'plain'), cleanTitle(st.transTitle, 'plain'),
        clean(st.location), clean(st.descType), lines(st.descDetails).join('; '), (Array.isArray(st.quals) ? st.quals : []).join('; '), clean(st.origLang),
        accessOf(st).join('; '), /^[A-F][1-6]$/.test(st.rating || '') ? st.rating : '', clean(st.publisher),
        ((st.dateKind === 'updated' || st.dateKind === 'captured') && d.text ? st.dateKind + ' ' : '') + d.text, normDate(st.accessed).text,
        normUrl(st.url).url, normUrl(st.archiveUrl).url, normDate(st.archiveDate).text, normLocator(st.locator), clean(st.note)]);
    });
    return '﻿' + rows.map(function (r) { return r.map(csvCell).join(','); }).join('\r\n') + '\r\n';
  }
  function listFile(name, items) {
    return JSON.stringify({
      app: 'OSINT Citation Generator', format: 2, name: name || '', savedAt: new Date().toISOString(),
      sources: items.map(function (x) { return { id: x.id, footnote: toMarkdown(build(x.st).seg), fields: x.st }; })
    }, null, 2) + '\n';
  }
  function parseListFile(text, typeNames, textKeys) {
    var data;
    try { data = JSON.parse(String(text).replace(/^﻿/, '')); } catch (e) { return { error: 'That is not a list file from this tool. It could not be read.' }; }
    var arr = Array.isArray(data) ? data : (data && Array.isArray(data.sources) ? data.sources : null);
    if (!arr) return { error: 'That is not a list file from this tool. It holds no source list.' };
    function strArr(v) {
      var a = Array.isArray(v) ? v : (typeof v === 'string' && v ? [v] : []);
      return a.filter(function (x) { return typeof x === 'string'; }).map(function (x) { return x.slice(0, 200); }).slice(0, 40);
    }
    var items = [], seen = {};
    arr.slice(0, 5000).forEach(function (x, n) {
      var f = x && typeof x === 'object' ? (x.fields || x.st) : null;
      if (!f || typeof f !== 'object') return;
      var st = {};
      textKeys.forEach(function (k) { st[k] = typeof f[k] === 'string' ? f[k].slice(0, 8000) : ''; });
      st.type = typeNames.indexOf(f.type) !== -1 ? f.type : 'web';
      st.access = strArr(f.access); st.quals = strArr(f.quals);
      st.shortUseTitle = f.shortUseTitle !== false;
      var up = upgradeState({ editors: st.editors, translators: st.translators, contributors: st.contributors,
        contribs: typeof f.contribs === 'string' ? f.contribs.slice(0, 8000) : '', contribRole: typeof f.contribRole === 'string' ? f.contribRole : '',
        transTitle: st.transTitle, origLang: st.origLang, transBy: st.transBy, langMode: f.langMode });
      st.editors = up.editors; st.translators = up.translators; st.contributors = up.contributors; st.langMode = up.langMode;
      if (build(st).empty) return;
      var id = typeof x.id === 'string' && x.id && x.id.length <= 80 ? x.id : 'f' + n + '-' + Math.floor(Math.random() * 1e9);
      if (seen[id]) id += '-' + n;
      seen[id] = 1;
      items.push({ id: id, st: st });
    });
    return { name: data && typeof data.name === 'string' ? data.name.slice(0, 200) : '', items: items };
  }

  // ---- reading a link: what the address alone can tell us ----
  // Each entry: host -> [source type, location, kind of source, extra fields].
  var SITES = {
    'nytimes.com': ['news', 'The New York Times', 'News Article'], 'washingtonpost.com': ['news', 'The Washington Post', 'News Article'],
    'wsj.com': ['news', 'The Wall Street Journal', 'News Article'], 'ft.com': ['news', 'Financial Times', 'News Article'],
    'reuters.com': ['news', 'Reuters', 'Wire Service Report'], 'apnews.com': ['news', 'AP News', 'Wire Service Report'],
    'bbc.com': ['news', 'BBC News', 'News Article'], 'bbc.co.uk': ['news', 'BBC News', 'News Article'],
    'theguardian.com': ['news', 'The Guardian', 'News Article'], 'economist.com': ['news', 'The Economist', 'Magazine Article'],
    'bloomberg.com': ['news', 'Bloomberg', 'News Article'], 'politico.com': ['news', 'Politico', 'News Article'], 'politico.eu': ['news', 'Politico', 'News Article'],
    'aljazeera.com': ['news', 'Al Jazeera', 'News Article'], 'cnn.com': ['news', 'CNN', 'News Article'], 'npr.org': ['news', 'NPR', 'News Article'],
    'axios.com': ['news', 'Axios', 'News Article'], 'thehill.com': ['news', 'The Hill', 'News Article'], 'propublica.org': ['news', 'ProPublica', 'Investigative Report'],
    'foreignpolicy.com': ['news', 'Foreign Policy', 'Magazine Article'], 'foreignaffairs.com': ['news', 'Foreign Affairs', 'Magazine Article'],
    'theatlantic.com': ['news', 'The Atlantic', 'Magazine Article'], 'thediplomat.com': ['news', 'The Diplomat', 'Magazine Article'],
    'defensenews.com': ['news', 'Defense News', 'News Article'], 'breakingdefense.com': ['news', 'Breaking Defense', 'News Article'],
    'twz.com': ['news', 'The War Zone', 'News Article'], 'navalnews.com': ['news', 'Naval News', 'News Article'], 'news.usni.org': ['news', 'USNI News', 'News Article'],
    'janes.com': ['news', 'Janes', 'News Article'], 'militarytimes.com': ['news', 'Military Times', 'News Article'], 'stripes.com': ['news', 'Stars and Stripes', 'News Article'],
    'c4isrnet.com': ['news', 'C4ISRNET', 'News Article'], 'kyivindependent.com': ['news', 'The Kyiv Independent', 'News Article'], 'kyivpost.com': ['news', 'Kyiv Post', 'News Article'],
    'meduza.io': ['news', 'Meduza', 'News Article'], 'themoscowtimes.com': ['news', 'The Moscow Times', 'News Article'], 'scmp.com': ['news', 'South China Morning Post', 'News Article'],
    'japantimes.co.jp': ['news', 'The Japan Times', 'News Article'], 'asia.nikkei.com': ['news', 'Nikkei Asia', 'News Article'], 'timesofisrael.com': ['news', 'The Times of Israel', 'News Article'],
    'haaretz.com': ['news', 'Haaretz', 'News Article'], 'dw.com': ['news', 'DW', 'News Article'], 'france24.com': ['news', 'France 24', 'News Article'],
    'rferl.org': ['news', 'Radio Free Europe/Radio Liberty', 'News Article'],
    'tass.com': ['news', 'TASS', 'State Media Report'], 'rt.com': ['news', 'RT', 'State Media Report'], 'sputnikglobe.com': ['news', 'Sputnik', 'State Media Report'],
    'xinhuanet.com': ['news', 'Xinhua', 'State Media Report'], 'news.cn': ['news', 'Xinhua', 'State Media Report'], 'globaltimes.cn': ['news', 'Global Times', 'State Media Report'],
    'chinadaily.com.cn': ['news', 'China Daily', 'State Media Report'], 'cgtn.com': ['news', 'CGTN', 'State Media Report'], 'presstv.ir': ['news', 'Press TV', 'State Media Report'],
    'kcna.kp': ['news', 'KCNA', 'State Media Report'], 'irna.ir': ['news', 'IRNA', 'State Media Report'],
    'warontherocks.com': ['web', 'War on the Rocks', 'Defense Analysis Article'], 'mwi.westpoint.edu': ['web', 'Modern War Institute', 'Defense Analysis Article'],
    'csis.org': ['web', 'CSIS', 'Policy Analysis'], 'brookings.edu': ['web', 'Brookings', 'Policy Analysis'], 'carnegieendowment.org': ['web', 'Carnegie Endowment for International Peace', 'Policy Analysis'],
    'atlanticcouncil.org': ['web', 'Atlantic Council', 'Policy Analysis'], 'cnas.org': ['web', 'CNAS', 'Policy Analysis'], 'iiss.org': ['web', 'IISS', 'Policy Analysis'],
    'rusi.org': ['web', 'RUSI', 'Policy Analysis'], 'cfr.org': ['web', 'Council on Foreign Relations', 'Policy Analysis'], 'chathamhouse.org': ['web', 'Chatham House', 'Policy Analysis'],
    'ecfr.eu': ['web', 'ECFR', 'Policy Analysis'], 'fpri.org': ['web', 'FPRI', 'Policy Analysis'], 'lowyinstitute.org': ['web', 'Lowy Institute', 'Policy Analysis'],
    'stimson.org': ['web', 'Stimson Center', 'Policy Analysis'], '38north.org': ['web', '38 North', 'Policy Analysis'], 'jamestown.org': ['web', 'The Jamestown Foundation', 'Policy Analysis'],
    'sipri.org': ['web', 'SIPRI', 'Policy Analysis'], 'rand.org': ['web', 'RAND', 'Think Tank Report'],
    'understandingwar.org': ['web', 'Institute for the Study of War', 'Campaign Assessment'], 'criticalthreats.org': ['web', 'Critical Threats', 'Campaign Assessment'],
    'bellingcat.com': ['web', 'Bellingcat', 'Open-Source Investigation'], 'lawfaremedia.org': ['web', 'Lawfare', 'Expert Commentary'], 'justsecurity.org': ['web', 'Just Security', 'Expert Commentary'],
    'substack.com': ['web', 'Substack', 'Newsletter Article'], 'medium.com': ['web', 'Medium', 'Blog Post'], 'wikipedia.org': ['web', 'Wikipedia', 'Wiki Article'],
    'ssrn.com': ['journal', 'SSRN', 'Preprint Paper'],
    'whitehouse.gov': ['web', 'White House Government Website', 'Government Web Page', { publisher: 'US Government' }],
    'defense.gov': ['web', 'Defense Department Website', 'Government Web Page', { publisher: 'US Government' }], 'war.gov': ['web', 'Defense Department Website', 'Government Web Page', { publisher: 'US Government' }],
    'state.gov': ['web', 'State Department Website', 'Government Web Page', { publisher: 'US Government' }], 'justice.gov': ['web', 'US Dept. of Justice Website', 'Government Web Page', { publisher: 'US Government' }],
    'treasury.gov': ['web', 'US Treasury Dept. Website', 'Government Web Page', { publisher: 'US Government' }],
    'sanctionslist.ofac.treas.gov': ['live', 'US Treasury Dept. Website', 'Sanctions List', { publisher: 'US Government', authors: 'US Department of the Treasury' }],
    'crsreports.congress.gov': ['report', 'CRS Reports Website', 'CRS Report', { publisher: 'US Congress', authors: 'Congressional Research Service' }],
    'congress.gov': ['web', 'Congress.gov', 'Government Web Page', { publisher: 'US Congress' }], 'gao.gov': ['report', 'GAO Website', 'GAO Report', { publisher: 'GAO', authors: 'US Government Accountability Office' }],
    'federalregister.gov': ['web', 'Federal Register', 'Federal Register Notice', { publisher: 'US Government' }], 'archives.gov': ['archival', 'US National Archives Website', 'Archival Material'],
    'gov.uk': ['web', 'UK Government Website', 'Government Web Page', { publisher: 'UK Government' }], 'nato.int': ['web', 'NATO Website', 'NATO Publication', { publisher: 'NATO' }],
    'un.org': ['web', 'UN Website', '', { publisher: 'UN' }], 'undocs.org': ['report', 'UN Website', '', { publisher: 'UN' }], 'iaea.org': ['web', 'IAEA Website', '', { publisher: 'IAEA' }],
    'flightradar24.com': ['live', 'Flightradar24', 'Flight Tracking Data'], 'adsbexchange.com': ['live', 'ADS-B Exchange', 'Flight Tracking Data'],
    'marinetraffic.com': ['live', 'MarineTraffic', 'Ship Tracking (AIS)'], 'vesselfinder.com': ['live', 'VesselFinder', 'Ship Tracking (AIS)'],
    'liveuamap.com': ['live', 'Liveuamap', 'Interactive Map'], 'deepstatemap.live': ['live', 'DeepStateMAP', 'Control-of-Terrain Map'],
    'facebook.com': ['social', 'Facebook', 'Social Media Post'], 'instagram.com': ['social', 'Instagram', 'Social Media Post'], 'threads.net': ['social', 'Threads', 'Social Media Post'],
    'threads.com': ['social', 'Threads', 'Social Media Post'], 'linkedin.com': ['social', 'LinkedIn', 'Social Media Post'], 'reddit.com': ['social', 'Reddit', 'Forum Post'],
    'vk.com': ['social', 'VK', 'Social Media Post'], 'weibo.com': ['social', 'Weibo', 'Social Media Post'], 'truthsocial.com': ['social', 'Truth Social', 'Social Media Post'],
    'vimeo.com': ['video', 'Vimeo', 'Video'], 'rumble.com': ['video', 'Rumble', 'Video'], 'odysee.com': ['video', 'Odysee', 'Video']
  };
  var ARCHIVE_HOSTS = ['archive.ph', 'archive.today', 'archive.is', 'archive.md', 'archive.li', 'archive.vn', 'archive.fo'];
  var TRACKERS = /^(utm_[a-z_]+|fbclid|gclid|dclid|msclkid|mc_cid|mc_eid|igshid|igsh|ref_src|ref_url|smid|smtyp|cmpid|ocid|ncid|taid|at_medium|at_campaign|__twitter_impression)$/i;
  var B32 = '234567abcdefghijklmnopqrstuvwxyz';

  function siteFor(host) {
    var h = host, i;
    while (h) { if (SITES[h]) return SITES[h]; i = h.indexOf('.'); if (i < 0) break; h = h.slice(i + 1); }
    return null;
  }
  function utcDate(ms) { var d = new Date(ms); return pad2(d.getUTCDate()) + ' ' + MONTHS[d.getUTCMonth()] + ' ' + d.getUTCFullYear(); }
  function shiftRight(idText, bits) {
    if (typeof BigInt !== 'function') return NaN;
    try { return Number(BigInt(idText) >> BigInt(bits)); } catch (e) { return NaN; }
  }
  function clockOf(t) {
    var m = String(t).match(/^(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s?)?$/), secs, h, mi, s;
    if (!m || !(m[1] || m[2] || m[3])) return '';
    secs = (+m[1] || 0) * 3600 + (+m[2] || 0) * 60 + (+m[3] || 0);
    if (!secs) return '';
    h = Math.floor(secs / 3600); mi = Math.floor((secs % 3600) / 60); s = secs % 60;
    return (h ? h + ':' + pad2(mi) : String(mi)) + ':' + pad2(s);
  }
  function parseUrl(s) {
    var u;
    try { u = new URL(s); } catch (e) { return null; }
    if (!/^https?:$/.test(u.protocol) || u.hostname.indexOf('.') < 0) return null;
    return u;
  }

  function readLink(raw, nowMs, todayText) {
    var now = nowMs || Date.now(), s = String(raw == null ? '' : raw).trim(), u, m, f = {}, notes = [], type = '', known = false;
    if (!s || /\s/.test(s)) return null;
    u = parseUrl(normUrl(s).url);
    if (!u) return null;
    var today = todayText || utcDate(now);
    var host = u.hostname.toLowerCase().replace(/^(www|m|mobile)\./, '');

    // An archive link: keep it as the archive, and read the original address and capture date out of it.
    var orig = '';
    if (host === 'web.archive.org' && (m = u.pathname.match(/^\/web\/(\d{4})(\d{2})(\d{2})\d{0,6}[a-z_]*\/(.+)$/))) orig = m[4];
    else if (ARCHIVE_HOSTS.indexOf(host) !== -1) {
      if ((m = u.pathname.match(/^\/(\d{4})\.(\d{2})\.(\d{2})-\d{6}\/(.+)$/))) orig = m[4];
      else { f.archiveUrl = u.href; notes.push('This is an archive link with no original address in it. Paste the original link too.'); return { type: '', fields: f, notes: notes, known: false }; }
    }
    if (orig) {
      var inner = parseUrl(normUrl(orig + u.search + u.hash).url);
      f.archiveUrl = u.href;
      if (+m[2] >= 1 && +m[2] <= 12 && +m[3] >= 1 && +m[3] <= 31) f.archiveDate = pad2(+m[3]) + ' ' + MONTHS[+m[2] - 1] + ' ' + m[1];
      notes.push('This is an archive link, so it went in as the archive copy and the original address was read from it.');
      if (!inner) return { type: '', fields: f, notes: notes, known: false };
      u = inner; host = u.hostname.toLowerCase().replace(/^(www|m|mobile)\./, '');
    }

    function dateFromId(ms, minYear, why) {
      if (isFinite(ms) && ms >= Date.UTC(minYear, 0, 1) && ms <= now + 1728e5) { f.date = utcDate(ms); notes.push(why); }
    }
    function dropParams(test) {
      var keep = [], dropped = false;
      u.searchParams.forEach(function (v, k) { if (test(k)) dropped = true; else keep.push([k, v]); });
      if (!dropped) return;
      u.search = '';
      keep.forEach(function (kv) { u.searchParams.append(kv[0], kv[1]); });
    }
    var seg = u.pathname.split('/').filter(Boolean), handleNote = 'The author is the handle from the link. Use the account name instead if it differs.';
    dropParams(function (k) { return TRACKERS.test(k); });
    if (/^#:~:/.test(u.hash)) u.hash = '';

    if (host === 'x.com' || host === 'twitter.com') {
      type = 'social'; known = true; f.location = 'X'; f.descType = 'Social Media Post';
      if (seg.length >= 3 && seg[1] === 'status' && /^\d+$/.test(seg[2])) {
        if (!/^(i|intent|home|search)$/.test(seg[0])) { f.authors = '@' + seg[0]; notes.push(handleNote); }
        if (seg[2].length >= 15) dateFromId(shiftRight(seg[2], 22) + 1288834974657, 2010, 'The date was read from the post ID and is in UTC.');
        u.search = ''; u.pathname = '/' + seg.slice(0, 3).join('/');
      } else if (seg.length === 1) { f.authors = '@' + seg[0]; f.descType = 'Account Profile'; }
    } else if (host === 't.me' || host === 'telegram.me') {
      type = 'social'; known = true; f.location = 'Telegram'; f.descType = 'Channel Post';
      if (seg[0] === 's') { seg = seg.slice(1); u.pathname = '/' + seg.join('/'); }
      if (seg[0] === 'c') notes.push('This is a private-channel link. Readers without access cannot open it, so say that in the commentary.');
      else if (seg[0] && !/^(joinchat|addstickers|share|\+)/.test(seg[0])) { f.authors = seg[0]; notes.push('The author is the channel name from the link. Use the channel\'s display name if it differs.'); }
    } else if (host === 'youtube.com' || host === 'youtu.be' || host === 'music.youtube.com') {
      type = 'video'; known = true; f.location = 'YouTube'; f.descType = seg[0] === 'shorts' ? 'Short-Form Video' : 'Video';
      var t = clockOf(u.searchParams.get('t') || u.searchParams.get('start') || '');
      if (t) { f.locator = 'See ' + t; notes.push('The link pointed at a moment in the video, which went in as the locator.'); }
      dropParams(function (k) { return /^(si|feature|pp|t|start)$/.test(k); });
    } else if (host === 'tiktok.com') {
      type = 'social'; known = true; f.location = 'TikTok'; f.descType = 'Short-Form Video';
      if (seg[0] && seg[0].charAt(0) === '@') { f.authors = seg[0]; notes.push(handleNote); }
      if (seg[1] === 'video' && /^\d{17,}$/.test(seg[2] || '')) dateFromId(shiftRight(seg[2], 32) * 1000, 2016, 'The date was read from the video ID and is in UTC.');
      u.search = '';
    } else if (host === 'bsky.app') {
      type = 'social'; known = true; f.location = 'Bluesky'; f.descType = 'Social Media Post';
      if (seg[0] === 'profile' && seg[1]) { f.authors = '@' + seg[1]; notes.push(handleNote); }
      if (seg[2] === 'post' && /^[234567a-z]{13}$/.test(seg[3] || '')) {
        var v = 0, i;
        for (i = 0; i < 13; i++) v = v * 32 + B32.indexOf(seg[3].charAt(i));
        dateFromId(v / 1024 / 1000, 2022, 'The date was read from the post ID and is in UTC.');
      }
    } else if (host === 'discord.com' || host === 'discordapp.com') {
      type = 'social'; known = true; f.location = 'Discord'; f.descType = 'Group Chat Message';
      if (seg[0] === 'channels' && /^\d{15,}$/.test(seg[3] || '')) dateFromId(shiftRight(seg[3], 22) + 1420070400000, 2015, 'The date was read from the message ID and is in UTC.');
      notes.push('Discord links open only for members of that server, so say that in the commentary.');
    } else if (host === 'github.com' && seg.length >= 2) {
      type = 'web'; known = true; f.location = 'GitHub'; f.descType = 'Code Repository'; f.authors = seg[0]; f.title = seg[1];
    } else if (host === 'arxiv.org' && (m = u.pathname.match(/^\/(?:abs|pdf)\/(\d{2})(\d{2})\.\d{4,5}/))) {
      type = 'journal'; known = true; f.location = 'arXiv'; f.descType = 'Preprint Paper';
      if (+m[2] >= 1 && +m[2] <= 12) { f.date = MONTHS[+m[2] - 1] + ' 20' + m[1]; notes.push('The month was read from the arXiv number.'); }
    } else if (host === 'doi.org') {
      type = 'journal'; known = true;
    } else if ((host === 'google.com' && seg[0] === 'maps') || host === 'maps.google.com' || host === 'earth.google.com') {
      type = 'imagery'; known = true; f.location = host === 'earth.google.com' ? 'Google Earth' : 'Google Maps'; f.accessed = today;
      if ((m = u.pathname.match(/@(-?\d{1,2}\.\d+),(-?\d{1,3}\.\d+)/))) {
        f.descDetails = Math.abs(+m[1]).toFixed(4) + '° ' + (+m[1] < 0 ? 'S' : 'N') + ', ' + Math.abs(+m[2]).toFixed(4) + '° ' + (+m[2] < 0 ? 'W' : 'E');
        notes.push('The coordinates were read from the link.');
      }
    } else {
      var site = siteFor(host);
      if (site) {
        type = site[0]; known = true; f.location = site[1];
        if (site[2]) f.descType = site[2];
        if (site[3]) Object.keys(site[3]).forEach(function (k) { f[k] = site[3][k]; });
        if (host.slice(-13) === '.substack.com') f.publisher = host.slice(0, -13);
        if (host === 'instagram.com' && (seg[0] === 'reel' || seg[0] === 'reels')) f.descType = 'Short-Form Video';
        if (host === 'reddit.com' && seg[0] === 'r' && seg[1]) f.descDetails = 'r/' + seg[1];
        if ((host === 'threads.net' || host === 'threads.com' || host === 'truthsocial.com') && seg[0] && seg[0].charAt(0) === '@') { f.authors = seg[0]; notes.push(handleNote); }
        if (type === 'live') f.accessed = today;
      } else if (/\.(gov|mil)$/.test(host)) {
        type = 'web'; f.descType = 'Government Web Page';
      }
    }
    var pdf = /\.pdf$/i.test(u.pathname);
    if (pdf && (type === 'web' || type === 'news' || type === '')) { type = 'report'; if (f.descType === 'Government Web Page') delete f.descType; }

    // A date in the path, unless the path is an upload folder (those carry the upload month, not the publication date).
    if (!f.date && !/\/(wp-content|uploads|files|sites\/default|media|assets|images|static)\//i.test(u.pathname)) {
      var p = u.pathname;
      if ((m = p.match(/\/((?:19|20)\d{2})[\/-](\d{1,2})[\/-](\d{1,2})(?:[\/-]|$)/)) || (m = p.match(/\/((?:19|20)\d{2})(\d{2})(\d{2})(?:[\/-]|$)/)) || (m = p.match(/-((?:19|20)\d{2})-(\d{2})-(\d{2})(?:\/|$)/))) {
        if (+m[2] >= 1 && +m[2] <= 12 && +m[3] >= 1 && +m[3] <= 31) { f.date = pad2(+m[3]) + ' ' + MONTHS[+m[2] - 1] + ' ' + m[1]; notes.push('The date was read from the link. Check it against the page.'); }
      } else if ((m = p.match(/\/((?:19|20)\d{2})\/(\d{1,2})\//)) && +m[2] >= 1 && +m[2] <= 12) {
        f.date = MONTHS[+m[2] - 1] + ' ' + m[1]; notes.push('Only the month is in the link. Add the day from the page.');
      }
    }
    if (!known && !f.descType) notes.push('This site is not one the tool knows, so only the link' + (f.date ? ' and date were' : ' was') + ' read.');
    f.url = u.href;
    return { type: type, fields: f, notes: notes, known: known };
  }

  // ---- auditing a whole list ----
  function auditList(states) {
    var rows = [], flagged = {}, byUrl = {}, byShort = {}, unrated = 0, total = 0;
    states.forEach(function (st, i) {
      var n = i + 1, r = build(st), u, sf;
      if (r.empty) return;
      total++;
      r.checks.forEach(function (c) { if (c.level !== 'note') { rows.push({ n: n, level: c.level, msg: c.msg }); flagged[n] = 1; } });
      if (!r.rating && !st.ai) unrated++;
      u = normUrl(st.url).url.replace(/#.*$/, '').replace(/\/$/, '');
      if (u) (byUrl[u] = byUrl[u] || []).push(n);
      sf = toPlain(shortForms(Object.assign({}, st, { locator: '' })).short);
      if (sf) (byShort[sf] = byShort[sf] || []).push({ n: n, u: u });
    });
    Object.keys(byUrl).forEach(function (u) {
      var g = byUrl[u];
      if (g.length < 2) return;
      rows.push({ n: g[0], nums: g, level: 'check', msg: 'Sources ' + listJoin(g.map(String)) + ' cite the same link. If this is one source cited more than once, keep one entry and use its short form for the later citations.' });
      g.forEach(function (x) { flagged[x] = 1; });
    });
    Object.keys(byShort).forEach(function (k) {
      var g = byShort[k], sameLink = g.every(function (x) { return x.u && x.u === g[0].u; }), nums;
      if (g.length < 2 || sameLink) return;
      nums = g.map(function (x) { return x.n; });
      rows.push({ n: nums[0], nums: nums, level: 'check', msg: 'Sources ' + listJoin(nums.map(String)) + ' share the short form ' + k + ' Give each a short title that tells them apart.' });
      nums.forEach(function (x) { flagged[x] = 1; });
    });
    var order = { fix: 0, check: 1 };
    rows.sort(function (a, b) { return a.n - b.n || order[a.level] - order[b.level]; });
    return { total: total, attention: Object.keys(flagged).length, unrated: unrated, rows: rows };
  }

  var LIB_INDEX = {};
  function setLibrary(idx) { LIB_INDEX = idx || {}; }

  return { build: build, shortForms: shortForms, setLibrary: setLibrary, accessOf: accessOf, toHTML: toHTML, toMarkdown: toMarkdown, toPlain: toPlain, joinSources: joinSources, docxBytes: docxBytes, mdText: mdText, csvText: csvText, listFile: listFile, parseListFile: parseListFile, readLink: readLink, auditList: auditList, splitPeople: splitPeople, langModeOf: langModeOf, upgradeState: upgradeState,
    normDate: normDate, normLocator: normLocator, normUrl: normUrl, zoneOf: zoneOf, REL: REL, CRED: CRED, ZNAME: ZNAME, MONTHS: MONTHS, esc: esc };
})();
var OSINT_DATA = (function () {
  var TYPES = {
    book: { label: 'Book', style: 'italics', picks: ["Monograph", "Trade Book", "Edited Volume", "Textbook", "Memoir", "Official History"], loc: 'Series, if the book belongs to one',
      advice: { when: ['', 'monograph', 'trade book'], lead: 'Monograph or Trade Book?', text: 'Look at the publisher and the back of the book. A university or academic press, with notes and a bibliography, written for specialists: Monograph. A commercial house, written for general readers: Trade Book, even when a scholar wrote it. If you cannot tell, use Trade Book.' },
      ph: { location: 'Usually blank for a book', publisher: 'Cornell University Press', descDetails: '', locator: '25-27' },
      sample: { authors: 'Michael Beckley', title: "Unrivaled: Why America Will Remain the World's Sole Superpower", descType: 'Monograph', publisher: 'Cornell University Press', date: '2018', locator: '25-27' } },
    journal: { label: 'Journal article', style: 'quotes', start: 'A for peer-reviewed research', picks: ["Peer-Reviewed Article", "Journal Article", "Review Article", "Law Review Article", "Preprint Paper", "Working Paper", "Conference Paper"], loc: 'Journal',
      advice: { when: ['', 'journal article'], lead: 'Not sure it was refereed?', text: 'Use Journal Article and set the review status below. Peer-Reviewed Article is for journals you know send work to outside referees.' },
      ph: { location: 'Journal of Strategic Studies', publisher: 'Leave blank', descDetails: 'Vol. 45, No. 2', locator: '201-225' },
      sample: { authors: 'Sebastian Rosato', title: 'The Flawed Logic of Democratic Peace Theory', location: 'The American Political Science Review', descType: 'Peer-Reviewed Article', descDetails: 'Vol. 97, No. 4', date: '2003', locator: '585-602' } },
    news: { label: 'News or magazine', style: 'quotes', dayDate: true, start: 'B for major outlets, B–C for local and regional media', picks: ["News Article", "News Analysis", "Feature Article", "Wire Service Report", "Investigative Report", "Magazine Article", "Editorial / Op-Ed", "Explainer", "State Media Report"], loc: 'Outlet',
      ph: { location: 'The New York Times', publisher: 'Leave blank', descDetails: '', locator: '' },
      sample: { authors: 'Jane Doe', title: 'Harbor Authority Confirms Second Dredging Contract', location: 'The Example Dispatch', descType: 'News Article', rating: 'B2', date: '12 February 2026', url: 'https://www.example.com/2026/02/12/harbor-dredging-contract' } },
    chapter: { label: 'Chapter or section', style: 'quotes', picks: ["Book Section", "Handbook Chapter", "Long-Form Publication by Think Tank", "Reference Work Entry", "Encyclopedia Article"], loc: 'Containing volume',
      ph: { location: 'Title of the book or report the chapter sits in', publisher: 'RAND', descDetails: '', locator: 'Full page range of the chapter' },
      sample: { authors: 'Michael S. Chase\nJeffrey Engstrom\nTai Ming Cheung\nKristen A. Gunness', title: "People's Liberation Army Modernization: Mid-1990s to 2025", location: "China's Incomplete Military Transformation: Assessing the Weaknesses of the People's Liberation Army (PLA)", descType: 'Long-Form Publication by Think Tank', publisher: 'RAND', date: '2015', locator: '13' } },
    web: { label: 'Website or think tank', style: 'quotes', dayDate: true, start: 'B for think tanks, C–D for blogs and independent analysts', picks: ["Defense Analysis Article", "Policy Analysis", "Policy Brief", "Think Tank Report", "Expert Commentary", "Blog Post", "Web Page", "Corporate Press Release"], loc: 'Site',
      ph: { location: 'War on the Rocks', publisher: 'Only if it differs from the site', descDetails: '', locator: '' },
      sample: { authors: 'Michael Kofman\nRob Lee', title: "Not Built for Purpose: The Russian Military's Ill-Fated Force Design", location: 'War on the Rocks', descType: 'Defense Analysis Article', rating: 'B2', date: '6/2/2022', url: 'https://warontherocks.com/2022/06/not-built-for-purpose-the-russian-militarys-ill-fated-force-design/' } },
    report: { label: 'Report or government document', style: 'italics', start: 'A for government documents, B for think tank and corporate reports', picks: ["Government Report", "CRS Report", "Think Tank Report", "Defense White Paper", "National Strategy Document", "GAO Report", "Whitepaper", "Research Report"], loc: 'Site or series',
      ph: { location: 'White House Government Website', publisher: 'US Government', descDetails: 'Report #R12345', locator: 'CMC Reorganization Section' },
      sample: { authors: 'The White House', title: 'National Security Strategy of the United States of America', location: 'White House Government Website', descType: 'National Strategy Document', rating: 'A1', publisher: 'US Government', date: 'Nov 2025', url: 'https://www.whitehouse.gov/wp-content/uploads/2025/12/2025-National-Security-Strategy.pdf' } },
    social: { label: 'Social media post', style: 'quotes', dayDate: true, volatile: true, start: 'C for accounts with a track record, D–F for anonymous channels', picks: ["Social Media Post", "Thread", "Channel Post", "Video Post", "Short-Form Video", "Forum Post", "Deleted Post (Archived)", "Screenshot (Provenance Unverified)"], loc: 'Platform', pub: 'Publisher (account, if different from the author)',
      authHint: 'The person, or the account as it appears.',
      titleHint: 'A post has no headline. Use its opening words exactly as written, about a dozen, and end with an ellipsis (…) if you stop short. Keep its spelling, capitals, and hashtags. If the post has no text, describe it in a few plain words and set it as Plain.',
      ph: { location: 'X', publisher: 'Account name', descDetails: 'deleted by 16 February 2026', locator: '' },
      sample: { authors: 'ExampleMonitor', title: 'Drone Footage Near the River Crossing', location: 'X', descType: 'Social Media Post', rating: 'C3', date: '14 February 2026', url: 'https://x.com/example_monitor/status/1234567890', archiveUrl: 'https://archive.ph/example', archiveDate: '14 February 2026' } },
    video: { label: 'Video or podcast', style: 'quotes', dayDate: true, start: 'C for channels with a track record', picks: ["Video", "Podcast", "Recorded Interview", "Lecture (Recorded)", "Combat Footage", "Livestream Archive"], loc: 'Platform', pub: 'Publisher (channel or show)',
      ph: { location: 'YouTube', publisher: 'Channel or show name', descDetails: 'Eps. 225', locator: 'See 30:15-32:40 for …' },
      sample: { authors: 'John Doe', title: 'How a Tiltrotor Moves from Hover to Forward Flight', location: 'YouTube', descType: 'Video', rating: 'C3', publisher: 'Example Aviation Channel', date: '17 March 2026', url: 'https://www.youtube.com/watch?v=EXAMPLE0000', locator: 'See 30:15-32:40 for discussion of airframe design' } },
    archival: { label: 'Primary or archival', style: 'quotes', start: 'A for documents in a formal archive', picks: ["Archival Material", "Primary Source", "Declassified Document", "Historical Document", "FOIA-Released Document", "Oral History", "Personal Papers"], loc: 'Archive',
      ph: { location: 'US National Archives Website', publisher: '', descDetails: 'Primary Source; Record Group 46', locator: '' },
      sample: { authors: 'James Monroe', title: 'Message of President James Monroe at the Commencement of the First Session of the 18th Congress (The Monroe Doctrine)', location: 'US National Archives Website', descType: 'Archival Material', descDetails: 'Primary Source; Record Group 46; Records of the US Senate, 1789–1990', date: '2 December 1823', url: 'https://www.archives.gov/milestone-documents/monroe-doctrine' } },
    live: { label: 'Live list or tracker', style: 'quotes', live: true, start: 'A for government registries', picks: ["Sanctions List", "Flight Tracking Data", "Ship Tracking (AIS)", "Business Registry Record", "Government Dataset", "Data Dashboard", "Patent Filing"], loc: 'Site',
      ph: { location: 'US Treasury Dept. Website', publisher: 'US Government', descDetails: '', locator: '' },
      sample: { authors: 'US Department of the Treasury', title: 'Specially Designated Nationals List', location: 'US Treasury Dept. Website', descType: 'Sanctions List', rating: 'A1', publisher: 'US Government', date: '08 March 2026', dateKind: 'updated', accessed: '11 March 2026', url: 'https://sanctionslist.ofac.treas.gov/Home/SdnList' } },
    imagery: { label: 'Satellite imagery', style: 'quotes', live: true, start: 'A for raw imagery', picks: ["Commercial Satellite Imagery", "Synthetic Aperture Radar Imagery", "Government Satellite Release", "Annotated Satellite Imagery", "Drone Footage", "Geotagged Photo", "CCTV Footage"], loc: 'Platform', pub: 'Publisher (provider)',
      authHint: 'The provider. A geolocation you worked out yourself belongs in the commentary, with the reasoning.',
      ph: { location: 'Planet Explorer', publisher: 'Planet Labs PBC', descDetails: '3 m resolution; 45.7086° N, 34.4142° E', locator: '' },
      sample: { authors: 'Planet Labs PBC', title: 'PlanetScope Imagery of Dzhankoi Airbase', location: 'Planet Explorer', descType: 'Commercial Satellite Imagery', descDetails: '3 m resolution; 45.7086° N, 34.4142° E', rating: 'B2', publisher: 'Planet Labs PBC', date: '09 March 2026', dateKind: 'captured', accessed: '11 March 2026', url: 'https://www.planet.com/explorer/' } },
    ai: { label: 'AI model output', style: 'quotes', ai: true, dayDate: true, start: 'F. Model output is F6 by default', picks: ["AI Model Output"], loc: 'Platform', pub: 'Publisher (developer)', auth: 'Model name and version',
      authHint: 'Give the version. A product name alone is not a citation.',
      ph: { location: 'Claude.ai', publisher: 'Anthropic', descDetails: 'prompt and full transcript on file', locator: '' },
      sample: { authors: 'Claude Opus 4.5', title: 'Summary of open-source reporting on PLA joint logistics', location: 'Claude.ai', descType: 'AI Model Output', descDetails: 'prompt and full transcript on file', rating: 'F6', publisher: 'Anthropic', date: '12 March 2026' } }
  };
  var LIB = [{"c": "Government and Legal", "g": [{"n": "Legislative", "i": ["Congressional Report", "CRS Report", "Parliamentary Report", "Public Law / Statute", "Testimony Transcript", "Hearing", "Bill", "Resolution", "Committee Report", "Conference Report", "Committee Print", "Prepared Testimony", "Legislative Debate Record", "Parliamentary Question", "Roll-Call Vote Record", "Legislative History", "Constitution", "Constitutional Amendment", "Local Ordinance"]}, {"n": "Executive and regulatory", "i": ["Government Report", "Ministry Publication", "Defense White Paper", "Executive Order", "Regulatory Filing", "Government Press Release", "Public Safety Announcement", "Presidential Proclamation", "Presidential Memorandum", "National Security Directive", "Signing Statement", "Decree", "Regulation", "Proposed Rule", "Final Rule", "Federal Register Notice", "Official Gazette Notice", "Agency Guidance", "Public Comment", "Government Fact Sheet", "National Strategy Document", "Government White Paper", "Consultation Paper", "Official Speech", "Official Statement", "Press Briefing Transcript", "Government Web Page", "Government Circular", "Travel Advisory", "Export Control List", "Commission Report", "Public Inquiry Report", "Environmental Impact Statement", "Official Biography"]}, {"n": "Party-state systems", "i": ["Party Document", "Party Congress Report", "Party Regulation", "State Planning Document"]}, {"n": "Courts and legal practice", "i": ["Court Record", "Legal Opinion", "Indictment", "Deposition", "Arbitration Ruling", "Court Opinion", "Dissenting Opinion", "Judgment", "Court Order", "Court Filing", "Legal Brief", "Amicus Brief", "Complaint", "Plea Agreement", "Sentencing Memorandum", "Affidavit", "Sworn Declaration", "Search Warrant", "Trial Transcript", "Trial Exhibit", "Oral Argument", "Docket Sheet", "Consent Decree", "Settlement Agreement", "Administrative Ruling", "Court-Martial Record", "Contract", "Legal Treatise"]}, {"n": "Budget, procurement, and oversight", "i": ["Budget Document", "Procurement Record", "Public Tender / Contract", "Inspector General Report", "Central Bank Report", "Budget Justification", "Contract Award Notice", "Grant Award Record", "Spending Database Record", "Audit Report", "GAO Report", "CBO Cost Estimate"]}, {"n": "Registries and public records", "i": ["Patent Filing", "Trademark Database", "Sanctions List", "Police Report", "Sanctions Designation Notice", "Land / Property Record", "Vital Record", "Professional License Record", "Accident Investigation Report", "Wanted Notice"]}, {"n": "Elections, lobbying, and disclosure", "i": ["Election Results", "Campaign Finance Filing", "Lobbying Disclosure", "Foreign Agent Registration", "Financial Disclosure", "Party Platform", "Campaign Material", "Ballot Measure"]}, {"n": "Intelligence and released records", "i": ["Intelligence Assessment", "FOIA-Released Document", "Declassified Document", "National Intelligence Estimate", "Threat Assessment", "MDR-Released Document"]}]}, {"c": "International Organizations and Diplomacy", "g": [{"n": "UN system", "i": ["UN Report", "UN Resolution", "Peacekeeping Report", "Secretary-General Report", "Panel of Experts Report", "Special Rapporteur Report", "Commission of Inquiry Report", "UN Meeting Record", "UN Voting Record", "Treaty Body Observations", "IAEA Report", "Inspection Report"]}, {"n": "Treaties and agreements", "i": ["Treaty", "Executive Agreement", "Convention", "Protocol", "Memorandum of Understanding", "Status of Forces Agreement", "Arms Control Agreement", "Peace Agreement", "Ceasefire Agreement", "Trade Agreement", "Treaty Reservation", "Negotiating Record"]}, {"n": "Diplomatic practice", "i": ["Diplomatic Cable", "Diplomatic Note", "Joint Statement", "Joint Communiqué", "Summit Declaration", "Foreign Ministry Briefing", "Official Readout"]}, {"n": "Alliances and regional bodies", "i": ["NATO Publication", "Regional Org Publication", "NATO Standardization Agreement", "EU Legal Act", "Council Conclusions"]}, {"n": "International finance and development", "i": ["World Bank Dataset", "IMF Report", "WHO Health Data", "WTO Trade Data", "OECD Report", "World Bank Report", "Development Bank Report", "IMF Country Report", "WTO Dispute Ruling"]}, {"n": "International courts and monitoring", "i": ["International Court Ruling", "Election Monitoring Report", "Advisory Opinion", "International Court Filing", "Arrest Warrant"]}]}, {"c": "Academic and Research", "g": [{"n": "Books", "i": ["Monograph", "Trade Book", "Edited Volume", "Book Section", "Textbook", "Open Textbook", "Handbook Chapter", "Scholarly Edition", "Anthology", "Collected Works", "Multivolume Work", "Memoir", "Autobiography", "Biography", "Published Diary", "Published Correspondence", "Published Document Collection", "Official History", "Self-Published Book", "Foreword or Introduction", "Exhibition Catalog", "Pamphlet"]}, {"n": "Journal literature", "i": ["Peer-Reviewed Article", "Journal Article", "Literature Review", "Meta-Analysis", "Review Article", "Systematic Review", "Book Review", "Review Essay", "Research Note", "Scholarly Commentary", "Reply or Rejoinder", "Journal Editorial", "Special Issue Introduction", "Forum Contribution", "Case Study", "Replication Study", "Registered Report", "Data Paper", "Law Review Article", "Student Note", "Professional Journal Article", "Abstract", "Erratum", "Retraction Notice"]}, {"n": "Research papers and reports", "i": ["Working Paper", "Whitepaper", "Preprint Paper", "Research Report", "Field Research Report", "Technical Report", "Occasional Paper", "Discussion Paper", "Research Brief", "Pre-Registration", "Research Protocol", "Grant Proposal"]}, {"n": "Degrees and student work", "i": ["Dissertation", "Thesis", "Undergraduate Thesis", "Capstone Project", "Student Paper"]}, {"n": "Conferences and talks", "i": ["Conference Paper", "Lecture (Recorded)", "Conference Proceedings", "Conference Abstract", "Conference Poster", "Conference Presentation", "Keynote Address", "Panel Discussion", "Webinar", "Workshop Report"]}, {"n": "Unpublished and in progress", "i": ["Unpublished Manuscript", "Forthcoming Work", "Unpublished Data"]}]}, {"c": "Reference, Data, and Statistics", "g": [{"n": "Reference entries", "i": ["Reference Work Entry", "Encyclopedia Article", "Dictionary Entry", "Biographical Entry", "Wiki Article", "Country Profile"]}, {"n": "Reference volumes", "i": ["Statistical Yearbook", "Factbook", "Handbook", "Almanac", "Atlas", "Gazetteer", "Bibliography", "Annotated Bibliography", "Chronology", "Glossary", "Directory", "Style Manual", "Field Guide", "Library Catalog Record"]}, {"n": "Datasets", "i": ["Census Data", "Government Dataset", "Academic Dataset", "Index Dataset", "Data Aggregator", "Replication Data", "Event Dataset", "Time-Series Data", "Trade Statistics", "Database Record", "Codebook"]}, {"n": "Polling and surveys", "i": ["Public Opinion Poll", "Poll Crosstabs", "Survey Data", "Survey Instrument", "Expert Survey"]}, {"n": "Statistical products", "i": ["Statistical Release", "Data Dashboard", "Interactive Data Tool", "Forecast or Model Output", "Prediction Market Data"]}, {"n": "Charts and figures", "i": ["Reproduced Figure", "Data Visualization", "Infographic"]}]}, {"c": "Think Tank, Industry, and Finance", "g": [{"n": "Think tanks and policy shops", "i": ["Think Tank Report", "Policy Brief", "Policy Analysis", "Strategic Report", "Issue Brief", "Backgrounder", "Expert Commentary", "Task Force Report", "Scenario Study", "Event Transcript", "Interactive Tracker", "Sponsored Research Report", "Advocacy Group Report", "Consultancy Report"]}, {"n": "Corporate disclosure", "i": ["Quarterly Report", "Annual Report", "Investor Presentation", "SEC Filing", "Earnings Call Transcript", "Corporate Press Release", "M&A Filing", "Bankruptcy Record", "Stock Exchange Filing", "Prospectus", "Proxy Statement", "Financial Statement", "Auditor Report", "Sustainability Report", "Shareholder Letter", "Corporate Blog Post", "Company Web Page", "Job Posting"]}, {"n": "Markets and finance", "i": ["Credit Rating Report", "Market Research Report", "Analyst Note", "Market Data", "Commodity Price Data"]}, {"n": "Trade and industry", "i": ["Industry Whitepaper", "Trade Journal Article", "Professional Association Report", "Technical Standard", "Product Datasheet", "Product Brochure", "Product Catalog", "Trade Show Material", "User Manual", "Safety Data Sheet", "Business Survey"]}, {"n": "Ownership and commercial records", "i": ["Business Registry Record", "Ownership Database", "Beneficial Ownership Record", "Customs Record", "Bill of Lading", "Vessel Registry Record", "Aircraft Registry Record", "Insurance Record"]}]}, {"c": "News and Media", "g": [{"n": "Reporting", "i": ["News Article", "News Report", "Wire Service Report", "Investigative Report", "Magazine Article", "Newsletter Article", "Journalist Newsletter", "Fact-Check", "Conflict Reporting Platform", "Feature Article", "Live Blog", "News Brief", "Explainer", "Published Interview", "Profile", "Obituary", "Local News Report", "Student Newspaper Article", "Historical Newspaper Article", "Press Pool Report", "Aggregated News Report"]}, {"n": "Opinion and analysis", "i": ["News Analysis", "Editorial / Op-Ed", "Column", "Letter to the Editor", "Editorial Cartoon", "Satire", "Sponsored Content"]}, {"n": "Broadcast, audio, and video", "i": ["Broadcast Transcript", "TV Broadcast", "Radio Broadcast", "Live-Streamed Broadcast", "Podcast", "Video", "Broadcast Interview", "Press Conference", "Video Essay", "Newsreel"]}, {"n": "State and party media", "i": ["State Media Report", "State Media Commentary", "Party Newspaper Editorial"]}, {"n": "Monitoring and translation", "i": ["Media Monitoring Translation", "Press Digest"]}, {"n": "Visual and data journalism", "i": ["News Photograph", "Photo Essay", "Data Journalism Article", "Interactive Feature"]}]}, {"c": "Social, Web, and User-Generated", "g": [{"n": "Posts", "i": ["Social Media Post", "Video Post", "Reposted Content", "Blog Post", "Comment Section", "Thread", "Reply", "Quote Post", "Story Post", "Short-Form Video", "Livestream", "Livestream Chat Log", "Comment", "Meme"]}, {"n": "Messaging and channels", "i": ["Channel Post", "Group Chat Message", "Direct Message", "Voice Message", "Forwarded Message", "Chat Log Export"]}, {"n": "Accounts and platform features", "i": ["Account Profile", "Account Metadata", "Professional Profile", "Community Note", "Social Network Data"]}, {"n": "Forums and community", "i": ["Forum Post", "Forum Discussion", "Crowdsourced Investigation", "Q&A Site Answer", "Wiki Edit History", "User Review", "Mailing List Post", "Petition", "Crowdfunding Page", "Marketplace Listing", "Memorial Page"]}, {"n": "Web pages", "i": ["Archived Web Content", "Web Page", "Personal Website", "About Page", "FAQ Page"]}, {"n": "Capture and provenance", "i": ["Screenshot (Provenance Verified)", "Screenshot (Provenance Unverified)", "Deleted Post (Archived)", "Edited Post (Archived)", "Screen Recording"]}, {"n": "Synthetic and inauthentic", "i": ["AI-Generated Image", "AI-Generated Video", "AI-Generated Audio", "Suspected Synthetic Media", "Manipulated Media", "Suspected Inauthentic Account Post"]}]}, {"c": "Imagery, Geospatial, and Tracking", "g": [{"n": "Overhead imagery", "i": ["Commercial Satellite Imagery", "Government Satellite Release", "Satellite Time-Series", "Remote Sensing Dataset", "Synthetic Aperture Radar Imagery", "Multispectral Imagery", "Thermal / Infrared Imagery", "Nighttime Lights Data", "Active Fire Data", "Aerial Photograph", "Historical Aerial Photograph", "Declassified Reconnaissance Imagery", "Annotated Satellite Imagery"]}, {"n": "Ground-level imagery and footage", "i": ["Geotagged Photo", "Drone Footage", "Photograph (Verified)", "Video Footage (Verified)", "Audio Recording", "Livestream Archive", "Photograph (Unverified)", "Video Footage (Unverified)", "Street-Level Imagery", "CCTV Footage", "Dashcam Footage", "Body-Camera Footage", "Helmet-Camera Footage", "Webcam Feed"]}, {"n": "Maps and geodata", "i": ["GIS Dataset", "OpenStreetMap Data", "Terrain / Elevation Model", "Maritime Tracking Map", "Map", "Topographic Map", "Nautical Chart", "Historical Map", "Control-of-Terrain Map", "Interactive Map", "Crowdsourced Map", "3D Reconstruction", "Administrative Boundary Data"]}, {"n": "Movement tracking", "i": ["Flight Tracking Data", "Ship Tracking (AIS)", "Rail Tracking Data", "Port Authority Log", "Vehicle Tracking Data", "Aviation Accident Database", "Port Call Record", "Satellite Orbit Data", "Launch Notification", "Fitness Tracker Data", "Commercial Location Data", "Vehicle Registration Record"]}, {"n": "Notices, signals, and sensors", "i": ["NOTAM", "Navigational Warning", "GPS Interference Data", "Scanner Audio", "Seismic Data", "Weather Data"]}, {"n": "Verification products", "i": ["Geolocation Analysis", "Chronolocation Analysis", "File Metadata", "Reverse Image Search Result", "Visual Forensic Analysis"]}]}, {"c": "Military and Defense", "g": [{"n": "Doctrine and manuals", "i": ["Military Doctrine Publication", "Training Manual (Public)", "Training Manual (Leaked)", "Field Manual", "Joint Publication", "Technical Manual", "Law of War Manual", "Rules of Engagement", "Service Strategy Document", "Posture Statement", "Operating Concept"]}, {"n": "Operational records", "i": ["After-Action Report", "Operations Order", "Situation Report", "War Diary", "Unit History", "Lessons-Learned Report", "Staff Study", "Captured Document", "Intercepted Communication", "Service Record", "Award Citation", "Casualty List"]}, {"n": "Assessments and estimates", "i": ["Defense Analysis Article", "Order of Battle Assessment", "Casualty Estimate", "Wargame or Simulation", "Net Assessment", "Campaign Assessment", "Daily Intelligence Update", "Equipment Loss Tally", "Exercise Report", "War College Paper"]}, {"n": "Force data and equipment", "i": ["Defense Procurement Database", "Arms Transfer Database", "Conflict Incident Database", "Military Reference Yearbook", "Table of Organization and Equipment", "Equipment Recognition Guide", "Weapons System Fact Sheet", "Selected Acquisition Report", "Arms Catalog", "End-User Certificate", "Arms Export License Record", "Weapons Tracing Report"]}, {"n": "Official messaging", "i": ["Defense Ministry Briefing", "Military Press Release", "Operational Update", "Exercise Announcement", "Recruitment Material"]}, {"n": "Personal and frontline accounts", "i": ["Veteran / Soldier Account", "Military Blogger Post", "POW Statement", "Combat Footage"]}, {"n": "Armed group and propaganda material", "i": ["Armed Group Statement", "Claim of Responsibility", "Propaganda Video", "Propaganda Magazine", "Propaganda Leaflet", "Manifesto", "Religious Ruling", "Leader Message"]}]}, {"c": "Cyber and Technical", "g": [{"n": "Threat reporting", "i": ["Threat Intelligence Report", "Malware Analysis", "Security Blog Post", "Dark Web Monitoring Report", "Data Breach Disclosure", "Security Advisory", "Security Incident Report", "Threat Actor Profile", "Indicators of Compromise", "Sandbox Analysis Report", "Detection Rule", "Takedown Report", "Platform Transparency Report"]}, {"n": "Vulnerabilities", "i": ["CVE / NVD Entry", "Vulnerability Disclosure", "Proof-of-Concept Code", "Bug Bounty Report"]}, {"n": "Infrastructure and network data", "i": ["Network Scanning Data", "Sensor Network Data", "Smart Device Metadata", "Blockchain Transaction Record", "WHOIS Record", "DNS Record", "Passive DNS Data", "Certificate Transparency Log", "BGP Routing Data", "Internet Outage Data", "IP Geolocation Data", "Packet Capture", "Log File", "Smart Contract"]}, {"n": "Code and software", "i": ["Code Repository", "Technical Documentation", "Software", "Code Commit", "Issue Tracker Entry", "Release Notes", "API Documentation", "Technical Specification", "Request for Comments", "Mobile App", "App Store Listing"]}, {"n": "Leaks and illicit markets", "i": ["Leaked Dataset", "Leaked Document", "Internal Document", "Leak Database Entry", "Leak Site Post", "Dark Web Forum Post", "Dark Web Marketplace Listing", "Ransom Note", "Hacktivist Claim", "Paste Site Post"]}, {"n": "AI systems", "i": ["AI Model Output", "Model Card", "Dataset Card", "Benchmark Result"]}, {"n": "Platform rules", "i": ["Terms of Service", "Privacy Policy", "Community Guidelines"]}]}, {"c": "Science, Health, and Environment", "g": [{"n": "Clinical and public health", "i": ["Clinical Trial Registration", "Clinical Trial Results", "Clinical Practice Guideline", "Case Report", "Epidemiological Bulletin", "Disease Outbreak Notice", "Drug or Device Approval Record"]}, {"n": "Science and environment", "i": ["Scientific Assessment Report", "Environmental Monitoring Data", "Laboratory Protocol"]}, {"n": "Specimens and sites", "i": ["Museum Specimen Record", "Taxonomic Description", "Archaeological Site Report"]}]}, {"c": "NGO, Humanitarian, and Civil Society", "g": [{"n": "Reports and investigations", "i": ["Human Rights Report", "Transparency Org Report", "Anti-Corruption Report", "Field Investigation Report", "Open-Source Investigation", "Shadow Report", "Press Freedom Report"]}, {"n": "Humanitarian operations", "i": ["Crisis / Relief Update", "NGO Data", "Humanitarian Situation Report", "Needs Assessment", "Casualty Recording Database", "Witness Testimony"]}, {"n": "Statements and filings", "i": ["Public Statement", "Open Letter", "Charity Filing", "Foundation Grant Record"]}]}, {"c": "Archival and Primary Sources", "g": [{"n": "Archival records", "i": ["Archival Material", "Primary Source", "Historical Document", "Manuscript", "Archival Collection", "Personal Papers", "Finding Aid", "Meeting Minutes", "Telegram", "Ledger", "Logbook", "Colonial Administrative Record", "Mission Record", "Church Record", "Genealogical Record", "Will or Probate Record", "Passenger List"]}, {"n": "Personal writing and testimony", "i": ["Letter", "Memo", "Diary Entry", "Field Notes", "Oral History", "Oral Tradition"]}, {"n": "Printed and recorded ephemera", "i": ["Broadside", "Leaflet", "Ephemera", "Newspaper Clipping", "Archival Photograph", "Archival Audio Recording"]}]}, {"c": "Interviews, Communications, and Author's Own Work", "g": [{"n": "Interviews", "i": ["Personal Interview", "Recorded Interview", "Anonymized Interview", "Background Briefing", "Focus Group", "Survey Response"]}, {"n": "Communications", "i": ["Personal Communication", "E-mail", "Phone Call", "Text Message", "Video Call", "Q&A Remarks"]}, {"n": "Fieldwork", "i": ["Field Observation", "Site Visit Notes"]}, {"n": "Author's own work", "i": ["Author's Calculation", "Author's Compilation", "Author's Translation", "Author's Photograph", "Author's Dataset", "Author's Figure"]}]}, {"c": "Literary, Artistic, and Creative Works", "g": [{"n": "Literature", "i": ["Novel", "Short Story", "Poem", "Play", "Essay", "Graphic Novel", "Comic"]}, {"n": "Classical and sacred texts", "i": ["Classical Text", "Sacred Text", "Chronicle"]}, {"n": "Film, television, and music", "i": ["Film", "Documentary Film", "Short Film", "Television Episode", "Television Series", "Screenplay", "Music Recording", "Song", "Music Video", "Musical Score"]}, {"n": "Art, objects, and performance", "i": ["Artwork", "Poster", "Museum Object", "Exhibition", "Monument or Inscription", "Live Performance"]}, {"n": "Games", "i": ["Video Game", "Tabletop Game", "Game Rulebook", "Game Scenario"]}]}, {"c": "Education, Institutional, and General", "g": [{"n": "Teaching materials", "i": ["Syllabus", "Lecture Notes", "Lecture Slides", "Course Reader", "Online Course Module", "Study Guide", "Lesson Plan", "Curriculum Standard", "Standardized Test Material"]}, {"n": "Institutional documents", "i": ["Course Catalog", "Accreditation Report", "Institutional Research Report", "Program Review", "Institutional Policy", "Strategic Plan", "Charter or Bylaws", "Code of Conduct", "Organization Chart", "Standard Operating Procedure", "Organizational Newsletter", "Résumé / CV"]}, {"n": "General", "i": ["Advertisement", "Presentation", "Speech", "Sermon", "Press Kit", "Flyer", "Sign or Signage", "Label or Packaging", "Receipt or Invoice", "Event Program", "Form or Questionnaire"]}]}];
  var QUALIFIERS = [["Provenance", ["leaked", "declassified", "FOIA-released", "redacted", "captured", "official release", "provenance verified", "provenance unverified"]], ["Version", ["preprint", "accepted manuscript", "version of record", "advance online", "draft", "forthcoming", "revised", "corrected", "retracted", "superseded"]], ["Review status", ["peer-reviewed", "editor-reviewed", "student-edited", "not peer-reviewed", "review status unclear"]], ["Format", ["transcript", "video", "audio", "scan", "facsimile", "microfilm", "e-book", "audiobook", "abstract only", "excerpt"]], ["Capture status", ["archived", "edited after capture", "screenshot only", "reupload"]], ["Interest", ["industry-funded", "government-funded", "sponsored", "state-affiliated", "author affiliated with subject"]], ["Synthetic content", ["AI-generated", "AI-assisted", "suspected synthetic", "digitally altered"]]];
  var ACCESS = [["paywalled", "Paywalled"], ["metered paywall", "Metered paywall"], ["free registration required", "Free registration required"], ["institutional access", "Institutional access"], ["region-restricted", "Region-restricted"], ["app only", "App only"], ["other", "Something else"]];
  var LIB_INDEX = {}; LIB.forEach(function (c) { c.g.forEach(function (g) { g.i.forEach(function (x) { LIB_INDEX[x.toLowerCase()] = 1; }); }); });
  OSINT.setLibrary(LIB_INDEX);
  return { TYPES: TYPES, LIB: LIB, QUALIFIERS: QUALIFIERS, ACCESS: ACCESS };
})();
