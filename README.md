# Good Old Library (GOL)

A personal web library for ~14,800 books collected in the late 1990s/2000s
(three collections: `eng1996`, `rus1996`, `rus2004`), plus newer sets of FB2
books such as `izbrannoe` («Избранное»). Static site, no backend,
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
  │    fb2.js      renders FictionBook (.fb2) books; loaded only when one is opened
  │    main.js     wires it all together: theme, font size, keyboard shortcuts
  └─ assets/vendor/jszip.min.js         (vendored locally, not a CDN)

libs/                    the actual web root (matches the existing hosting
  meta.zip                convention of serving from a folder named "libs")
  eng1996/ rus1996/ rus2004/     raw book zips, one .txt per zip (not in git)
  izbrannoe/              «Избранное»: one .fb2 per zip (not in git) — see "FB2 books"
  data/                   generated catalogue JSON (in git — see below)
    catalog.json          one record per book: path, library, category, author, title, size
    categories.json       category code -> display name
    tree.json             library -> category -> [{filename, size}], from an actual disk scan
    libraries.json        library id -> label + counts

scripts/
  build_catalog.py        regenerates libs/data/*.json (run after adding books/libraries)
  library_labels.json      friendly labels for library ids, and the order libraries are listed in
  check_encoding.py        consistency check: verifies every book .txt is valid UTF-8
  libru_to_fb2.py          rebuilds a lib.ru book page as a structured .fb2.zip
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

Writes a short catalogue record — title, author(s), type, and a 100–200 word summary — for
each book, as JSON in a tree outside the book folders:

```
summaries/<model>/<library>/<category>/<book>.json
    e.g. summaries/qwen3.5-9b/rus1996/FANTAST/3_tale_2.json
```

Each record also stores how it was made (`meta`: backend, model, date, and whether the
model saw the full text or excerpts, with the prompt size), so weak cases — excerpted
books, a particular model — can be found and redone later. The summary language follows
the book: Russian for Cyrillic text, English otherwise (`--lang` overrides).

Why a separate tree and not files beside the zips: the book folders are gitignored raw
data and `libs/` is served live by nginx. Here the summaries are backed up in git, several
models can coexist, nothing is published until the site build picks a model, and the books
stay untouched.

Two backends:

- **`claude`** (default) shells out to the **`claude` CLI**, so it uses the local Claude
  Code subscription and needs no API key. The call is locked down: no tools, no session
  persistence, no MCP servers. Sends ~34k characters of beginning/middle/end excerpts.
- **`ollama`** calls an Ollama server, by default `http://localhost:11434` — the GPU box
  at 192.168.1.188 through an SSH tunnel (`ssh -f ollama-gpu`). Default model
  `qwen3.5:9b` with a 64k-token window, which takes most books whole (English up to
  ~220k characters, Russian ~165k); longer ones get large beginning/middle/end excerpts.
  Ollama silently drops the *start* of a prompt that overflows the window (system prompt
  and title page included), so a prompt that fills it is treated as a failure.

Before sending, runs of spaces from the old column formatting are collapsed (they cost
tokens and carry nothing).

```bash
# see exactly what would be sent, without calling the model
.venv/bin/python scripts/summarize_books.py libs/rus1996/FANTAST --limit 1 --dry-run

# one category on the GPU box (about a minute per long book)
.venv/bin/python scripts/summarize_books.py libs/rus1996/FANTAST --backend ollama

# a whole library -- folders are searched recursively
.venv/bin/python scripts/summarize_books.py libs/rus1996 --backend ollama

# with Claude, cheap model, in parallel
.venv/bin/python scripts/summarize_books.py libs/eng1996/ADVENTUR --model haiku --jobs 4
```

Existing records are skipped unless `--force`, so it is safe to interrupt and re-run.

Besides the text, the prompt carries what is already known: the catalogue's title and
author (from `libs/data/catalog.json`) and, for FB2 books, the book's own annotation. The
system prompt also says that front matter (copyright lines, the author's passport name,
e-mail, home pages) is not part of the story. On a 13-book test this removed more errors
than switching models did. Each record's `meta.input` notes whether the catalogue record
and an annotation were used.

**Title and author come from the catalogue**, not the model, whenever the catalogue has
them: small models copy whatever author they are shown or invent one (a book's hero
listed as its author, "Stevens" for Stevenson), and the site displays the catalogue's
anyway. Telling the model to "prefer the text" does not help, because many texts never
name their author (*Father Damien*, *St. Ives*). Wrong catalogue records are corrected
once, in `scripts/catalog_fixes.json` (`{"<library>/<category>/<file>": {"a": ..., "t":
...}}`), which `build_catalog.py` applies — so the fix reaches the site and the next
summary run alike.

**Local models tried** (Ollama on the 12 GB GPU box, 2026-10-17). On «Избранное» (13 books):
GigaChat 3.1 Lightning (`hf.co/ai-sage/GigaChat3.1-10B-A1.8B-GGUF:Q6_K`, `--num-ctx 32768`)
made the fewest errors; T-lite 2.1 (`hf.co/t-tech/T-lite-it-2.1-GGUF:Q6_K`,
`--num-ctx 28672`) was nearly as accurate and twice as fast; qwen3.5:9b was the most detailed
but the most often wrong; gemma4:e4b was generic. None is error-free — treat local summaries
as drafts. The books in the old libraries have no annotations, so expect weaker results there.

Then GigaChat on both Adventure categories (`eng1996/ADVENTUR` 39 books, `rus1996/ADVENTUR`
18), checked against the Claude pilot summaries and by searching the texts for every name:

| GigaChat 3.1 | time / book (eng / rus) | share of book read | correct / minor slips / serious errors (31 books checked) |
|---|---|---|---|
| Q6_K, 32k (0.7 GB off the GPU) | 77 s / 59 s | 41% / 27% | 12 / 13 / 6 |
| **Q4_K_M, 32k (all on the GPU)** | **59 s / 45 s** | 41% / 27% | **22 / 6 / 3** |
| Q4_K_M, 64k | 198 s / 128 s | 69% / 52% | 23 / 4 / 4 (+1 overflow) |

Q4 at 32k is the default for `--backend ollama`: fastest, and no less accurate than Q6
(the gap is within run-to-run variation). 64k reads more but is 3× slower for no clear
gain, and dialect-heavy books (*Huckleberry Finn*) overflow it. A full-library run at
Q4/32k is roughly 9 days of GPU time. These three runs predate the catalogue-authoritative
title/author change above.

**Claude Haiku** (`--model haiku`, 2026-10-18) on the same 57 Adventure books: 81 s for all
57 at `--jobs 4`, against ~50 min for GigaChat. On the 31 checked books: 16 correct / 14
minor slips / 1 serious error. Its summaries are longer and much more specific than
GigaChat's (it knows the famous books), so they carry more small slips (wrong number in a
series, a wrong surname). Haiku is now used for the bulk runs. **EROTIC and SEX-TECH are
not sent to Claude**; those stay on the local model.

**Status:** `claude-haiku` has the first five categories of every library (1,528 books); `claude-sonnet` has the 39 `eng1996/ADVENTUR` pilot summaries; `izbrannoe` has
summaries from all four local models above; both Adventure categories have GigaChat
summaries in three variants (Q6_K, Q4_K_M at 32k, and `gigachat3.1-q4-ctx64k` — an
Ollama copy of Q4_K_M named so its 64k results get their own folder). **Nothing reads the output yet** — surfacing it
means having `build_catalog.py` merge one model's records into `libs/data/`.

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

### Numbers (gzip, this collection: 14,845 books / 3 libraries / 92 categories)

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

## FB2 books

Newer sets come as FictionBook 2 (`.fb2`) files — XML with chapters, titles,
emphasis, annotations and embedded images. They are stored as-is, one `.fb2`
per `<name>.fb2.zip`, and rendered structurally rather than converted to text:

- **Reader:** `reader.js` picks the `.fb2` member when a zip has no `.txt`
  and lazy-loads `fb2.js`, which parses it with the browser's `DOMParser`
  (honouring the XML encoding, e.g. windows-1251) and renders sections as
  headings, a collapsible table of contents, epigraphs, poems, tables, the
  cover and annotation, footnotes and images. Everything is built with
  `createElement`/`textContent`, never `innerHTML`, so a hostile file can't
  inject markup; only `image/*` binaries become `data:` URIs and only
  http(s) links become links. Internal links scroll by script, because the
  hash router owns `location.hash`.
- **Hard-wrapped FB2s:** careless txt→FB2 conversions make every ~75-character
  *line* a `<p>`. `fb2.js` detects those (most `<p>`s end near one width) and
  joins lines back into paragraphs; mid-sentence lines join, dialogue dashes
  and capitalised headings break, sentence ends break unless the next word
  would not have fitted on the line.
- **Catalogue:** `build_catalog.py` takes author and title from the FB2's own
  `<title-info>` for books `meta.zip` doesn't list, so a new set needs no
  catalogue edits — drop `libs/<set>/<category>/*.fb2.zip` in, add a label to
  `scripts/library_labels.json`, rebuild.
- **Summaries:** `summarize_books.py` extracts FB2 body text too.
- **Reading order:** books in a category are listed by author and title, unless
  `scripts/book_order.json` gives that category a hand-picked order
  (`{"izbrannoe/FANTAST": ["hpmor_ru.fb2.zip", ...]}`) — e.g. a series in
  reading order. Listed books come first; rebuild the catalogue after editing.

**Adding books from lib.ru.** lib.ru's own FB2/EPUB exports are unreliable (the
Шумил set came as empty `.fb2.zip` files and EPUBs with all paragraphs flattened
into one). The book page itself keeps the original layout — indented
paragraphs, centred capital headings — so `scripts/libru_to_fb2.py` rebuilds a
proper FB2 from it (paragraphs, chapter sections, annotation, illustrations):

```bash
.venv/bin/python scripts/libru_to_fb2.py libs/izbrannoe/FANTAST \
    http://fan.lib.ru/s/shumil_p/text_0010-008.shtml
.venv/bin/python scripts/build_catalog.py
```

`inbox/` (not in git) is the drop folder for incoming files before they are
sorted into a set.

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
