#!/usr/bin/env python3
"""Write a short structured summary (<filename>.md) next to every <filename>.zip in a folder.

Each zip in the target folder holds one .txt book. For each one this reads the
text, sends a representative excerpt to Claude via the `claude` CLI (so it uses
the local Claude Code subscription auth -- no API key needed), and writes a
sibling Markdown file with the title, author(s) and a 100-200 word summary.

Existing .md files are skipped unless --force is given, so the script is safe to
re-run and to interrupt.

Usage:
    # test on 3 books first
    .venv/bin/python scripts/summarize_books.py libs/eng1996/ADVENTUR --limit 3

    # see exactly what would be sent, without calling the model
    .venv/bin/python scripts/summarize_books.py libs/eng1996/ADVENTUR --limit 1 --dry-run

    # full run with the cheap model
    .venv/bin/python scripts/summarize_books.py libs/eng1996/ADVENTUR --model haiku --jobs 4
"""
import argparse
import json
import re
import subprocess
import sys
import textwrap
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

# Excerpt budget. The head carries the title page/author/contents, the middle
# and tail samples prove what the book actually is (and catch anthologies whose
# front matter says nothing useful). ~34k chars is roughly 9k tokens.
HEAD_CHARS = 20000
MIDDLE_CHARS = 10000
TAIL_CHARS = 4000

# Encodings to try, in order, for books that are not valid UTF-8.
ENCODINGS = ("utf-8", "cp1251", "cp1252", "latin-1")

SYSTEM_PROMPT = """\
You are a library cataloguer. You are given excerpts from one book file and must
return a short catalogue record. Reply with a single JSON object and nothing else
-- no prose, no code fences.

Keys:
  "title"   -- the title of the book or collection, as a plain string. Use the
               work's real title, not the filename. If the excerpts give no
               title, use "" (empty string).
  "authors" -- a list of author names, e.g. ["Charles Dickens"]. Empty list if
               unknown or anonymous. For anthologies by many hands, list up to
               three and no more.
  "kind"    -- one of: "novel", "novella", "short stories", "collection",
               "poetry", "play", "non-fiction", "unknown".
  "summary" -- 100 to 200 words of plain prose describing what the book is
               about. Describe the work as a whole, not just the excerpt. For a
               collection, say what kind of pieces it gathers and name a few.
               No spoiler warnings, no meta-commentary, no markdown.

If the excerpts are too damaged or fragmentary to identify the work, still fill
in what you can and say so plainly in "summary"."""

USER_TEMPLATE = """\
File: {filename}
Category folder: {category}
Text length: {length} characters

The excerpts below are the beginning of the file, a passage from the middle, and
the end.

<beginning>
{head}
</beginning>

<middle>
{middle}
</middle>

<end>
{tail}
</end>"""


def read_book(zip_path: Path) -> str:
    """Return the decoded text of the single .txt member inside a book zip."""
    with zipfile.ZipFile(zip_path) as zf:
        names = [n for n in zf.namelist() if n.lower().endswith(".txt")]
        if not names:
            raise ValueError("no .txt member inside the zip")
        # More than one .txt is rare; take the largest and carry on.
        name = max(names, key=lambda n: zf.getinfo(n).file_size)
        data = zf.read(name)

    for encoding in ENCODINGS:
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def build_excerpts(text: str):
    """Split the text into (head, middle, tail) samples."""
    head = text[:HEAD_CHARS]
    if len(text) <= HEAD_CHARS + MIDDLE_CHARS + TAIL_CHARS:
        return head, text[HEAD_CHARS:-TAIL_CHARS] or "", text[-TAIL_CHARS:]
    mid_start = (len(text) - MIDDLE_CHARS) // 2
    return head, text[mid_start:mid_start + MIDDLE_CHARS], text[-TAIL_CHARS:]


def build_prompt(zip_path: Path, text: str) -> str:
    head, middle, tail = build_excerpts(text)
    return USER_TEMPLATE.format(
        filename=zip_path.name,
        category=zip_path.parent.name,
        length=len(text),
        head=head,
        middle=middle,
        tail=tail,
    )


def call_claude(prompt: str, model: str, timeout: int) -> str:
    """Run one non-interactive `claude` turn and return its text result."""
    cmd = [
        "claude", "--print",
        "--model", model,
        "--system-prompt", SYSTEM_PROMPT,
        "--tools", "",                 # pure text task: no tool access at all
        "--no-session-persistence",    # don't litter ~/.claude with 15k sessions
        "--strict-mcp-config",         # ignore the user's MCP servers
        "--output-format", "json",
    ]
    proc = subprocess.run(
        cmd, input=prompt, capture_output=True, text=True, timeout=timeout,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"claude exited {proc.returncode}: {proc.stderr.strip()[:400]}")

    envelope = json.loads(proc.stdout)
    if envelope.get("is_error"):
        raise RuntimeError(f"claude reported an error: {str(envelope.get('result'))[:400]}")
    return envelope["result"]


def parse_record(raw: str) -> dict:
    """Pull the JSON catalogue record out of the model's reply."""
    cleaned = raw.strip()
    fenced = re.match(r"^```(?:json)?\s*(.*?)\s*```$", cleaned, re.DOTALL)
    if fenced:
        cleaned = fenced.group(1)
    try:
        record = json.loads(cleaned)
    except json.JSONDecodeError:
        # Last resort: the outermost {...} in the reply.
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not match:
            raise ValueError(f"reply was not JSON: {cleaned[:200]!r}")
        record = json.loads(match.group(0))

    if not isinstance(record, dict):
        raise ValueError("reply JSON was not an object")

    authors = record.get("authors") or []
    if isinstance(authors, str):
        authors = [authors]
    return {
        "title": str(record.get("title") or "").strip(),
        "authors": [str(a).strip() for a in authors if str(a).strip()],
        "kind": str(record.get("kind") or "unknown").strip(),
        "summary": " ".join(str(record.get("summary") or "").split()),
    }


def render_markdown(zip_path: Path, record: dict) -> str:
    title = record["title"] or zip_path.stem
    authors = ", ".join(record["authors"]) if record["authors"] else "Unknown"
    lines = [
        f"# {title}",
        "",
        f"- **Author(s):** {authors}",
        f"- **Type:** {record['kind']}",
        f"- **File:** {zip_path.name}",
        "",
        "## Summary",
        "",
        # break_on_hyphens=False: a line break inside "bridge-building" would
        # render as "bridge- building", since Markdown joins soft breaks with a space.
        textwrap.fill(record["summary"], width=79,
                      break_on_hyphens=False, break_long_words=False)
        if record["summary"] else "_No summary produced._",
        "",
    ]
    return "\n".join(lines)


def process(zip_path: Path, args) -> str:
    """Summarize one book. Returns a one-line status for the log."""
    out_path = zip_path.with_suffix(".md")
    if out_path.exists() and not args.force:
        return f"skip   {zip_path.name} (.md exists)"

    try:
        text = read_book(zip_path)
    except Exception as exc:
        return f"FAIL   {zip_path.name}: unreadable ({exc})"

    prompt = build_prompt(zip_path, text)

    if args.dry_run:
        print(f"----- prompt for {zip_path.name} "
              f"({len(prompt)} chars) -----\n{prompt}\n", flush=True)
        return f"dry    {zip_path.name}"

    last_error = None
    for attempt in range(1, args.retries + 1):
        try:
            record = parse_record(call_claude(prompt, args.model, args.timeout))
            break
        except Exception as exc:
            last_error = exc
    else:
        return f"FAIL   {zip_path.name}: {last_error}"

    out_path.write_text(render_markdown(zip_path, record), encoding="utf-8")
    words = len(record["summary"].split())
    return f"ok     {zip_path.name} -> {out_path.name} ({words} words)"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Summarize the book zips in a folder into sibling .md files.",
    )
    parser.add_argument("folder", type=Path,
                        help="folder of *.zip books, e.g. libs/eng1996/ADVENTUR")
    parser.add_argument("--model", default="sonnet",
                        help="model passed to `claude --model` "
                             "(default: sonnet; use 'haiku' for bulk runs)")
    parser.add_argument("--limit", type=int, default=None,
                        help="only process the first N zips (for testing)")
    parser.add_argument("--jobs", type=int, default=1,
                        help="how many books to summarize in parallel (default: 1)")
    parser.add_argument("--force", action="store_true",
                        help="overwrite existing .md files")
    parser.add_argument("--dry-run", action="store_true",
                        help="print the prompts instead of calling the model")
    parser.add_argument("--retries", type=int, default=2,
                        help="attempts per book before giving up (default: 2)")
    parser.add_argument("--timeout", type=int, default=300,
                        help="seconds to allow per book (default: 300)")
    args = parser.parse_args()

    if not args.folder.is_dir():
        sys.exit(f"not a directory: {args.folder}")

    zips = sorted(p for p in args.folder.iterdir() if p.suffix.lower() == ".zip")
    if not zips:
        sys.exit(f"no .zip files in {args.folder}")
    if args.limit is not None:
        zips = zips[:args.limit]

    print(f"{len(zips)} book(s) in {args.folder}, model={args.model}, jobs={args.jobs}",
          file=sys.stderr)

    failures = 0
    if args.jobs > 1:
        with ThreadPoolExecutor(max_workers=args.jobs) as pool:
            results = pool.map(lambda p: process(p, args), zips)
            for line in results:
                print(line, flush=True)
                failures += line.startswith("FAIL")
    else:
        for zip_path in zips:
            line = process(zip_path, args)
            print(line, flush=True)
            failures += line.startswith("FAIL")

    print(f"done: {len(zips) - failures} ok, {failures} failed", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
