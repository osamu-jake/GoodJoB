"""search/tokenizer.py のテスト（U-03）。"""

from search import tokenizer


def test_u03_品詞フィルタで名詞_動詞_形容詞のみが残る():
    """U-03: 助詞・記号を含む日本語文 → 名詞・動詞・形容詞のみが残る（助詞「を」「が」や句読点は消える）。"""
    words = tokenizer.tokenize("皮脂を吸着する微粒子を用いて、髪の毛がべたつくのを抑える。")

    assert "皮脂" in words and "吸着" in words and "微粒子" in words  # 名詞
    assert "べたつく" in words and "抑える" in words  # 動詞は基本形になる
    for dropped in ("を", "が", "の", "、", "。", "て"):  # 助詞・記号
        assert dropped not in words


def test_u03_ストップワードが除かれる():
    """U-03: ストップワード（する／なる／本発明 等）が除かれる。"""
    words = tokenizer.tokenize("本発明は髪を整えることを目的とする。夕方になるとべたつく。")

    for stop in ("本発明", "する", "なる"):
        assert stop not in words
    assert "目的" in words and "夕方" in words


def test_記号だけの語_数字_1文字の仮名は残らない():
    words = tokenizer.tokenize("SPF50+ 100% の ね")

    assert all(any(c.isalnum() for c in w) for w in words)
    assert "100" not in words and "ね" not in words


def test_空やNoneは空リスト():
    assert tokenizer.tokenize("") == []
    assert tokenizer.tokenize(None) == []
    assert tokenizer.to_fts_text(None) == ""
    assert tokenizer.to_fts_query("") == ""


def test_検索クエリは重複を除いてORでつなぐ():
    assert tokenizer.to_fts_query("皮脂が皮脂を吸着する") == '"皮脂" OR "吸着"'


def test_索引側と検索側で同じ語になる():
    """索引（to_fts_text）の語とクエリ（to_fts_query）の語が一致する。ずれると入れた語で引けなくなる。"""
    text = "夕方になると前髪がベタついて束になる"
    assert tokenizer.to_fts_text(text).split() == tokenizer.tokenize(text)


def test_find_spansは原文中の位置を返す():
    text = "汗をかくと日焼けして肌が荒れた"
    spans = tokenizer.find_spans(text, {"日焼け", "荒れる"})

    assert [text[s:e] for s, e in spans] == ["日焼け", "荒れ"]  # 基本形で比べ、原文の表記（活用形）で切り出す


def test_find_spansは語が無ければ空():
    assert tokenizer.find_spans("汗をかく", {"日焼け"}) == []
    assert tokenizer.find_spans("", {"汗"}) == []
