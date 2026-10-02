"""search/vector.py のテスト（U-05・U-06・U-07）。"""

import numpy as np
import pytest

from search import vector

from .fake_encoder import fake_encode


def test_u05_クエリにはquery_文書にはpassageのプレフィックスが付く(monkeypatch):
    """U-05: クエリ文・文書文 → `query: `／`passage: ` プレフィックスが付与される（ADR-0005）。"""
    seen = []

    def spy(texts):
        seen.extend(texts)
        return fake_encode(texts)

    monkeypatch.setattr(vector, "_encode", spy)

    vector.encode_query("前髪がべたつく")
    vector.encode_passage(["皮脂を吸着する", "汗に強い"])

    assert seen == ["query: 前髪がべたつく", "passage: 皮脂を吸着する", "passage: 汗に強い"]


def test_encode_queryは1次元_encode_passageは件数x次元(fake_encoder):
    assert vector.encode_query("あ").shape == (384,)
    assert vector.encode_passage(["あ", "い", "う"]).shape == (3, 384)


def test_blobの往復で値が変わらない():
    vec = np.random.default_rng(0).random(384).astype(np.float32)
    assert np.array_equal(vector.from_blob(vector.to_blob(vec)), vec)


def test_u06_正規化済みベクトルの内積がコサイン類似度と一致する():
    """U-06: 正規化済みベクトル2本 → 内積がコサイン類似度と一致する。"""
    rng = np.random.default_rng(1)
    a, b = rng.normal(size=384), rng.normal(size=384)
    a, b = (a / np.linalg.norm(a)).astype(np.float32), (b / np.linalg.norm(b)).astype(np.float32)
    cosine = float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b)))  # 定義どおりの計算

    rows = [{"doc_id": 1, "field": "body", "vec": vector.to_blob(b)}]
    ((_, _, sim),) = vector.similarities(a, rows)

    assert sim == pytest.approx(cosine, abs=1e-6)


def test_u07_同一doc_idの複数フィールドが最大類似度に集約される():
    """U-07: 同一doc_idの複数フィールドのベクトル → 最大類似度に集約される（ADR-0021）。"""
    scored = [(1, "body", 0.50), (1, "problem", 0.82), (1, "background", 0.61), (2, "body", 0.70)]

    best = vector.best_by_doc(scored)

    assert best == {1: (0.82, "problem"), 2: (0.70, "body")}  # 文書1は problem の値。1文書1エントリ


def test_rankは類似度の降順で上位k件_同点はdoc_idの小さい順():
    best = {3: (0.5, "body"), 1: (0.9, "body"), 2: (0.5, "problem"), 4: (0.1, "body")}
    assert vector.rank(best, 3) == [1, 2, 3]


def test_ベクトルが無ければ検索結果は空(con):
    con.execute("DELETE FROM embeddings")
    assert vector.search(con, "前髪", "seed") == {}


@pytest.mark.model
def test_実モデルは384次元の正規化済みfloat32を返す():
    """実際の multilingual-e5-small を読み込んで確認する（初回は読み込みに時間がかかる）。"""
    try:
        v = vector.encode_query("夕方になると前髪がベタつく")
    except Exception as e:  # モデルを取得できない環境（オフライン・証明書など）
        pytest.skip(f"モデルを読み込めない: {type(e).__name__}")
    assert v.shape == (384,) and v.dtype == np.float32
    assert abs(float(np.linalg.norm(v)) - 1.0) < 1e-4
