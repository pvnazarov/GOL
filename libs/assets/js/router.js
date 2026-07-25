// Minimal hash-based router. The hash fully describes app state so
// back/forward/reload/bookmarking all behave predictably.
//
// Routes:
//   #/                              libraries: root (list of libraries)
//   #/libraries/<lib>                libraries: categories of one library
//   #/libraries/<lib>/<cat>           libraries: books in one category
//   #/search?q=...                  search view
//   #/files                         files: root
//   #/files/<lib>                    files: one library's categories
//   #/files/<lib>/<cat>               files: files in one category
//   #/book/<lib>/<cat>/<filename>?from=<encoded-hash-to-return-to>

let onRouteChange = () => {};

export function initRouter(callback) {
  onRouteChange = callback;
  window.addEventListener("hashchange", () => onRouteChange(parseRoute()));
  if (!location.hash) {
    location.hash = "#/"; // triggers hashchange, which dispatches below
  } else {
    onRouteChange(parseRoute());
  }
}

export function navigate(hash) {
  if (location.hash === hash) {
    onRouteChange(parseRoute()); // same hash: re-dispatch (e.g. re-clicking a tab)
  } else {
    location.hash = hash;
  }
}

export function currentHash() {
  return location.hash || "#/";
}

function parseRoute() {
  const raw = (location.hash || "#/").slice(1); // drop leading '#'
  const [pathPart, queryPart] = raw.split("?");
  const segments = pathPart.split("/").filter(Boolean).map(decodeURIComponent);
  const params = new URLSearchParams(queryPart || "");

  if (segments.length === 0) return { view: "libraries", path: [] };

  const [head, ...rest] = segments;
  if (head === "search") return { view: "search", query: params.get("q") || "" };
  if (head === "files") return { view: "files", path: rest };
  if (head === "libraries") return { view: "libraries", path: rest };
  if (head === "book") {
    // URLSearchParams already percent-decodes values, so params.get("from")
    // is the plain "#/..." hash -- decoding it again would be wrong if a
    // path segment ever contained a literal "%".
    return { view: "book", path: rest, from: params.get("from") };
  }
  return { view: "libraries", path: [] };
}

export function hashForLibraries(path = []) {
  return `#/libraries/${path.map(encodeURIComponent).join("/")}`.replace(/\/$/, "");
}

export function hashForFiles(path = []) {
  return `#/files/${path.map(encodeURIComponent).join("/")}`.replace(/\/$/, "");
}

export function hashForSearch(q = "") {
  return q ? `#/search?q=${encodeURIComponent(q)}` : "#/search";
}

export function hashForBook(bookPath, fromHash) {
  const encodedPath = bookPath.split("/").map(encodeURIComponent).join("/");
  const from = fromHash ? `?from=${encodeURIComponent(fromHash)}` : "";
  return `#/book/${encodedPath}${from}`;
}
