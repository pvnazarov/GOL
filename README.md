# Good Old Library (GOL)

A personal web library for ~14,800 books collected in the late 1990s/2000s
(three collections: `eng1996`, `rus1996`, `rus2004`). Static site, no backend,
no database — a small Python build step turns the raw data into a compact
JSON catalogue that a vanilla-JS frontend loads once at startup.

This replaces the previous single-file app in `example/index.html` (kept
in place for comparison — see "Status" below).

## Architecture

```
Browser
  ├─ index.html + assets/app.css        (shell, restrained design)
  ├─ assets/js/*.js  (ES modules, no bundler, no framework)
  │    data.js     loads data/*.json once, builds in-memory lookup indices
  │    router.js   hash-based routing (#/libraries/…, #/search?q=…, #/files/…, #/book/…)
  │    search.js   field-prefixed search (author:/title:/category:/collection:/file:)
  │    ui.js       shared list/breadcrumb rendering, incremental "load more" paging
  │    reader.js   fetches ONE book zip on demand, unzips (lazy-loaded JSZip), renders it
  │    main.js     wires it all together: theme, font size, keyboard shortcuts
  └─ assets/vendor/jszip.min.js         (vendored locally, not a CDN)

libs/                    the actual web root (matches the existing hosting
  meta.zip                convention of serving from a folder named "libs")
  eng1996/ rus1996/ rus2004/     raw book zips, one .txt per zip (not in git)
  data/                   generated catalogue JSON (in git — see below)
    catalog.json          one record per book: path, library, category, author, title, size
    categories.json       category code -> display name
    tree.json             library -> category -> [{filename, size}], from an actual disk scan
    libraries.json        library id -> label + counts

scripts/
  build_catalog.py        regenerates libs/data/*.json (run after adding books/libraries)
  library_labels.json      optional friendly labels for library ids (e.g. rus2004 -> "2004 · Русский")
  check_encoding.py        consistency check: verifies every book .txt is valid UTF-8
  summarize_books.py       writes a <book>.md catalogue record beside each <book>.zip
                           using the `claude` CLI. Not wired into the app yet — see below

example/                  the OLD implementation, untouched, kept for comparison
```

No database, no auth, no application server — just static files plus one
offline build step, as the brief asked for.

## How the catalogue is built

`libs/meta.zip` contains `catalog.tsv` (path/author/title/category/size for
every book) and `categories.tsv` (category code -> Russian display name).
`scripts/build_catalog.py`:

1. Reads `catalog.tsv`/`categories.tsv` from `meta.zip`.
2. Independently walks the actual `libs/<library>/<category>/*.zip` files on
   disk — this is the ground truth for the **Files** view, so it stays
   correct even if the catalogue is stale or a book was added/removed by hand.
3. Cross-references the two: catalog rows without a matching file are
   dropped (logged), and files with no catalog row still show up in Files
   view (with the filename as the title).
4. Writes the four JSON files above.

**Libraries are discovered automatically** — there is no hardcoded list of
three. Any top-level folder under `libs/` containing `<category>/*.zip`
becomes a library. To add one: drop the folder in, optionally add a
friendly name to `scripts/library_labels.json` (falls back to the raw
folder name otherwise), and rerun the build script. Adding books to an
existing library/category works the same way — add the zip, rerun the
build script.

## Book summaries (`scripts/summarize_books.py`)

Writes a short catalogue record — title, author(s), type, and a 100–200 word summary — as
`<book>.md` next to each `<book>.zip`. It reads the text out of the zip, samples the
beginning, middle and end (~34k characters, roughly 9k tokens), and asks a model for a
single JSON object, which it renders to Markdown.

It shells out to the **`claude` CLI**, so it uses the local Claude Code subscription and
needs no API key — nothing secret lives in this file. The call is deliberately locked down:
no tools, no session persistence, no MCP servers.

```bash
# see exactly what would be sent, without calling the model
.venv/bin/python scripts/summarize_books.py libs/eng1996/ADVENTUR --limit 1 --dry-run

# try three books
.venv/bin/python scripts/summarize_books.py libs/eng1996/ADVENTUR --limit 3

# a full category, cheap model, in parallel
.venv/bin/python scripts/summarize_books.py libs/eng1996/ADVENTUR --model haiku --jobs 4
```

Existing `.md` files are skipped unless `--force`, so it is safe to interrupt and re-run.

**Status: piloted on 1 of 92 categories — 39 summaries under `eng1996/ADVENTUR` — and
nothing reads the output yet.** The app does
not know these files exist — surfacing them in the catalogue or the reader is still to do.
Note that the summaries land inside `libs/<library>/<category>/`, which `.gitignore`
excludes along with the book data, so they are not tracked.

## Running locally

```
cd libs
python3 -m http.server 8000
# open http://localhost:8000/
```

Any static file server works (this one, `nginx`, `apache`) — there is no
Node.js/dev-server dependency at runtime, only for the optional testing
described below.

## Rebuilding the catalogue

```
cd GOL
.venv/bin/python scripts/build_catalog.py     # regenerates libs/data/*.json
.venv/bin/python scripts/check_encoding.py    # optional consistency check
```

(`.venv` is a local virtualenv with `chardet` installed — see below — not
committed to git.)

## Deployment

`libs/` **is** the web root — no copy/rsync step needed, the live site is
served directly from this directory.

Currently deployed at `http://192.168.1.12/gol/` via the machine's
existing nginx (which also serves an unrelated app, alcmaeon, at `/` —
see `/etc/nginx/sites-available/alcmaeon`), through:

```
location = /gol { return 301 /gol/; }
location /gol/ {
	alias /home/pin/ai/GOL/libs/;
	index index.html;
}
```

Since nginx reads straight from this path, editing files here (or pulling
a new commit) takes effect immediately — no restart, no rebuild, no
sync. The only host-level requirement was letting `www-data` traverse
into `/home/pin` (`chmod o+x /home/pin`, execute-only — it still can't
list or read the rest of the home directory).

If this ever moves to a different machine/server instead: the app has no
server-side dependency beyond static file serving, so pointing any web
server's document root/alias at `libs/` (containing the real
`eng1996/`, `rus1996/`, `rus2004/`, `meta.zip`, and generated `data/`)
is enough — nothing needs building at deploy time beyond the offline
catalogue step above.

## What's tracked in git vs. not

`.gitignore` excludes `libs/*.zip` and every top-level folder under `libs/`
*except* `assets/` and `data/` — so the app code and the small generated
catalogue are tracked, and the ~4 GB of actual book archives are not. This
works for any future library folder automatically, without editing
`.gitignore` again.

---

## Performance investigation

### What made the old version slow

1. **Metadata was refetched and reparsed from scratch on every single page
   load.** The old code had a full Cache-API scaffold for this
   (`old-books-cache-v3`, `META_CACHE_KEY`) but `readMetaCache()`,
   `writeMetaCache()`, and `loadStateFromCache()` were all stubbed to
   no-ops, and `initializeLibrary()` called
   `localStorage.removeItem(META_CACHE_KEY)` at the end of every run — the
   caching code existed but did nothing. Every visit re-fetched `meta.zip`,
   re-unzipped it client-side with JSZip, and re-ran a hand-rolled TSV
   parser over all 14,845 rows.
2. **JSZip loaded from a CDN** on every page view, even before any book was
   opened — an external network dependency with no local fallback.
3. **Unbounded DOM rendering.** `showBooks()` and the sidebar's
   `renderList()` built one `<li>`/list item per result with no cap —
   the largest category (`rus2004/DRAMA`) has 1,958 books, so opening it
   built ~1,958 DOM nodes in one pass; a broad search could do the same.
4. **No URL routing.** State lived only in JS variables, so the browser
   back/forward buttons didn't map to app navigation, and nothing was
   bookmarkable or shareable.
5. **Duplicated data**: every catalog row repeated the full Russian
   category name (`CATNAME`) as a string instead of a small code looked
   up once.
6. Reading view was one `white-space:pre-wrap` block in a monospace font
   with no max line width — fine for the ASCII-art banners, poor for long
   prose on a wide desktop screen.

### What changed

- **Catalogue as JSON, not a zipped TSV.** `catalog.json` (2.05 MB raw /
  **455 KB gzipped**) is a plain `fetch` + `JSON.parse` — no client-side
  unzip, no custom parser, and normal HTTP caching actually works this
  time (nothing disables it).
- **JSZip vendored locally, and lazy-loaded.** It's not in the initial
  script payload at all — `reader.js` injects the `<script>` tag the first
  time a book is opened, so the ~28 KB gzipped library never loads for a
  visit that only browses/searches.
- **Book content is never fetched until a book is opened**, and each
  book's zip is fetched and unzipped individually, exactly once per
  session (an in-memory cache avoids re-fetching if you reopen it).
- **Incremental rendering.** Category/search/file lists render 150 rows at
  a time with a "Show more" button, instead of building the full DOM tree
  up front — verified against the 1,958-book `DRAMA` category.
- **Debounced, pre-indexed search.** Each catalogue entry gets its
  lowercased searchable fields computed once at load; typing re-filters
  the in-memory array (debounced 150 ms) instead of touching zipped/parsed
  data per keystroke.
- **Hash-based router** (`#/libraries/…`, `#/search?q=…`, `#/files/…`,
  `#/book/…`) makes back/forward, reload, and bookmarking behave
  predictably; `Library`/`Files` browsing state and `Search` queries are
  reflected in the URL without spamming browser history on every keystroke
  (search updates the URL via `replaceState`, not `pushState`).
- **Reading typography**: max line width sized in mostly-vw units
  (`min(1400px, 94vw)`, deliberately not `ch`) so it tracks available
  window/canvas space rather than the font size — doesn't shrink when the
  font gets smaller, and doesn't stay capped to a narrow fixed column when
  it gets bigger either; choice of monospace (default) or serif reading
  font — control lives in the header next to font size and theme —
  paragraph spacing, full dark-mode support for the reading pane itself
  (not just the chrome around it) — see "Reader design" below for how
  legacy ASCII-art banners are still
  preserved correctly.

### Numbers (gzip, this collection: 14,845 books / 3 libraries / 108 categories)

| Asset | Size |
|---|---|
| `data/catalog.json` | 455 KB |
| `data/tree.json` | 127 KB |
| `data/categories.json` / `libraries.json` | ~1 KB |
| all app JS (6 modules) | ~10.4 KB |
| `assets/app.css` | ~2.2 KB |
| JSZip (deferred, only on first book open) | ~28 KB |

Total initial load (before opening any book): **≈595 KB gzipped**, entirely
independent of which/how many books exist beyond the catalogue metadata
itself — opening a book only ever fetches that one book's zip (typically a
few KB to a few hundred KB).

### Remaining/accepted trade-offs

- `catalog.json`/`tree.json` are loaded in full at startup rather than
  paged from a server (there's no server to page from). At ~15k books this
  is fast and simple; if the collection grew an order of magnitude larger,
  this would need chunking or a real search index — not needed today, so
  not built.
- No service worker. Ordinary HTTP caching of static files is enough for a
  personal library site; adding one would be sophistication without a
  clear win here.
- Very large individual books render as one DOM tree in the reader
  (no virtualization inside the reading pane) — continuous reading, unlike
  a list, doesn't benefit from virtualizing away off-screen paragraphs the
  way a 2000-row list benefits from paging.

---

## Reader design (a deliberate deviation from the brief)

The task brief assumed `example/` would contain sample **HTML** book files
to test reader compatibility against. It doesn't — `example/` only holds
the old app's `index.html` shell. Every one of the 14,845 books in this
collection is a plain **UTF-8 `.txt`** file inside a zip (confirmed
collection-wide, 0 encoding issues — see `scripts/check_encoding.py`).

So the reader isn't an HTML sandbox (no iframe, no sanitizer needed) — it's
a plain-text-to-typography renderer:

- Lines are classified as **"graphic"** (legacy cover-page ASCII art /
  box-drawing banners — detected via Unicode box-drawing characters, or a
  low letter-to-symbol ratio measured against *non-whitespace* characters,
  so that right-justified prose like `Amendment I          (1791)` isn't
  mistaken for decoration) or **"text"**.
- Consecutive "graphic" lines always render in a monospace `<pre>` block
  (so box-drawing characters stay aligned), regardless of the reader's
  chosen font; everything else renders as paragraphs in the user's chosen
  reading font (monospace by default, serif as an alternative — toggled in
  the header), with the original line breaks preserved
  (`white-space: pre-wrap`) rather than reflowed — this matters because
  some categories are poetry/song lyrics (`POEMS`, `SONGS`, `LYRIC`), where
  the author's line breaks are structural, not just hard-wrapping.
- Detection runs over the *whole* file, not just the first lines, since
  pseudographic banners can appear mid-book too.
- Content is inserted via `textContent`, never `innerHTML` — book text is
  untrusted plain data, not markup.

Tested against three representative real books (a short legal document, a
270 KB single work, and a 2.7 MB multi-work compilation) — see "Testing
performed" below.

---

## Testing performed

**No visual/interactive browser was available in this environment** (no
Chrome extension configured, no browser binary installed). To compensate,
a local Node.js runtime was downloaded into `GOL/.tools/` (not on `PATH`,
not committed) purely for testing, and used to:

- Syntax-check all 6 JS modules (`node --check`).
- Run logic-level tests of `data.js` and `search.js` against the **real**
  generated catalogue served over HTTP (14,845 books): library/category/book
  counts, path lookups, Files-view folder listing, and search — including
  `author:tolstoy`, Cyrillic `author:Толстой`, `category:`, `collection:`,
  combined field queries, empty query, and a query with 0 matches.
- Run an end-to-end fetch → unzip → decode → paragraph/graphic-block
  classification test against three real book archives over HTTP. This
  caught and fixed a real bug: right-justified lines with long runs of
  padding spaces (e.g. `"Amendment I                    (1791)"`) were
  being misclassified as decorative ASCII art; the classifier now measures
  the letter ratio against non-whitespace characters only.
- Verified every static asset referenced by `index.html` resolves (200)
  with the correct MIME type from a live static server.

**Not verified: actual visual rendering, layout, click-through navigation,
and theme/font toggling in a real browser.** Please open
`http://localhost:8000/` (after `python3 -m http.server 8000` from `libs/`)
yourself to confirm the visual/interactive experience — happy to fix
anything that doesn't look or behave right.

## Status

`example/index.html` (the old implementation) is left untouched for
comparison, per the brief. Once you've confirmed the new version works as
expected in your own browser, it can be removed.
