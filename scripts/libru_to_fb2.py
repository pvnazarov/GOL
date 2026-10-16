#!/usr/bin/env python3
"""Convert lib.ru book pages into FictionBook (.fb2) zips for GOL.

lib.ru (and its mirrors such as fan.lib.ru) serve each book as one HTML page
whose text sits in a <pre> block, laid out the old plain-text way: paragraphs
start with an indent, chapter headings are centred capitals after blank lines,
and the lines are hard-wrapped. The site's own FB2/EPUB exports lose that
structure (or come out empty), so this rebuilds it from the page itself:

  * paragraphs from the indentation, hard wraps joined back up;
  * a new <section> with a <title> at each centred all-caps heading run,
    so the reader gets a table of contents; letter-spaced headings
    ("К Н И Г А   П Е Р В А Я") are closed up;
  * other centred lines become <subtitle>s, illustrations become embedded
    images, the page's "Аннотация" becomes the FB2 annotation;
  * author and title come from the page <title> ("Author. Title").

Output is <out>/<author-folder>--<page>.fb2.zip, e.g.
libs/izbrannoe/FANTAST/shumil_p--text_0010-008.fb2.zip, matching the file
names of the site's own FB2 downloads.

Usage:
    .venv/bin/python scripts/libru_to_fb2.py libs/izbrannoe/FANTAST \\
        http://fan.lib.ru/s/shumil_p/text_0010-008.shtml [more URLs ...]
"""
import argparse
import base64
import html
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

FB2_NS = "http://www.gribuser.ru/xml/fictionbook/2.0"
XLINK_NS = "http://www.w3.org/1999/xlink"
ET.register_namespace("", FB2_NS)
ET.register_namespace("l", XLINK_NS)

USER_AGENT = "Mozilla/5.0 (GOL book importer)"

# Layout of lib.ru <pre> text, measured on the Shumil pages: body paragraphs
# are indented ~6 spaces, centred lines 10 or more.
CENTRED_INDENT = 10


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def decode_page(data: bytes) -> str:
    head = data[:2000].decode("ascii", "replace")
    match = re.search(r"charset=([\w-]+)", head, re.I)
    for encoding in ([match.group(1)] if match else []) + ["cp1251", "utf-8"]:
        try:
            return data.decode(encoding)
        except (LookupError, UnicodeDecodeError):
            continue
    return data.decode("cp1251", errors="replace")


def strip_tags(fragment: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", fragment))


def is_caps(line: str) -> bool:
    return bool(re.search(r"[A-ZА-ЯЁ].*[A-ZА-ЯЁ]", line)) and not re.search(r"[a-zа-яё]", line)


def close_up(line: str) -> str:
    """'К Н И Г А    П Е Р В А Я' -> 'КНИГА ПЕРВАЯ'; also squeeze runs of spaces."""
    words = re.split(r"\s{2,}", line.strip())
    if all(re.fullmatch(r"\S( \S)+|\S", w) for w in words) and any(" " in w for w in words):
        words = [w.replace(" ", "") for w in words]
    return " ".join(" ".join(w.split()) for w in words)


def join_lines(lines):
    text = ""
    for line in lines:
        line = " ".join(line.split())
        if not text:
            text = line
        elif re.search(r"\w-$", text) and line[:1].islower():
            text += line          # word hyphenated across the wrap
        else:
            text += " " + line
    return text


class Book:
    """Collects sections of FB2 blocks while walking the text lines."""

    def __init__(self):
        self.sections = [{"title": [], "blocks": []}]
        self.images = []          # [(id, content-type, bytes)]

    @property
    def current(self):
        return self.sections[-1]

    def heading(self, line):
        # Consecutive heading lines with no text between share one title.
        if not self.current["blocks"] and self.current["title"]:
            self.current["title"].append(line)
        elif not self.current["blocks"] and len(self.sections) == 1 and not self.current["title"]:
            self.current["title"].append(line)
        else:
            self.sections.append({"title": [line], "blocks": []})

    def add(self, kind, value=None):
        blocks = self.current["blocks"]
        if kind == "empty-line" and (not blocks or blocks[-1][0] == "empty-line"):
            return
        blocks.append((kind, value))


def parse_body(pre: str, base_url: str, book: Book):
    lines = pre.replace("\r", "").split("\n")
    para, blanks = [], 0

    def flush():
        nonlocal para
        if para:
            book.add("p", join_lines(para))
            para = []

    for raw in lines:
        img = re.search(r"<img[^>]*src=\"([^\"]+)\"", raw, re.I)
        if img:
            flush()
            src = urllib.parse.urljoin(base_url, img.group(1))
            try:
                data = fetch(src)
                kind = "image/png" if data[:4] == b"\x89PNG" else "image/jpeg"
                image_id = f"img{len(book.images) + 1}{'.png' if kind == 'image/png' else '.jpg'}"
                book.images.append((image_id, kind, data))
                book.add("image", image_id)
            except Exception as exc:  # an illustration is not worth failing the book
                print(f"  warning: image {src} skipped ({exc})", file=sys.stderr)
            raw = re.sub(r"<img[^>]*>", "", raw)
        line = strip_tags(raw).rstrip()
        if not line.strip():
            flush()
            blanks += 1
            continue
        indent = len(line) - len(line.lstrip(" "))
        text = line.strip()
        heading = (indent >= CENTRED_INDENT and blanks >= 2 and is_caps(text)
                   and not text.startswith(("-", "—")))
        if blanks >= 2 and book.current["blocks"] and not heading:
            book.add("empty-line")        # scene break
        if heading:
            flush()
            book.heading(close_up(text))
        elif indent >= CENTRED_INDENT:
            flush()
            book.add("subtitle", close_up(text))
        elif indent > 0 or not para:
            flush()
            para = [text]
        else:
            para.append(text)
        blanks = 0
    flush()


def build_fb2(meta: dict, book: Book) -> bytes:
    q = lambda tag: f"{{{FB2_NS}}}{tag}"
    root = ET.Element(q("FictionBook"))
    desc = ET.SubElement(root, q("description"))
    info = ET.SubElement(desc, q("title-info"))
    ET.SubElement(info, q("genre")).text = meta["genre"]
    author = ET.SubElement(info, q("author"))
    ET.SubElement(author, q("first-name")).text = meta["first_name"]
    ET.SubElement(author, q("last-name")).text = meta["last_name"]
    ET.SubElement(info, q("book-title")).text = meta["title"]
    if meta["annotation"]:
        annotation = ET.SubElement(info, q("annotation"))
        for line in meta["annotation"]:
            ET.SubElement(annotation, q("p")).text = line
    ET.SubElement(info, q("lang")).text = "ru"
    doc_info = ET.SubElement(desc, q("document-info"))
    ET.SubElement(doc_info, q("program-used")).text = "GOL scripts/libru_to_fb2.py"
    ET.SubElement(doc_info, q("src-url")).text = meta["url"]

    body = ET.SubElement(root, q("body"))
    title = ET.SubElement(body, q("title"))
    ET.SubElement(title, q("p")).text = meta["author"]
    ET.SubElement(title, q("p")).text = meta["title"]
    for section in book.sections:
        if not section["title"] and not section["blocks"]:
            continue
        sec = ET.SubElement(body, q("section"))
        if section["title"]:
            sec_title = ET.SubElement(sec, q("title"))
            for line in section["title"]:
                ET.SubElement(sec_title, q("p")).text = line
        for kind, value in section["blocks"]:
            if kind == "image":
                ET.SubElement(sec, q("image"), {f"{{{XLINK_NS}}}href": f"#{value}"})
            else:
                ET.SubElement(sec, q(kind)).text = value
    for image_id, kind, data in book.images:
        ET.SubElement(root, q("binary"), {"id": image_id, "content-type": kind}).text = \
            base64.b64encode(data).decode("ascii")

    ET.indent(root, space="")
    return b'<?xml version="1.0" encoding="utf-8"?>\n' + ET.tostring(root, encoding="utf-8")


def convert(url: str, out_dir: Path, genre: str) -> str:
    page = decode_page(fetch(url))
    page_title = strip_tags(re.search(r"<title>(.*?)</title>", page, re.S | re.I).group(1))
    page_title = re.sub(r"^.*?:\s*", "", page_title.strip())     # drop "Lib.ru/Фантастика: "
    author, _, title = page_title.partition(". ")
    last_name, _, first_name = author.partition(" ")

    annotation = []
    match = re.search(r"Аннотация:</b>(.*?)</i>", page, re.S)
    if match:
        annotation = [" ".join(strip_tags(part).split())
                      for part in re.split(r"<br\s*/?>", match.group(1), flags=re.I)]
        annotation = [line for line in annotation if line]

    start = page.find("<pre>", page.find("Собственно произведение"))
    if start < 0:
        raise ValueError("no <pre> text block found on the page")
    pre = page[start + len("<pre>"):page.find("</pre>", start)]

    book = Book()
    parse_body(pre, url, book)
    fb2 = build_fb2({
        "url": url, "genre": genre, "author": author.strip(), "title": title.strip(),
        "first_name": first_name.strip(), "last_name": last_name.strip(),
        "annotation": annotation,
    }, book)

    parts = urllib.parse.urlparse(url).path.strip("/").split("/")
    stem = f"{parts[-2]}--{Path(parts[-1]).stem}"
    out_path = out_dir / f"{stem}.fb2.zip"
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        zf.writestr(f"{Path(parts[-1]).stem}.fb2", fb2)
    headings = sum(1 for s in book.sections if s["title"])
    paragraphs = sum(1 for s in book.sections for kind, _ in s["blocks"] if kind == "p")
    return (f"ok  {out_path.name}: {author.strip()} -- {title.strip()} "
            f"({paragraphs} paragraphs, {headings} headings, {len(book.images)} images)")


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert lib.ru book pages to .fb2.zip files.")
    parser.add_argument("out_dir", type=Path, help="target folder, e.g. libs/izbrannoe/FANTAST")
    parser.add_argument("urls", nargs="+", help="lib.ru book page URLs (.shtml)")
    parser.add_argument("--genre", default="sf", help="FB2 genre code (default: sf)")
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    failures = 0
    for url in args.urls:
        try:
            print(convert(url, args.out_dir, args.genre), flush=True)
        except Exception as exc:
            failures += 1
            print(f"FAIL {url}: {exc}", flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
