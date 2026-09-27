"""意味検索（ADR-0004・0005・0021）。

- モデルはローカル実行（API課金ゼロ）
- e5系は query: / passage: のプレフィックスが必須。付け忘れても
  エラーにならず静かに精度が落ちるため、ここで必ず付ける
- 文書側はフィールドごとに別ベクトルを持ち、doc_idごとに最大類似度へ集約する
"""

from functools import lru_cache

import numpy as np

MODEL_NAME = "intfloat/multilingual-e5-small"

# ADR-0021のとおり要約・課題・背景の3つ。titleは入れない。
# 短いタイトルはe5では類似度が一様に高く出るうえ順位が不安定で、最大値を取る方式では
# 常にタイトルが勝ってしまい「ニーズ文→課題」の経路が潰れる（実測で確認済み）。
# タイトルはBM25側（documents_fts）で拾う。
FIELDS = ("body", "problem", "background")


@lru_cache(maxsize=1)
def _model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(MODEL_NAME)


def encode_passage(texts: list[str]) -> np.ndarray:
    """文書側のベクトル化。normalize済みなので内積＝コサイン類似度。"""
    prefixed = [f"passage: {t}" for t in texts]
    return _model().encode(prefixed, normalize_embeddings=True)


def encode_query(text: str) -> np.ndarray:
    """クエリ側のベクトル化。検索の都度その場で計算する。"""
    return _model().encode(f"query: {text}", normalize_embeddings=True)


def to_blob(vec: np.ndarray) -> bytes:
    return np.asarray(vec, dtype=np.float32).tobytes()


def from_blob(blob: bytes) -> np.ndarray:
    return np.frombuffer(blob, dtype=np.float32)


def best_by_doc(
    query_vec: np.ndarray,
    rows: list[tuple[int, str, bytes]],
) -> dict[int, tuple[float, str]]:
    """フィールド別ベクトルとの類似度を計算し、doc_idごとに最大値へ集約する（全件）。

    rows は (doc_id, field, vec_blob) の一覧。
    戻り値は doc_id -> (最大類似度, 最も効いたフィールド名)。

    上位k件で打ち切らないのは、BM25だけでヒットした文書にも関連度を付けて
    同じ土俵で並べるため（ADR-0023）。
    """
    best: dict[int, tuple[float, str]] = {}
    for doc_id, field, blob in rows:
        score = float(np.dot(query_vec, from_blob(blob)))
        if doc_id not in best or score > best[doc_id][0]:
            best[doc_id] = (score, field)
    return best


def rank(best: dict[int, tuple[float, str]], k: int = 50) -> list[int]:
    """類似度の降順でdoc_idを最大k件返す（RRFへの入力用）。"""
    ranked = sorted(best.items(), key=lambda kv: kv[1][0], reverse=True)
    return [doc_id for doc_id, _ in ranked[:k]]
