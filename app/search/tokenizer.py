"""日本語の分かち書き（ADR-0011：Janome＋品詞フィルタ）。

trigramを使わないのは、意味を持たない3文字断片が偶然ヒットして
「キーワード検索で0件」というデモの前提が崩れるため。
"""

from functools import lru_cache

KEEP_POS = ("名詞", "動詞", "形容詞")

# 除外する名詞の細分類。「こと」「もの」「ため」等は内容語ではない
DROP_NOUN_SUBPOS = ("非自立", "代名詞", "数", "接尾")

# どんな文にも現れる汎用語。残すとニーズ文と技術文が「する」だけで一致してしまい、
# 「キーワード検索で0件」という前提が崩れる（ADR-0011の「実データで調整する」に相当）
STOPWORDS = {
    "する", "なる", "ある", "いる", "できる", "れる", "られる", "しまう", "みる",
    "行う", "用いる", "含む", "有する", "得る", "示す", "よる", "おく", "いう",
    "本発明", "発明", "従来", "課題", "手段", "効果", "特徴", "技術", "方法",
    "以上", "以下", "場合", "際", "上", "下", "中", "内", "的",
}


@lru_cache(maxsize=1)
def _tokenizer():
    from janome.tokenizer import Tokenizer

    return Tokenizer()


def tokenize(text: str) -> list[str]:
    """名詞・動詞・形容詞だけを残して分かち書きする。"""
    if not text:
        return []
    words = []
    for token in _tokenizer().tokenize(text):
        parts = token.part_of_speech.split(",")
        pos, subpos = parts[0], parts[1]
        if pos not in KEEP_POS:
            continue
        if pos == "名詞" and subpos in DROP_NOUN_SUBPOS:
            continue
        word = token.base_form if token.base_form != "*" else token.surface
        if word in STOPWORDS or len(word) == 1 and word.isascii():
            continue
        words.append(word)
    return words


def to_fts_text(text: str) -> str:
    """FTS5（unicode61）に入れるための分かち書き済みテキスト。"""
    return " ".join(tokenize(text))


def to_fts_query(text: str) -> str:
    """FTS5のMATCH句に渡すクエリ。語をORで繋ぐ。"""
    words = tokenize(text)
    if not words:
        return ""
    escaped = ['"' + w.replace('"', '""') + '"' for w in words]
    return " OR ".join(escaped)
