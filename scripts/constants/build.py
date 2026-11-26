#!/usr/bin/env python3
"""Build the «Константы (Constants)» library: libs/constants/IRRATIONAL/.

For every constant in articles.py this writes
  libs/constants/IRRATIONAL/<stem>.fb2.zip         the article (a GOL book)
  libs/constants/IRRATIONAL/digits/<stem>.zip      2^20 digits as one .txt
The digits are NOT put into the book; it links to the zip instead. The catalogue scans
only <category>/*.zip, so the digits/ subfolder never shows up as books.

Digits come from DIGITS_DIR (default ~/ai/irrational_constants, one <stem>.txt per
constant: integer part, '.', 1,048,576 truncated digits, newline).

Usage: python3 scripts/constants/build.py [DIGITS_DIR]
Then:  .venv/bin/python scripts/build_catalog.py
"""
import datetime
import re
import sys
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

sys.path.insert(0, str(Path(__file__).resolve().parent))
from articles import ARTICLES  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "libs" / "constants" / "IRRATIONAL"
PUBLIC_URL = "https://hatkapina.cc/gol/constants/IRRATIONAL/digits/"
N_DIGITS = 1 << 20
SERIES = "Константы"


def inline(text: str) -> str:
    """Escape, then turn ^{..} / _{..} / **..** into FB2 sup / sub / strong."""
    s = escape(text)
    s = re.sub(r"\^\{([^}]*)\}", r"<sup>\1</sup>", s)
    s = re.sub(r"_\{([^}]*)\}", r"<sub>\1</sub>", s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    return s


def group(digits: str, size: int = 5) -> str:
    return " ".join(digits[i:i + size] for i in range(0, len(digits), size))


def read_digits(path: Path):
    text = path.read_text()
    ipart, frac = text.strip().split(".")
    assert text.endswith("\n") and ipart.isdigit() and frac.isdigit(), path
    assert len(frac) == N_DIGITS, (path, len(frac))
    return ipart, frac


def write_digits_zip(src: Path, dest: Path) -> int:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        z.write(src, src.name)
    return dest.stat().st_size


def fb2(article: dict, number: int, ipart: str, frac: str, zip_name: str, zip_kb: int) -> str:
    today = datetime.date.today().isoformat()
    sym, title = article["symbol"], article["title"]
    value = f"{ipart},{group(frac[:50])}…"
    url = PUBLIC_URL + zip_name
    paras = "\n".join(f"    <p>{inline(p)}</p>" for p in article["paragraphs"])
    return f"""<?xml version="1.0" encoding="utf-8"?>
<FictionBook xmlns="http://www.gribuser.ru/xml/fictionbook/2.0" xmlns:l="http://www.w3.org/1999/xlink">
 <description>
  <title-info>
   <genre>sci_math</genre>
   <author><nickname>{escape(sym)}</nickname></author>
   <book-title>{escape(title)}</book-title>
   <annotation>
    <p>{escape(sym)} = {value}</p>
    <p>Статус: {escape(article["status"])}.</p>
   </annotation>
   <lang>ru</lang>
   <sequence name="{SERIES}" number="{number}"/>
  </title-info>
  <document-info>
   <author><nickname>Claude</nickname></author>
   <date>{today}</date>
   <id>gol-constants-{article["stem"]}</id>
   <version>1.0</version>
  </document-info>
 </description>
 <body>
  <title><p>{escape(sym)}</p><p>{escape(title)}</p></title>
  <section>
    <p><strong>{escape(sym)} = {value}</strong></p>
    <p><emphasis>Статус: {escape(article["status"])}.</emphasis></p>
{paras}
  </section>
  <section>
   <title><p>Цифры</p></title>
    <p>2<sup>20</sup> = 1 048 576 знаков после запятой одним текстовым файлом:
     <a l:href="{url}">{escape(zip_name)}</a> (zip, {zip_kb} КБ).</p>
    <p>Файл — одна строка: целая часть, точка и 1 048 576 цифр. Цифры обрезаны, а не округлены.</p>
  </section>
 </body>
</FictionBook>
"""


def main():
    digits_dir = Path(sys.argv[1] if len(sys.argv) > 1 else Path.home() / "ai" / "irrational_constants")
    OUT.mkdir(parents=True, exist_ok=True)
    for number, art in enumerate(ARTICLES, 1):
        stem = art["stem"]
        src = digits_dir / f"{stem}.txt"
        ipart, frac = read_digits(src)
        zip_name = f"{stem}.zip"
        zip_kb = round(write_digits_zip(src, OUT / "digits" / zip_name) / 1024)
        book = OUT / f"{stem}.fb2.zip"
        with zipfile.ZipFile(book, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
            z.writestr(f"{stem}.fb2", fb2(art, number, ipart, frac, zip_name, zip_kb))
        print(f"{book.relative_to(ROOT)}  + digits/{zip_name} ({zip_kb} KB)")


if __name__ == "__main__":
    main()
