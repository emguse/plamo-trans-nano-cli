import pytest
from plamo_trans.chunker import split_document, trim_history
from plamo_trans.client import Options, TranslateError, check_text
from plamo_trans.cli import parse_glossary


def test_roundtrip_and_code_preserved():
    doc = "# Title\n\nPara one\nline two\n\n\n```py\nx = 1\n\ny = 2\n```\n\nLast para"
    segs = split_document(doc)
    assert "".join(t + s for t, _, s in segs) == doc
    code = [t for t, tr, _ in segs if not tr]
    assert code == ["```py\nx = 1\n\ny = 2\n```"]


def test_validate():
    with pytest.raises(TranslateError):
        Options(source="ja").validate()
    with pytest.raises(TranslateError):
        Options(target="en", form="polite").validate()
    Options(target="ja", form="polite", source="en").validate()


def test_kwargs_and_reserved():
    o = Options(target="JA", glossary=[("a", "b")])
    o.validate()
    assert o.kwargs() == {"target_lang": "ja", "glossary": [{"source": "a", "target": "b"}]}
    with pytest.raises(TranslateError):
        check_text("x <|plamo:tag|>")


def test_glossary_and_history():
    assert parse_glossary(["管理画面 => dashboard"]) == [("管理画面", "dashboard")]
    assert len(trim_history([("a", "b")] * 10)) == 4


def test_read_block_blank_line_and_commands(monkeypatch):
    from plamo_trans import cli

    def feed(lines):
        it = iter(lines)

        def fake_input(*_):
            try:
                return next(it)
            except StopIteration:
                raise EOFError

        monkeypatch.setattr("builtins.input", fake_input)

    feed(["a", "b", "", "/clear"])
    assert cli.read_block() == "a\nb"
    assert cli.read_block() == "/clear"
    assert cli.read_block() is None


def test_safety_limits_and_sanitize():
    import io
    import pytest
    from plamo_trans import cli
    from plamo_trans.client import Options, TranslateError, check_text

    with pytest.raises(TranslateError):
        check_text("x" * 30_001)
    with pytest.raises(TranslateError):
        Options(context="<|plamo:bos|>").check_extras()
    with pytest.raises(TranslateError):
        Options(glossary=[("a", "<|plamo:tag|>")]).check_extras()
    buf = io.StringIO()
    cli.SafeOut(buf).write("a\x1b[31mb\tc\nd\x9be\x07")
    assert buf.getvalue() == "a[31mb\tc\nde"
    with pytest.raises(TranslateError):
        cli._read_limited(io.StringIO("x" * (cli.MAX_INPUT_CHARS + 1)))


def test_split_document_bounds_unpunctuated_paragraph():
    from plamo_trans.chunker import split_document

    for text in ("word " * 6201, "あ" * 31_000):
        segs = split_document(text)
        assert all(len(t) <= 2000 for t, tr, _ in segs if tr)
        assert "".join(t for t, _, _ in segs).replace(" ", "").replace("\n", "") == text.replace(" ", "")


def test_hard_split_keeps_word_boundaries():
    from plamo_trans.chunker import _hard_split, split_document

    t = "word " * 400 + "x"
    assert "".join(_hard_split(t, 2000)) == t
    assert "".join(s for s, _, _ in split_document(t)).endswith("word x")
