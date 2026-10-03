"""テスト用の疑似エンコーダ。モデル（約470MB）を読み込まずに、埋め込みの配管をテストするために使う。

文字2連続（バイグラム）をハッシュで384次元に散らして長さ1に揃えるだけの仕組み。
同じ文字列は同じベクトルになり、共通の文字が多い文ほど内積（コサイン類似度）が高くなる。
意味の近さは見ない。意味検索の品質は、実モデルを使う `model` マーク付きのテストで確認する。
"""

import zlib

import numpy as np

DIM = 384


def fake_encode(prefixed_texts: list[str]) -> np.ndarray:
    out = np.zeros((len(prefixed_texts), DIM), dtype=np.float32)
    for i, text in enumerate(prefixed_texts):
        body = text.split(": ", 1)[1] if ": " in text else text  # プレフィックスは見ない
        for a, b in zip(body, body[1:]):
            out[i, zlib.crc32((a + b).encode("utf-8")) % DIM] += 1.0
        norm = np.linalg.norm(out[i])
        if norm > 0:
            out[i] /= norm
    return out
