"""Split documents into translatable paragraphs, keeping fenced code verbatim."""
from __future__ import annotations

import re
from typing import Iterator

# (text, translatable, separator_after)
Segment = tuple[str, bool, str]


def split_document(text: str, max_chars: int = 2000) -> list[Segment]:
    segs: list[Segment] = []
    in_code = False
    buf: list[str] = []

    def flush(translatable: bool, sep: str):
        if buf:
            segs.append(("\n".join(buf), translatable, sep))
            buf.clear()

    lines = text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.lstrip().startswith("```"):
            if not in_code:
                flush(True, "\n")
                in_code = True
                buf.append(line)
            else:
                buf.append(line)
                in_code = False
                flush(False, "\n")
        elif in_code:
            buf.append(line)
        elif line.strip() == "":
            if buf:
                flush(True, "\n\n")
            else:
                if not segs:
                    segs.append(("", False, ""))
                t, tr, sp = segs[-1]
                segs[-1] = (t, tr, sp + "\n")
        else:
            buf.append(line)
        i += 1
    flush(not in_code, "")
    # tidy: separators between code block and neighbours
    out: list[Segment] = []
    for t, tr, s in segs:
        if tr and len(t) > max_chars:
            parts = _split_long(t, max_chars)
            for k, p in enumerate(parts):
                out.append((p, True, s if k == len(parts) - 1 else " "))
        else:
            out.append((t, tr, s))
    return out


def _hard_split(text: str, max_chars: int) -> list[str]:
    """Bounded fallback for a single sentence longer than max_chars.

    Breaks after whitespace when possible, else cuts. Pieces keep their characters, so
    concatenating them reproduces the sentence exactly (word boundaries survive recombination).
    """
    out = []
    while len(text) > max_chars:
        cut = text.rfind(" ", 0, max_chars) + 1  # keep the space at the end of the piece
        if cut <= 0:
            cut = max_chars
        out.append(text[:cut])
        text = text[cut:]
    out.append(text)
    return out


def _split_long(text: str, max_chars: int) -> list[str]:
    sents = re.split(r"(?<=[。！？.!?])\s*", text)
    parts, cur = [], ""
    for s in (q for sent in sents for q in _hard_split(sent, max_chars)):
        if cur and len(cur) + len(s) > max_chars:
            parts.append(cur)
            cur = ""
        cur += s
    if cur:
        parts.append(cur)
    return parts or [text]


def trim_history(history: list[tuple[str, str]], max_pairs: int = 4, max_chars: int = 3000) -> list[tuple[str, str]]:
    h = history[-max_pairs:]
    while h and sum(len(a) + len(b) for a, b in h) > max_chars:
        h = h[1:]
    return h
