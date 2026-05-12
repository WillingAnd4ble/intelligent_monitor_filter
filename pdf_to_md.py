#!/usr/bin/env python3
"""Convert a PDF file to Markdown.

Usage:
    python pdf_to_md.py <input.pdf> [output.md]

If output is omitted, replaces .pdf with .md in the same directory.
"""
import sys
import pdfplumber


def convert(pdf_path: str, md_path: str | None = None) -> str:
    if md_path is None:
        if pdf_path.lower().endswith(".pdf"):
            md_path = pdf_path[:-4] + ".md"
        else:
            md_path = pdf_path + ".md"

    doc = pdfplumber.open(pdf_path)
    parts: list[str] = []
    for page in doc.pages:
        text = page.extract_text() or ""
        if text.strip():
            parts.append(text)
        parts.append("")

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(parts))

    print(f"{len(doc.pages)} pages -> {md_path}")
    return md_path


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__.strip())
        sys.exit(1)
    convert(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)