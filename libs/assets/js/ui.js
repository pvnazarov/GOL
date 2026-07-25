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
export function renderIncrementalList(container, items, renderRow, emptyMessage) {
  container.innerHTML = "";
  if (!items.length) {
    container.appendChild(el("div", "empty-state", [document.createTextNode(emptyMessage || "Nothing here.")]));
    return;
  }

  const list = el("div", "item-list");
  container.appendChild(list);
  let shown = 0;

  function renderMore() {
    const next = items.slice(shown, shown + PAGE_SIZE);
    const frag = document.createDocumentFragment();
    for (const item of next) frag.appendChild(renderRow(item));
    list.appendChild(frag);
    shown += next.length;
    loadMoreWrap.remove();
    if (shown < items.length) container.appendChild(loadMoreWrap);
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

  renderMore();
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
  const row = el("button", "item-row");
  row.type = "button";
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
  return row;
}
