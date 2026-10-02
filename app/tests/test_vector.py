"""search/vector.py のテスト。U-05は2-4(#37)、U-06・U-07は2-6(#39)で書く。"""

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
    pytest.skip("2-6 (#39) で実装")


def test_u07_同一doc_idの複数フィールドが最大類似度に集約される():
    """U-07: 同一doc_idの複数フィールドのベクトル → 最大類似度に集約される（ADR-0021）。"""
    pytest.skip("2-6 (#39) で実装")


@pytest.mark.model
def test_実モデルは384次元の正規化済みfloat32を返す():
    """実際の multilingual-e5-small を読み込んで確認する（初回は読み込みに時間がかかる）。"""
    try:
        v = vector.encode_query("夕方になると前髪がベタつく")
    except Exception as e:  # モデルを取得できない環境（オフライン・証明書など）
        pytest.skip(f"モデルを読み込めない: {type(e).__name__}")
    assert v.shape == (384,) and v.dtype == np.float32
    assert abs(float(np.linalg.norm(v)) - 1.0) < 1e-4
