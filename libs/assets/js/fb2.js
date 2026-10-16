// Renders a FictionBook 2 (.fb2) document as reader HTML. Loaded on demand
// by main.js only when an opened book's zip holds an .fb2 instead of a .txt.
//
// FB2 is XML: <description> carries the metadata (title, authors, annotation,
// cover), one <body> holds the book as nested <section>s, and optional extra
// bodies hold footnotes; images are base64 <binary> elements. The browser's own
// DOMParser does the parsing. Output is built with createElement/textContent
// only -- nothing from the file is ever inserted as HTML, so a hostile book
// can't inject markup or script. Only image/* binaries become data: URIs and
// only http(s) links become real links.
//
// Some FB2 files are careless conversions of hard-wrapped plain text: every
// ~75-character *line* became its own <p>. Those are detected (most <p>s end
// near one common width) and their lines are joined back into paragraphs.

const FB2_NS = "http://www.gribuser.ru/xml/fictionbook/2.0";
const XLINK_NS = "http://www.w3.org/1999/xlink";
const ID_PREFIX = "fb2-";

// Inline FB2 elements -> HTML tags. Anything unknown is rendered as its
// children only, so new or vendor-specific tags degrade to plain text.
const INLINE = {
  emphasis: "em", strong: "strong", strikethrough: "s",
  sub: "sub", sup: "sup", code: "code", style: "span",
};

// Decode the raw .fb2 bytes, honouring the XML declaration's encoding
// (older FB2 files are often windows-1251).
export function decodeFb2(bytes) {
  const head = new TextDecoder("ascii").decode(bytes.subarray(0, 200));
  const match = head.match(/encoding\s*=\s*["']([\w-]+)["']/i);
  let decoder;
  try { decoder = new TextDecoder(match ? match[1] : "utf-8"); }
  catch { decoder = new TextDecoder("utf-8"); }
  return decoder.decode(bytes);
}

export function parseFb2(xmlText) {
  const doc = new DOMParser().parseFromString(xmlText, "application/xml");
  if (doc.getElementsByTagName("parsererror").length) {
    throw new Error("This FB2 file is not well-formed XML");
  }
  return doc;
}

// Direct children of `node` in the FB2 namespace, optionally by local name.
// Walks siblings rather than `node.children`, which is slow to index on the
// huge single-section bodies some converted books have.
function kids(node, name) {
  const out = [];
  for (let c = node.firstElementChild; c; c = c.nextElementSibling) {
    if (c.namespaceURI === FB2_NS && (!name || c.localName === name)) out.push(c);
  }
  return out;
}

function href(node) {
  return node.getAttributeNS(XLINK_NS, "href") || node.getAttribute("href") || "";
}

function text(node) {
  return node.textContent.replace(/\s+/g, " ").trim();
}

// ---------- reflow of hard-wrapped line-per-<p> books ----------
const DASH_START = /^[-–—]\s/;
const SENTENCE_END = /[.!?…»"'):;]$/;
const CONTINUES = /[,\-–(]$/;
const HEADING = /^(ЧАСТЬ|Часть|ГЛАВА|Глава|КНИГА|Книга|PART|Part|CHAPTER|Chapter|BOOK|Book)\s+\S+$|^\d{1,3}\.?$|^[IVXLC]{1,6}\.?$/;

function isUpper(t) {
  return /[A-ZА-ЯЁ].*[A-ZА-ЯЁ]/.test(t) && !/[a-zа-яё]/.test(t);
}

// The wrap width if the document looks hard-wrapped, else 0.
function detectWrapWidth(doc) {
  const lengths = [];
  // Plain tree walk: indexing a live getElementsByTagNameNS collection of
  // ~20k nodes is quadratic in some DOM implementations.
  const walk = (node) => {
    for (let c = node.firstElementChild; c; c = c.nextElementSibling) {
      if (c.localName === "binary") continue;
      if (c.localName === "p") {
        const n = text(c).length;
        if (n) lengths.push(n);
      } else {
        walk(c);
      }
    }
  };
  walk(doc.documentElement);
  if (lengths.length < 200) return 0;
  lengths.sort((a, b) => a - b);
  const width = lengths[Math.floor(lengths.length * 0.99)];
  const nearWidth = lengths.filter((n) => n >= width - 20 && n <= width).length;
  return width <= 100 && nearWidth >= lengths.length / 2 ? width : 0;
}

// Does a paragraph end after line `cur` (followed by line `next`)?
function endsParagraph(cur, next, width) {
  if (!next) return true;
  if (DASH_START.test(next) || isUpper(cur) || isUpper(next) || HEADING.test(cur) || HEADING.test(next)) return true;
  // At a sentence end: a break unless the next word would not have fitted
  // on this line -- i.e. the line was only ended by wrapping.
  if (SENTENCE_END.test(cur)) return cur.length + 1 + next.split(" ")[0].length <= width;
  // Mid-sentence lines continue, except short standalone lines (titles,
  // signatures) followed by a capitalised line.
  return cur.length < width / 2 && !CONTINUES.test(cur) && /^[A-ZА-ЯЁ]/.test(next);
}

class Renderer {
  constructor(doc, container) {
    this.doc = doc;
    this.container = container;
    this.binaries = new Map();
    for (const b of doc.getElementsByTagNameNS(FB2_NS, "binary")) {
      this.binaries.set(b.getAttribute("id"), b);
    }
    this.toc = [];
    this.wrapWidth = detectWrapWidth(doc);
  }

  // Joins a run of consecutive line-<p>s back into paragraphs.
  reflow(run) {
    const lines = run.map(text);
    const out = [];
    let cur = null;
    lines.forEach((line, i) => {
      if (!cur) cur = this.withId(run[i], document.createElement("p"));
      else cur.appendChild(document.createTextNode(" "));
      this.inline(run[i], cur);
      if (!endsParagraph(line, lines[i + 1] || "", this.wrapWidth)) return;
      const standalone = !cur.childNodes.length || cur.textContent.trim() === line;
      if (standalone && (HEADING.test(line) || isUpper(line))) {
        cur.className = "fb2-subtitle";
        if (HEADING.test(line)) {
          if (!cur.id) cur.id = `${ID_PREFIX}toc-${this.toc.length}`;
          this.toc.push({ id: cur.id.slice(ID_PREFIX.length), label: line, depth: 2 });
        }
      }
      out.push(cur);
      cur = null;
    });
    if (cur) out.push(cur);
    return out;
  }

  // Internal links/footnotes: scrolled to by script, since the app's
  // hash-based router owns location.hash.
  jumpTo(id) {
    const target = this.container.querySelector(`[id="${CSS.escape(ID_PREFIX + id)}"]`);
    if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  withId(src, el) {
    const id = src.getAttribute("id");
    if (id) el.id = ID_PREFIX + id;
    return el;
  }

  inline(node, parent) {
    for (const child of node.childNodes) {
      if (child.nodeType === Node.TEXT_NODE) {
        // XML line breaks inside a paragraph are just source wrapping.
        parent.appendChild(document.createTextNode(child.data.replace(/\s+/g, " ")));
      } else if (child.nodeType === Node.ELEMENT_NODE) {
        parent.appendChild(this.inlineElement(child));
      }
    }
    return parent;
  }

  inlineElement(node) {
    const name = node.localName;
    if (name === "a") return this.link(node);
    if (name === "image") return this.image(node, true) || document.createTextNode("");
    const el = document.createElement(INLINE[name] || "span");
    return this.inline(node, el);
  }

  link(node) {
    const target = href(node);
    if (target.startsWith("#")) {
      const a = document.createElement("a");
      a.href = "javascript:void(0)";
      a.className = node.getAttribute("type") === "note" ? "fb2-noteref" : "fb2-link";
      a.addEventListener("click", (e) => { e.preventDefault(); this.jumpTo(target.slice(1)); });
      return this.inline(node, a);
    }
    if (/^https?:\/\//i.test(target)) {
      const a = document.createElement("a");
      a.href = target;
      a.target = "_blank";
      a.rel = "noopener noreferrer";
      return this.inline(node, a);
    }
    return this.inline(node, document.createElement("span"));
  }

  image(node, inline = false) {
    const binary = this.binaries.get(href(node).replace(/^#/, ""));
    const type = binary && binary.getAttribute("content-type");
    if (!binary || !/^image\/(jpeg|png|gif|webp)$/i.test(type || "")) return null;
    const img = document.createElement("img");
    img.src = `data:${type};base64,${binary.textContent.replace(/\s+/g, "")}`;
    img.alt = node.getAttribute("alt") || "";
    img.loading = "lazy";
    img.className = inline ? "fb2-inline-image" : "fb2-image";
    return this.withId(node, img);
  }

  // Block-level content of a section, epigraph, cite, annotation, etc.
  blocks(node, parent, depth) {
    let run = [];
    const flush = () => {
      for (const p of this.reflow(run)) parent.appendChild(p);
      run = [];
    };
    for (const child of kids(node)) {
      if (this.wrapWidth && child.localName === "p") { run.push(child); continue; }
      if (run.length) flush();
      const el = this.block(child, depth);
      if (el) parent.appendChild(el);
    }
    if (run.length) flush();
    return parent;
  }

  block(node, depth) {
    switch (node.localName) {
      case "p": return this.withId(node, this.inline(node, document.createElement("p")));
      case "empty-line": return el("div", "fb2-gap");
      case "subtitle": return this.withId(node, this.inline(node, el("p", "fb2-subtitle")));
      case "text-author": return this.inline(node, el("p", "fb2-text-author"));
      case "title": return this.title(node, depth);
      case "section": return this.section(node, depth + 1);
      case "image": return this.image(node);
      case "epigraph": return this.withId(node, this.blocks(node, el("blockquote", "fb2-epigraph"), depth));
      case "cite": return this.withId(node, this.blocks(node, el("blockquote", "fb2-cite"), depth));
      case "annotation": return this.blocks(node, el("div", "fb2-annotation"), depth);
      case "poem": return this.withId(node, this.blocks(node, el("div", "fb2-poem"), depth));
      case "stanza": return this.blocks(node, el("div", "fb2-stanza"), depth);
      case "v": return this.inline(node, el("p", "fb2-verse"));
      case "date": return this.inline(node, el("p", "fb2-date"));
      case "table": return this.table(node);
      default: return this.blocks(node, el("div"), depth);
    }
  }

  title(node, depth) {
    const level = Math.min(6, depth + 1);
    const h = el(`h${level}`, "fb2-title");
    kids(node).forEach((p, i) => {
      if (i) h.appendChild(document.createElement("br"));
      if (p.localName === "p") this.inline(p, h);
    });
    return h;
  }

  section(node, depth) {
    const sec = this.withId(node, el("section", "fb2-section"));
    const title = kids(node, "title")[0];
    if (title && depth <= 3 && text(title)) {
      if (!sec.id) sec.id = `${ID_PREFIX}toc-${this.toc.length}`;
      const label = kids(title, "p").map(text).filter(Boolean).join(" · ") || text(title);
      this.toc.push({ id: sec.id.slice(ID_PREFIX.length), label, depth });
    }
    return this.blocks(node, sec, depth);
  }

  table(node) {
    const table = el("table", "fb2-table");
    for (const tr of kids(node, "tr")) {
      const row = document.createElement("tr");
      for (const cell of kids(tr)) {
        row.appendChild(this.inline(cell, document.createElement(cell.localName === "th" ? "th" : "td")));
      }
      table.appendChild(row);
    }
    return table;
  }

  // Cover and annotation from <description><title-info>.
  front() {
    const info = this.doc.getElementsByTagNameNS(FB2_NS, "title-info")[0];
    if (!info) return null;
    const front = el("div", "fb2-front");
    const cover = kids(info, "coverpage")[0];
    const coverImage = cover && kids(cover, "image")[0];
    const img = coverImage && this.image(coverImage);
    if (img) { img.className = "fb2-cover"; front.appendChild(img); }
    const annotation = kids(info, "annotation")[0];
    if (annotation) front.appendChild(this.blocks(annotation, el("div", "fb2-annotation"), 1));
    return front.childNodes.length ? front : null;
  }

  tocElement(contentsLabel) {
    if (this.toc.length < 3) return null;
    const details = el("details", "fb2-toc");
    const summary = document.createElement("summary");
    summary.textContent = `${contentsLabel} (${this.toc.length})`;
    details.appendChild(summary);
    const list = el("ol");
    for (const item of this.toc) {
      const li = el("li", `fb2-toc-depth-${item.depth}`);
      const button = el("button");
      button.type = "button";
      button.textContent = item.label;
      button.addEventListener("click", () => this.jumpTo(item.id));
      li.appendChild(button);
      list.appendChild(li);
    }
    details.appendChild(list);
    return details;
  }

  render() {
    const root = this.doc.documentElement;
    const bodies = kids(root, "body");
    const frag = document.createDocumentFragment();
    bodies.forEach((body, i) => {
      const wrap = el("div", i === 0 ? "fb2-body" : "fb2-notes");
      if (i > 0) wrap.appendChild(el("hr", "fb2-rule"));
      this.blocks(body, wrap, 0);
      frag.appendChild(wrap);
    });
    const lang = (this.doc.getElementsByTagNameNS(FB2_NS, "lang")[0]?.textContent || "").trim();
    const front = this.front();
    const toc = this.tocElement(lang.startsWith("ru") ? "Содержание" : "Contents");
    if (toc) frag.prepend(toc);
    if (front) frag.prepend(front);
    this.container.appendChild(frag);
  }
}

function el(tag, className) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  return node;
}

export function renderFb2(container, doc) {
  container.innerHTML = "";
  container.classList.add("fb2");
  new Renderer(doc, container).render();
}
