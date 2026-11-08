from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

from .chunker import split_document, trim_history
from .client import Client, Options, TranslateError
from .server import ALIAS, QUANTS, Server, SetupError, find_llama, resolve_model


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="plamo-trans", description="Translate with PLaMo 3 Translate 0.8B (GGUF).")
    p.add_argument("text", nargs="*", help="text to translate (default: stdin)")
    p.add_argument("-t", "--target", help="target language (ja, en, zh-hans, ...); default: ja<->en auto")
    p.add_argument("-s", "--source", help="source language (needs --target)")
    p.add_argument("--form", choices=["polite", "plain"], help="Japanese output style (needs -t ja)")
    p.add_argument("--glossary", action="append", default=[], metavar="FILE|'a=>b'", help="repeatable")
    p.add_argument("--context", help="reference context text or file path")
    p.add_argument("-f", "--file", help="translate a text/markdown file")
    p.add_argument("-o", "--output", help="output file for --file (default: stdout)")
    p.add_argument("-i", "--interactive", action="store_true", help="REPL mode")
    p.add_argument("--quant", default="Q4_K_M", choices=QUANTS)
    p.add_argument("--model", help="local GGUF path")
    p.add_argument("--offline", action="store_true", help="no network at all (also passed to llama serve; HF_HUB_OFFLINE=1 implies it)")
    p.add_argument("--server", help="use an existing server URL instead of launching one")
    p.add_argument("--llama-bin", help="path to `llama` or `llama-server`")
    p.add_argument("--ctx", type=int, default=16384)
    p.add_argument("--max-tokens", type=int, default=2048)
    p.add_argument("-v", "--verbose", action="store_true", help="show llama server logs")
    return p


MAX_INPUT_CHARS = 2_000_000  # hard cap for stdin / files read into memory

_CTRL = re.compile("[\x00-\x08\x0b-\x1f\x7f-\x9f]")  # keeps \n and \t


class SafeOut:
    """stdout wrapper for terminals: strips control chars (ESC etc.) so text cannot drive the terminal."""

    def __init__(self, f):
        self._f = f

    def write(self, s: str) -> int:
        return self._f.write(_CTRL.sub("", s))

    def __getattr__(self, name):
        return getattr(self._f, name)


def _read_limited(f) -> str:
    text = f.read(MAX_INPUT_CHARS + 1)
    if len(text) > MAX_INPUT_CHARS:
        raise TranslateError(f"input is larger than {MAX_INPUT_CHARS} chars")
    return text


def _read_arg(v: str) -> str:
    pth = Path(v)
    return pth.read_text(encoding="utf-8") if pth.is_file() else v


def parse_glossary(items: list[str]) -> list[tuple[str, str]]:
    out = []
    for it in items:
        if "=>" in it:
            lines = [it]
        elif Path(it).is_file():
            lines = [l for l in Path(it).read_text(encoding="utf-8").splitlines() if l.strip()]
        else:
            raise TranslateError(f"glossary must be 'src=>dst' or a file: {it}")
        for l in lines:
            if l.lstrip().startswith("#"):
                continue
            s, _, t = l.partition("=>")
            if not s.strip() or not t.strip():
                raise TranslateError(f"bad glossary line: {l}")
            out.append((s.strip(), t.strip()))
    return out


def translate_doc(client: Client, text: str, opt: Options, out) -> None:
    history: list[tuple[str, str]] = []
    for seg, translatable, sep in split_document(text):
        if translatable and seg.strip():
            parts = []
            for d in client.stream(seg, trim_history(history), opt):
                parts.append(d)
                out.write(d)
                out.flush()
            history.append((seg, "".join(parts)))
        else:
            out.write(seg)
        out.write(sep)
        out.flush()


_READLINE = False


def setup_readline() -> None:
    """Enable arrow-key editing and input history when stdin is a terminal."""
    global _READLINE
    if not sys.stdin.isatty():
        return
    try:
        import atexit
        import readline
    except ImportError:
        return
    readline.parse_and_bind("set enable-bracketed-paste off")  # keep "blank line confirms" for pasted text
    base = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state")
    hist = base / "plamo-trans" / "history"
    try:
        hist.parent.mkdir(parents=True, exist_ok=True)
        readline.set_history_length(1000)
        if hist.exists():
            readline.read_history_file(hist)
        atexit.register(lambda: _save_history(readline, hist))
    except OSError:
        pass
    _READLINE = True


def _save_history(readline, hist: Path) -> None:
    try:
        readline.write_history_file(hist)
    except OSError:
        pass


def read_block() -> str | None:
    """Read lines until a blank line (or EOF). A leading /command is returned at once. None = EOF."""
    lines: list[str] = []
    while True:
        prompt = "> " if not lines else "  "
        try:
            if _READLINE and sys.stdout.isatty():
                line = input(prompt)  # readline needs to know the prompt to redraw correctly
            else:
                if sys.stdin.isatty():
                    sys.stderr.write(prompt)  # prompt on stderr, never mixed into output
                    sys.stderr.flush()
                line = input()
        except EOFError:
            return "\n".join(lines) if lines else None
        if not lines and line.strip().startswith("/"):
            return line.strip()
        if not line.strip():
            if lines:
                return "\n".join(lines)
            continue
        lines.append(line)


def repl(client: Client, opt: Options) -> None:
    history: list[tuple[str, str]] = []
    setup_readline()
    print("plamo-trans REPL  (blank line to translate; /target LANG, /clear, /quit)", file=sys.stderr)
    while True:
        try:
            line = read_block()
        except KeyboardInterrupt:
            print()
            return
        if line is None or line in ("/quit", "/exit"):
            return
        if line == "/clear":
            history.clear()
            continue
        if line.startswith("/target"):
            opt.target = line.split(None, 1)[1] if " " in line else None
            try:
                opt.validate()
            except TranslateError as e:
                print(f"error: {e}", file=sys.stderr)
            history.clear()
            continue
        try:
            parts = []
            for d in client.stream(line, trim_history(history), opt):
                parts.append(d)
                print(d, end="", flush=True)
            print()
            history.append((line, "".join(parts)))
        except TranslateError as e:
            print(f"error: {e}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    a = build_parser().parse_args(argv)
    if os.environ.get("HF_HUB_OFFLINE") == "1":  # honor the standard HF switch too
        a.offline = True
    try:
        opt = Options(a.target, a.source, a.form, parse_glossary(a.glossary),
                      _read_arg(a.context) if a.context else None, a.max_tokens)
        opt.validate()
        opt.check_extras()
        if sys.stdout.isatty():
            sys.stdout = SafeOut(sys.stdout)
        if a.interactive:
            src = None
        elif a.file:
            with open(a.file, encoding="utf-8") as f:
                src = _read_limited(f)
        elif a.text:
            src = " ".join(a.text)
        elif not sys.stdin.isatty():
            src = _read_limited(sys.stdin)
        else:
            build_parser().print_usage(sys.stderr)
            return 2
        if src is not None and not src.strip():
            return 0

        server = None
        if a.server:
            base = a.server
        else:
            model = Path(a.model) if a.model else resolve_model(a.quant, a.offline)
            server = Server(find_llama(a.llama_bin), model, a.ctx, a.verbose, a.offline)
            print("starting llama server...", file=sys.stderr)
            server.start()
            base = server.base_url
        try:
            client = Client(base, ALIAS)
            if a.interactive:
                repl(client, opt)
            elif a.file:
                if a.output:
                    with open(a.output, "w", encoding="utf-8") as f:
                        translate_doc(client, src, opt, f)
                else:
                    translate_doc(client, src, opt, sys.stdout)
            else:
                if len(src.strip().splitlines()) > 1 and not a.text:
                    translate_doc(client, src.rstrip("\n"), opt, sys.stdout)
                    print()
                else:
                    print(client.translate(src.strip(), (), opt))
        finally:
            if server:
                server.stop()
    except (SetupError, TranslateError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
