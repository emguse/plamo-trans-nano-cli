"""Chat Completions client for the PLaMo translate chat template."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Iterator

import httpx

STOP = ["<|plamo:tag|>", "<|plamo:bos|>"]


class TranslateError(ValueError):
    pass


def norm_lang(code: str | None) -> str | None:
    if code is None:
        return None
    c = code.strip().lower()
    return "ja-easy" if c == "ja(easy)" else c


@dataclass
class Options:
    target: str | None = None  # None/auto = ja<->en switching
    source: str | None = None
    form: str | None = None
    glossary: list[tuple[str, str]] = field(default_factory=list)
    context: str | None = None
    max_tokens: int = 2048

    def check_extras(self) -> None:
        if self.context:
            check_text(self.context, "context", 8_000)
        for s, t in self.glossary:
            check_text(s, "glossary", 500)
            check_text(t, "glossary", 500)

    def validate(self) -> None:
        self.target, self.source = norm_lang(self.target), norm_lang(self.source)
        auto = self.target in (None, "auto")
        if self.source and auto:
            raise TranslateError("--source requires a concrete --target (e.g. -t en)")
        if self.form and self.target != "ja":
            raise TranslateError("--form requires --target ja")

    def kwargs(self) -> dict:
        kw: dict = {}
        if self.target and self.target != "auto":
            kw["target_lang"] = self.target
        if self.source:
            kw["source_lang"] = self.source
        if self.form:
            kw["form"] = self.form
        if self.glossary:
            kw["glossary"] = [{"source": s, "target": t} for s, t in self.glossary]
        if self.context:
            kw["context"] = self.context
        return kw


MAX_REQUEST_CHARS = 30_000  # one request must fit in the context window; longer text goes through -f (chunked)


def check_text(text: str, what: str = "input", limit: int = MAX_REQUEST_CHARS) -> None:
    if "<|plamo:" in text:
        raise TranslateError(f"{what} contains reserved token '<|plamo:'")
    if len(text) > limit:
        raise TranslateError(f"{what} is too long ({len(text)} > {limit} chars); use -f to translate in chunks")


class Client:
    def __init__(self, base_url: str, model: str = "plamo-3-translate", timeout: float = 300):
        self.http = httpx.Client(base_url=base_url.rstrip("/"), timeout=timeout)
        self.model = model

    def _body(self, text, history, opt, stream):
        check_text(text)
        msgs = []
        for src, tr in history:
            msgs += [{"role": "user", "content": src}, {"role": "assistant", "content": tr}]
        msgs.append({"role": "user", "content": text})
        return {"model": self.model, "messages": msgs, "temperature": 0, "max_tokens": opt.max_tokens,
                "stop": STOP, "stream": stream, "chat_template_kwargs": opt.kwargs()}

    def translate(self, text, history=(), opt: Options | None = None) -> str:
        opt = opt or Options()
        r = self.http.post("/v1/chat/completions", json=self._body(text, history, opt, False))
        if r.status_code != 200:
            raise TranslateError(f"server error {r.status_code}: {r.text[:300]}")
        return r.json()["choices"][0]["message"]["content"]

    def stream(self, text, history=(), opt: Options | None = None) -> Iterator[str]:
        opt = opt or Options()
        with self.http.stream("POST", "/v1/chat/completions", json=self._body(text, history, opt, True)) as r:
            if r.status_code != 200:
                r.read()
                raise TranslateError(f"server error {r.status_code}: {r.text[:300]}")
            for line in r.iter_lines():
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                delta = json.loads(data)["choices"][0].get("delta", {}).get("content")
                if delta:
                    yield delta
