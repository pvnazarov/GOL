#!/usr/bin/env python3
"""Write a short structured catalogue record for every book zip under libs/.

Each zip holds one .txt book. For each one this reads the text, sends it (or, if
it is too long, large excerpts from the beginning, middle and end) to a model,
and stores the reply as JSON in a tree outside the book folders:

    summaries/<model>/<library>/<category>/<book>.json
    e.g. summaries/qwen3.5-9b/rus1996/FANTAST/3_tale_2.json

The record holds title, author(s), kind and a 100-200 word summary, plus how it
was made (backend, model, language, full text or excerpts, prompt size), so weak
cases can be found and redone later. The summaries/ tree is tracked in git; the
book folders are not.

Two backends:
  claude  -- the `claude` CLI, using the local Claude Code subscription (no API
             key). Sends ~34k characters of excerpts.
  ollama  -- an Ollama server (default http://localhost:11434, e.g. the GPU box
             through `ssh -f ollama-gpu`). Sends as much text as fits the context
             window -- the whole book when it fits.

The summary language defaults to the book's own language (Russian for Cyrillic
text, otherwise English). Existing records are skipped unless --force is given,
so the script is safe to re-run and to interrupt.

Usage:
    # see exactly what would be sent, without calling the model
    .venv/bin/python scripts/summarize_books.py libs/rus1996/FANTAST --limit 1 --dry-run

    # one category on the GPU box
    .venv/bin/python scripts/summarize_books.py libs/rus1996/FANTAST --backend ollama

    # a whole library (folders are searched recursively)
    .venv/bin/python scripts/summarize_books.py libs/rus1996 --backend ollama

    # with Claude instead
    .venv/bin/python scripts/summarize_books.py libs/eng1996/ADVENTUR --model haiku --jobs 4
"""
import argparse
import json
import os
import re
import subprocess
import sys
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIBS = ROOT / "libs"
SUMMARIES = ROOT / "summaries"

DEFAULT_MODELS = {"claude": "sonnet", "ollama": "qwen3.5:9b"}

# Claude backend: a fixed excerpt budget, ~9k tokens.
CLAUDE_CHARS = 34000

# Ollama backend: fill the context window, leaving room for the system prompt,
# the headers and the reply. Characters per token were measured on qwen3.5
# (English ~3.9, Russian ~2.9) and are rounded down for safety. If the prompt
# still overflows, Ollama silently drops its *beginning* -- system prompt and
# title page included -- so that case is detected and treated as a failure.
OLLAMA_CTX = 65536
OLLAMA_PREDICT = 1024
OLLAMA_OVERHEAD = 3000
CHARS_PER_TOKEN = {"cyrillic": 2.7, "latin": 3.7}

# How an over-long book is split: beginning (title page, set-up), a middle
# passage, and the end (catches anthologies whose front matter says nothing).
SPLIT = (0.58, 0.30, 0.12)

FB2_NS = "{http://www.gribuser.ru/xml/fictionbook/2.0}"
# FB2 elements whose text is one line of the extracted plain text. Titles'
# own <p>s are reached as children of <title>, so only leaf-level blocks.
FB2_BLOCKS = {f"{FB2_NS}{tag}" for tag in ("p", "v", "subtitle", "text-author")}

# Encodings to try, in order, for books that are not valid UTF-8.
ENCODINGS = ("utf-8", "cp1251", "cp1252", "latin-1")

KINDS = ["novel", "novella", "short stories", "collection",
         "poetry", "play", "non-fiction", "unknown"]

SYSTEM_PROMPT = """\
You are a library cataloguer. You are given the text of one book file, or
excerpts from it, and must return a short catalogue record. Reply with a single
JSON object and nothing else -- no prose, no code fences.

Keys:
  "title"   -- the title of the book or collection, as a plain string. Use the
               work's real title, not the filename. If the text gives no
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

If the text is too damaged or fragmentary to identify the work, still fill in
what you can and say so plainly in "summary".

Write "title", "authors" and "summary" in {lang}, using the conventional {lang}
spelling of names. Keep "kind" as one of the English values above."""

USER_TEMPLATE = """\
File: {filename}
Category folder: {category}
Text length: {length} characters

{intro}

{body}"""

RECORD_SCHEMA = {
    "type": "object",
    "required": ["title", "authors", "kind", "summary"],
    "properties": {
        "title": {"type": "string"},
        "authors": {"type": "array", "items": {"type": "string"}},
        "kind": {"type": "string", "enum": KINDS},
        "summary": {"type": "string"},
    },
}


def fb2_text(data: bytes) -> str:
    """Plain text of a FictionBook's bodies, one paragraph per line."""
    root = ET.fromstring(data)       # honours the XML declaration's encoding
    lines = []
    for body in root.findall(f"{FB2_NS}body"):
        for el in body.iter():
            if el.tag in FB2_BLOCKS:
                lines.append(" ".join("".join(el.itertext()).split()))
            elif el.tag == f"{FB2_NS}empty-line":
                lines.append("")
    return "\n".join(lines)


def read_book(zip_path: Path) -> str:
    """Return the text of the book inside a zip: a .txt, or else an .fb2."""
    with zipfile.ZipFile(zip_path) as zf:
        names = [n for n in zf.namelist() if n.lower().endswith(".txt")]
        if not names:
            fb2 = [n for n in zf.namelist() if n.lower().endswith(".fb2")]
            if not fb2:
                raise ValueError("no .txt or .fb2 member inside the zip")
            return fb2_text(zf.read(fb2[0]))
        # More than one .txt is rare; take the largest and carry on.
        name = max(names, key=lambda n: zf.getinfo(n).file_size)
        data = zf.read(name)

    for encoding in ENCODINGS:
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def normalize(text: str) -> str:
    """Collapse the column-formatting padding of the old plain-text books.

    Runs of spaces cost tokens and carry nothing; line breaks are kept.
    """
    lines = (re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines())
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines))


def script_of(text: str) -> str:
    sample = text[:20000]
    cyrillic = sum("Ѐ" <= ch <= "ӿ" for ch in sample)
    return "cyrillic" if cyrillic > 0.3 * max(1, len(sample)) else "latin"


def select_text(text: str, budget: int):
    """Return (input description, prompt intro, prompt body) for a char budget."""
    if len(text) <= budget:
        return ({"mode": "full", "chars_sent": len(text)},
                "The full text of the book follows.",
                f"<book>\n{text}\n</book>")
    head, middle, tail = (int(budget * share) for share in SPLIT)
    mid_start = (len(text) - middle) // 2
    body = (f"<beginning>\n{text[:head]}\n</beginning>\n\n"
            f"<middle>\n{text[mid_start:mid_start + middle]}\n</middle>\n\n"
            f"<end>\n{text[-tail:]}\n</end>")
    return ({"mode": "excerpts", "chars_sent": head + middle + tail},
            "The book is too long to include whole. Below are a passage from the "
            "beginning, one from the middle, and the end.",
            body)


def call_claude(system: str, prompt: str, args):
    """Run one non-interactive `claude` turn; return (reply text, prompt tokens)."""
    cmd = [
        "claude", "--print",
        "--model", args.model,
        "--system-prompt", system,
        "--tools", "",                 # pure text task: no tool access at all
        "--no-session-persistence",    # don't litter ~/.claude with 15k sessions
        "--strict-mcp-config",         # ignore the user's MCP servers
        "--output-format", "json",
    ]
    proc = subprocess.run(
        cmd, input=prompt, capture_output=True, text=True, timeout=args.timeout,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"claude exited {proc.returncode}: {proc.stderr.strip()[:400]}")

    envelope = json.loads(proc.stdout)
    if envelope.get("is_error"):
        raise RuntimeError(f"claude reported an error: {str(envelope.get('result'))[:400]}")
    usage = envelope.get("usage") or {}
    tokens = sum(usage.get(k) or 0 for k in (
        "input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")) or None
    return envelope["result"], tokens


def call_ollama(system: str, prompt: str, args):
    """Run one /api/chat request; return (reply text, prompt tokens)."""
    body = {
        "model": args.model,
        "stream": False,
        "think": False,
        "format": RECORD_SCHEMA,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": prompt}],
        "options": {"num_ctx": args.num_ctx, "num_predict": OLLAMA_PREDICT,
                    "temperature": 0.3},
    }
    request = urllib.request.Request(
        args.ollama_url.rstrip("/") + "/api/chat", json.dumps(body).encode(),
        {"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=args.timeout) as response:
        reply = json.load(response)
    tokens = reply.get("prompt_eval_count")
    if tokens and tokens >= args.num_ctx - OLLAMA_PREDICT:
        raise RuntimeError(f"prompt filled the context window ({tokens} tokens) "
                           "and was truncated by Ollama")
    return reply["message"]["content"], tokens


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


def model_dir(backend: str, model: str) -> str:
    """Folder name for a model under summaries/, e.g. claude-sonnet, qwen3.5-9b."""
    name = model.replace(":", "-").replace("/", "-")
    return f"claude-{name}" if backend == "claude" else name


def out_path_for(zip_path: Path, args) -> Path:
    rel = zip_path.resolve().relative_to(LIBS)
    return SUMMARIES / model_dir(args.backend, args.model) / rel.with_suffix(".json")


def process(zip_path: Path, args) -> str:
    """Summarize one book. Returns a one-line status for the log."""
    rel = zip_path.resolve().relative_to(LIBS)
    out_path = out_path_for(zip_path, args)
    if out_path.exists() and not args.force:
        return f"skip   {rel} (exists)"

    try:
        text = normalize(read_book(zip_path))
    except Exception as exc:
        return f"FAIL   {rel}: unreadable ({exc})"

    script = script_of(text)
    lang = args.lang if args.lang != "auto" else (
        "Russian" if script == "cyrillic" else "English")
    if args.backend == "ollama":
        budget = int((args.num_ctx - OLLAMA_PREDICT - OLLAMA_OVERHEAD)
                     * CHARS_PER_TOKEN[script])
    else:
        budget = CLAUDE_CHARS
    source, intro, body = select_text(text, budget)
    prompt = USER_TEMPLATE.format(filename=zip_path.name, category=zip_path.parent.name,
                                  length=len(text), intro=intro, body=body)
    system = SYSTEM_PROMPT.replace("{lang}", lang)

    if args.dry_run:
        print(f"----- prompt for {rel} ({lang}, {source['mode']}, "
              f"{len(prompt)} chars) -----\n{prompt}\n", flush=True)
        return f"dry    {rel}"

    call = call_ollama if args.backend == "ollama" else call_claude
    last_error = None
    for attempt in range(1, args.retries + 1):
        try:
            raw, tokens = call(system, prompt, args)
            record = parse_record(raw)
            break
        except Exception as exc:
            last_error = exc
    else:
        return f"FAIL   {rel}: {last_error}"

    record["lang"] = lang
    record["meta"] = {
        "source": str(rel),
        "backend": args.backend,
        "model": args.model,
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "input": {**source, "text_chars": len(text), "prompt_tokens": tokens},
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    os.replace(tmp, out_path)
    words = len(record["summary"].split())
    return f"ok     {rel} ({source['mode']}, {tokens} tokens, {words} words)"


def find_zips(paths):
    zips = []
    for path in paths:
        if path.is_dir():
            zips += path.rglob("*.zip")
        elif path.suffix.lower() == ".zip":
            zips.append(path)
        else:
            sys.exit(f"not a folder or .zip: {path}")
    for z in zips:
        if not z.resolve().is_relative_to(LIBS):
            sys.exit(f"not under {LIBS}: {z}")
    return sorted(set(zips))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Summarize book zips into summaries/<model>/<library>/<category>/*.json.",
    )
    parser.add_argument("paths", type=Path, nargs="+",
                        help="book zips or folders under libs/ (searched recursively), "
                             "e.g. libs/eng1996/ADVENTUR or libs/rus1996")
    parser.add_argument("--backend", choices=("claude", "ollama"), default="claude",
                        help="claude CLI or an Ollama server (default: claude)")
    parser.add_argument("--model", default=None,
                        help="model name (default: sonnet for claude -- 'haiku' for bulk "
                             "runs -- and qwen3.5:9b for ollama)")
    parser.add_argument("--lang", default="auto",
                        help="summary language: 'auto' (Russian for Cyrillic books, "
                             "otherwise English) or a language name (default: auto)")
    parser.add_argument("--ollama-url", default="http://localhost:11434",
                        help="Ollama server (default: http://localhost:11434)")
    parser.add_argument("--num-ctx", type=int, default=OLLAMA_CTX,
                        help=f"Ollama context window in tokens (default: {OLLAMA_CTX}; "
                             "qwen3.5:9b fits ~80k on the 12 GB GPU, gemma4 ~40k)")
    parser.add_argument("--limit", type=int, default=None,
                        help="only process the first N zips (for testing)")
    parser.add_argument("--jobs", type=int, default=1,
                        help="how many books to summarize in parallel (default: 1; "
                             "keep 1 for ollama -- one GPU runs one request at a time)")
    parser.add_argument("--force", action="store_true",
                        help="overwrite existing records")
    parser.add_argument("--dry-run", action="store_true",
                        help="print the prompts instead of calling the model")
    parser.add_argument("--retries", type=int, default=2,
                        help="attempts per book before giving up (default: 2)")
    parser.add_argument("--timeout", type=int, default=600,
                        help="seconds to allow per book (default: 600)")
    args = parser.parse_args()
    args.model = args.model or DEFAULT_MODELS[args.backend]

    zips = find_zips(args.paths)
    if not zips:
        sys.exit("no .zip files found")
    if args.limit is not None:
        zips = zips[:args.limit]

    print(f"{len(zips)} book(s), backend={args.backend}, model={args.model}, "
          f"jobs={args.jobs} -> {SUMMARIES / model_dir(args.backend, args.model)}",
          file=sys.stderr)

    failures = 0
    if args.jobs > 1:
        with ThreadPoolExecutor(max_workers=args.jobs) as pool:
            for line in pool.map(lambda p: process(p, args), zips):
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
