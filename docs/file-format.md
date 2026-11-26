# The Anabasis project file

A project is one UTF-8 JSON file. Anabasis writes it with two-space indentation, so it diffs well in Git. This page describes **format 2**, written by Anabasis 1.0 and later.

The format is open on purpose. Your work should never depend on this app to be readable.

## Compatibility promise

Format 2 is frozen for Anabasis 2.x. Every 2.x release opens every file written by 1.0 or later, and keeps anything in a file it doesn’t understand rather than dropping it. New features add optional fields (listed below with the version that added them); they never change the meaning of an existing one. If a future release ever needs a format 3, it will still open format 2 files, and a 2.x copy opening a format 3 file will say so before it changes anything.

## Top level

```json
{
  "app": "Anabasis",
  "format": 2,
  "appVersion": "1.0.0",
  "saved": "2026-11-22T18:00:00.000Z",
  "id": "p_…",
  "title": "My research",
  "created": "…", "modified": "…",
  "docs": [], "parts": [], "notes": [], "piles": [], "sources": [],
  "entities": [], "indexTerms": [], "indexOpts": {},
  "plan": {}, "goal": {}, "stats": {},
  "assets": {}, "acronyms": [], "acroIgnore": [], "places": [], "relations": [], "relLayout": {},
  "house": {}, "checkpoints": [],
  "threads": [], "claims": [], "reviewKeys": [],
  "journal": { "design": {}, "hypotheses": [], "log": [], "searches": [] },
  "datasets": [], "dashboards": [],
  "collab": { "sent": [] }, "copyOf": {}
}
```

| Field | What it holds |
|---|---|
| `format` | The file-format version. Anabasis migrates older formats on opening, and warns before opening a newer one. |
| `docs` | Documents, in binder order (`order`) and optionally grouped into `parts` (`partId`). |
| `notes` | Research notes: `title`, `body` (Markdown), `kind` (`quote`, `paraphrase`, `summary`, `idea`), `sourceId`, `locator`, `tags`, `date`, `pile`. |
| `sources` | Bibliography entries. `csl` is a [CSL-JSON](https://citeproc-js.readthedocs.io/en/latest/csl-json/markup.html) item; `osint` holds OSINT Style Guide fields and the reliability `rating` (Admiralty code such as `B2`); `transcript` holds interview text. |
| `assets` | Images, keyed by id: `{ data: "data:image/…;base64,…", w, h, type, spec? }`. `spec` keeps the settings of an editable chart, map, timeline or relationship figure. |
| `entities` | Names & spellings: people, places and organizations, with variant spellings. |
| `house` | House-style rules. |
| `checkpoints` | Names and dates of whole-project checkpoints. The checkpoint contents stay in the browser that made them. |
| `threads` | Research threads: `{ id, name, color, note, hidden }`. Their passages are marked in document `html` (below). Since 1.1. |
| `sources` (1.7) | A source may carry `stype`: `primary`, `secondary` or `tertiary`. A note may carry `stype` too, overriding its source’s; `none` means no type. |
| `sources` (1.9) | A web source may carry `lc`, the last link check: `at` (date), `url` (the Wayback Machine copy), `ts` (its timestamp), `st` (the HTTP status the archive saw) or `err`. `citeArchive: true` cites the archived address (kept in `osint.archiveUrl`) instead of the live one. |
| `collab` (2.0) | What you’ve sent collaborators: `sent` holds up to five `{ id, at, to, note, back, docs: [{ id, title, html, comments }], colls }`, the documents and collections as they were sent (or as they last came back), so their changes can be told from yours. Never included in a copy you send. |
| `copyOf` (2.0) | On a copy made with Send a copy: `{ send, from, to, at, note }`, matching it to the `collab.sent` record when it comes back. |
| `ins.sg` / `del.sg` with `class="sgb"` on their paragraph (2.0) | A paragraph a collaborator added or removed as a whole; accepting or rejecting the suggestion keeps or removes the paragraph rather than leaving an empty line. |
| `claims` | The claims register: `{ id, status, note, checkedText, checkedAt, checkedBy }` (`checkedBy` since 1.5: the name in Settings when the claim was marked supported). `status` is `open` (not checked), `ok` (supported), `need` (needs a source), `disp` (contested) or `cut`. `checkedText` is the claim's text when it was marked supported, so later edits can be flagged. Since 1.1. |
| `reviewKeys` | Review keys: `{ id, reason, due, note, done, doneAt }`, with `due` as `YYYY-MM-DD` or empty. Since 1.1. |
| `datasets` | Since 1.7. Tables kept in the project: `{ id, name, cols, rows, sourceId, note }`, `cols` a list of column names and `rows` a list of rows of strings. |
| `dashboards` | Since 1.7. `{ id, title, subtitle, tiles }`. A tile is `{ id, type, w, h, title, note, ds, sourceId, … }` with `type` one of `stat`, `chart`, `map`, `timeline`, `table`, `text`, `image`, `video`, `w` from 1 to 4 (quarters of the width) and `h` from 1 to 3; the other fields depend on the type (`col` and `agg` for numbers, `kind`, `labelCol` and `valueCols` for charts, `latCol` and `lonCol` for maps, `dateCol` for timelines, `cols` and `sortCol` for tables, `body` for text, `asset` for images, `url` for video). |
| `journal` | The research journal. Since 1.4. `design` has text fields `purpose`, `methods`, `data`, `scope`, `ethics`, `timeline`. `hypotheses`: `{ id, text, rationale, status, questionId, links, history }`, `status` one of `untested`, `supported`, `mixed`, `weakened`, `refuted`; `history` entries are `{ at, from, to, note }`. `log`: `{ id, date, kind, text, tags, links, done, doneAt }`, `date` as `YYYY-MM-DD`, `kind` one of `did`, `found`, `decided`, `dead`, `idea`, `question`, `next` (a next step, since 1.5; `done` and `doneAt` apply only to these), `auto` (recorded by Anabasis). `searches`: `{ id, date, where, terms, filters, results, kept, notes }`. A link is `{ k, id, stance }`: `k` is `cl` (a claim id), `note`, `src` (a source id) or `q` (a plan question id), and `stance` is `for`, `against` or empty. |
| `plan` | The plan (outline and argument map). Items of `type: "question"` are also the research questions passages can be linked to. |
| `notes` (2.6) | A note may carry `pdfHl`, where it was highlighted in its source’s PDF: `[{ p, r: [[x, y, w, h], …] }]`, `p` the PDF page (from 1) and each rectangle in fractions of the page. `codes` lists the ids of its codes; `photo` is the id of the archive photo it was made from. |
| `sources` (2.6) | A source may carry `read` (`toread`, `reading` or `read`) and `prio: 1` (read this first); `rc`, the last retraction check, `{ at, notices: [{ type, doi, date, label }] }` with `type` as Crossref gives it (`retraction`, `withdrawal`, `expression_of_concern`, `correction` …); `evidence`, file fingerprints, `[{ id, name, size, type, sha256, modified, added, captured, from, note }]`; and `photos`, archive photos, `[{ id, name, box, folder, item, date, caption, text, sha256, size, taken, added, rot }]`. The images themselves stay in the browser, under the photo’s id. |
| `codes` (2.6) | The codebook: `{ id, name, color, def, parent }`. Coded passages are research marks with `data-k="cd"` and `data-ref` the code’s id. |
| `litGrid` (2.6) | The literature grid: `cols` (`{ id, name, q }`, `q` the id of a research question, if the column is one), `rows` (`notes`, `cited` or `all`) and `cells`, `{ sourceId: { columnId: text } }`. |
| `entities` (2.6) | A name may carry `pseudo` (the name used in exports), `aka` (other forms to replace) and `consent` (`given`, `pending`, `declined`, `withdrawn` or `public`). `pseudoOn: false` at the top level turns pseudonyms off. |
| `journal.checks` (2.6) | Ticks in the research guide’s checklists: `{ listKey: { itemKey: "YYYY-MM-DD" } }`. |
| `notDup` (2.6) | Pairs of source ids (`"a|b"`) you’ve said aren’t duplicates. |
| `events` (2.6.2) | Calendar items: `{ id, date ("YYYY-MM-DD"), time ("HH:MM" or ""), title, kind (visit, interview, meeting, deadline or other), note, created, modified }`. |
| `scratch` (2.6.2) | The scratch pad’s text. |
| `trash` (2.6.2) | Deleted notes: `{ at, note }`, the note as it was. Entries older than 30 days are dropped when the project is opened. |
| `notes` (2.7) | A note of `kind: "translation"` carries `orig` (the original text), `origLang` (its language, a code such as `grc` or `de`), `translit`, `transBy` (`me` or `other`) and `translator`. Its `body` is the translation. |
| `journal.trans` (2.7) | The translation journal: `{ from, to, system, insert, mine, glossary }`. `from` and `to` are language codes; `system` a transliteration table (`ru-ala`, `ru-bgn`, `ru-simple`, `uk-nat`, `uk-ala`, `bg`, `sr`, `el`, `grc`, `ar`); `insert` how translation notes go into the text (`note`, `brackets`, `orig` or `none`); `mine` whether to add “My translation.”. `glossary`: `{ id, term, lang, render, avoid: [renderings decided against], note, translit, created }`. |
| `trw` (2.7) | Translations in the translation workspace: `{ id, title, from, to, sourceId, created, modified, segs }`, each segment `{ id, o (the original), t (the translation), st ("", "draft" or "done"), n (a note), p (the paragraph it came from, from 0) }`. |
| `subs` (2.7) | Submissions: `{ id, docId, outlet, editor, kind (pitch or submission), sent, status, followUp, fee, notes, closed, created, modified }`, dates as `YYYY-MM-DD`. `status` is `planned`, `sent`, `followed`, `accepted`, `published`, `rejected` (shown as Declined) or `withdrawn`. |

Unknown fields are kept when Anabasis saves, so add-ons and future versions can store their own data.

## Documents

```json
{
  "id": "d_…", "title": "Chapter 1", "html": "<h1>…</h1><p>…</p>",
  "style": "chicago-notes-bibliography",
  "partId": "", "order": 0, "role": "body", "status": "", "target": 0, "lang": "",
  "meta": { "author": "", "subtitle": "", "date": "", "showTitleBlock": false,
            "abstract": { "shape": "humanities", "parts": {}, "text": "", "keywords": [], "limit": 250, "include": true, "auto": true } },
  "layout": { "font": "book", "size": "12", "spacing": "2", "paper": "letter", "pdfNotes": "foot", "marginalia": "page" },
  "snapshots": [ { "id": "…", "name": "Draft 2", "kind": "draft", "note": "", "date": "…", "html": "…" } ],
  "comments": [ { "id": "…", "text": "…" } ]
}
```

`lang` (since 2.7.0) is the document’s language as a BCP 47 code such as `de` or `pt-BR`; empty means English (US). It sets spell-checking, quotation marks, citation terms and direction.

`html` is a small, fixed subset of HTML. Anabasis’s own markup inside it:

| Markup | Meaning |
|---|---|
| `<span class="cite" contenteditable="false" data-items='[{"id":"s_…","locator":"17","label":"page"}]'></span>` | A citation of one or more sources. The visible text is generated. |
| `<span class="fn" contenteditable="false" data-text="…">*</span>` | A text footnote. |
| `<figure class="fig"><img data-asset="a_…" alt="…"><figcaption>…</figcaption></figure>` | A figure. The image comes from `assets`; `src` is never stored. |
| `<figure class="tbl"><table>…</table><figcaption>…</figcaption></figure>` | A numbered table. `tbl av` is a script’s A/V table. |
| `data-dl='{"type":"table","ds":"ds_…",…}'` on a `figure`, or `<span class="dnum" contenteditable="false" data-dl='…'>4.1% of GDP</span>` | Since 1.7.1. A figure, table or number taken from a dataset. `data-dl` is a copy of the dashboard tile it was made from (the tile fields above, without `id`, `w`, `h`, `note`, `body`, `asset` and `url`); **Update from data** redraws it from the dataset named by `ds`. The visible content is ordinary text, table or image, so a reader that ignores `data-dl` loses nothing. |
| `<span class="math" contenteditable="false" data-tex="E = mc^2">E = mc^2</span>` | Since 1.8.0. An equation in a sentence. `data-tex` is the TeX, and the text is the same TeX, so the file reads sensibly anywhere. The drawing is made when the document opens and is never saved. |
| `<p class="eq num" contenteditable="false" data-tex="…">…</p>` | Since 1.8.0. An equation on its own line; `num` means it is numbered. Numbers are worked out in order each time, so they aren't stored. |
| `<span class="xref" contenteditable="false" data-ref="x…" data-form="full">Figure 3</span>` | Since 1.9.0. A cross-reference. `data-ref` is the `data-xid` of a figure, table, numbered equation or heading, or `doc:<id>` for a whole document; `data-form` is `full`, `lower`, `num` or `title`. The text is the last label shown and is worked out again on opening and on export. |
| `data-xid="x…"` on a `figure`, `p.eq` or `h1`–`h3` | Since 1.9.0. A lasting id that cross-references point to. Added only when something refers to it. |
| `data-credit`, `data-rights`, `data-holder`, `data-rnote` on a `figure` | Since 1.9.0. Credit line (added to the caption on export), permission status (`own`, `pd`, `open`, `fair`, `needed`, `asked`, `granted`, `refused`), whom to ask, and private notes. Only the credit line is ever exported. |
| `<span class="cmt" data-cmt="c_…">…</span>` | Text a margin note is attached to (an empty `cmt cmt-pt` marks a point). The note itself is in `comments`. |
| `<ins class="sg" data-sg="sg_…" data-by="Name" data-at="ISO date">…</ins>`, `<del class="sg" …>…</del>` | A suggested insertion or deletion, waiting to be accepted or rejected. Pieces of one suggestion share `data-sg`. Word exports write them as tracked changes; every other export shows them as accepted. Since 1.3. |
| `<span class="rm" data-rm="m_…" data-k="th" data-ref="th_…">…</span>` | A research mark. One passage can be split into several spans (one per run of text, across paragraphs and around citations) that share `data-rm`. `data-k` is `th` (thread; `data-ref` is the thread id), `cl` (claim; `data-rm` is the id in `claims`), `rv` (review key; `data-rm` is the id in `reviewKeys`) or `q` (question; `data-ref` is a plan item id). Marks are removed from every export. |
| `<span lang="de" dir="ltr">…</span>` | Since 2.7.0. A passage in another language (Mark → Language of this passage). `dir` is `rtl` for Arabic, Hebrew, Persian and Urdu. |

Anything outside this subset is removed when a file is opened (see [privacy](privacy.md#files-from-other-people)).

## Locked files

A locked project is saved as an envelope around the encrypted JSON:

```json
{
  "app": "Anabasis", "encrypted": 1, "v": 1,
  "kdf": { "name": "PBKDF2", "hash": "SHA-256", "iter": 600000, "salt": "<base64>" },
  "cipher": "AES-GCM", "iv": "<base64, 12 bytes>", "data": "<base64 ciphertext>"
}
```

The key is a 256-bit AES-GCM key derived from the password with the given salt and iterations. `data` decrypts to the ordinary project JSON above. Before writing a locked file, Anabasis decrypts what it is about to write and compares it with the original. If they differ, nothing is written.

## Changing the format

When a change would make older versions misread a file:

1. Bump `FORMAT` in `src/app.js`.
2. Add a step to `MIGRATIONS` that turns a project at the old version into the new one.
3. Describe the change here and in the changelog.
