# GOL — to do

Updated 2026-10-18. Working notes are in `CLAUDE.md`.

## Content review (user)

All of these are served on the public site today.

- [ ] **EROTIC books that may involve minors.** Flagged from GigaChat's summaries;
  only *The Johnsons* is confirmed from the text itself.
  - Summary says so:
    - eng1996: `johns` (*The Johnsons*, confirmed by its own preface), `misty`,
      `platon`, `fdt`
    - rus1996: `deflorat`, `pansion`, `plem`, `inna`, `montel`
  - Unclear:
    - eng1996: `accting`
    - rus1996 and rus2004: `10letter`, `lesson`
    - rus1996: `betti`
    - rus2004: `chldpoem` (Armalinsky's folklore anthology)
- [ ] **`rus2004/CHILDREN/erik.zip`** — «История Эрика», a corporal-punishment
  story about a 13-year-old, filed as a children's book.
- [ ] **Bomb- and drug-making how-to files in TEACHER**:
  - eng1996: `ane`, `bombs`, `handbook`, `pyro`
  - rus1996 and rus2004: `blast`
  - rus2004: `drugsmak`

  Not flagged: `rus2004/TEACHER/vv`, Багал's chemistry textbook.
- [ ] Decide which of these to remove from `libs/` and the catalogue (then rebuild
  the catalogue), and whether to delete their summaries.
- [x] EROTIC GigaChat summaries committed (reviewed 2026-11-22), minus the 15
  flagged books (gitignored).

## Summaries

- [x] **Show the summaries on the site** (2026-11-22): per-folder files in
  `libs/data/summaries/`, two-line snippets in lists, full text in the book view.
  EROTIC summaries reviewed by the user and shown (2026-11-22), except the 15
  books flagged below for minors (`SUMMARY_SKIP_BOOKS`; files gitignored).
- [ ] Better summaries for long rus2004 books. Haiku read a median of only ~8% of
  them. Options: a larger excerpt (Haiku's price stays flat up to ~100k
  tokens), or Sonnet for chosen books.
- [ ] Older runs predate "catalogue sets title/author" (the 39 `claude-sonnet`
  books and the GigaChat Adventure runs). Rerun them if they are to be used.
- [ ] Broken characters (U+FFFD) in the source text of
  `rus1996/DETECT/sadstory` and `rus2004/TALES/krokus`.

## Catalogue

- [ ] Fill gaps from the summaries: 912 books have no author and ~305 have only
  the file name as title. Haiku's records hold suggestions; check them before
  adding to `scripts/catalog_fixes.json`.
- [ ] Spelling: «Ватьясана» → «Ватсьяяна» (Kama Sutra, rus1996 and rus2004
  SEX-TECH).
- [ ] Titles are lowercase-mangled in the old catalogue ("Before adam"). Cosmetic.

## Site

- [ ] Confirm the Cloudflare setting "Respect Existing Headers", so that new JS
  reaches users without a hard refresh.
