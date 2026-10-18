"""Build the Haiku summaries browser page from summaries/claude-haiku JSON records.

Writes reports/summaries_page/haiku-summaries.html plus summaries-N.json data parts
(split because one published Artifact file is limited to 16 MB). Published as
https://claude.ai/artifact/D7fTRjjnxFKQzv8fQVyJP1 -- republish the page with all
the parts as supporting files.

    python3 scripts/summaries_page/build.py
"""
import json
import statistics as st
from collections import defaultdict
from pathlib import Path

GOL = Path("/home/pin/ai/GOL")
HERE = Path(__file__).parent
OUT = GOL / "reports/summaries_page"
SRC = GOL / "summaries/claude-haiku"

CATS = json.loads((GOL / "libs/data/categories.json").read_text())
LIBS = json.loads((GOL / "scripts/library_labels.json").read_text())
FLAGS = {
    "rus2004/CHILDREN/erik": "For review: a corporal-punishment story about a 13-year-old, filed under children's books.",
    "eng1996/TEACHER/ane": "For review: a 1990s bulletin-board how-to file with instructions for making explosives.",
    "eng1996/TEACHER/bombs": "For review: a 1990s bulletin-board how-to file with instructions for making explosives.",
    "eng1996/TEACHER/handbook": "For review: a 1990s bulletin-board how-to file with instructions for making explosives.",
    "rus1996/TEACHER/blast": "For review: a 1990s bulletin-board how-to file with instructions for making explosives.",
    "rus2004/TEACHER/blast": "For review: a 1990s bulletin-board how-to file with instructions for making explosives.",
    "rus2004/TEACHER/drugsmak": "For review: the drugs section of The Anarchist Cookbook, with instructions for making psychoactive substances.",
}

books = []
for f in sorted(SRC.glob("*/*/*.json")):
    r = json.loads(f.read_text())
    lib, cat = f.parent.parent.name, f.parent.name
    i = r["meta"]["input"]
    key = f"{lib}/{cat}/{f.stem}"
    books.append({
        "k": key, "l": lib, "c": cat,
        "t": r["title"], "a": ", ".join(r["authors"]), "kind": r["kind"],
        "s": r["summary"], "w": len(r["summary"].split()),
        "r": round(100 * i["chars_sent"] / i["text_chars"]) if i.get("text_chars") else None,
        "m": i["mode"], "tok": i.get("prompt_tokens"),
        "flag": FLAGS.get(key),
    })

stats = defaultdict(lambda: defaultdict(list))
for b in books:
    stats[b["l"]][b["c"]].append(b)

libs = []
for lib in LIBS:
    if lib not in stats:
        continue
    cats = []
    for cat, bs in sorted(stats[lib].items()):
        cats.append({"code": cat, "name": CATS.get(cat, cat), "n": len(bs),
                     "words": round(st.mean(b["w"] for b in bs)),
                     "read": round(st.median(b["r"] for b in bs if b["r"] is not None))})
    allb = [b for bs in stats[lib].values() for b in bs]
    libs.append({"code": lib, "name": LIBS[lib], "n": len(allb), "cats": cats,
                 "words": round(st.mean(b["w"] for b in allb)),
                 "read": round(st.median(b["r"] for b in allb if b["r"] is not None))})

data = {"libs": libs, "books": books}
# The summaries ship as JSON parts next to the page: 8,800 Cyrillic summaries are
# ~17 MB, over the 16 MB limit for one published file.
PART_BYTES = 6_000_000
OUT.mkdir(parents=True, exist_ok=True)
for old in OUT.glob("summaries-*.json"):
    old.unlink()
parts, cur, size = [], [], 0
for b in books:
    n = len(json.dumps(b, ensure_ascii=False).encode())
    if cur and size + n > PART_BYTES:
        parts.append(cur); cur, size = [], 0
    cur.append(b); size += n
parts.append(cur)
for i, part in enumerate(parts, 1):
    (OUT / f"summaries-{i}.json").write_text(json.dumps(part, ensure_ascii=False, separators=(",", ":")).replace("\ufffd", "\\ufffd"))
meta = json.dumps({"libs": libs, "parts": len(parts)}, ensure_ascii=False).replace("</", "<\\/")
(OUT / "haiku-summaries.html").write_text((HERE / "template.html").read_text().replace("/*META*/null", meta))
print(len(books), "books;", {l["code"]: l["n"] for l in libs}, "parts:",
      [f"{(OUT / f'summaries-{i}.json').stat().st_size/1e6:.1f} MB" for i in range(1, len(parts) + 1)])
