"""search/highlight.py のテスト（U-12）。

語句ベクトルを手で決めた疑似エンコーダに差し替え、「意味的に最も近いペアが選ばれる」ことを確かめる。
実モデルでの挙動は test_semantic.py で見る。
"""

import numpy as np
import pytest

from search import highlight, vector

from .fake_encoder import DIM, fake_encode


def unit(*pairs):
    v = np.zeros(DIM, dtype=np.float32)
    for index, value in pairs:
        v[index] = value
    return v / np.linalg.norm(v)


# 意味が近い語句どうしが近いベクトルになるよう、手で決める（それ以外の語は疑似エンコーダに任せる）
WORD_VECTORS = {
    "べたつく": unit((0, 1.0)),
    "皮脂": unit((0, 0.9), (1, 0.1)),  # べたつく ≒ 皮脂（0.99）
    "夕方": unit((2, 1.0)),
    "時間": unit((2, 0.8), (3, 0.2)),  # 夕方 ≒ 時間（0.97）
}


def stub_encode(prefixed_texts):
    out = []
    for text in prefixed_texts:
        word = text.split(": ", 1)[1]
        out.append(WORD_VECTORS.get(word, fake_encode([text])[0] * 0.2))
    return np.vstack(out).astype(np.float32)


@pytest.fixture
def stubbed(monkeypatch):
    monkeypatch.setattr(vector, "_encode", stub_encode)


def test_u12_意味的に最も近い語句のペアが抽出される(con, stubbed):
    """U-12: クエリ語句と文書語句 → 意味的に最も近いペアが抽出される。"""
    matches = highlight.highlight(con, "夕方に髪がべたつく", doc_id=1, top_n=2)

    assert [(m.query_phrase, m.doc_phrase) for m in matches] == [("べたつく", "皮脂"), ("夕方", "時間")]
    assert matches[0].similarity > matches[1].similarity > 0.9


def test_文書側の位置が原文の表記で返る(con, stubbed):
    match = highlight.highlight(con, "夕方に髪がべたつく", doc_id=1, top_n=1)[0]
    text = con.execute("SELECT problem FROM documents WHERE id = 1").fetchone()[0]

    assert match.field == "problem"
    assert [text[s:e] for s, e in match.spans] == ["皮脂"]


def test_同じ文書語句は2回使わない(stubbed):
    # クエリの2語が、どちらも文書の「皮脂」に一番近くても、皮脂は1回しか選ばれない
    pairs = highlight.nearest_pairs(["べたつく", "皮脂"], ["皮脂", "時間"], top_n=5)

    assert len({d for _, d, _ in pairs}) == len(pairs)
    assert ("皮脂", "皮脂") == pairs[0][:2]  # 同じ語は最も近い（類似度1.0）


def test_件数はtop_nまでで_類似度の降順(con, stubbed):
    matches = highlight.highlight(con, "夕方に髪がべたつく", doc_id=1, top_n=3)

    assert len(matches) <= 3
    sims = [m.similarity for m in matches]
    assert sims == sorted(sims, reverse=True)


def test_クエリに語が無い_文書が無い_は空(con, stubbed):
    assert highlight.highlight(con, "は、が。", doc_id=1) == []
    assert highlight.highlight(con, "夕方に髪がべたつく", doc_id=9999) == []
    assert highlight.nearest_pairs([], ["皮脂"]) == []


def test_語句は内容語の基本形で重複が無い():
    assert highlight.phrases("皮脂が出て、皮脂が増える") == ["皮脂", "出る", "増える"]
