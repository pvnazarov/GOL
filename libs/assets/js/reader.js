// Fetches a single book's zip on demand, unzips it client-side (JSZip),
// and renders it as readable typography. The old collections are plain UTF-8
// .txt files (confirmed -- see scripts/check_encoding.py); newer sets may hold
// a FictionBook .fb2 instead, which fb2.js renders. Either way there is no
// per-book HTML/CSS to sandbox.
//
// Legacy cover-page ASCII art / box-drawing banners only line up in a
// monospace font, so lines that look like "graphics" (few letters, lots of
// symbols, or actual box-drawing characters) are rendered in <pre> blocks;
// everything else is rendered as ordinary paragraphs in the reading font.
// Detection runs on the whole file (not just the head) since these banners
// can appear anywhere, not only at the top.

const bookCache = new Map(); // path -> {format, text}, kept for this page's lifetime

// JSZip (~28 KB gzipped) is only needed once a book is actually opened, so it
// is not in the initial <script> payload -- it's injected on first use and
// cached as a promise so later opens reuse the same loaded instance.
let jszipPromise = null;
function loadJSZip() {
  if (window.JSZip) return Promise.resolve(window.JSZip);
  if (!jszipPromise) {
    jszipPromise = new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = "assets/vendor/jszip.min.js";
      script.onload = () => resolve(window.JSZip);
      script.onerror = () => reject(new Error("Failed to load JSZip"));
      document.head.appendChild(script);
    });
  }
  return jszipPromise;
}

const FONT_KEY = "gol-font-size";
const MIN_FONT = 13;
const MAX_FONT = 32;
const DEFAULT_FONT = 18;

const FONT_FAMILY_KEY = "gol-font-family";
const DEFAULT_FONT_FAMILY = "mono";
// Old plain-text books were formatted assuming a monospace terminal (fixed
// column widths, ASCII-art banners), so monospace is the default reading
// font; serif is offered as an alternative for plain prose. Both stacks use
// only faces present on essentially every OS so the choice looks the same
// everywhere.
export const FONT_FAMILIES = {
  mono: { label: "Mono", stack: 'ui-monospace, SFMono-Regular, "Cascadia Mono", Menlo, Consolas, "Liberation Mono", monospace' },
  serif: { label: "Serif", stack: 'Georgia, "Iowan Old Style", "Palatino Linotype", "Book Antiqua", serif' },
};

const BOX_DRAWING_RE = /[─-▟]/; // box drawing + block elements
const LETTER_RE = /\p{L}/gu;

function classifyLine(line) {
  if (BOX_DRAWING_RE.test(line)) return "graphic";
  const trimmed = line.trim();
  if (!trimmed) return "text";
  // Ratio is measured against non-whitespace characters only: old plain-text
  // books often right-align short fragments with long runs of padding spaces
  // (e.g. "Amendment I                    (1791)"), which would otherwise
  // look symbol-heavy and get misclassified as decorative ASCII art.
  const stripped = trimmed.replace(/\s+/g, "");
  if (stripped.length < 4) return "text";
  const letters = (stripped.match(LETTER_RE) || []).length;
  if (letters / stripped.length < 0.35) return "graphic";
  return "text";
}

function groupLines(lines) {
  const blocks = [];
  for (const line of lines) {
    const type = classifyLine(line);
    const last = blocks[blocks.length - 1];
    if (last && last.type === type) last.lines.push(line);
    else blocks.push({ type, lines: [line] });
  }
  return blocks;
}

// Returns {format: "txt" | "fb2", text}.
export async function fetchBook(path) {
  if (bookCache.has(path)) return bookCache.get(path);
  const [response, JSZip] = await Promise.all([fetch(path), loadJSZip()]);
  if (!response.ok) throw new Error(`HTTP ${response.status} fetching ${path}`);
  const buffer = await response.arrayBuffer();
  const zip = await JSZip.loadAsync(buffer);
  const names = Object.keys(zip.files).filter((n) => !zip.files[n].dir);
  if (!names.length) throw new Error("Archive is empty");
  const target = names.find((n) => n.toLowerCase().endsWith(".txt"))
    || names.find((n) => n.toLowerCase().endsWith(".fb2"))
    || names[0];
  let book;
  if (target.toLowerCase().endsWith(".fb2")) {
    // FB2 declares its own encoding in the XML header, so decode from bytes.
    const [{ decodeFb2 }, bytes] = await Promise.all([
      import("./fb2.js"), zip.files[target].async("uint8array")]);
    if (!bytes.length) throw new Error("The book file inside the archive is empty");
    book = { format: "fb2", text: decodeFb2(bytes) };
  } else {
    let text = await zip.files[target].async("string");
    text = text.replace(/^\uFEFF/, "").replace(/\r\n/g, "\n").replace(/\r/g, "\n");
    book = { format: "txt", text };
  }
  bookCache.set(path, book);
  return book;
}

export function renderBookContent(container, text) {
  container.innerHTML = "";
  const blocks = groupLines(text.split("\n"));
  const frag = document.createDocumentFragment();
  for (const block of blocks) {
    const content = block.lines.join("\n");
    if (!content.trim()) continue;
    const el = document.createElement(block.type === "graphic" ? "pre" : "p");
    el.textContent = content;
    frag.appendChild(el);
  }
  container.appendChild(frag);
}

export function getFontSize() {
  const stored = parseInt(localStorage.getItem(FONT_KEY), 10);
  return Number.isFinite(stored) ? clampFont(stored) : DEFAULT_FONT;
}

export function clampFont(px) {
  return Math.min(MAX_FONT, Math.max(MIN_FONT, px));
}

export function setFontSize(px) {
  const clamped = clampFont(px);
  localStorage.setItem(FONT_KEY, String(clamped));
  document.documentElement.style.setProperty("--reader-font-size", clamped + "px");
  return clamped;
}

export function getFontFamily() {
  const stored = localStorage.getItem(FONT_FAMILY_KEY);
  return FONT_FAMILIES[stored] ? stored : DEFAULT_FONT_FAMILY;
}

export function setFontFamily(name) {
  const key = FONT_FAMILIES[name] ? name : DEFAULT_FONT_FAMILY;
  localStorage.setItem(FONT_FAMILY_KEY, key);
  document.documentElement.style.setProperty("--reader-font-family", FONT_FAMILIES[key].stack);
  return key;
}
