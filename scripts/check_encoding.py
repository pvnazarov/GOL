#!/usr/bin/env python3
"""Scan GOL/libs zip archives and verify the .txt inside each is valid UTF-8.

Usage:
    .venv/bin/python scripts/check_encoding.py [libs_dir] [--report report.csv]
"""
import argparse
import csv
import sys
import zipfile
from pathlib import Path

import chardet


def middle_sample(data: bytes, sample_size: int = 8192) -> bytes:
    """Bytes from the middle of the file, away from cover-page pseudographics
    headers (and any footer cruft) that can skew chardet's byte-frequency guess."""
    if len(data) <= sample_size:
        return data
    start = (len(data) - sample_size) // 2
    return data[start:start + sample_size]


def check_zip(zip_path: Path):
    """Return a list of issue dicts for a single zip file (empty if all OK)."""
    issues = []
    try:
        with zipfile.ZipFile(zip_path) as zf:
            bad = zf.testzip()
            if bad is not None:
                issues.append({"issue": "corrupt_member", "detail": bad})
                return issues

            txt_names = [n for n in zf.namelist() if n.lower().endswith(".txt")]
            if not txt_names:
                issues.append({"issue": "no_txt_inside", "detail": ""})
                return issues
            if len(txt_names) > 1:
                issues.append({"issue": "multiple_txt", "detail": ", ".join(txt_names)})

            for name in txt_names:
                data = zf.read(name)
                if not data:
                    issues.append({"issue": "empty_file", "detail": name})
                    continue
                try:
                    data.decode("utf-8", errors="strict")
                except UnicodeDecodeError:
                    guess = chardet.detect(middle_sample(data))
                    issues.append({
                        "issue": "not_utf8",
                        "detail": name,
                        "guessed_encoding": guess.get("encoding"),
                        "confidence": guess.get("confidence"),
                    })
    except zipfile.BadZipFile:
        issues.append({"issue": "bad_zip", "detail": ""})
    except OSError as e:
        issues.append({"issue": "read_error", "detail": str(e)})
    return issues


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("libs_dir", nargs="?", default=str(Path(__file__).resolve().parent.parent / "libs"))
    parser.add_argument("--report", default=str(Path(__file__).resolve().parent.parent / "reports" / "encoding_report.csv"))
    parser.add_argument("--skip", action="append", default=["meta.zip"], help="zip filename(s) to skip")
    args = parser.parse_args()

    libs_dir = Path(args.libs_dir)
    if not libs_dir.is_dir():
        sys.exit(f"libs directory not found: {libs_dir}")

    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    zip_paths = sorted(p for p in libs_dir.rglob("*.zip") if p.name not in args.skip)
    total = len(zip_paths)
    print(f"Scanning {total} zip files under {libs_dir} ...")

    rows = []
    for i, zip_path in enumerate(zip_paths, 1):
        for issue in check_zip(zip_path):
            rows.append({"path": str(zip_path.relative_to(libs_dir)), **issue})
        if i % 1000 == 0 or i == total:
            print(f"  {i}/{total} scanned, {len(rows)} issues so far")

    with report_path.open("w", newline="", encoding="utf-8") as f:
        fieldnames = ["path", "issue", "detail", "guessed_encoding", "confidence"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})

    print(f"\nDone. {total} zips scanned, {len(rows)} issues found.")
    print(f"Report written to {report_path}")

    if rows:
        by_issue = {}
        for row in rows:
            by_issue[row["issue"]] = by_issue.get(row["issue"], 0) + 1
        print("\nBreakdown:")
        for issue, count in sorted(by_issue.items(), key=lambda x: -x[1]):
            print(f"  {issue}: {count}")


if __name__ == "__main__":
    main()
