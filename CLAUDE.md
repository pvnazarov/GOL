# GOL — notes for Claude

Read `README.md` first: it is the source of truth for the app, the catalogue, FB2
books and the summaries pipeline. This file holds the working rules and
environment facts that the README does not. Open items are in `TODO.md`.

## Working rules (from the user)

- Commit and push only when asked. Repo `git@github.com:pvnazarov/GOL.git`, branch
  `master`. End commit messages with the Co-Authored-By line.
- Never change PATH or symlink binaries. Python is `.venv/bin/python`; Node is
  vendored in `.tools/node/bin` and used per command
  (`PATH=.tools/node/bin:$PATH node ...`).
- **EROTIC and SEX-TECH folders are never sent to Claude** (cloud). They go to the
  local GigaChat model only. SEX-TECH summaries are committed; EROTIC summaries
  stay **uncommitted** until the user has reviewed that folder (some books there
  involve minors; see `TODO.md`).
- A book Haiku fails on (refusal, stub replies) is summarized with local GigaChat
  instead; the site should use Haiku's summary and fall back to GigaChat's.
- The user writes in English and Russian; answer in the language of the message.

## Environment

- **Live site:** nginx serves `libs/` directly (`location /gol/ { alias
  /home/pin/ai/GOL/libs/; }` on 192.168.1.12). Public URL https://hatkapina.cc/gol/
  through Cloudflare; LAN http://192.168.1.12/gol/. Rebuilding `libs/data/*.json`
  (`.venv/bin/python scripts/build_catalog.py`) changes the live site at once.
- **Cloudflare browser cache** (max-age 14400) can serve stale JS after a change:
  tell the user to hard-refresh. "Respect Existing Headers" was recommended but
  not confirmed.
- **Book files** (`libs/<library>/<CAT>/*.zip`) are not in git; `libs/assets/` and
  `libs/data/` are. `inbox/` is the user's drop folder for new books (ignored).
- **Ollama GPU box** 192.168.1.188 (12 GB): open the tunnel with `ssh -f ollama-gpu`,
  then the API is http://localhost:11434. `ollamauser` has no shell: API only
  (`/api/pull`, `/api/copy`, `DELETE /api/delete`, `/api/ps`). Ollama 0.20.2 is too
  old for gemma4 12b/26b. Tunnel does not survive a reboot.
- **Claude backend** runs the `claude` CLI on the user's subscription (no API key).

## Summaries workflow (state 2026-10-18)

- `summaries/claude-haiku/` — Haiku, 14,666 books: every book outside EROTIC and
  SEX-TECH. Committed (`475396e`).
- `summaries/hf.co-ai-sage-GigaChat3.1-10B-A1.8B-GGUF-Q4_K_M/` — GigaChat Q4 @32k:
  the two Haiku failures (`eng1996/TEACHER/pyro`, `rus2004/PHYLOS/alievm`,
  committed), the 73 SEX-TECH books (committed) and the 117 EROTIC books
  (**not committed**).
- Run commands:
  - Haiku: `.venv/bin/python scripts/summarize_books.py --model haiku --jobs 4 libs/<lib>/<CAT> ...`
    (~41 books/min).
  - GigaChat: `.venv/bin/python scripts/summarize_books.py --backend ollama libs/<lib>/<CAT>`
    (30–60 s/book).
  - Existing records are skipped; `--force` redoes a book.
- **Checks after every run:**
  1. `FAIL` lines in the log.
  2. Wrong language: books in the rus libraries whose text is mostly Latin
     letters get English summaries under `--lang auto`; redo them with
     `--lang Russian --force`.
  3. Catalogue authors: translators, e-text editors and epigraph authors have
     shown up as authors. Fix them in `scripts/catalog_fixes.json`, rebuild the
     catalogue, then `--force` the book (title/author are copied from the
     catalogue into the record).
  4. Content-flag scan of the summaries (minors, explosives) for the user's
     review list.
  5. Read a random sample.
- **Results page:** https://claude.ai/artifact/D7fTRjjnxFKQzv8fQVyJP1 (private).
  Rebuild with `python3 scripts/summaries_page/build.py`; output goes to
  `reports/summaries_page/` (ignored). Republish the page with all
  `summaries-N.json` parts as supporting files: a single published file is
  limited to 16 MB, and `.gz` files are not served.
- Model comparisons (Haiku vs GigaChat Q6/Q4, qwen, gemma, T-lite) are in the README.
