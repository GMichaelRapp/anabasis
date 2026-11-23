# Contributing to Anabasis

Thanks for helping. Bug reports, fixes, citation-style corrections, translations of the interface text and documentation are all welcome.

## Reporting a bug

Open an [issue](https://github.com/gmichaelrapp/anabasis/issues/new/choose) using the bug template. The most useful reports include:

- the Anabasis version (Help → the number next to the title) and your browser;
- what you did, what you expected and what happened;
- if you can share it, a small project file that shows the problem. Remove anything private first.

**Security problems** go through a private advisory instead. See [SECURITY.md](SECURITY.md).

## How the code is laid out

```
src/shell.html       markup and CSS for the whole interface
src/app.js           all application code, in one script (sections are marked with banner comments)
src/doc.css          styles for the page itself, shared by the editor, PDF, ePub and HTML exports
vendor/js, vendor/csl  third-party libraries and citation styles, pinned and checksummed
data/                map and gazetteer data (see tools/data/README.md)
assets/              fonts, background and icon
build.py             inlines everything into dist/anabasis.html
tests/               Playwright suites (see tests/run_tests.py for what each covers)
tools/site/          builds the installable hosted copy for GitHub Pages (manifest, service worker, icons)
tools/guide/         regenerates the quick-start and README screenshots
```

The app is deliberately a single file with no framework and no build step beyond inlining. Keep it that way: plain JavaScript, no new runtime dependencies without discussion, and everything must work offline from `file://`.

## Making a change

```sh
python build.py --check          # build dist/anabasis.html
python tests/run_tests.py        # all suites (about 6 minutes)
python tests/run_tests.py t20    # one suite
python tests/smoke.py --browser firefox   # quick check in another engine
```

Before you open a pull request:

- Run the full suite. Add or extend a test for what you changed.
- Keep `dist/anabasis.html` under the 25 MB budget. `build.py` refuses to go over it. Size isn't the only budget: anything large should stay packed until it's first used, so the app opens as fast as it does now.
- To add a citation style, copy an independent style (no `independent-parent` link) from the CSL styles repository into `vendor/csl/`, add its entry to `vendor/manifest.json`, and give it a label and group in `STYLES` in `src/app.js`.
- If you change what a project file holds, follow [Changing the format](docs/file-format.md#changing-the-format).
- If the change is user-visible, add a line to `CHANGELOG.md` under **Unreleased**, and update Help in `src/shell.html` if it explains the feature.
- If the change alters a screen shown in the [quick start](docs/quick-start.md), regenerate its screenshots with `python tools/guide/quickstart.py` (after `python build.py`).
- Interface screenshots in the README come from `python tools/guide/screenshots.py`.
- New toolbar, document-bar or top-bar buttons need `data-pri` (higher moves into the ⋯ menu sooner) and `data-label` (their name in that menu); toolbar buttons also need `data-tb`, so they can be hidden in Customize toolbar. Check the layout at 390 px wide as well as on a desktop.
- Interface text: plain verbs, sentence case, and a button says what it does (“Save checkpoint”, not “Submit”).

Don’t commit `dist/`. Releases are built by GitHub Actions from the tagged commit.

## Updating a vendored library

1. Replace the file under `vendor/` with the new release’s file from npm or the project’s own release.
2. Update its `version` and `sha256` in `vendor/manifest.json` (`sha256sum <file>`), and the version in the banner comment in `build.py` if it has one.
3. Update `THIRD-PARTY-NOTICES.md` and `licenses/` if the license or copyright changed.
4. Run the full suite.

## License of contributions

Anabasis is licensed under the AGPL-3.0-or-later. By contributing, you agree that your contribution is licensed under the same terms.
