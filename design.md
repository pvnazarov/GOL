# Good Old Library — Visual Integration Brief for Claude Code

## Objective

Redesign the visual presentation of the **Good Old Library** website so that the attached historical library image becomes the main visual identity of the browsing interface.

Current site:

- `http://pin.ydns.eu/gol`

The image shows an old wooden library with bookshelves, fireplace, candles, and a portrait of Johannes Gutenberg above the fireplace.

The goal is to create the feeling that the user is entering an old physical library, while keeping the actual interface modern, readable, responsive, and fast.

---

## Core design concept

Use the historical library image primarily as **atmosphere**, not as content.

The conceptual distinction should be:

> **Browsing = old physical library**  
> **Reading = quiet digital book**

The library image should therefore be prominent on navigation/search/browsing pages, but should disappear when the user opens a book for reading.

---

## 1. Library browsing pages

Use the library image as a full-page or large hero/background image on:

- main page;
- library-selection page;
- search page;
- author/book browsing;
- file-navigation page.

Recommended behavior:

- fill the viewport;
- use `background-size: cover`;
- keep Gutenberg and the fireplace approximately in the upper-middle area;
- darken the image significantly so text stays readable;
- optionally apply a very small blur or dark overlay;
- place functional UI elements in dark, semi-opaque panels;
- retain enough of the image so that the room remains recognizable.

Do **not** place normal text directly on the undarkened photograph.

---

## 2. Suggested page composition

A possible conceptual layout:

```text
┌──────────────────────────────────────────────────────────────┐
│                                                              │
│                  [ old library background ]                  │
│                     Gutenberg portrait                       │
│                                                              │
│                  GOOD OLD LIBRARY                            │
│              Books from another time                         │
│                                                              │
│              [ Search books... ]                             │
│                                                              │
│         Libraries       Authors       Files                  │
│                                                              │
│ ┌──────────────────────────────────────────────────────────┐ │
│ │ Actual library interface / book list                    │ │
│ │                                                        │ │
│ └──────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

Possible subtitle:

> Books from another time.

Alternative:

> A personal collection of old digital libraries.

Do not overdecorate the page. The library photograph should provide most of the visual character.

---

## 3. Reading view

When a user opens a book, remove the historical photograph completely.

The reader should become minimal and distraction-free.

Example:

```text
                    Chapter VII

        It was already late when he entered...
```

The reading interface should preserve:

- adjustable font size;
- light/dark reader themes;
- comfortable line width;
- good typography;
- clear navigation;
- responsive layout.

The reader should feel visually separate from the browsing interface.

---

## 4. Recommended visual palette

Derive the site colors from the historical library image.

Suggested palette:

| Purpose | Color |
|---|---|
| Main dark background | `#17110D` |
| Primary panel | `#241A13` |
| Secondary panel | `#33241A` |
| Main text | `#E8DDC8` |
| Muted text | `#AE9C82` |
| Gold accent | `#B58A45` |
| Gold hover | `#D0A65E` |
| Dark wood border | `#59402B` |

Example CSS variables:

```css
:root {
    --bg: #17110d;
    --panel: #241a13;
    --panel-alt: #33241a;

    --text: #e8ddc8;
    --text-muted: #ae9c82;

    --accent: #b58a45;
    --accent-hover: #d0a65e;

    --border: #59402b;
}
```

Avoid bright modern colors unless required for accessibility.

---

## 5. Background implementation

A possible starting point:

```css
.library-page {
    min-height: 100vh;
    position: relative;
    isolation: isolate;

    background:
        linear-gradient(
            rgba(12, 8, 5, 0.58),
            rgba(12, 8, 5, 0.82)
        ),
        url("/images/library-gutenberg.webp");

    background-size: cover;
    background-position: center 28%;
    background-attachment: fixed;
}

.library-content {
    width: min(1200px, calc(100% - 32px));
    margin: 0 auto;

    background: rgba(24, 18, 13, 0.88);
    border: 1px solid rgba(210, 175, 110, 0.18);

    box-shadow:
        0 12px 45px rgba(0, 0, 0, 0.35);

    border-radius: 8px;
}
```

Treat this as a starting point rather than a mandatory implementation.

Adjust opacity, positioning, image treatment, and panel contrast based on the existing layout.

---

## 6. UI style

Preferred:

- dark wood/brown interface;
- muted cream typography;
- restrained gold highlights;
- subtle borders;
- very subtle shadows;
- minimal rounded corners;
- classical rather than glossy styling.

Avoid:

- strong glassmorphism;
- neon accents;
- excessive gradients;
- large modern pill-shaped controls;
- visually aggressive animations;
- decorative elements that compete with the library image.

A restrained interface should make the site feel like an old private library rather than a generic modern dashboard.

---

## 7. Header and navigation

The top area should establish the identity immediately.

Suggested hierarchy:

```text
GOOD OLD LIBRARY
Books from another time

[ Search by title, author, ... ]

Libraries   Authors   Files
```

The three main navigation methods should remain clearly visible:

1. browse by library;
2. search;
3. browse by files.

Search should remain one of the most visually prominent controls.

---

## 8. Responsive image behavior

The current source image is approximately 4:3.

For desktop use, a wider version would be preferable.

Recommended assets:

```text
library-gutenberg-wide.webp     # desktop, ideally ~16:9 or 2:1
library-gutenberg.webp          # tablet
library-gutenberg-mobile.webp   # optional mobile crop
```

Use `<picture>`, CSS media queries, or responsive background switching.

Important:

- Gutenberg portrait should remain visible on desktop;
- avoid cropping the fireplace completely;
- mobile cropping may focus more tightly on Gutenberg/fireplace;
- do not force the entire room into a narrow mobile viewport.

---

## 9. Image performance

The background must not make the site slow.

Please:

- convert the final image to WebP and/or AVIF;
- generate appropriately sized desktop/tablet/mobile variants;
- avoid serving a multi-megabyte source image directly;
- preload only if justified;
- lazy-load non-critical decorative assets;
- inspect current image loading and rendering performance.

A target desktop background width of roughly 1600–2000 px is likely sufficient for most displays.

---

## 10. Accessibility

Maintain strong contrast between text and the background.

Requirements:

- readable text at WCAG-friendly contrast levels;
- visible keyboard focus states;
- controls must not depend only on color;
- all navigation must work with keyboard;
- background image is decorative and should not require alt text;
- respect `prefers-reduced-motion` if animations are added.

---

## 11. Reader themes

The historical color palette should mainly influence browsing.

The reader should remain simple.

Suggested reader themes:

### Light

```css
--reader-bg: #f4efe6;
--reader-text: #24201c;
```

### Dark

```css
--reader-bg: #171513;
--reader-text: #e8e1d7;
```

Do not place the photographic background behind book text.

---

## 12. Interaction details

Subtle interaction is appropriate.

Examples:

- gold underline or border on hover;
- slightly lighter wood panel on hover;
- small transition of `150–250 ms`;
- search field focus with muted gold border.

Avoid dramatic animation.

Example:

```css
.nav-link {
    color: var(--text-muted);
    transition:
        color 180ms ease,
        border-color 180ms ease;
}

.nav-link:hover,
.nav-link:focus-visible {
    color: var(--accent-hover);
}
```

---

## 13. Preserve existing functionality

Do not sacrifice existing features for visual redesign.

Keep working:

- navigation by libraries;
- search by title/author/etc.;
- navigation by files;
- book reading;
- font-size controls;
- dark/light reader mode;
- current URLs/book links where possible.

Refactor implementation only where useful.

---

## 14. Inspect current implementation first

Before modifying code:

1. inspect the existing project;
2. identify the framework and component structure;
3. inspect the existing HTML/CSS/JS;
4. identify why the current interface may be slow;
5. determine which parts can be reused;
6. avoid unnecessary rewrites.

Please also inspect any example/reference HTML already present in the repository, especially an `example/` directory if available.

---

## 15. Performance investigation

Apart from the visual redesign, investigate the current performance.

Check at least:

- unnecessarily large assets;
- synchronous network requests;
- repeated API/database calls;
- inefficient search implementation;
- rendering large book lists;
- unnecessary DOM work;
- repeated parsing of metadata;
- missing caching;
- server-side response time;
- image sizes;
- font loading;
- unnecessary JavaScript dependencies.

Measure rather than guess.

Where possible, provide before/after timings.

---

## 16. Preferred implementation approach

Please implement the redesign directly in the existing project rather than building an isolated mock-up.

Before making major architectural changes:

- understand the current structure;
- preserve working functionality;
- use the smallest reasonable refactor;
- keep code maintainable.

The final result should work well on:

- desktop;
- laptop;
- tablet;
- mobile.

---

## 17. Overall design target

The site should feel like:

> entering a dimly lit old European private library, finding a book, and then opening it into a clean modern reader.

The historical image should establish mood and identity.

The interface itself should remain:

- readable;
- fast;
- restrained;
- functional;
- responsive.

Do not turn the site into a decorative historical simulation. The library image is the visual frame; books and navigation remain the primary purpose.
