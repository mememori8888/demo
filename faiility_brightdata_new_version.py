#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
faiility_brightdata_new_version.py
新仕様: PRIVATE_DATA_ROOT のデータを使って施設スクレイパーを起動するラッパー

使用方法:
  # ローカル（データが /workspaces/googlemap にある場合、自動検出）
  python faiility_brightdata_new_version.py

  # データルートを明示指定
  PRIVATE_DATA_ROOT=/path/to/data python faiility_brightdata_new_version.py

  # 設定ファイルを指定
  CONFIG_FILE=settings/care_roujin-home.json python faiility_brightdata_new_version.py
"""
import os
import sys
import subprocess
from pathlib import Path


# ─────────────────────────────────────────────
# データルート検出
# 優先順位: PRIVATE_DATA_ROOT env > /workspaces/googlemap > カレントディレクトリ
# ─────────────────────────────────────────────
def detect_data_root() -> Path:
    """データルートを検出する（フェイルセーフ設計）"""

    # 1. 環境変数で明示指定
    env_root = os.environ.get("PRIVATE_DATA_ROOT", "").strip()
    if env_root:
        p = Path(env_root)
        if p.exists() and (p / "settings").exists():
            return p
        print(f"⚠️  PRIVATE_DATA_ROOT='{env_root}' に settings/ ディレクトリが見つかりません", file=sys.stderr)

    # 2. Codespaces / ローカルの標準パス
    for candidate in [Path("/workspaces/googlemap"), Path.home() / "googlemap"]:
        if candidate.exists() and (candidate / "settings").exists():
            return candidate

    # 3. カレントディレクトリにフォールバック
    cwd = Path.cwd()
    if (cwd / "settings").exists():
        return cwd

    # 4. スクリプトのディレクトリにフォールバック
    return Path(__file__).parent


# ─────────────────────────────────────────────
# メイン
# ─────────────────────────────────────────────
def main() -> None:
    data_root = detect_data_root()
    settings_dir = data_root / "settings"
    results_dir = data_root / "results"

    # ─── 必須ディレクトリ検証 ───
    if not settings_dir.exists():
        print(f"❌ エラー: settings/ ディレクトリが見つかりません: {settings_dir}", file=sys.stderr)
        print("  PRIVATE_DATA_ROOT 環境変数でデータディレクトリを指定してください", file=sys.stderr)
        sys.exit(1)

    results_dir.mkdir(parents=True, exist_ok=True)

    # ─── 設定ファイルの解決 ───
    config_file_raw = os.environ.get("CONFIG_FILE", "settings/settings.json")
    config_path = Path(config_file_raw)
    if not config_path.is_absolute():
        config_path = data_root / config_file_raw
    config_path = config_path.resolve()

    if not config_path.exists():
        print(f"❌ エラー: 設定ファイルが見つかりません: {config_path}", file=sys.stderr)
        sys.exit(1)

    # ─── 呼び出しスクリプトの確認 ───
    script_path = (Path(__file__).parent / "facility_BrightData_20.py").resolve()
    if not script_path.exists():
        print(f"❌ エラー: facility_BrightData_20.py が見つかりません: {script_path}", file=sys.stderr)
        sys.exit(1)

    print(f"📁 データルート  : {data_root}")
    print(f"⚙️  設定ファイル : {config_path}")
    print(f"📂 results/      : {results_dir}")

    # ─── 環境変数の構築 ───
    env = os.environ.copy()
    env["PRIVATE_DATA_ROOT"] = str(data_root)
    env["CONFIG_FILE"] = str(config_path)

    # ─── 実行（CWD をデータルートに設定してパスを自然に解決）───
    result = subprocess.run(
        [sys.executable, str(script_path)],
        env=env,
        cwd=str(data_root),
    )
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
