Everything in Anabasis belongs to a **project**: its documents, notes, sources, images, plan, research records and settings. This page explains where a project is kept, how saving works in each browser, and the ways to keep a second copy safe.

## One project, two copies

A project lives in two places:

1. **The project file**, a single `.json` file you save wherever you like. This is the real copy. It holds everything, including images and figures, so one file is all you need to move, send or back up.
2. **A working copy in your browser** (IndexedDB). Anabasis writes to it as you type, so closing the tab, a crash or a flat battery doesn’t lose anything. It stays on your computer, and clearing the browser’s site data removes it.

Because the working copy can be lost with the browser’s data, treat the file as the copy that counts. Keep it somewhere that’s backed up: a synced folder (iCloud Drive, OneDrive, Dropbox, Google Drive) or a private GitHub repository.

Anabasis works on one project at a time. To switch, save the one that’s open, then open or start another.

## Saving

Press **Ctrl+S** (**⌘S** on a Mac) or choose **Save** in the top bar.

- **In Chrome, Edge and other Chromium browsers**, the first save asks where to put the file. Later saves write straight back to the same file, and **Recent files** on Project home reopen it in one click.
- **In Firefox and Safari**, each save downloads a fresh copy of the file. Your browser decides where it goes (usually Downloads). Keep the newest one and open that next time.
- **On a phone or tablet**, saving puts the file in Files (or Downloads) each time.

**Save project as…** (Export menu, under *The project file*) saves a copy under a new name, which then becomes the file Anabasis saves to.

### The reminder bar

If you haven’t saved the file for a while (15 minutes by default; change it in Settings), a bar appears at the top to remind you. Your work is already in the browser’s working copy; the reminder is about the file.

### Autosave to the file

In Chrome and Edge you can turn on **Autosave to file** in Settings. After you’ve saved the project once, Anabasis writes to the same `.json` a few seconds after you stop typing. After the browser restarts, it may need one click (**Resume autosave**, in the top bar) before it’s allowed to write again. That’s the browser’s rule, not Anabasis’s.

### When the file and the browser disagree

If you open a project file and this browser holds newer unsaved work on the same project, Anabasis asks which to use, so you never silently lose the more recent version.

### Two tabs at once

Keep Anabasis open in one tab. If you open it in a second tab, you’ll get a warning, so the two don’t overwrite each other’s working copy.

## Opening a project

Choose **Open** in the top bar and pick a `.json` file. In Chrome and Edge, **Recent files** on Project home reopen recent projects without the file picker.

A project file is data, but a file someone sends you could be crafted to smuggle in code. Anabasis cleans every document, draft and note when it opens a file: scripts, event handlers, `javascript:` links, frames, forms and remote images are removed before anything reaches the page. A file from a collaborator is safe to open.

## Keeping more than one copy

### Project checkpoints

**Project checkpoints** (Export menu) save a copy of the whole project inside this browser. Use one before a big reorganization or before taking changes back from a co-writer.

- **Compare** a checkpoint with now to see which documents were added, removed or changed, then open any changed document side by side in Drafts.
- **Restore** brings the whole project back to the checkpoint. It saves the current state as a checkpoint first, so restoring can be undone.
- **Download** keeps a checkpoint as a file somewhere else. Checkpoints otherwise live only in this browser.

Checkpoints are for the whole project. For one document, use **Drafts** in the document bar, which saves numbered drafts you can compare paragraph by paragraph.

### GitHub backup

**Back up to GitHub…** (Export menu) commits the project file to a private repository you choose, either when you ask or every time you save. Every backup stays in the repository’s history, and Anabasis can reopen any earlier one.

To set it up you need a GitHub account, a private repository, and a **fine-grained personal access token** limited to that one repository with **Contents: Read and write** permission. Make it on GitHub under Settings → Developer settings.

- Give the token **Only select repositories** with just the backup repository, **Contents: Read and write** and nothing else, and an expiration date (90 days is sensible). If it ever leaks, it reaches only those backups, and only until it expires. Anabasis warns if you use a classic token, which can reach all your repositories.
- The token is kept in memory for the session. If you tick **Remember** while a locked project is open, it’s stored encrypted with that project’s password. Otherwise it’s stored in this browser’s localStorage unencrypted, so anyone who can use your browser profile could read it.
- Anabasis won’t back up to a public repository without asking, and automatic backups never do.
- **Picking up on another device:** enter the same repository and token there, then choose **Open a project…** in the GitHub dialog (or **From GitHub…** on Project home). When a newer backup of the open project turns up from another device, a notice offers to open it.
- Backing up over a newer backup asks first, and automatic backups never do it. Nothing is lost either way, because every backup stays in the history.

### The archive: plain files for the long term

**Archive: everything as plain files (.zip)** (Export menu) saves the whole project as files that don’t need Anabasis to read:

- every document as Markdown, with its figures and Pandoc-style citations;
- every note as its own Markdown file;
- the sources as BibTeX and CSL-JSON;
- the research memo;
- the project file itself;
- and a README explaining what’s where.

It’s the copy to keep for years, or to hand to someone who doesn’t use Anabasis.

## Locking a project

**Lock project with a password…** (Export menu) encrypts the project file and this browser’s working copy. A locked project shows a lock badge in the top bar and asks for the password when it opens.

- Encryption is AES-256-GCM, with a key made from your password by PBKDF2 (SHA-256, 600,000 iterations).
- The password is never stored. **There is no way to recover a locked project if you forget the password**, and nobody, including the author, can open it for you.
- A locked project is backed up to GitHub locked.
- The PDFs, ePubs and archive photos the project keeps in this browser are encrypted with the same password, and open only while the project is unlocked.
- Passwords need at least 10 characters, and the commonest ones are refused. A phrase of three or four unrelated words is strong and easy to remember.
- **Stepping away:** after 15 minutes with no typing or clicking, a locked project hides itself and asks for the password again. Choose the time (or never) in the lock settings, or press **Lock now** there to hide it at once.

## Privacy

Anabasis has no account, no server, no analytics and no advertising. Nobody can see what you write in it. It goes online only when you ask it to, and only to these places:

| You choose | Anabasis contacts | What it sends |
|---|---|---|
| Add a source by DOI | doi.org (which may hand off to Crossref or DataCite) | the DOI |
| Add a source by ISBN | openlibrary.org | the ISBN |
| Add a source by web address | Wikipedia’s citation service | the address |
| Check links | the Internet Archive’s Wayback Machine | your web sources’ addresses, one at a time |
| Check for retractions | Crossref (api.crossref.org) | your sources’ DOIs, one at a time |
| Back up to GitHub, or open a backup | api.github.com | your project file and token, to the repository you chose |
| Check for a newer version | api.github.com | only the request for the latest version number |

**Work offline** (Settings) turns all of these off at once.

The page’s content security policy blocks every other connection. Images in your documents are stored inside the project, never loaded from the web, and pictures lose their location (GPS) and camera details when you add them. Every web page Anabasis saves carries its own content security policy, so it can’t load anything from the internet either. Socrates, the Oracle, Proofread, Close to your notes, coding and the research guide run entirely in the page. Evidence fingerprints are worked out in the browser; the files are never stored or sent. The full details are in [docs/privacy.md](https://github.com/gmichaelrapp/anabasis/blob/main/docs/privacy.md).

## The project file format

The `.json` file is plain, documented JSON, so your work is never locked in. Documents are stored as HTML, notes as Markdown, and sources as CSL-JSON, the format Zotero and most citation tools use. The full format is in [docs/file-format.md](https://github.com/gmichaelrapp/anabasis/blob/main/docs/file-format.md).

## Starting fresh

**Start fresh** (Settings, or search for it with Ctrl+K) offers two choices:

- **Blank project** clears the current project from this browser and starts empty. Your settings are kept.
- **Erase everything** removes every trace Anabasis keeps in this browser: the working copy, stored PDFs, settings and autosaves. Then it reloads, empty.

Both offer to download a backup of the current project first, and that box is ticked unless you untick it. Project files you’ve saved to your computer aren’t touched.

## Troubleshooting

- **“My work is gone after I cleared my browser.”** Clearing site data removes the working copy. Open your last saved project file. If you used GitHub backup, open the latest backup from the GitHub dialog.
- **“Saving downloads a new file every time.”** That’s how Firefox and Safari work. Use Chrome or Edge to save back to the same file, or keep the newest download.
- **“Autosave stopped.”** After a browser restart, click **Resume autosave** in the top bar.
- **“I opened the hosted copy and my project isn’t there.”** Each address keeps its own working copy. Save the file where you were working and open it at the new address.

## Related pages

- [Getting started](Getting-Started)
- [Exporting](Exporting)
