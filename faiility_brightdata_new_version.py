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
#!/usr/bin/env python3
"""Facility scraper launcher for the new Web Scraper API workflow.

This wrapper enforces a private-data-first setup and delegates execution to
facility_BrightData_20.py with USE_NEW_API enabled.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path


def detect_data_root(cli_data_root: str = "") -> Path:
    candidate = cli_data_root or os.getenv("PRIVATE_DATA_ROOT", "")
    if candidate:
        root = Path(candidate).expanduser().resolve()
        if not root.exists():
            raise FileNotFoundError(f"PRIVATE_DATA_ROOT does not exist: {root}")
        if not (root / "settings").exists() or not (root / "results").exists():
            raise FileNotFoundError(f"PRIVATE_DATA_ROOT must contain settings/ and results/: {root}")
        return root

    default_private = Path("/workspaces/googlemap")
    if (default_private / "settings").exists() and (default_private / "results").exists():
        return default_private

    return Path(__file__).resolve().parent


def resolve_config_path(config_value: str, data_root: Path) -> Path:
    path = Path(config_value)
    if path.is_absolute():
        return path

    normalized = config_value.replace("\\", "/")
    if normalized.startswith("settings/") or normalized.startswith("results/"):
        return data_root / normalized
    return data_root / "settings" / normalized


def main() -> int:
    parser = argparse.ArgumentParser(description="Run facility scraper in new API mode")
    parser.add_argument("--config", default="settings/settings.json", help="Config file path")
    parser.add_argument("--data-root", default=os.getenv("PRIVATE_DATA_ROOT", ""), help="Private data root path")
    parser.add_argument("--use-old-api", action="store_true", help="Disable new API and use old mode")
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    target_script = script_dir / "facility_BrightData_20.py"
    if not target_script.exists():
        print(f"❌ facility_BrightData_20.py not found: {target_script}")
        return 1

    data_root = detect_data_root(args.data_root)
    config_path = resolve_config_path(args.config, data_root)
    if not config_path.exists():
        print(f"❌ Config file not found: {config_path}")
        return 1

    env = os.environ.copy()
    env["PRIVATE_DATA_ROOT"] = str(data_root)
    env["CONFIG_FILE"] = str(config_path)
    env["USE_NEW_API"] = "false" if args.use_old_api else "true"

    print(f"📂 Data root: {data_root}")
    print(f"📄 Config: {config_path}")
    print(f"🌐 USE_NEW_API: {env['USE_NEW_API']}")

    proc = subprocess.run([sys.executable, str(target_script)], env=env)
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
