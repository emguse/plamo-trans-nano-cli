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
