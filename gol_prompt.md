# Claude Code task: redesign and optimize “Library in the Pocket” into "Good Old Libraries (GOL)"

## Objective

Redesign and rebuild my personal web-based book library.

The current deployed version is available at:

`https://pin.ydns.eu/libs/`

and a copy of source html is in /example/ folder

Use the existing project as the starting point. Do not blindly rewrite it from scratch. First understand how it currently works, identify performance bottlenecks and useful existing components, then design and implement an improved version.

The website is a personal library containing a potentially large number of books/files from 199x-200x and should remain lightweight, fast, simple to maintain, and comfortable for long-form reading.

---

# 1. First inspect the existing project

Before making substantial changes:

1. Inspect the complete existing source tree.
2. Understand:
   - how libraries are represented;
   - how book metadata are stored or generated;
   - how search currently works;
   - how directory/file browsing works;
   - how books are loaded into the reader;
   - whether book contents or metadata are loaded eagerly;
   - what caching mechanisms exist;
   - which libraries/frameworks are currently used.
3. Look specifically inside:

`./example/`

This directory contains example HTML book files. Inspect several of them carefully because the new reader must display these existing HTML files correctly.

Do not modify the original book files simply to make the reader work unless there is a compelling reason.

Also inspect the currently deployed website where useful:

`https://pin.ydns.eu/libs/`

---

# 2. Performance investigation

The current website feels slow.

Do not assume the reason. Profile and inspect the implementation first.

Look specifically for problems such as:

- loading the complete contents of all books at startup;
- loading unnecessarily large JSON/index files;
- constructing very large DOM trees;
- recursively rendering the entire file hierarchy;
- inefficient JavaScript loops;
- repeated HTTP requests;
- repeated parsing of the same metadata;
- search performed inefficiently on every keystroke;
- lack of debouncing;
- duplicate indexing;
- large third-party JavaScript libraries;
- blocking resources;
- unnecessary network requests;
- poor HTTP/browser caching;
- excessively large HTML/CSS/JS bundles.

Use browser Performance/Network information, JavaScript Performance APIs, file sizes, or other suitable profiling methods where useful.

Before or during implementation, briefly document:

1. the main causes of the current slowdown;
2. which optimizations you implemented;
3. any remaining bottlenecks.

A key architectural target is:

**The size of the actual book collection should have minimal influence on initial page-load time. Book contents must not be downloaded until a user opens a book.**

Loading a compact metadata/search index at startup is acceptable if justified.

---

# 3. Main user interface

The application should have three primary ways of finding a book.

## A. Libraries

Navigate through the logical book libraries/collections.

There are currently three libraries, but **do not hard-code the number three**.

The system should make it straightforward to add/remove libraries later through configuration or automatic indexing.

Useful hierarchy might be:

`Library → category/subcategory → books`

Use the actual metadata and structure of the current collection rather than inventing an incompatible hierarchy.

Provide breadcrumbs where useful.

---

## B. Search

Provide a prominent fast search interface.

Search should support at least:

- book title;
- author;
- library/collection;
- category;
- filename/path.

Preserve or improve the current field-specific search syntax where practical, for example:

`author:tolstoy`

`title:war`

`category:history`

`collection:gutenberg`

`file:...`

Ordinary text without a prefix should search the most useful combined fields, primarily title and author.

Requirements:

- case-insensitive;
- Unicode-safe;
- work properly with Latin and Cyrillic text;
- fast for a large catalogue;
- search results should update interactively;
- debounce input if appropriate;
- avoid rescanning or reparsing book files for every query.

Display useful result information such as:

**Book title**  
Author  
Library / category  
File information when useful

Clicking a result should immediately open the book.

Consider lightweight fuzzy matching only if it improves usability without noticeably increasing complexity or latency. Exact and substring search must remain predictable.

---

## C. Files

Provide traditional file-system-style navigation through the library.

The user should be able to browse folders and files independently of book metadata.

Useful features:

- folders first;
- clear folder/file distinction;
- breadcrumbs;
- filename;
- sensible sorting;
- ability to move back to parent directory;
- clicking a readable book file opens it in the reader.

Do not render an enormous recursive directory tree at startup. Load/render only the level currently required or use another efficient approach.

---

# 4. Book reader

Reading is a major function of the site, not just a preview.

When a book is selected, show it in a clean reading interface.

The existing HTML books in `./example/` are important compatibility tests.

The reader must support:

## Font size

Provide easy controls to increase/decrease text size.

For example:

`A−   16px   A+`

Changes should happen immediately.

Use a sensible minimum and maximum.

Remember the user's selected font size using `localStorage`.

---

## Light / dark mode

Provide:

- Light
- Dark

Optionally also support:

- System

The setting should persist in `localStorage`.

Dark mode must apply properly to the **book content itself**, not only to the application's menus.

Take special care with legacy HTML containing its own colors or formatting.

Avoid ugly results such as white book pages inside an otherwise dark application.

---

## Reading layout

Optimize typography for long reading:

- comfortable line height;
- readable maximum line width;
- appropriate margins;
- good typography;
- no unnecessary visual clutter;
- responsive layout.

Do not force a narrow mobile-style column on a desktop display.

---

## Reader compatibility

Study the HTML files in `./example/`.

Determine whether the safest implementation is:

- an iframe;
- DOM insertion;
- parsed/sanitized HTML;
- another lightweight approach.

Choose based on the actual files.

The chosen approach should:

- preserve book structure;
- preserve headings and paragraphs;
- preserve useful internal links;
- allow reader font-size control;
- allow dark/light styling;
- avoid book CSS breaking the surrounding application;
- avoid the application CSS destroying book formatting.

Document the reasoning briefly.

---

# 5. General UI design

I want a restrained library/reader interface rather than a flashy commercial website.

Priorities:

1. books;
2. search;
3. reading;
4. speed.

The current title **“Библиотека в кармане” / “Library in the Pocket”** to be chaged to "Good Old Libraries" / "Старые Добрые Библиотеки".

Use a clean modern design with good desktop usability and reasonable mobile/tablet behaviour.

A possible desktop layout is:

- compact header;
- left navigation panel;
- main book/result/file panel;
- reader occupying most available space when a book is open.

However, adapt this if a better layout emerges from the existing implementation.

Avoid:

- excessive animations;
- oversized cards;
- unnecessary whitespace;
- huge icons;
- complex visual effects;
- heavyweight UI frameworks without justification.

---

# 6. State and navigation

The application should behave naturally when navigating between books.

Where practical, preserve:

- selected library;
- current folder;
- search query;
- reader theme;
- reader font size.

Consider remembering the last opened book and/or reading position if this can be implemented reliably and simply. This is useful but secondary to the core requirements.

Browser Back/Forward should not behave surprisingly.

---

# 7. Architecture

Prefer the simplest architecture that fits the existing deployment environment.

This is a personal library website, not a SaaS application.

Avoid adding:

- databases;
- authentication systems;
- application servers;
- large frameworks;

unless the existing architecture or an important technical requirement genuinely needs them.

A static frontend plus a generated catalogue/search index is likely preferable if technically appropriate.

---

# 8. Scalability

Design for substantially more books than are currently present.

Important principles:

- never preload all book contents;
- avoid creating DOM elements for thousands of items unnecessarily;
- cache reusable metadata;
- lazy-load books;
- avoid repeated parsing;
- use pagination, incremental rendering or virtualization if result lists become large;
- keep search responsive.

Initial application loading should depend primarily on application assets and catalogue metadata, rather than the aggregate size of the books.

---

# 9. Caching

Investigate the existing caching behaviour.

Use browser caching appropriately for:

- CSS;
- JavaScript;
- icons;
- catalogue/index;
- opened book files where appropriate.

A service worker may be used if it gives a clear benefit, but do not add one merely for architectural sophistication.

Avoid stale catalogue problems when the library changes.

If caching/index versioning is needed, implement a simple reliable mechanism.

---

# 10. Deployment

Preserve compatibility with the way the existing site is hosted wherever possible.

Do not require a permanent Node.js development server simply to use the site unless the current hosting architecture requires it.

The final production output should preferably be deployable as ordinary static files through Apache/nginx or a similarly simple web server.

Any build/index-generation step should be documented clearly.

---

# 11. Error handling

Handle gracefully:

- missing book files;
- malformed metadata;
- malformed or unusual HTML books;
- unsupported file types;
- failed network requests;
- empty search results;
- empty directories.

Never leave the UI permanently showing only `Loading…` after an error.

Provide a useful error message and allow the user to continue navigating.

---

# 12. Code quality

Keep the implementation understandable and maintainable.

Requirements:

- clear file structure;
- sensible naming;
- minimal dependencies;
- avoid duplicated logic;
- comments where behaviour is non-obvious;
- separate catalogue/search/reader/UI responsibilities where practical;
- remove obsolete code after verifying it is no longer required.

Do not over-engineer the application.

---

# 13. Testing

Use the books in the project folder - i put the entire library there (for GIT we should exclude books themselves, keeping only meta data, html  and scripts).

Test at least:

### Navigation

- opening each library;
- navigating categories;
- browsing directories;
- opening books from all three navigation mechanisms.

### Search

- title;
- author;
- partial title;
- Cyrillic text;
- Latin text;
- field syntax;
- nonexistent query.

### Reader

- several representative HTML books;
- font increase/decrease;
- light → dark → light;
- persistence after reload;
- internal book formatting;
- long books;
- scrolling.

### Performance

Verify that:

- initial loading does not fetch the contents of every book;
- opening one book does not fetch unrelated books;
- search remains responsive;
- large result sets do not freeze the interface.

---

# 14. Responsive behaviour

The primary environment is desktop, but the site should remain usable on:

- laptop;
- tablet;
- phone.

On small screens, navigation panels may collapse into a drawer/menu.

Reading remains the priority.

---

# 15. Accessibility and keyboard use

Implement basic accessibility:

- semantic HTML;
- accessible buttons;
- visible keyboard focus;
- sufficient contrast;
- sensible labels/tooltips.

Useful keyboard behaviour is encouraged, particularly:

- `/` or `Ctrl+F`-like shortcut to focus library search if it does not interfere with browser behaviour;
- Escape to close overlays/navigation where applicable.

Do not make keyboard shortcuts complicated.

---

# 16. Implementation workflow

Work in this order:

### Phase 1 — Investigation

Inspect the existing application, `./example/`, library structure and current performance.

Write a concise technical assessment of:

- existing architecture;
- useful components worth preserving;
- likely causes of slowness;
- proposed architecture.

### Phase 2 — Implementation

Implement the redesigned application.

Preserve the old implementation until the replacement is demonstrably working.

### Phase 3 — Validation

Test:

- all three navigation methods;
- multiple representative books;
- search;
- theme;
- font size;
- responsive layout;
- error handling;
- performance.

### Phase 4 — Cleanup

Remove obsolete code, unnecessary dependencies and debugging artefacts.

---

# 17. Documentation

Create/update `README.md` with:

- application architecture;
- directory structure;
- how libraries are configured/discovered;
- how the catalogue/index is generated;
- how to add a new library;
- how to add books;
- how to run locally;
- how to rebuild;
- how to deploy;
- performance optimizations made.

Also include a short section:

## Performance investigation

describing:

- what made the previous version slow;
- measurements/evidence where available;
- what was changed.

---

# 18. Acceptance criteria

The project is successful when:

1. The user can find books through **Libraries**, **Search**, or **Files**.
2. All three methods eventually open the same reader.
3. Search works for titles, authors and relevant metadata.
4. Existing HTML and books, particularly  in `./example/`, render correctly.
5. Font size can be changed while reading.
6. Light/dark reader mode works correctly.
7. Reader preferences persist across reloads.
8. Book contents are loaded on demand rather than globally at startup.
9. The UI remains responsive with a large catalogue.
10. The application loads noticeably faster than the current implementation.
11. Adding another library does not require redesigning or hard-coding the interface.
12. The final site remains simple to host and maintain.

When trade-offs are necessary, prioritize in this order:

**correct book rendering → navigation/search usability → performance → maintainability → visual sophistication.**
