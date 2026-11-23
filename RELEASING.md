# Releasing Anabasis

## One-time setup on GitHub

1. Create a **public** repository named `anabasis` and push this folder to its `main` branch (see below).
2. **Settings → Pages**: set *Source* to **GitHub Actions**. The hosted copy appears at `https://<you>.github.io/anabasis/` after the first release.
3. **Settings → Code security**: turn on **Private vulnerability reporting** (SECURITY.md points people there) and **Dependabot alerts**.
4. **Settings → General**: add a description (“A writing desk for nonfiction: documents, notes, sources and citations in one offline HTML file”), the website link to the Pages URL, and topics such as `writing`, `citations`, `zotero-alternative`, `nonfiction`, `offline-first`, `osint`.
5. **Settings → Branches**: optionally protect `main` and require the **CI** check to pass.

If your GitHub username isn’t `gmichaelrapp`, replace it everywhere: `grep -rl gmichaelrapp . | xargs sed -i 's/gmichaelrapp/<you>/g'`. The OSINT_Cites links point at the published style guide, so check those separately.

### First push

```sh
cd anabasis
git init -b main
git add .
git commit -m "Anabasis 1.0.0"
git remote add origin https://github.com/<you>/anabasis.git
git push -u origin main
```

The **CI** workflow runs on every push: it builds, runs every test suite in Chromium (also with newer browser APIs switched off), and smoke-tests Firefox and WebKit.

## Cutting a release

1. Make sure CI is green on `main`.
2. Set the version in `src/app.js` (`APP_VERSION`), following semver.
3. In `CHANGELOG.md`, rename **Unreleased** to the version and date, for example `## [1.0.0] — 2026-12-01`, and start a fresh **Unreleased** section above it.
4. Commit, tag and push:

   ```sh
   git commit -am "Release 1.0.0"
   git tag v1.0.0
   git push && git push --tags
   ```

The **Release** workflow checks that the tag matches `APP_VERSION`, builds, runs the tests, and publishes a GitHub release. The release attaches `anabasis.html` and `SHA256SUMS.txt`, with the changelog section as its notes. Its last step starts **Publish to GitHub Pages**, which updates the hosted copy.

If something goes wrong, delete the tag (`git push --delete origin v1.0.0` and `git tag -d v1.0.0`), fix the problem, and tag again.

## Before a major release

- Try a real project for a week in Chrome, Firefox and Safari.
- Check that an old project file still opens and saves. Keep a few real files from earlier versions for this.
- Read through Help in the app for anything out of date.
