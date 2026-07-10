#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
reviews_brightData_new_version.py
新仕様: PRIVATE_DATA_ROOT のデータを使ってレビュースクレイパーを起動するラッパー

run_reviews_local_interactive.py の自動実行（非対話）バージョン。
データディレクトリを PRIVATE_DATA_ROOT 環境変数で切り替えられる。

使用方法:
  # ローカル（データが /workspaces/googlemap にある場合、自動検出）
  python reviews_brightData_new_version.py

  # データルートを明示指定
  PRIVATE_DATA_ROOT=/path/to/data python reviews_brightData_new_version.py

  # 主要パラメータを env で指定
  INPUT_CSV=results/dental_new.csv \\
  OUTPUT_CSV=results/dental_reviews.csv \\
  DAYS_BACK=10 \\
  python reviews_brightData_new_version.py
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
        if p.exists() and (p / "results").exists():
            return p
        print(f"⚠️  PRIVATE_DATA_ROOT='{env_root}' に results/ ディレクトリが見つかりません", file=sys.stderr)

    # 2. Codespaces / ローカルの標準パス
    for candidate in [Path("/workspaces/googlemap"), Path.home() / "googlemap"]:
        if candidate.exists() and (candidate / "results").exists():
            return candidate

    # 3. カレントディレクトリにフォールバック
    cwd = Path.cwd()
    if (cwd / "results").exists():
        return cwd

    # 4. スクリプトのディレクトリにフォールバック
    return Path(__file__).parent


# ─────────────────────────────────────────────
# パスの解決ユーティリティ
# ─────────────────────────────────────────────
def resolve_path(raw: str, data_root: Path) -> Path:
    """相対パスは data_root 基準で絶対パスに変換する"""
    p = Path(raw)
    return p if p.is_absolute() else (data_root / p).resolve()


# ─────────────────────────────────────────────
# メイン
# ─────────────────────────────────────────────
def main() -> None:
    data_root = detect_data_root()
    results_dir = data_root / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    # ─── ファイルパスの解決 ───
    csv_file = resolve_path(
        os.environ.get("INPUT_CSV", "results/dental_new.csv"),
        data_root,
    )
    output_file = resolve_path(
        os.environ.get("OUTPUT_CSV", "results/dental_new_reviews.csv"),
        data_root,
    )

    print(f"📁 データルート : {data_root}")
    print(f"📂 入力CSV      : {csv_file}")
    print(f"📄 出力CSV      : {output_file}")

    # ─── 入力ファイルの存在確認 ───
    if not csv_file.exists():
        print(f"❌ エラー: 入力CSVが見つかりません: {csv_file}", file=sys.stderr)
        print("  INPUT_CSV 環境変数で正しいパスを指定してください", file=sys.stderr)
        sys.exit(1)

    # ─── 呼び出しスクリプトの確認 ───
    script_path = (Path(__file__).parent / "run_reviews_local_interactive.py").resolve()
    if not script_path.exists():
        print(f"❌ エラー: run_reviews_local_interactive.py が見つかりません: {script_path}", file=sys.stderr)
        sys.exit(1)

    # ─── コマンドライン引数の構築 ───
    cmd = [
        sys.executable,
        str(script_path),
        "--non-interactive",
        "--input", str(csv_file),
        "--output", str(output_file),
    ]

    # オプション引数（環境変数から取得）
    optional_args = [
        ("DAYS_BACK",         "--days-back"),
        ("BATCH_SIZE",        "--batch-size"),
        ("MAX_WAIT_MINUTES",  "--max-wait-minutes"),
        ("DATASET_ID",        "--dataset-id"),
        ("SKIP_COLUMN",       "--skip-column"),
        ("START_ROW",         "--start-row"),
        ("END_ROW",           "--end-row"),
        ("ROWS_PER_BATCH",    "--rows-per-batch"),
        ("BATCH_WAIT",        "--batch-wait"),
    ]
    for env_key, flag in optional_args:
        val = os.environ.get(env_key, "").strip()
        if val:
            cmd += [flag, val]

    # バッチモード
    if os.environ.get("BATCH_MODE", "").lower() in ("true", "1", "yes"):
        cmd.append("--batch-mode")

    # 増分ファイル
    update_raw = os.environ.get("UPDATE_FILE", "").strip()
    if update_raw:
        update_file = resolve_path(update_raw, data_root)
        cmd += ["--update", str(update_file)]

    # ─── 環境変数の構築 ───
    env = os.environ.copy()
    env["PRIVATE_DATA_ROOT"] = str(data_root)

    # ─── 実行（CWD をデータルートに設定してパスを自然に解決）───
    result = subprocess.run(
        cmd,
        env=env,
        cwd=str(data_root),
    )
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""New-version launcher for review scraping (Web Scraper API).

This is a thin wrapper around run_reviews_local_interactive.py with
private-data-root support enabled by default.
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Run review scraper in new-version mode")
    parser.add_argument("--data-root", default=os.getenv("PRIVATE_DATA_ROOT", ""), help="Private data root path")
    parser.add_argument("--input", default="results/dental_new.csv", help="Input CSV path")
    parser.add_argument("--output", default="results/dental_new_reviews.csv", help="Output CSV path")
    parser.add_argument("--api-token", default=os.getenv("BRIGHTDATA_API_TOKEN"), help="BrightData API token")
    parser.add_argument("--days-back", type=int, default=10)
    parser.add_argument("--start-row", type=int, default=1)
    parser.add_argument("--end-row", type=int, default=None)
    parser.add_argument("--batch-size", type=int, default=50)
    parser.add_argument("--max-wait-minutes", type=int, default=90)
    parser.add_argument("--dataset-id", default="gd_luzfs1dn2oa0teb81")
    parser.add_argument("--skip-column", default="web")
    parser.add_argument("--update", default=None)
    parser.add_argument("--interactive", action="store_true", help="Enable interactive mode")
    parser.add_argument("--batch-mode", action="store_true")
    parser.add_argument("--rows-per-batch", type=int, default=500)
    parser.add_argument("--batch-wait", type=int, default=120)
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    target_script = script_dir / "run_reviews_local_interactive.py"
    if not target_script.exists():
        print(f"❌ run_reviews_local_interactive.py not found: {target_script}")
        return 1

    data_root = detect_data_root(args.data_root)

    cmd = [
        sys.executable,
        str(target_script),
        "--data-root", str(data_root),
        "--input", args.input,
        "--output", args.output,
        "--days-back", str(args.days_back),
        "--start-row", str(args.start_row),
        "--batch-size", str(args.batch_size),
        "--max-wait-minutes", str(args.max_wait_minutes),
        "--dataset-id", args.dataset_id,
        "--skip-column", args.skip_column,
    ]

    if args.api_token:
        cmd.extend(["--api-token", args.api_token])
    if args.end_row is not None:
        cmd.extend(["--end-row", str(args.end_row)])
    if args.update:
        cmd.extend(["--update", args.update])
    if not args.interactive:
        cmd.append("--non-interactive")
    if args.batch_mode:
        cmd.append("--batch-mode")
        cmd.extend(["--rows-per-batch", str(args.rows_per_batch)])
        cmd.extend(["--batch-wait", str(args.batch_wait)])

    env = os.environ.copy()
    env["PRIVATE_DATA_ROOT"] = str(data_root)

    print(f"📂 Data root: {data_root}")
    proc = subprocess.run(cmd, env=env)
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
