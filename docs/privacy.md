# Privacy

Anabasis has no account, no server, no analytics and no advertising. Nobody, including the author, can see what you write in it.

## Where your work is kept

- **Your project file.** Save writes the whole project (documents, notes, sources, images and settings) to one `.json` file wherever you choose. This is the real copy. Back it up the way you back up anything else.
- **Your browser.** As you type, Anabasis keeps a working copy in your browser’s own storage (IndexedDB, with localStorage as a fallback), so a closed tab or a crash doesn’t lose anything. It stays on your computer. Clearing your browser’s site data removes it. **Start fresh** in the app erases it too.
- **Checkpoints** of the whole project are kept in the same browser storage. Download a checkpoint to keep it anywhere else.
- **Preferences**, such as theme and check settings, are kept in localStorage.

If you open the hosted copy on GitHub Pages, the same rules apply. GitHub serves the file, but your work stays in your browser. GitHub’s own [privacy statement](https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement) covers serving the page.

## When Anabasis goes online

Only when you ask it to, and only to these addresses:

| You choose | Anabasis contacts | What it sends |
|---|---|---|
| Add a source by DOI | doi.org (which may hand off to Crossref or DataCite) | the DOI |
| Add a source by ISBN | openlibrary.org | the ISBN |
| Add a source by web address | en.wikipedia.org (its citation service) | the address |
| Back up to GitHub | api.github.com | your project file and your access token, sent to a repository you choose |

The page’s content security policy blocks every other connection. Images in your documents are stored inside the project, never loaded from the web.

## GitHub backup

If you turn on GitHub backup, you give Anabasis a personal access token. It is kept in memory for the session. If you tick **Remember**, it is stored in this browser’s localStorage, unencrypted. Anyone who can use your browser profile could read it, so use a fine-grained token limited to one private repository. A locked project is backed up locked.

## Password lock

A locked project is encrypted with AES-256-GCM, using a key derived from your password with PBKDF2 (SHA-256, 600,000 iterations). The password is never stored. Nobody can recover a locked project without the password, including the author.

## Files from other people

A project file is data, but a crafted one could try to smuggle in code. Anabasis cleans every document, draft and note when it opens a file. Scripts, event handlers, `javascript:` links, frames, forms and remote images are removed before anything reaches the page.
