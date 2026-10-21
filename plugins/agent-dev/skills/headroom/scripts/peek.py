#!/usr/bin/env python3
"""Summarize a large file without reading it into the conversation."""
import collections
import csv
import json
import os
import re
import sys


def human(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def markdown(path):
    print("Outline (line: heading):")
    with open(path, encoding="utf-8", errors="ignore") as f:
        for no, line in enumerate(f, 1):
            if re.match(r"#{1,4} ", line):
                print(f"  {no}: {line.rstrip()}")


def logs(path):
    pattern = collections.Counter()
    levels = collections.Counter()
    first = {}
    with open(path, encoding="utf-8", errors="ignore") as f:
        for no, line in enumerate(f, 1):
            m = re.search(r"\b(ERROR|WARN(ING)?|INFO|DEBUG|FATAL|CRITICAL)\b", line)
            if m:
                levels[m.group(1)] += 1
            key = re.sub(r"\d+", "N", re.sub(r"[0-9a-f]{8,}", "ID", line.strip()))[:120]
            pattern[key] += 1
            first.setdefault(key, no)
    if levels:
        print("Levels: " + ", ".join(f"{k}={v}" for k, v in levels.most_common()))
    print("Most frequent line patterns (count, first line, pattern):")
    for key, count in pattern.most_common(12):
        print(f"  {count:6}  L{first[key]:<7} {key}")


def json_file(path, size):
    if size > 200 * 1024 * 1024:
        print("JSON larger than 200 MB: use grep or jq on specific keys.")
        return
    data = json.load(open(path, encoding="utf-8"))

    def walk(node, prefix, depth):
        if depth > 2:
            return
        if isinstance(node, dict):
            for k, v in list(node.items())[:40]:
                desc = type(v).__name__ + (f"[{len(v)}]" if isinstance(v, (list, dict)) else "")
                print(f"  {prefix}{k}: {desc}")
                walk(v, prefix + "  ", depth + 1)
        elif isinstance(node, list) and node:
            print(f"  {prefix}[0] of {len(node)}: {type(node[0]).__name__}")
            walk(node[0], prefix + "  ", depth + 1)

    print("Structure (first levels):")
    walk(data, "", 0)


def csv_file(path):
    with open(path, encoding="utf-8", errors="ignore", newline="") as f:
        reader = csv.reader(f)
        header = next(reader, [])
        rows = [r for _, r in zip(range(3), reader)]
    print(f"Columns ({len(header)}): " + ", ".join(header))
    for r in rows:
        print("  " + " | ".join(r)[:200])


def main():
    if len(sys.argv) != 2 or not os.path.isfile(sys.argv[1]):
        sys.exit("usage: peek.py <file>")
    path = sys.argv[1]
    size = os.path.getsize(path)
    with open(path, "rb") as f:
        lines = sum(1 for _ in f)
    print(f"{path}: {human(size)}, {lines} lines")
    ext = os.path.splitext(path)[1].lower()
    if ext in (".md", ".markdown", ".mdx", ".rst", ".txt"):
        markdown(path)
    elif ext == ".json":
        json_file(path, size)
    elif ext in (".csv", ".tsv"):
        csv_file(path)
    else:
        logs(path)


if __name__ == "__main__":
    main()
