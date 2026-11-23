# The Anabasis project file

A project is one UTF-8 JSON file. Anabasis writes it with two-space indentation, so it diffs well in Git. This page describes **format 2**, written by Anabasis 1.0 and later.

The format is open on purpose. Your work should never depend on this app to be readable.

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
  "threads": [], "claims": [], "reviewKeys": []
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
| `claims` | The claims register: `{ id, status, note, checkedText, checkedAt }`. `status` is `open` (not checked), `ok` (supported), `need` (needs a source), `disp` (contested) or `cut`. `checkedText` is the claim's text when it was marked supported, so later edits can be flagged. Since 1.1. |
| `reviewKeys` | Review keys: `{ id, reason, due, note, done, doneAt }`, with `due` as `YYYY-MM-DD` or empty. Since 1.1. |
| `plan` | The plan (outline and argument map). Items of `type: "question"` are also the research questions passages can be linked to. |

Unknown fields are kept when Anabasis saves, so add-ons and future versions can store their own data.

## Documents

```json
{
  "id": "d_…", "title": "Chapter 1", "html": "<h1>…</h1><p>…</p>",
  "style": "chicago-notes-bibliography",
  "partId": "", "order": 0, "role": "body", "status": "", "target": 0,
  "meta": { "author": "", "subtitle": "", "date": "", "showTitleBlock": false },
  "layout": { "font": "book", "size": "12", "spacing": "2", "paper": "letter", "pdfNotes": "foot", "marginalia": "page" },
  "snapshots": [ { "id": "…", "name": "Draft 2", "kind": "draft", "note": "", "date": "…", "html": "…" } ],
  "comments": [ { "id": "…", "text": "…" } ]
}
```

`html` is a small, fixed subset of HTML. Anabasis’s own markup inside it:

| Markup | Meaning |
|---|---|
| `<span class="cite" contenteditable="false" data-items='[{"id":"s_…","locator":"17","label":"page"}]'></span>` | A citation of one or more sources. The visible text is generated. |
| `<span class="fn" contenteditable="false" data-text="…">*</span>` | A text footnote. |
| `<figure class="fig"><img data-asset="a_…" alt="…"><figcaption>…</figcaption></figure>` | A figure. The image comes from `assets`; `src` is never stored. |
| `<figure class="tbl"><table>…</table><figcaption>…</figcaption></figure>` | A numbered table. `tbl av` is a script’s A/V table. |
| `<span class="cmt" data-cmt="c_…">…</span>` | Text a margin note is attached to (an empty `cmt cmt-pt` marks a point). The note itself is in `comments`. |
| `<span class="rm" data-rm="m_…" data-k="th" data-ref="th_…">…</span>` | A research mark. One passage can be split into several spans (one per run of text, across paragraphs and around citations) that share `data-rm`. `data-k` is `th` (thread; `data-ref` is the thread id), `cl` (claim; `data-rm` is the id in `claims`), `rv` (review key; `data-rm` is the id in `reviewKeys`) or `q` (question; `data-ref` is a plan item id). Marks are removed from every export. |

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
