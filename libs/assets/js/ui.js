// Small rendering helpers shared by the libraries/files/search views.
// Lists render incrementally (an initial page + a "load more" button) instead
// of building thousands of DOM nodes up front -- some categories have 1900+
// books, and unbounded search results can be much larger.

const PAGE_SIZE = 150;

export function el(tag, className, children) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (children) for (const c of children) node.appendChild(c);
  return node;
}

export function formatSize(kbOrBytes, unit) {
  const kb = unit === "bytes" ? kbOrBytes / 1024 : kbOrBytes;
  if (kb == null || Number.isNaN(kb)) return "";
  if (kb < 1024) return `${Math.max(1, Math.round(kb))} KB`;
  return `${(kb / 1024).toFixed(1)} MB`;
}

// Renders `items` into `container` using `renderRow(item) -> HTMLElement`,
// paging in more rows as the user clicks "load more" (or scrolls near it).
// Multi-column ("cols") lists read top-to-bottom, then left-to-right. CSS
// decides how many columns fit (auto-fill); here we read that count back and
// set rows = ceil(n / cols) with column-major flow. Only one list is live at a
// time, so a single observer is reused and disconnected on re-render.
let colsObserver = null;

function layoutColumns(list) {
  const cols = getComputedStyle(list).gridTemplateColumns.split(" ").filter(Boolean).length || 1;
  const rows = Math.max(1, Math.ceil(list.children.length / cols));
  list.style.gridTemplateRows = `repeat(${rows}, auto)`;
  list.style.gridAutoFlow = "column";
}

// `listClass` adds a modifier class to the list (e.g. "cols" for a multi-column grid).
export function renderIncrementalList(container, items, renderRow, emptyMessage, listClass) {
  if (colsObserver) { colsObserver.disconnect(); colsObserver = null; }
  container.innerHTML = "";
  if (!items.length) {
    container.appendChild(el("div", "empty-state", [document.createTextNode(emptyMessage || "Nothing here.")]));
    return;
  }

  const list = el("div", listClass ? `item-list ${listClass}` : "item-list");
  container.appendChild(list);
  let shown = 0;

  function renderMore() {
    const next = items.slice(shown, shown + PAGE_SIZE);
    const frag = document.createDocumentFragment();
    for (const item of next) frag.appendChild(renderRow(item));
    list.appendChild(frag);
    shown += next.length;
    if (isCols) layoutColumns(list);
    loadMoreWrap.remove();
    if (shown < items.length) list.after(loadMoreWrap);
  }

  const loadMoreWrap = el("div", "load-more-wrap");
  const btn = el("button", "load-more-btn");
  btn.type = "button";
  btn.textContent = `Show more (${items.length - PAGE_SIZE} remaining)`;
  btn.addEventListener("click", () => {
    renderMore();
    if (shown < items.length) {
      loadMoreWrap.querySelector("button").textContent = `Show more (${items.length - shown} remaining)`;
    }
  });
  loadMoreWrap.appendChild(btn);

  const isCols = (listClass || "").split(" ").includes("cols");
  if (isCols && typeof ResizeObserver !== "undefined") {
    colsObserver = new ResizeObserver(() => layoutColumns(list));
    colsObserver.observe(list);
  }
  renderMore();
}

// A library note (disclaimer etc.), built without innerHTML; only http(s) links.
export function libraryNote(note) {
  const box = el("aside", "lib-note");
  if (note.title) box.appendChild(el("div", "lib-note-title", [document.createTextNode(note.title)]));
  for (const para of note.paragraphs || []) {
    const p = el("p");
    for (const seg of para) {
      if (typeof seg === "string") { p.appendChild(document.createTextNode(seg)); continue; }
      if (seg && /^https?:\/\//.test(seg.href || "")) {
        const a = el("a", null, [document.createTextNode(seg.text || seg.href)]);
        a.href = seg.href; a.target = "_blank"; a.rel = "noopener";
        p.appendChild(a);
      } else if (seg && seg.text) {
        p.appendChild(document.createTextNode(seg.text));
      }
    }
    box.appendChild(p);
  }
  return box;
}

export function renderBreadcrumb(container, parts) {
  container.innerHTML = "";
  parts.forEach((part, i) => {
    if (i > 0) container.appendChild(el("span", "sep", [document.createTextNode("/")]));
    if (part.href && i < parts.length - 1) {
      const a = document.createElement("a");
      a.href = part.href;
      a.textContent = part.label;
      container.appendChild(a);
    } else {
      container.appendChild(el("span", "current", [document.createTextNode(part.label)]));
    }
  });
}

function filenameOf(path) {
  return path.split("/").pop();
}

export function bookRow(entry, onOpen, options) {
  const opts = options || {};
  // A div rather than a <button>, so the summary's own "more" button is not
  // nested inside another button; keyboard users still get Enter/Space.
  const row = el("div", "item-row book-row");
  row.tabIndex = 0;
  row.setAttribute("role", "button");
  const main = el("div", "item-main");
  main.appendChild(el("div", "item-title", [document.createTextNode(entry.t || entry.p)]));
  const subParts = [entry.a || "Unknown author"];
  if (opts.showCategory) subParts.push(`${entry.l} / ${entry.c}`);
  subParts.push(filenameOf(entry.p));
  main.appendChild(el("div", "item-sub", [document.createTextNode(subParts.join(" • "))]));
  row.appendChild(el("span", "item-icon", [document.createTextNode("📖")]));
  row.appendChild(main);
  if (entry.s) row.appendChild(el("span", "item-extra", [document.createTextNode(formatSize(entry.s))]));
  row.addEventListener("click", () => onOpen(entry));
  row.addEventListener("keydown", (e) => {
    if (e.target === row && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); onOpen(entry); }
  });
  if (opts.summary) opts.summary(entry).then((text) => { if (text) main.appendChild(summarySnippet(text)); });
  return row;
}

// Two clamped lines under the author; "ещё" expands them in place (and does
// not open the book). The toggle only appears when the text is actually cut.
function summarySnippet(text) {
  const wrap = el("div", "item-summary");
  const body = el("div", "item-summary-text", [document.createTextNode(text)]);
  body.title = text;
  const toggle = el("button", "item-summary-toggle", [document.createTextNode("▾ ещё")]);
  toggle.type = "button";
  toggle.hidden = true;
  toggle.addEventListener("click", (e) => {
    e.stopPropagation();
    const open = wrap.classList.toggle("open");
    toggle.textContent = open ? "▴ свернуть" : "▾ ещё";
    body.title = open ? "" : text;
  });
  wrap.appendChild(body);
  wrap.appendChild(toggle);
  requestAnimationFrame(() => { toggle.hidden = body.scrollHeight <= body.clientHeight + 1; });
  return wrap;
}
