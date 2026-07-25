// Field-prefixed search over the in-memory catalogue.
// Plain words match title+author (the most useful combined fields);
// "field:value" restricts to one field. Multi-word values can be quoted.
//
//   tolstoy war          -> title/author contains both words
//   author:tolstoy        -> author field only
//   title:"war and peace" -> quoted multi-word value
//   category:detect collection:rus2004

const FIELD_ALIASES = {
  author: "author",
  a: "author",
  title: "title",
  t: "title",
  category: "category",
  cat: "category",
  collection: "collection",
  coll: "collection",
  lib: "collection",
  library: "collection",
  file: "path",
  path: "path",
};

const TOKEN_RE = /(\w+):(?:"([^"]+)"|(\S+))|(\S+)/g;

export function parseQuery(raw) {
  const fieldTerms = {};
  const genericTerms = [];
  const text = raw.trim().toLocaleLowerCase();
  let match;
  TOKEN_RE.lastIndex = 0;
  while ((match = TOKEN_RE.exec(text)) !== null) {
    if (match[1]) {
      const field = FIELD_ALIASES[match[1]];
      const value = (match[2] || match[3] || "").trim();
      if (field && value) {
        (fieldTerms[field] || (fieldTerms[field] = [])).push(value);
        continue;
      }
    }
    if (match[4]) genericTerms.push(match[4]);
  }
  return { fieldTerms, genericTerms, isEmpty: !genericTerms.length && !Object.keys(fieldTerms).length };
}

export function runSearch(catalog, raw, limit = Infinity) {
  const query = parseQuery(raw);
  if (query.isEmpty) return { results: [], query };

  const fieldEntries = Object.entries(query.fieldTerms);
  const results = [];
  for (const entry of catalog) {
    const hay = entry._search;
    let ok = true;
    for (const [field, terms] of fieldEntries) {
      if (!terms.every((term) => hay[field].includes(term))) { ok = false; break; }
    }
    if (ok && query.genericTerms.length && !query.genericTerms.every((term) => hay.names.includes(term))) {
      ok = false;
    }
    if (ok) {
      results.push(entry);
      if (results.length >= limit) break;
    }
  }
  return { results, query };
}
