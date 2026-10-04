"""S-14（F-18 一致理由ハイライト）：検索結果カードに「一致理由」（クエリと文書の対応語句）が出ることを、
実ブラウザ（Edge）で操作してスクショに残す。

Streamlit を新しいDB（一時フォルダ）で起動 → 入力例①の短文で検索 → 画面を撮る → Streamlit を止める。

前提（手元だけで使う。requirements.txt には入れていない）:
  pip install playwright     # ブラウザは入れず、PCに入っている Edge を使う
実行（リポジトリ直下から）:
  python evidence/3-4_S-14_shot.py
"""

import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]  # このファイルは evidence/ にある
OUT = ROOT / "evidence" / "3-4_S-14.png"
PORT = 8599
WORK = Path(tempfile.mkdtemp(prefix="s14_"))
CARD = '[class*="st-key-card-"]'

env = dict(os.environ, KNOWLEDGE_DB=str(WORK / "knowledge.db"), HF_HUB_OFFLINE="1", PYTHONUTF8="1")
server = subprocess.Popen(
    [sys.executable, "-m", "streamlit", "run", str(ROOT / "app" / "app.py"),
     "--server.headless", "true", "--server.port", str(PORT), "--browser.gatherUsageStats", "false"],
    cwd=ROOT, env=env, stdout=open(WORK / "streamlit.log", "w", encoding="utf-8"), stderr=subprocess.STDOUT,
)
try:
    for _ in range(60):
        try:
            urllib.request.urlopen(f"http://localhost:{PORT}/_stcore/health", timeout=2)
            break
        except Exception:
            time.sleep(1)
    else:
        raise RuntimeError("Streamlit が起動しませんでした")

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 2000})
        page.goto(f"http://localhost:{PORT}")
        page.wait_for_selector(".st-key-search-btn button", timeout=180_000)  # DB組み立て・モデル読み込みを待つ
        page.click(".st-key-search-btn button")
        page.wait_for_selector(CARD, timeout=60_000)
        page.get_by_text("一致理由").first.wait_for(timeout=30_000)

        # 結果は順に描画されるので、カードの数が3秒間変わらなくなるまで待つ（描画の途中で撮らないため）
        count, stable_since, deadline = -1, time.time(), time.time() + 60
        while time.time() < deadline:
            now = page.locator(CARD).count()
            if now != count:
                count, stable_since = now, time.time()
            elif time.time() - stable_since >= 3:
                break
            page.wait_for_timeout(500)

        # 右上の「実行中」表示が消えるのを待つ（実行中のアイコンが写らないように）
        status = page.locator('[data-testid="stStatusWidget"]')
        try:
            status.wait_for(state="detached", timeout=30_000)
            print("実行中の表示: 消えるのを確認")
        except Exception:
            print("実行中の表示: 30秒待っても消えなかった（そのまま撮影）")

        cards = page.locator(CARD).all()
        with_reason = [c for c in cards if "一致理由" in c.inner_text()]
        print(f"結果カード: {len(cards)}件 ／ うち「一致理由」の行があるカード: {len(with_reason)}件")

        lines = [ln for ln in cards[0].inner_text().splitlines() if ln.strip()]
        start = next(i for i, ln in enumerate(lines) if "一致理由" in ln)
        end = next(i for i, ln in enumerate(lines) if "この技術が解決しようとしている課題" in ln)
        print("1件目:", lines[0], "／", " ".join(lines[start:end]))

        page.screenshot(path=str(OUT))
        browser.close()
    print("保存:", OUT.relative_to(ROOT))
finally:
    server.terminate()
    server.wait(timeout=15)
    print("Streamlit を終了しました")
