# Good Old Library — Light Theme Design Guide

## Purpose

This document defines the visual treatment for the **light mode** of the Good Old Library website.

The light theme should feel like an old private library viewed in soft daylight. It should complement the dark version while matching the existing reading theme based on **aged paper / parchment**.

The visual concept is:

> **Old paper + warm wood + muted colour + green marble + antique brass**

The interface should remain readable, calm, and restrained. It should not become bright white or look like a modern dashboard.

---

## Reference image

Use the following image as the primary visual reference and, where appropriate, as the browsing-page background:

![Good Old Library — light theme](library-gol-light.png)

Suggested project location:

```text
pic/library-gol-light.png
```

For production, generate an optimized WebP or AVIF version as well:

```text
pic/library-gol-light.webp
pic/library-gol-light.avif
```

---

# 1. Core light-theme palette

The colours should be derived from the reference image rather than from generic white/grey UI colours.

| Role | Colour | Purpose |
|---|---:|---|
| Old-paper background | `#E8D9B8` | Main page / reader background |
| Light parchment | `#F1E6CE` | Elevated surfaces, cards |
| Warm cream highlight | `#F6EEDC` | Very light surfaces |
| Medium parchment | `#D8C39B` | Secondary surfaces |
| Main text | `#3A2A20` | Body text |
| Dark text / headings | `#2B2019` | Strong headings |
| Muted text | `#725D49` | Metadata, secondary labels |
| Warm wood | `#765238` | Strong decorative accents |
| Dark wood | `#493326` | Borders and strong separators |
| Antique gold | `#9A7438` | Links, icons, selected states |
| Gold hover | `#B68A45` | Hover / focus state |
| Soft brass | `#B8955B` | Secondary accent |
| Green marble | `#61715B` | Distinctive historical accent |
| Dark green marble | `#465545` | Hover/strong accent |
| Burgundy | `#7B493D` | Optional secondary accent |

The palette does **not** need to use every colour everywhere. Parchment, brown, gold and green should dominate.

---

# 2. CSS variables

Recommended starting point:

```css
[data-theme="light"] {
    --bg: #e8d9b8;
    --surface: #f1e6ce;
    --surface-light: #f6eedc;
    --surface-muted: #d8c39b;

    --text: #3a2a20;
    --text-strong: #2b2019;
    --text-muted: #725d49;

    --wood: #765238;
    --wood-dark: #493326;

    --accent: #9a7438;
    --accent-hover: #b68a45;
    --brass: #b8955b;

    --green: #61715b;
    --green-dark: #465545;

    --burgundy: #7b493d;

    --border: rgba(73, 51, 38, 0.30);
    --shadow: rgba(58, 42, 32, 0.16);
}
```

These are design targets, not rigid constraints. Adjust slightly after testing against the actual image and existing UI.

---

# 3. Main page background

Use the light library image on browsing/navigation pages.

Recommended treatment:

```css
[data-theme="light"] .library-page {
    min-height: 100vh;

    background:
        linear-gradient(
            rgba(232, 217, 184, 0.14),
            rgba(232, 217, 184, 0.36)
        ),
        url("/pic/library-gol-light.webp");

    background-size: cover;
    background-position: center 28%;
    background-attachment: fixed;
}
```

The image is already light and should **not** receive a strong white overlay.

The goal is to keep visible:

- Gutenberg portrait;
- green marble fireplace;
- coloured book spines;
- wood grain;
- Beethoven bust;
- brass details.

---

# 4. Light-mode surfaces

Content panels should resemble paper laid over the library image.

Recommended:

```css
.light-panel {
    background: rgba(241, 230, 206, 0.92);
    color: var(--text);

    border: 1px solid rgba(73, 51, 38, 0.24);

    box-shadow:
        0 8px 28px rgba(58, 42, 32, 0.12);

    border-radius: 6px;
}
```

Avoid pure white:

```css
/* Avoid */
background: #ffffff;
```

Use warm cream/parchment instead.

---

# 5. Typography

Primary text:

```css
color: #3a2a20;
```

Headings:

```css
color: #2b2019;
```

Secondary information:

```css
color: #725d49;
```

Links and active navigation:

```css
color: #9a7438;
```

Hover:

```css
color: #b68a45;
```

Do not use black (`#000`) for normal text unless needed for accessibility in a specific component.

---

# 6. Green marble as the characteristic accent

The green marble around the fireplace is an important counterbalance to the warm brown/parchment palette.

Use this selectively in the UI.

Good uses include:

- active library indicator;
- selected navigation item;
- small icons;
- separators;
- search-field focus;
- subtle badges;
- progress indicator.

Example:

```css
.nav-link.active {
    color: var(--green-dark);
    border-bottom: 2px solid var(--green);
}
```

Do not turn the whole interface green. It should remain an accent derived from the fireplace.

---

# 7. Gold / brass accents

Use antique gold for interactive elements rather than bright yellow.

```css
a {
    color: var(--accent);
}

a:hover,
a:focus-visible {
    color: var(--accent-hover);
}
```

Good targets:

- links;
- icons;
- button outlines;
- selected states;
- tiny decorative separators.

Avoid large solid gold areas.

---

# 8. Search field

The search field is a major UI element and should resemble a clean paper surface.

Example:

```css
.search-input {
    background: rgba(246, 238, 220, 0.96);
    color: var(--text-strong);

    border: 1px solid rgba(73, 51, 38, 0.32);

    box-shadow:
        inset 0 1px 2px rgba(58, 42, 32, 0.08);
}

.search-input::placeholder {
    color: var(--text-muted);
}

.search-input:focus {
    outline: none;
    border-color: var(--green);
    box-shadow:
        0 0 0 2px rgba(97, 113, 91, 0.18);
}
```

---

# 9. Buttons

Primary button:

```css
.button-primary {
    background: #765238;
    color: #f6eedc;
    border: 1px solid #493326;
}

.button-primary:hover {
    background: #63452f;
}
```

Alternative accent button:

```css
.button-accent {
    background: #61715b;
    color: #f6eedc;
    border: 1px solid #465545;
}
```

Avoid bright blue default browser-style buttons.

---

# 10. Library / book cards

Recommended visual structure:

```css
.book-card {
    background: rgba(241, 230, 206, 0.94);
    border: 1px solid rgba(73, 51, 38, 0.22);
    box-shadow: 0 4px 14px rgba(58, 42, 32, 0.10);
}

.book-card:hover {
    background: rgba(246, 238, 220, 0.98);
    border-color: rgba(154, 116, 56, 0.55);
}
```

Keep shadows weak. The page should feel like paper and wood, not floating glass cards.

---

# 11. Reader mode

Do **not** use the library photograph behind book text.

The reading view should be quiet.

Suggested light reader colours:

```css
[data-theme="light"] .reader {
    --reader-bg: #e8d9b8;
    --reader-page: #f1e6ce;
    --reader-text: #30251d;
    --reader-muted: #725d49;
}
```

A slightly lighter inner reading area is appropriate:

```css
.reader-page {
    background: #f1e6ce;
    color: #30251d;
}
```

The reader should evoke old paper without adding fake stains or aggressive texture behind the text.

---

# 12. Navigation

Use wood and gold/green rather than standard grey UI conventions.

Default:

```css
.nav-link {
    color: #725d49;
}
```

Hover:

```css
.nav-link:hover {
    color: #9a7438;
}
```

Active:

```css
.nav-link.active {
    color: #465545;
    border-bottom-color: #61715b;
}
```

This introduces the green-marble accent in a controlled way.

---

# 13. Borders and separators

Use translucent dark brown rather than grey:

```css
border-color: rgba(73, 51, 38, 0.25);
```

For stronger separators:

```css
border-color: #b8955b;
```

or:

```css
border-color: #61715b;
```

Use gold/green separators only sparingly.

---

# 14. Shadows

Shadows should be warm:

```css
box-shadow:
    0 8px 24px rgba(58, 42, 32, 0.14);
```

Avoid neutral/blue-black shadows such as:

```css
rgba(0, 0, 0, 0.35)
```

unless used very subtly.

---

# 15. Image-specific visual identity

Preserve the following features when generating future variants of the light image:

- Johannes Gutenberg portrait above the fireplace;
- Beethoven bust on the right;
- green-veined marble fireplace surround;
- three **unlit** candles;
- clearly visible **black wicks**;
- warm natural wood;
- coloured antique book spines;
- brass fireplace accessories;
- burgundy chair upholstery;
- muted oriental rug colours;
- soft daylight rather than candlelight.

These details create continuity between the site's visual identity and the library image.

---

# 16. Avoid excessive monochrome treatment

The earlier light version became too uniformly beige.

The final version deliberately restores restrained colour.

Maintain:

- green marble;
- green/blue/red/brown book bindings;
- burgundy upholstery;
- warm gold/brass;
- darker brick fireplace interior;
- varied natural wood tones.

The overall image should remain warm, but individual materials should still be distinguishable.

---

# 17. Relationship to dark mode

The light and dark versions should represent the **same conceptual room** under different lighting conditions.

### Dark mode

- evening / candlelight;
- dark walnut;
- deep shadows;
- gold highlights;
- intimate atmosphere.

### Light mode

- soft daylight;
- parchment;
- honey/medium wood;
- green marble;
- muted coloured books;
- antique brass.

They should feel related, not like two unrelated themes.

---

# 18. Recommended asset naming

```text
pic/
├── library-gol-dark.webp
├── library-gol-light.webp
├── library-gol-dark.png
└── library-gol-light.png
```

Theme switch:

```css
[data-theme="dark"] .library-page {
    background-image:
        linear-gradient(
            rgba(10, 7, 5, 0.30),
            rgba(10, 7, 5, 0.55)
        ),
        url("/pic/library-gol-dark.webp");
}

[data-theme="light"] .library-page {
    background-image:
        linear-gradient(
            rgba(232, 217, 184, 0.14),
            rgba(232, 217, 184, 0.36)
        ),
        url("/pic/library-gol-light.webp");
}
```

---

# 19. Performance

For production:

1. preserve the PNG as the master;
2. generate WebP and optionally AVIF;
3. resize to the actual maximum rendering resolution;
4. avoid serving the full master PNG unnecessarily;
5. use a separate mobile crop if needed.

Suggested desktop width:

```text
1600–2000 px
```

A 4:3 source can be retained as the master, but a wider desktop crop may eventually work better for full-screen backgrounds.

---

# 20. Overall target

The light theme should feel like:

> **an old European library illuminated by quiet daylight, with the interface printed on warm aged paper.**

The UI should not compete with the image.

Use:

- parchment for surfaces;
- dark brown for text;
- warm wood for structure;
- antique gold for interaction;
- green marble for identity and selected states;
- restrained burgundy as an optional secondary accent.

The result should remain elegant, readable and slightly historical without becoming theatrical or overly decorative.
