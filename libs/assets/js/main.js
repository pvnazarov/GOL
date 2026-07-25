import {
  loadLibraryData, getLibraries, getCategoriesForLibrary, getCategoryLabel,
  getBooksForCategory, getBookByPath, listFolder, getAllCatalog, getLibraryLabel,
} from "./data.js";
import { runSearch } from "./search.js";
import { initRouter, navigate, currentHash, hashForLibraries, hashForFiles, hashForSearch, hashForBook } from "./router.js";
import { el, renderIncrementalList, renderBreadcrumb, bookRow, formatSize } from "./ui.js";
import { fetchBookText, renderBookContent, getFontSize, setFontSize, getFontFamily, setFontFamily, FONT_FAMILIES } from "./reader.js";

const THEME_KEY = "gol-theme";
const LAST_BOOK_KEY = "gol-last-book";

const breadcrumbEl = document.getElementById("breadcrumb");
const viewRootEl = document.getElementById("view-root");
const statusEl = document.getElementById("status");
const themeToggleBtn = document.getElementById("theme-toggle");
const tabButtons = Array.from(document.querySelectorAll(".tab"));
const topbarEl = document.querySelector(".topbar");
const fontFamilyBtn = document.getElementById("font-family-toggle");
const fontDecBtn = document.getElementById("font-dec");
const fontIncBtn = document.getElementById("font-inc");
const fontValEl = document.getElementById("font-val");

// The header is fixed (see app.css) and can wrap to two lines on narrow
// screens, so its height isn't a constant -- keep --topbar-h in sync with
// the real rendered height so #app's padding-top and the reader toolbar's
// sticky offset never sit behind or leave a gap under it.
function syncTopbarHeight() {
  document.documentElement.style.setProperty("--topbar-h", topbarEl.offsetHeight + "px");
}
window.addEventListener("resize", syncTopbarHeight);
syncTopbarHeight();

let statusHideTimer = null;
function showStatus(message, sticky = false) {
  statusEl.textContent = message;
  statusEl.classList.add("visible");
  clearTimeout(statusHideTimer);
  if (!sticky) statusHideTimer = setTimeout(() => statusEl.classList.remove("visible"), 3500);
}

function showError(message, detail) {
  viewRootEl.innerHTML = "";
  const box = el("div", "error-box", [document.createTextNode(message)]);
  if (detail) {
    const small = document.createElement("div");
    small.style.marginTop = "6px";
    small.style.fontSize = "0.85em";
    small.style.opacity = "0.85";
    small.textContent = detail;
    box.appendChild(small);
  }
  viewRootEl.appendChild(box);
}

// ---------- theme ----------
function resolveTheme(mode) {
  return mode === "system" ? (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light") : mode;
}
function themeIcon(mode, resolved) {
  if (mode === "system") return "🖥️";
  return resolved === "dark" ? "🌙" : "☀️";
}
function applyTheme(mode) {
  localStorage.setItem(THEME_KEY, mode);
  const resolved = resolveTheme(mode);
  document.documentElement.dataset.theme = resolved;
  themeToggleBtn.textContent = themeIcon(mode, resolved);
  themeToggleBtn.title = `Theme: ${mode} (click to change)`;
  themeToggleBtn.dataset.mode = mode;
}
themeToggleBtn.addEventListener("click", () => {
  const order = ["light", "dark", "system"];
  const current = themeToggleBtn.dataset.mode || "system";
  applyTheme(order[(order.indexOf(current) + 1) % order.length]);
});
matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
  if ((localStorage.getItem(THEME_KEY) || "system") === "system") applyTheme("system");
});
applyTheme(localStorage.getItem(THEME_KEY) || "system");

// ---------- reader font (size + family), controls live in the header ----------
function refreshFontFamilyBtn(family) {
  fontFamilyBtn.textContent = FONT_FAMILIES[family].label;
  fontFamilyBtn.title = `Reader font: ${FONT_FAMILIES[family].label} (click to change)`;
}
function refreshFontVal(px) {
  fontValEl.textContent = px + "px";
}
fontFamilyBtn.addEventListener("click", () => {
  const order = Object.keys(FONT_FAMILIES);
  const next = order[(order.indexOf(getFontFamily()) + 1) % order.length];
  refreshFontFamilyBtn(setFontFamily(next));
});
fontDecBtn.addEventListener("click", () => refreshFontVal(setFontSize(getFontSize() - 1)));
fontIncBtn.addEventListener("click", () => refreshFontVal(setFontSize(getFontSize() + 1)));
refreshFontFamilyBtn(setFontFamily(getFontFamily()));
refreshFontVal(setFontSize(getFontSize()));

// ---------- tabs ----------
function setActiveTab(view) {
  for (const btn of tabButtons) btn.setAttribute("aria-selected", String(btn.dataset.view === view));
}
for (const btn of tabButtons) {
  btn.addEventListener("click", () => {
    if (btn.dataset.view === "libraries") navigate(hashForLibraries([]));
    if (btn.dataset.view === "search") navigate(hashForSearch(""));
    if (btn.dataset.view === "files") navigate(hashForFiles([]));
  });
}

// ---------- debounce ----------
function debounce(fn, wait) {
  let t;
  return (...args) => {
    clearTimeout(t);
    t = setTimeout(() => fn(...args), wait);
  };
}

// ---------- "continue reading" ----------
function getLastBook() {
  try { return JSON.parse(localStorage.getItem(LAST_BOOK_KEY) || "null"); } catch { return null; }
}
function setLastBook(path, title) {
  try { localStorage.setItem(LAST_BOOK_KEY, JSON.stringify({ path, title })); } catch {}
}

// ---------- Libraries view ----------
function renderLibrariesView(path) {
  const crumbs = [{ label: "Library", href: hashForLibraries([]) }];

  if (path.length === 0) {
    renderBreadcrumb(breadcrumbEl, crumbs);
    viewRootEl.innerHTML = "";

    const lastBook = getLastBook();
    if (lastBook) {
      const link = document.createElement("a");
      link.href = hashForBook(lastBook.path, hashForLibraries([]));
      link.textContent = `Continue reading: ${lastBook.title}`;
      link.className = "search-help";
      link.style.display = "block";
      link.style.marginBottom = "10px";
      viewRootEl.appendChild(link);
    }

    const grid = el("div", "lib-grid");
    for (const lib of getLibraries()) {
      const card = el("button", "lib-card");
      card.type = "button";
      card.appendChild(el("div", "lib-title", [document.createTextNode(lib.label)]));
      card.appendChild(el("div", "lib-meta", [document.createTextNode(`${lib.categoryCount} categories • ${lib.bookCount} books`)]));
      card.addEventListener("click", () => navigate(hashForLibraries([lib.id])));
      grid.appendChild(card);
    }
    viewRootEl.appendChild(grid);
    return;
  }

  if (path.length === 1) {
    const [libId] = path;
    crumbs.push({ label: getLibraryLabel(libId) });
    renderBreadcrumb(breadcrumbEl, crumbs);
    const cats = getCategoriesForLibrary(libId);
    renderIncrementalList(viewRootEl, cats, (cat) => {
      const row = el("button", "item-row");
      row.type = "button";
      row.appendChild(el("span", "item-icon", [document.createTextNode("📁")]));
      const main = el("div", "item-main");
      main.appendChild(el("div", "item-title", [document.createTextNode(cat.label)]));
      main.appendChild(el("div", "item-sub", [document.createTextNode(cat.code)]));
      row.appendChild(main);
      row.appendChild(el("span", "item-extra", [document.createTextNode(`${cat.bookCount} books`)]));
      row.addEventListener("click", () => navigate(hashForLibraries([libId, cat.code])));
      return row;
    }, "No categories in this library.");
    return;
  }

  const [libId, catCode] = path;
  crumbs.push({ label: getLibraryLabel(libId), href: hashForLibraries([libId]) });
  crumbs.push({ label: getCategoryLabel(catCode) });
  renderBreadcrumb(breadcrumbEl, crumbs);
  const books = getBooksForCategory(libId, catCode);
  const from = currentHash();
  renderIncrementalList(viewRootEl, books, (b) => bookRow(b, (entry) => navigate(hashForBook(entry.p, from))), "No books in this category.");
}

// ---------- Files view ----------
function renderFilesView(path) {
  const crumbs = [{ label: "Files", href: hashForFiles([]) }];
  path.forEach((seg, i) => crumbs.push({ label: seg, href: hashForFiles(path.slice(0, i + 1)) }));
  renderBreadcrumb(breadcrumbEl, crumbs);

  const items = listFolder(path);
  const from = currentHash();
  renderIncrementalList(viewRootEl, items, (item) => {
    if (item.type === "dir") {
      const row = el("button", "item-row");
      row.type = "button";
      row.appendChild(el("span", "item-icon", [document.createTextNode("📁")]));
      const main = el("div", "item-main");
      main.appendChild(el("div", "item-title", [document.createTextNode(item.label === item.name ? item.name : `${item.label} (${item.name})`)]));
      row.appendChild(main);
      row.appendChild(el("span", "item-extra", [document.createTextNode(`${item.count} items`)]));
      row.addEventListener("click", () => navigate(hashForFiles([...path, item.name])));
      return row;
    }
    const row = el("button", "item-row");
    row.type = "button";
    row.appendChild(el("span", "item-icon", [document.createTextNode("📄")]));
    const main = el("div", "item-main");
    main.appendChild(el("div", "item-title", [document.createTextNode(item.meta ? item.meta.t : item.name)]));
    const sub = item.meta ? `${item.meta.a || "Unknown author"} • ${item.name}` : item.name;
    main.appendChild(el("div", "item-sub", [document.createTextNode(sub)]));
    row.appendChild(main);
    row.appendChild(el("span", "item-extra", [document.createTextNode(formatSize(item.size, "bytes"))]));
    row.addEventListener("click", () => navigate(hashForBook(item.path, from)));
    return row;
  }, "This folder is empty.");
}

// ---------- Search view ----------
function renderSearchView(initialQuery) {
  renderBreadcrumb(breadcrumbEl, [{ label: "Search" }]);
  viewRootEl.innerHTML = "";

  const box = el("div", "search-box");
  const input = document.createElement("input");
  input.type = "search";
  input.id = "search-input";
  input.placeholder = "Search title, author… try author:tolstoy or category:detect";
  input.value = initialQuery || "";
  input.autocomplete = "off";
  box.appendChild(input);
  box.appendChild(el("div", "search-help", [document.createTextNode(
    "Plain words search title + author. Field filters: "
  )]));
  const codeWrap = box.querySelector(".search-help");
  ["author:", "title:", "category:", "collection:", "file:"].forEach((f, i) => {
    if (i > 0) codeWrap.appendChild(document.createTextNode(" "));
    const code = document.createElement("code");
    code.textContent = f;
    codeWrap.appendChild(code);
  });
  viewRootEl.appendChild(box);

  const resultsEl = el("div", "");
  viewRootEl.appendChild(resultsEl);

  const catalog = getAllCatalog();

  function runAndRender(value) {
    if (!value.trim()) {
      resultsEl.innerHTML = "";
      resultsEl.appendChild(el("div", "empty-state", [document.createTextNode(`Type to search across ${catalog.length} books.`)]));
      return;
    }
    const { results } = runSearch(catalog, value);
    renderIncrementalList(resultsEl, results, (entry) => bookRow(entry, (e) => navigate(hashForBook(e.p, currentHash())), { showCategory: true }),
      "No matches. Try fewer or different words.");
  }

  const debouncedRun = debounce((value) => {
    history.replaceState(null, "", hashForSearch(value));
    runAndRender(value);
  }, 150);

  input.addEventListener("input", () => debouncedRun(input.value));
  runAndRender(input.value);
  if (!initialQuery) input.focus();
}

// ---------- Book / reader view ----------
async function renderBookView(bookPath, fromHash) {
  breadcrumbEl.innerHTML = "";
  const meta = getBookByPath(bookPath);
  const parts = bookPath.split("/");
  const title = meta ? meta.t : parts[parts.length - 1].replace(/\.zip$/i, "");

  viewRootEl.innerHTML = "";
  const toolbar = el("div", "reader-toolbar");
  const backBtn = el("button", "reader-back", [document.createTextNode("← Back")]);
  backBtn.type = "button";
  backBtn.addEventListener("click", () => {
    // Prefer the recorded origin view; falling back to history.back() here
    // would risk leaving the app entirely for a bookmarked/direct book link
    // that has no in-app "from" state.
    navigate(fromHash || hashForLibraries([]));
  });
  toolbar.appendChild(backBtn);
  toolbar.appendChild(el("div", "reader-title", [document.createTextNode(title)]));
  viewRootEl.appendChild(toolbar);

  const loading = el("div", "loading-state", [document.createTextNode("Loading book…")]);
  viewRootEl.appendChild(loading);
  showStatus(`Opening ${bookPath}…`, true);

  try {
    const text = await fetchBookText(bookPath);
    loading.remove();

    const filename = parts[parts.length - 1];
    const metaEl = el("div", "reader-meta");
    if (meta) {
      metaEl.innerHTML =
        `<div><b>${escapeHtml(meta.t)}</b></div>` +
        `<div>${escapeHtml(meta.a || "Unknown author")} • ${escapeHtml(getLibraryLabel(meta.l))} / ${escapeHtml(getCategoryLabel(meta.c))}${meta.s ? " • " + formatSize(meta.s) : ""}</div>` +
        `<div><code>${escapeHtml(filename)}</code></div>`;
    } else {
      metaEl.innerHTML = `<div><code>${escapeHtml(filename)}</code></div>`;
    }
    viewRootEl.appendChild(metaEl);

    const article = el("article", "reader-article");
    viewRootEl.appendChild(article);
    renderBookContent(article, text);
    document.title = `${title} — Good Old Library`;
    setLastBook(bookPath, title);
    showStatus(`Loaded: ${title}`);
  } catch (err) {
    loading.remove();
    showError(`Could not open this book.`, err.message);
    showStatus("Error loading book");
  }
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = String(text || "");
  return div.innerHTML;
}

// ---------- routing ----------
function dispatch(route) {
  // Tag the body with the active view so CSS can show the atmospheric library
  // photo while browsing and remove it entirely in the reader (book view).
  document.body.dataset.view = route.view;
  if (route.view === "libraries") { setActiveTab("libraries"); renderLibrariesView(route.path); }
  else if (route.view === "files") { setActiveTab("files"); renderFilesView(route.path); }
  else if (route.view === "search") { setActiveTab("search"); renderSearchView(route.query); }
  else if (route.view === "book") { renderBookView(route.path.join("/"), route.from); }
}

// ---------- keyboard shortcuts ----------
document.addEventListener("keydown", (e) => {
  if (e.key === "/" && document.activeElement.tagName !== "INPUT") {
    e.preventDefault();
    navigate(hashForSearch(""));
  } else if (e.key === "Escape" && document.activeElement.tagName === "INPUT") {
    document.activeElement.blur();
  }
});

// ---------- boot ----------
(async function boot() {
  showStatus("Loading catalogue…", true);
  try {
    const { bookCount, libraryCount } = await loadLibraryData();
    showStatus(`${bookCount} books across ${libraryCount} libraries.`);
    initRouter(dispatch);
  } catch (err) {
    showError("Failed to load the library catalogue.", err.message);
    showStatus("Initialization error", true);
  }
})();
