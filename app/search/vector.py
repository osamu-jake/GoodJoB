"""ベクトル検索（ADR-0004・0005・0021）。

埋め込みモデルは `intfloat/multilingual-e5-small`。e5は入力の先頭に用途を示すプレフィックスを
付ける決まりで、**クエリには `query: `、文書には `passage: `** を付ける（ADR-0005）。
付け忘れると精度が落ちるので、付与はこのファイルの `encode_query`／`encode_passage` の中だけで行う。

ベクトルは `normalize_embeddings=True` で長さ1に揃える。すると**内積がそのままコサイン類似度**になる。

DBには、文書1件につきフィールド（要約body・課題problem・背景background）ごとに別のベクトルを
BLOB（float32を `numpy.tobytes()` したもの）で持つ。**titleは埋め込まない**（ADR-0021）。
"""

import numpy as np

MODEL_NAME = "intfloat/multilingual-e5-small"

# 埋め込むフィールド。title は含めない（短い文字列は類似度が一様に高く出て、
# 最大値を採る方式では常にタイトルが勝ってしまうため。ADR-0021）
FIELDS = ("body", "problem", "background")

QUERY_PREFIX = "query: "
PASSAGE_PREFIX = "passage: "

_model_cache = None


def with_query_prefix(text: str) -> str:
    return QUERY_PREFIX + text


def with_passage_prefix(text: str) -> str:
    return PASSAGE_PREFIX + text


def _model():
    # モデルのダウンロード・読み込みは重いので、初めて使うときに1回だけ行う
    global _model_cache
    if _model_cache is None:
        from sentence_transformers import SentenceTransformer

        _model_cache = SentenceTransformer(MODEL_NAME)
    return _model_cache


def _encode(prefixed_texts: list[str]) -> np.ndarray:
    """プレフィックス付きの文を、正規化済みの float32 行列 (件数, 次元) にする。

    テストでは、モデルを読み込まずに済むようこの関数を差し替える。
    """
    vecs = _model().encode(prefixed_texts, normalize_embeddings=True, convert_to_numpy=True)
    return np.asarray(vecs, dtype=np.float32)


def encode_passage(texts: list[str]) -> np.ndarray:
    """文書側の文をベクトルにする（`passage: ` を付ける）。"""
    return _encode([with_passage_prefix(t) for t in texts])


def encode_query(text: str) -> np.ndarray:
    """クエリ文をベクトルにする（`query: ` を付ける）。形は (次元,)。"""
    return _encode([with_query_prefix(text)])[0]


def to_blob(vec: np.ndarray) -> bytes:
    """DBに保存する形（float32のバイト列）にする。"""
    return np.asarray(vec, dtype=np.float32).tobytes()


def from_blob(blob: bytes) -> np.ndarray:
    return np.frombuffer(blob, dtype=np.float32)
