"""言い換え候補の提示（F-21）。

ヒットが少ない・0件のときに検索を終わらせないための機能。
生活者の言葉に近い語を、反対側の文書に実在する語へ橋渡しする。

PoCでは対応表を手で持つ。本番では検索ログと埋め込みの近傍語から育てる。
"""

SYNONYMS: dict[str, list[str]] = {
    "べたつく": ["皮脂", "粘性", "油分"],
    "ベタつく": ["皮脂", "粘性", "油分"],
    "束になる": ["毛束", "凝集", "収束"],
    "崩れる": ["保持性", "経時変化", "形状保持"],
    "パサつく": ["乾燥", "水分保持", "キューティクル"],
    "きしむ": ["摩擦", "潤滑", "感触"],
    "乾燥": ["保湿", "水分蒸散", "バリア機能"],
    "かゆみ": ["刺激", "低刺激", "敏感肌"],
    "汗": ["発汗", "耐水性", "耐皮脂"],
}


def suggest(query_text: str, limit: int = 3) -> list[str]:
    """クエリに含まれる生活者語から、技術側で使われる語の候補を返す。"""
    found: list[str] = []
    for consumer_word, technical_words in SYNONYMS.items():
        if consumer_word in query_text:
            for w in technical_words:
                if w not in found:
                    found.append(w)
    return found[:limit]
