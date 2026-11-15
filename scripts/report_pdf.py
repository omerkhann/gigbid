"""Render docs/REPORT.md to docs/REPORT.pdf (Markdown -> styled HTML -> headless Edge/Chrome print).

  uv run --no-project --with markdown python scripts/report_pdf.py
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parents[1]
CSS = """
@page { size: A4; margin: 16mm 15mm; }
body { font-family: "Segoe UI", Arial, sans-serif; font-size: 9.6pt; line-height: 1.42; color: #1a1a1a; }
h1 { font-size: 17pt; margin: 0 0 4pt; } h2 { font-size: 12.5pt; margin: 14pt 0 4pt; border-bottom: 1px solid #ccc; }
h3 { font-size: 10.5pt; margin: 10pt 0 3pt; }
table { border-collapse: collapse; width: 100%; margin: 6pt 0; font-size: 8.4pt; page-break-inside: avoid; }
th, td { border: 1px solid #bbb; padding: 2.5pt 4pt; text-align: left; vertical-align: top; }
th { background: #f0f0f0; }
code { font-family: Consolas, monospace; font-size: 8.4pt; background: #f4f4f4; padding: 0 2pt; }
pre { background: #f4f4f4; padding: 5pt; font-size: 7.8pt; white-space: pre-wrap; page-break-inside: avoid; }
p, li { margin: 3pt 0; }
"""


def browser() -> str:
    for c in (r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files\Google\Chrome\Application\chrome.exe"):
        if Path(c).exists():
            return c
    for name in ("chromium", "google-chrome", "msedge"):
        if shutil.which(name):
            return shutil.which(name)
    sys.exit("No Edge/Chrome found for printing to PDF")


def main() -> None:
    md = (ROOT / "docs/REPORT.md").read_text(encoding="utf-8")
    # Python-Markdown needs a blank line before a list that directly follows a paragraph line.
    md = re.sub(r"(?m)^(?!\s*(?:[-*]|\d+\.)\s)(?!\s*$)(.+)\n(\s*(?:[-*]|\d+\.)\s)", r"\1\n\n\2", md)
    # ...and 4-space indentation for nested lists (the Markdown source uses 2 or 3).
    md = re.sub(r"(?m)^ {2,3}((?:[-*]|\d+\.)\s)", r"    \1", md)
    body = markdown.markdown(md, extensions=["tables", "fenced_code", "sane_lists"])
    html = ROOT / "docs/REPORT.html"
    html.write_text(f"<!doctype html><html><head><meta charset='utf-8'><title>GigBid R&D report</title>"
                    f"<style>{CSS}</style></head><body>{body}</body></html>", encoding="utf-8")
    pdf = ROOT / "docs/REPORT.pdf"
    subprocess.run([browser(), "--headless", "--disable-gpu", "--no-pdf-header-footer",
                    f"--print-to-pdf={pdf}", html.as_uri()], check=True, timeout=120)
    html.unlink()
    print(f"wrote {pdf} ({pdf.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
