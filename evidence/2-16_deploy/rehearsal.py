"""2-16 デプロイ予行：DBが無い状態からの初回起動の時間・メモリと、1回目の検索の時間を測る（読み取りのみ）。

AppTest で app.py をそのまま実行する（DB組み立て＋埋め込みモデル読み込み＋検索は本番と同じ処理）。
Streamlitサーバー本体の分のメモリは含まれない。
"""

import ctypes
import os
import sys
import tempfile
import time
from ctypes import wintypes
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[2] / "app"  # このファイルは evidence/2-16_deploy/ にある
tmp = Path(tempfile.mkdtemp(prefix="rehearsal_"))
os.environ["KNOWLEDGE_DB"] = str(tmp / "knowledge.db")  # 必ず新規（DBが無い状態）
sys.path.insert(0, str(APP_DIR))


class PMC(ctypes.Structure):
    _fields_ = [(n, ctypes.c_size_t if n != "cb" and n != "PageFaultCount" else wintypes.DWORD) for n in
                ("cb", "PageFaultCount", "PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
                 "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage", "QuotaNonPagedPoolUsage",
                 "PagefileUsage", "PeakPagefileUsage")]


kernel32, psapi = ctypes.windll.kernel32, ctypes.windll.psapi
kernel32.GetCurrentProcess.restype = wintypes.HANDLE
psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(PMC), wintypes.DWORD]


def mem_mb():
    c = PMC()
    c.cb = ctypes.sizeof(c)
    psapi.GetProcessMemoryInfo(kernel32.GetCurrentProcess(), ctypes.byref(c), c.cb)
    return c.WorkingSetSize / 1e6, c.PeakWorkingSetSize / 1e6


from streamlit.testing.v1 import AppTest  # noqa: E402

print(f"DBの場所: {os.environ['KNOWLEDGE_DB']}（存在: {Path(os.environ['KNOWLEDGE_DB']).exists()}）")
print(f"計測前メモリ: {mem_mb()[0]:.0f} MB")

t0 = time.perf_counter()
at = AppTest.from_file(str(APP_DIR / "app.py"), default_timeout=600).run()
t1 = time.perf_counter()
now, peak = mem_mb()
print(f"初回起動（DB組み立て＋モデル読み込み＋画面描画）: {t1 - t0:.1f} 秒 ／ 例外: {len(at.exception)}件")
print(f"初回起動後メモリ: {now:.0f} MB ／ ここまでのピーク: {peak:.0f} MB")

t2 = time.perf_counter()
next(b for b in at.button if b.key == "search-btn").click().run()
t3 = time.perf_counter()
cards = [b for b in at.button if (b.key or "").startswith("detail-")]
print(f"1回目の検索（入力例①短文・両方併用）: {t3 - t2:.1f} 秒 ／ 結果カード: {len(cards)}件 ／ 例外: {len(at.exception)}件")
now, peak = mem_mb()
print(f"検索後メモリ: {now:.0f} MB ／ ピーク: {peak:.0f} MB")
print(f"生成されたDBのサイズ: {Path(os.environ['KNOWLEDGE_DB']).stat().st_size / 1e3:.0f} KB")
