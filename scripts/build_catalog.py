#!/usr/bin/env python3
"""Generate the static catalogue/tree JSON that the GOL webapp loads at startup.

Reads libs/meta.zip (catalog.tsv + categories.tsv) for rich book metadata, and
independently walks the libs/ filesystem for the raw folder/file structure
(so the Files view stays correct even if the catalogue is stale or missing
entries). Libraries are discovered automatically -- adding a new top-level
folder under libs/ with .zip books in it is enough, no code change needed.

Usage:
    .venv/bin/python scripts/build_catalog.py [libs_dir]

Output (written to <libs_dir>/data/):
    catalog.json     one record per book known to catalog.tsv AND present on disk
    categories.json  category code -> display name
    tree.json        library -> category -> [{n: filename, s: size_bytes}], from disk
    libraries.json   library id -> label + counts, from disk
"""
import argparse
import io
import json
import sys
import zipfile
from pathlib import Path

SKIP_DIRS = {"assets", "data"}  # app code / generated output, not library folders


def load_meta(libs_dir: Path):
    meta_path = libs_dir / "meta.zip"
    if not meta_path.is_file():
        sys.exit(f"meta.zip not found at {meta_path}")
    with zipfile.ZipFile(meta_path) as zf:
        catalog_name = next(n for n in zf.namelist() if n.lower().endswith("catalog.tsv"))
        categories_name = next(n for n in zf.namelist() if n.lower().endswith("categories.tsv"))
        catalog_text = zf.read(catalog_name).decode("utf-8")
        categories_text = zf.read(categories_name).decode("utf-8")
    return catalog_text, categories_text


def parse_categories(text: str):
    names = {}
    for line in text.splitlines():
        line = line.rstrip("\r\n")
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) >= 2 and parts[0]:
            names[parts[0]] = parts[1]
    return names


def split_tsv_row(line: str, n_fields: int):
    parts = line.split("\t")
    if len(parts) == n_fields:
        return parts
    if len(parts) > n_fields:
        # a stray tab inside the last free-text field (TITLE) -- rejoin the tail
        return parts[:n_fields - 1] + ["\t".join(parts[n_fields - 1:])]
    return parts + [""] * (n_fields - len(parts))  # missing trailing fields


def parse_catalog(text: str):
    lines = [l.rstrip("\r\n") for l in text.splitlines() if l.strip()]
    if not lines:
        return []
    header = lines[0].split("\t")
    n = len(header)
    idx = {name: i for i, name in enumerate(header)}
    rows = []
    for line in lines[1:]:
        fields = split_tsv_row(line, n)
        rows.append({
            "path": fields[idx["FILEPATH"]].strip().replace("\\", "/"),
            "category": fields[idx["CATEGORY"]].strip(),
            "author": fields[idx["AUTHOR"]].strip(),
            "title": fields[idx["TITLE"]].strip(),
            "size_kb": fields[idx["SIZE_KB"]].strip(),
        })
    return rows


def scan_disk(libs_dir: Path):
    """Ground-truth walk of libs/<library>/<category>/*.zip, independent of catalog.tsv."""
    tree = {}
    for library_dir in sorted(libs_dir.iterdir()):
        if not library_dir.is_dir() or library_dir.name in SKIP_DIRS or library_dir.name.startswith("."):
            continue
        categories = {}
        for category_dir in sorted(library_dir.iterdir()):
            if not category_dir.is_dir():
                continue
            files = []
            for zip_path in sorted(category_dir.glob("*.zip")):
                files.append({"n": zip_path.name, "s": zip_path.stat().st_size})
            if files:
                categories[category_dir.name] = files
        if categories:
            tree[library_dir.name] = categories
    return tree


def build_catalog_json(catalog_rows, tree):
    on_disk = set()
    for library, categories in tree.items():
        for category, files in categories.items():
            for f in files:
                on_disk.add(f"{library}/{category}/{f['n']}")

    entries = []
    seen_paths = set()
    missing_on_disk = 0
    for row in catalog_rows:
        path = row["path"]
        if not path or path in seen_paths:
            continue
        seen_paths.add(path)
        if path not in on_disk:
            missing_on_disk += 1
            continue
        parts = path.split("/")
        library = parts[0] if parts else ""
        try:
            size_kb = int(row["size_kb"]) if row["size_kb"] else None
        except ValueError:
            size_kb = None
        entries.append({
            "p": path,
            "l": library,
            "c": row["category"],
            "a": row["author"],
            "t": row["title"] or parts[-1].rsplit(".", 1)[0],
            "s": size_kb,
        })

    catalogued_paths = seen_paths
    not_in_catalog = len(on_disk - catalogued_paths)
    return entries, missing_on_disk, not_in_catalog


def build_libraries_json(tree, labels_override):
    libraries = []
    for library_id, categories in sorted(tree.items()):
        book_count = sum(len(files) for files in categories.values())
        libraries.append({
            "id": library_id,
            "label": labels_override.get(library_id, library_id),
            "categoryCount": len(categories),
            "bookCount": book_count,
        })
    return libraries


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    default_libs = Path(__file__).resolve().parent.parent / "libs"
    parser.add_argument("libs_dir", nargs="?", default=str(default_libs))
    args = parser.parse_args()

    libs_dir = Path(args.libs_dir)
    if not libs_dir.is_dir():
        sys.exit(f"libs directory not found: {libs_dir}")

    out_dir = libs_dir / "data"
    out_dir.mkdir(parents=True, exist_ok=True)

    labels_path = Path(__file__).resolve().parent / "library_labels.json"
    labels_override = json.loads(labels_path.read_text(encoding="utf-8")) if labels_path.is_file() else {}

    print("Reading meta.zip ...")
    catalog_text, categories_text = load_meta(libs_dir)
    categories = parse_categories(categories_text)
    catalog_rows = parse_catalog(catalog_text)
    print(f"  {len(catalog_rows)} catalog rows, {len(categories)} categories")

    print("Scanning libs/ on disk ...")
    tree = scan_disk(libs_dir)
    n_libraries = len(tree)
    n_files = sum(len(files) for cats in tree.values() for files in cats.values())
    print(f"  {n_libraries} libraries, {n_files} book files on disk")

    catalog_entries, missing_on_disk, not_in_catalog = build_catalog_json(catalog_rows, tree)
    libraries = build_libraries_json(tree, labels_override)

    if missing_on_disk:
        print(f"  warning: {missing_on_disk} catalog rows point to files not found on disk (skipped)")
    if not_in_catalog:
        print(f"  warning: {not_in_catalog} files on disk have no catalog entry (shown in Files view only, with filename as title)")

    (out_dir / "catalog.json").write_text(
        json.dumps(catalog_entries, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (out_dir / "categories.json").write_text(
        json.dumps(categories, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    (out_dir / "tree.json").write_text(
        json.dumps(tree, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (out_dir / "libraries.json").write_text(
        json.dumps(libraries, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\nWrote:")
    for name in ("catalog.json", "categories.json", "tree.json", "libraries.json"):
        p = out_dir / name
        print(f"  {p}  ({p.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
