"""日本語の分かち書き（ADR-0011）。

Janomeで形態素に分け、品詞フィルタ（名詞・動詞・形容詞だけ残す）とストップワード除去をかける。
索引を張る側（db/build_db.py）と検索する側（search/bm25.py）が**必ずこの関数を使う**。
ここがずれると「入れた語で引けない」不具合になるため、分かち書きのルールはこのファイルの1か所に置く。

trigramを使わないのは、意味のない3文字断片が偶然ヒットして
「キーワードで0件」というデモの前提（N-06）が崩れるため。
"""

import re
import unicodedata
from functools import lru_cache

# 残す品詞
KEEP_POS = ("名詞", "動詞", "形容詞")

# 名詞のうち内容語でないもの。「こと」「もの」（非自立）、「これ」（代名詞）、数、接尾辞
DROP_NOUN_SUBPOS = ("非自立", "代名詞", "数", "接尾")

# どの文書にも出る汎用語。残すとニーズ文と特許文が「する」だけで一致して、
# 「キーワードで0件」にならなくなる。実データを入れたあと check_gap.py の結果を見て調整する
STOPWORDS = frozenset(
    {
        # 動詞（機能語化しているもの）
        "する", "なる", "ある", "いる", "できる", "れる", "られる", "しまう", "みる", "おく",
        "行う", "用いる", "含む", "有する", "得る", "示す", "よる", "いう", "もつ", "持つ",
        # 特許文書の定型語
        "本発明", "発明", "従来", "課題", "手段", "効果", "特徴", "方法", "技術",
        # 位置・範囲を表すだけの語
        "以上", "以下", "場合", "際", "上", "下", "中", "内", "的",
    }
)

_SINGLE_KANA_OR_ASCII = re.compile(r"^[ぁ-ゟ\x00-\x7f]$")


@lru_cache(maxsize=1)
def _janome():
    # 辞書の読み込みに1秒ほどかかるので、使うときまで遅らせて1回だけ作る
    from janome.tokenizer import Tokenizer

    return Tokenizer()


def _normalize(word: str) -> str:
    return unicodedata.normalize("NFKC", word).lower()


def _keep(token) -> str | None:
    """残すべき語なら正規化した語を返し、捨てるなら None を返す。"""
    pos, subpos = token.part_of_speech.split(",")[:2]
    if pos not in KEEP_POS:
        return None
    if subpos == "非自立":
        return None
    if pos == "名詞" and subpos in DROP_NOUN_SUBPOS:
        return None
    word = token.base_form if token.base_form != "*" else token.surface
    word = _normalize(word)
    if word in STOPWORDS:
        return None
    if _SINGLE_KANA_OR_ASCII.match(word):
        return None
    return word


def tokenize(text: str | None) -> list[str]:
    """名詞・動詞・形容詞だけを、基本形にして返す。"""
    if not text:
        return []
    words = []
    for token in _janome().tokenize(text):
        word = _keep(token)
        if word:
            words.append(word)
    return words


def to_fts_text(text: str | None) -> str:
    """FTS5（unicode61）の索引に入れる、空白区切りの分かち書き済みテキスト。"""
    return " ".join(tokenize(text))


def to_fts_query(text: str | None) -> str:
    """FTS5のMATCH句に渡すクエリ。重複を除いた語をORでつなぐ。語が無ければ空文字。"""
    words = list(dict.fromkeys(tokenize(text)))
    return " OR ".join('"' + w.replace('"', '""') + '"' for w in words)


def find_spans(text: str | None, terms: set[str] | frozenset[str]) -> list[tuple[int, int]]:
    """`text` の中で、`terms` に含まれる語（基本形で比較）が現れる範囲 (開始, 終了) を返す。

    BM25のスニペット切り出しと、一致語のハイライトに使う。contentless構成のFTS5は
    snippet() が使えないため、原文を同じ分かち書きにかけて位置を求める。
    """
    if not text or not terms:
        return []
    spans = []
    pos = 0
    for token in _janome().tokenize(text):
        end = pos + len(token.surface)
        word = _keep(token)
        if word and word in terms:
            spans.append((pos, end))
        pos = end
    return spans
