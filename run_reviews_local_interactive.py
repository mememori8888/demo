#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
get_reviews_from_dental_new.py をローカルで実行するための対話型ラッパースクリプト

GitHub Actionsのワークフローで使用されている環境変数を設定して、
ローカル環境で簡単に実行できるようにします。
"""
import os
import sys
import subprocess
import argparse
import datetime
import time
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description='BrightData Web Scraper APIを使用してGoogleマップレビューを取得（ローカル実行用）',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
使用例:
  # 基本的な実行（対話モード）
  python run_reviews_local_interactive.py
  
  # コマンドライン引数で指定
  python run_reviews_local_interactive.py `
    --input results/dental_new.csv `
    --output results/dental_new_reviews.csv `
    --api-token YOUR_API_TOKEN `
    --days-back 10 `
    --start-row 1 `
    --end-row 100
        '''
    )
    
    # 必須引数
    parser.add_argument(
        '--input',
        type=str,
        default='results/dental_new.csv',
        help='入力CSVファイルのパス（施設情報） (デフォルト: results/dental_new.csv)'
    )
    
    parser.add_argument(
        '--output',
        type=str,
        default='results/dental_new_reviews.csv',
        help='出力CSVファイルのパス（レビュー情報） (デフォルト: results/dental_new_reviews.csv)'
    )
    
    parser.add_argument(
        '--api-token',
        type=str,
        default=None,
        help='BrightData APIトークン（環境変数 BRIGHTDATA_API_TOKEN でも設定可）'
    )
    
    # オプション引数
    parser.add_argument(
        '--update',
        type=str,
        default=None,
        help='増分ファイルのパス（新規レビューのみ出力） (オプション)'
    )
    
    parser.add_argument(
        '--start-row',
        type=int,
        default=1,
        help='処理開始行（1ベース、ヘッダー除く） (デフォルト: 1)'
    )
    
    parser.add_argument(
        '--end-row',
        type=int,
        default=None,
        help='処理終了行（指定しない場合は最終行まで） (オプション)'
    )
    
    parser.add_argument(
        '--days-back',
        type=int,
        default=10,
        help='何日前までのレビューを取得するか (デフォルト: 10)'
    )
    
    parser.add_argument(
        '--batch-size',
        type=int,
        default=50,
        help='API 1回あたりの処理件数 (デフォルト: 50)'
    )
    
    parser.add_argument(
        '--max-wait-minutes',
        type=int,
        default=90,
        help='スナップショット待機時間（分） (デフォルト: 90)'
    )
    
    parser.add_argument(
        '--dataset-id',
        type=str,
        default='gd_luzfs1dn2oa0teb81',
        help='BrightData Dataset ID (デフォルト: gd_luzfs1dn2oa0teb81)'
    )
    
    parser.add_argument(
        '--skip-column',
        type=str,
        default='web',
        help='スキップ判定列名（この列が空の行はスキップ） (デフォルト: web)'
    )
    
    parser.add_argument(
        '--non-interactive',
        action='store_true',
        help='対話モードを無効化（すべての引数をコマンドラインで指定）'
    )
    
    parser.add_argument(
        '--batch-mode',
        action='store_true',
        help='バッチモード: 指定行数ごとに分割処理して各バッチの結果を保存'
    )
    
    parser.add_argument(
        '--rows-per-batch',
        type=int,
        default=500,
        help='バッチモード時の1バッチあたりの行数 (デフォルト: 500)'
    )
    
    parser.add_argument(
        '--batch-wait',
        type=int,
        default=120,
        help='バッチ間の待機時間（秒） (デフォルト: 120)'
    )
    
    args = parser.parse_args()
    
    # 対話モード
    if not args.non_interactive:
        print("=" * 60)
        print("🚀 BrightData レビュー取得ツール（ローカル実行版）")
        print("=" * 60)
        print()
        
        # APIトークンの確認
        api_token = args.api_token or os.getenv('BRIGHTDATA_API_TOKEN')
        if not api_token:
            print("⚠️  BrightData APIトークンが設定されていません")
            print()
            api_token = input("APIトークンを入力してください: ").strip()
            if not api_token:
                print("❌ APIトークンは必須です")
                sys.exit(1)
        else:
            print(f"✅ APIトークン: {'*' * 20}{api_token[-8:] if len(api_token) > 8 else '****'}")
        
        # 入出力ファイルの確認と変更
        print()
        print("📁 ファイル設定:")
        print(f"   入力CSV: {args.input}")
        print(f"   出力CSV: {args.output}")
        
        # 入力ファイルの変更
        print()
        new_input = input(f"入力CSVを変更しますか？ [{args.input}] (Enter でスキップ): ").strip()
        if new_input:
            args.input = new_input
            print(f"  ✅ 入力CSVを {args.input} に変更")
        
        # 入力ファイルの存在確認
        if not Path(args.input).exists():
            print(f"  ❌ エラー: 入力ファイルが見つかりません: {args.input}")
            sys.exit(1)
        
        # 出力ファイルの変更
        new_output = input(f"出力CSVを変更しますか？ [{args.output}] (Enter でスキップ): ").strip()
        if new_output:
            args.output = new_output
            print(f"  ✅ 出力CSVを {args.output} に変更")
        
        # 処理範囲の確認
        print()
        print("📊 処理範囲:")
        try:
            with open(args.input, 'r', encoding='utf-8') as f:
                total_rows = sum(1 for _ in f) - 1  # ヘッダー除く
            print(f"   総行数: {total_rows}行")
        except Exception as e:
            print(f"   総行数: 不明（エラー: {e}）")
            total_rows = None
        
        print(f"   開始行: {args.start_row}")
        if args.end_row:
            print(f"   終了行: {args.end_row}")
            print(f"   処理件数: {args.end_row - args.start_row + 1}件")
        else:
            if total_rows:
                print(f"   終了行: {total_rows}（最終行まで）")
                print(f"   処理件数: {total_rows - args.start_row + 1}件")
            else:
                print(f"   終了行: 最終行まで")
        
        # 処理範囲の変更
        print()
        new_start = input(f"開始行を変更しますか？ [{args.start_row}] (Enter でスキップ): ").strip()
        if new_start and new_start.isdigit():
            args.start_row = int(new_start)
            print(f"  ✅ 開始行を {args.start_row} に変更")
        
        end_row_display = args.end_row if args.end_row else "最終行まで"
        new_end = input(f"終了行を変更しますか？ [{end_row_display}] (Enter でスキップ): ").strip()
        if new_end and new_end.isdigit():
            args.end_row = int(new_end)
            print(f"  ✅ 終了行を {args.end_row} に変更")
        
        # 設定の確認
        print()
        print("⚙️  設定:")
        print(f"   Days back: {args.days_back}日")
        print(f"   Batch size: {args.batch_size}件/回")
        print(f"   Max wait: {args.max_wait_minutes}分")
        print(f"   Dataset ID: {args.dataset_id}")
        print(f"   Skip column: {args.skip_column}")
        
        if args.update:
            print(f"   増分ファイル: {args.update}")
        
        # 設定の変更オプション
        print()
        print("📝 設定を変更しますか？（Enter でスキップ）")
        
        # Days back の変更
        new_days = input(f"  Days back [{args.days_back}日]: ").strip()
        if new_days and new_days.isdigit():
            args.days_back = int(new_days)
            print(f"  ✅ Days back を {args.days_back}日 に変更")
        
        # Batch size の変更
        new_batch = input(f"  Batch size [{args.batch_size}件/回]: ").strip()
        if new_batch and new_batch.isdigit():
            args.batch_size = int(new_batch)
            print(f"  ✅ Batch size を {args.batch_size}件/回 に変更")
        
        # Max wait minutes の変更
        new_wait = input(f"  Max wait [{args.max_wait_minutes}分]: ").strip()
        if new_wait and new_wait.isdigit():
            args.max_wait_minutes = int(new_wait)
            print(f"  ✅ Max wait を {args.max_wait_minutes}分 に変更")
        
        # Dataset ID の変更
        new_dataset = input(f"  Dataset ID [{args.dataset_id}]: ").strip()
        if new_dataset:
            args.dataset_id = new_dataset
            print(f"  ✅ Dataset ID を {args.dataset_id} に変更")
        
        # Skip column の変更
        new_skip = input(f"  Skip column [{args.skip_column}]: ").strip()
        if new_skip:
            args.skip_column = new_skip
            print(f"  ✅ Skip column を {args.skip_column} に変更")
        
        # 増分ファイルの指定
        if not args.update:
            new_update = input(f"  増分ファイル出力 [なし]: ").strip()
            if new_update:
                args.update = new_update
                print(f"  ✅ 増分ファイル出力を {args.update} に設定")
        
        # バッチモードの設定
        print()
        print("📦 バッチモード設定:")
        print("   バッチモード: 大量データを分割処理し、途中で止まっても再開可能")
        batch_mode_input = input("バッチモードを有効にしますか？ (y/N): ").strip().lower()
        if batch_mode_input in ['y', 'yes']:
            args.batch_mode = True
            print("  ✅ バッチモードを有効化")
            
            # バッチサイズの設定
            batch_size_input = input(f"  1バッチあたりの行数 [{args.rows_per_batch}]: ").strip()
            if batch_size_input and batch_size_input.isdigit():
                args.rows_per_batch = int(batch_size_input)
            print(f"  ✅ バッチサイズ: {args.rows_per_batch}行")
            
            # バッチ間待機時間
            wait_input = input(f"  バッチ間の待機時間（秒） [{args.batch_wait}]: ").strip()
            if wait_input and wait_input.isdigit():
                args.batch_wait = int(wait_input)
            print(f"  ✅ バッチ間待機: {args.batch_wait}秒")
        
        # 実行確認
        print()
        confirm = input("この設定で実行しますか？ (y/N): ").strip().lower()
        if confirm not in ['y', 'yes']:
            print("❌ キャンセルしました")
            sys.exit(0)
        
        args.api_token = api_token
    else:
        # 非対話モード
        api_token = args.api_token or os.getenv('BRIGHTDATA_API_TOKEN')
        if not api_token:
            print("❌ エラー: APIトークンが設定されていません")
            print("   --api-token で指定するか、環境変数 BRIGHTDATA_API_TOKEN を設定してください")
            sys.exit(1)
        
        if not Path(args.input).exists():
            print(f"❌ エラー: 入力ファイルが見つかりません: {args.input}")
            sys.exit(1)
        
        args.api_token = api_token
    
    # スクリプトのパス
    script_path = Path(__file__).parent / 'get_reviews_from_dental_new.py'
    
    if not script_path.exists():
        print(f"❌ エラー: スクリプトが見つかりません: {script_path}")
        sys.exit(1)
    
    # 実行時刻を記録
    start_time = datetime.datetime.now()
    
    # ログディレクトリとログファイルの設定
    log_dir = Path('results/logs')
    log_dir.mkdir(parents=True, exist_ok=True)
    log_filename = f"wrapper_{start_time.strftime('%Y%m%d_%H%M%S')}.log"
    log_file_path = log_dir / log_filename
    
    def log_and_print(message, log_file=None):
        """コンソールとログファイルの両方に出力"""
        print(message)
        if log_file:
            log_file.write(message + '\n')
            log_file.flush()
    
    print()
    print("=" * 60)
    print("🚀 処理を開始します...")
    print("=" * 60)
    print()
    print(f"⏰ 開始時刻: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📝 ログファイル: {log_file_path}")
    print()
    
    # ログファイルを開く
    try:
        log_file = open(log_file_path, 'w', encoding='utf-8')
    except Exception as e:
        print(f"❌ エラー: ログファイルが作成できません: {e}")
        sys.exit(1)
    
    # ログファイルにヘッダー情報を記録
    log_file.write("=" * 60 + '\n')
    log_file.write("BrightData レビュー取得ツール - 実行ログ\n")
    log_file.write("=" * 60 + '\n')
    log_file.write(f"開始時刻: {start_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    log_file.write(f"入力CSV: {args.input}\n")
    log_file.write(f"出力CSV: {args.output}\n")
    log_file.write(f"処理範囲: {args.start_row} ～ {args.end_row if args.end_row else '最終行'}\n")
    log_file.write(f"Days back: {args.days_back}日\n")
    log_file.write(f"Batch size: {args.batch_size}件/回\n")
    log_file.write(f"Max wait: {args.max_wait_minutes}分\n")
    log_file.write(f"Dataset ID: {args.dataset_id}\n")
    log_file.write(f"Skip column: {args.skip_column}\n")
    if args.batch_mode:
        log_file.write(f"バッチモード: 有効\n")
        log_file.write(f"  - 1バッチあたり: {args.rows_per_batch}行\n")
        log_file.write(f"  - バッチ間待機: {args.batch_wait}秒\n")
    log_file.write("=" * 60 + '\n\n')
    log_file.flush()
    
    # バッチモードの処理
    if args.batch_mode:
        log_and_print("📦 バッチモードで実行します", log_file)
        log_and_print("", log_file)
        
        # 総行数を取得
        try:
            with open(args.input, 'r', encoding='utf-8') as f:
                total_rows = sum(1 for _ in f) - 1  # ヘッダー除く
        except Exception as e:
            log_and_print(f"❌ エラー: 入力ファイルの行数を取得できません: {e}", log_file)
            log_file.close()
            sys.exit(1)
        
        # バッチ範囲の計算
        start_row = args.start_row
        end_row = args.end_row if args.end_row else total_rows
        total_batches = ((end_row - start_row + 1) + args.rows_per_batch - 1) // args.rows_per_batch
        
        log_and_print(f"📊 バッチ処理概要:", log_file)
        log_and_print(f"   総行数: {total_rows}行", log_file)
        log_and_print(f"   処理範囲: {start_row} ～ {end_row}行", log_file)
        log_and_print(f"   バッチサイズ: {args.rows_per_batch}行", log_file)
        log_and_print(f"   総バッチ数: {total_batches}", log_file)
        log_and_print(f"   バッチ間待機: {args.batch_wait}秒", log_file)
        log_and_print("", log_file)
        
        success_count = 0
        error_count = 0
        batch_details = []  # バッチごとの詳細を記録
        
        for batch_num in range(1, total_batches + 1):
            batch_start = start_row + (batch_num - 1) * args.rows_per_batch
            batch_end = min(batch_start + args.rows_per_batch - 1, end_row)
            batch_start_time = datetime.datetime.now()
            
            log_and_print("=" * 60, log_file)
            log_and_print(f"📦 バッチ {batch_num}/{total_batches} 開始", log_file)
            log_and_print(f"   範囲: 行 {batch_start} ～ {batch_end} ({batch_end - batch_start + 1}件)", log_file)
            log_and_print(f"   開始時刻: {batch_start_time.strftime('%Y-%m-%d %H:%M:%S')}", log_file)
            log_and_print("=" * 60, log_file)
            log_and_print("", log_file)
            
            # 環境変数を設定
            env = os.environ.copy()
            env['INPUT_CSV'] = str(Path(args.input).absolute())
            env['OUTPUT_CSV'] = str(Path(args.output).absolute())
            env['START_ROW'] = str(batch_start)
            env['END_ROW'] = str(batch_end)
            env['DAYS_BACK'] = str(args.days_back)
            env['BATCH_SIZE'] = str(args.batch_size)
            env['MAX_WAIT_MINUTES'] = str(args.max_wait_minutes)
            env['BRIGHTDATA_API_TOKEN'] = args.api_token
            env['BRIGHTDATA_DATASET_ID'] = args.dataset_id
            env['SKIP_COLUMN'] = args.skip_column
            
            # バッチごとの増分ファイル
            batch_update_file = Path(args.output).parent / f"batch_{batch_num}_{Path(args.output).name}"
            env['UPDATE_CSV'] = str(batch_update_file.absolute())
            
            # バッチ処理実行
            try:
                process = subprocess.Popen(
                    [sys.executable, str(script_path)],
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    universal_newlines=True
                )
                
                # 出力をリアルタイムで表示（ログにも記録）
                for line in process.stdout:
                    print(line, end='')
                    log_file.write(line)
                    log_file.flush()
                
                return_code = process.wait()
                batch_end_time = datetime.datetime.now()
                batch_elapsed = batch_end_time - batch_start_time
                
                # バッチ結果を記録
                batch_info = {
                    'batch_num': batch_num,
                    'start_row': batch_start,
                    'end_row': batch_end,
                    'start_time': batch_start_time,
                    'end_time': batch_end_time,
                    'elapsed': str(batch_elapsed).split('.')[0],
                    'return_code': return_code,
                    'output_file': str(batch_update_file)
                }
                
                if return_code == 0:
                    success_count += 1
                    batch_info['status'] = 'success'
                    log_and_print("", log_file)
                    log_and_print(f"✅ バッチ {batch_num} 完了", log_file)
                    log_and_print(f"⏱️  処理時間: {batch_info['elapsed']}", log_file)
                    log_and_print(f"💾 増分ファイル: {batch_update_file}", log_file)
                else:
                    error_count += 1
                    batch_info['status'] = 'error'
                    log_and_print("", log_file)
                    log_and_print(f"❌ バッチ {batch_num} でエラー発生（終了コード: {return_code}）", log_file)
                    log_and_print(f"⏱️  処理時間: {batch_info['elapsed']}", log_file)
                    log_and_print(f"⚠️  次のバッチに進みます...", log_file)
                
                batch_details.append(batch_info)
                
            except Exception as e:
                error_count += 1
                batch_end_time = datetime.datetime.now()
                batch_elapsed = batch_end_time - batch_start_time
                batch_info = {
                    'batch_num': batch_num,
                    'start_row': batch_start,
                    'end_row': batch_end,
                    'start_time': batch_start_time,
                    'end_time': batch_end_time,
                    'elapsed': str(batch_elapsed).split('.')[0],
                    'status': 'exception',
                    'error': str(e)
                }
                batch_details.append(batch_info)
                log_and_print(f"❌ バッチ {batch_num} で例外発生: {e}", log_file)
            
            log_and_print("", log_file)
            
            # 最後のバッチでなければ待機
            if batch_num < total_batches:
                log_and_print(f"⏳ {args.batch_wait}秒待機中...", log_file)
                time.sleep(args.batch_wait)
                log_and_print("", log_file)
        
        # 最終レポート
        end_time = datetime.datetime.now()
        elapsed_time = end_time - start_time
        
        log_and_print("", log_file)
        log_and_print("=" * 60, log_file)
        log_and_print("📊 バッチ処理完了サマリー", log_file)
        log_and_print("=" * 60, log_file)
        log_and_print(f"⏰ 終了時刻: {end_time.strftime('%Y-%m-%d %H:%M:%S')}", log_file)
        log_and_print(f"⏱️  処理時間: {str(elapsed_time).split('.')[0]}", log_file)
        log_and_print(f"✅ 成功バッチ: {success_count}/{total_batches}", log_file)
        log_and_print(f"❌ エラーバッチ: {error_count}/{total_batches}", log_file)
        log_and_print(f"📁 出力ファイル: {args.output}", log_file)
        log_and_print("", log_file)
        log_and_print(f"💡 増分ファイル: results/batch_*_{Path(args.output).name}", log_file)
        log_and_print(f"📝 ログファイル: {log_file_path}", log_file)
        log_and_print("=" * 60, log_file)
        
        # バッチ詳細をログに記録
        log_file.write("\n\n")
        log_file.write("=" * 60 + '\n')
        log_file.write("📋 バッチ別詳細レポート\n")
        log_file.write("=" * 60 + '\n')
        for detail in batch_details:
            log_file.write(f"\nバッチ {detail['batch_num']}:\n")
            log_file.write(f"  行範囲: {detail['start_row']} ～ {detail['end_row']}\n")
            log_file.write(f"  開始時刻: {detail['start_time'].strftime('%Y-%m-%d %H:%M:%S')}\n")
            log_file.write(f"  終了時刻: {detail['end_time'].strftime('%Y-%m-%d %H:%M:%S')}\n")
            log_file.write(f"  処理時間: {detail['elapsed']}\n")
            log_file.write(f"  ステータス: {detail['status']}\n")
            if 'output_file' in detail:
                log_file.write(f"  出力ファイル: {detail['output_file']}\n")
            if 'error' in detail:
                log_file.write(f"  エラー: {detail['error']}\n")
        
        log_file.close()
        sys.exit(0 if error_count == 0 else 1)
    
    # 通常モード（バッチなし）
    try:
        # 環境変数を設定
        env = os.environ.copy()
        env['INPUT_CSV'] = str(Path(args.input).absolute())
        env['OUTPUT_CSV'] = str(Path(args.output).absolute())
        env['START_ROW'] = str(args.start_row)
        env['DAYS_BACK'] = str(args.days_back)
        env['BATCH_SIZE'] = str(args.batch_size)
        env['MAX_WAIT_MINUTES'] = str(args.max_wait_minutes)
        env['BRIGHTDATA_API_TOKEN'] = args.api_token
        env['BRIGHTDATA_DATASET_ID'] = args.dataset_id
        env['SKIP_COLUMN'] = args.skip_column
        
        if args.end_row:
            env['END_ROW'] = str(args.end_row)
        
        if args.update:
            env['UPDATE_CSV'] = str(Path(args.update).absolute())
        
        # Process実行
        process = subprocess.Popen(
            [sys.executable, str(script_path)],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        # 出力をリアルタイムで表示（ログにも記録）
        line_count = 0
        for line in process.stdout:
            print(line, end='')
            log_file.write(line)
            log_file.flush()
            line_count += 1
            
            # 進捗ログを定期的に表示
            if line_count % 50 == 0:
                elapsed = datetime.datetime.now() - start_time
                progress_msg = f"\n⏱️  経過時間: {str(elapsed).split('.')[0]} ({line_count}行出力)\n"
                print(progress_msg)
                log_file.write(progress_msg)
                log_file.flush()
        
        # プロセスの終了を待機
        return_code = process.wait()
        
        # 終了時刻と経過時間を表示
        end_time = datetime.datetime.now()
        elapsed_time = end_time - start_time
        
        log_and_print("", log_file)
        log_and_print("=" * 60, log_file)
        log_and_print(f"⏰ 終了時刻: {end_time.strftime('%Y-%m-%d %H:%M:%S')}", log_file)
        log_and_print(f"⏱️  処理時間: {str(elapsed_time).split('.')[0]}", log_file)
        
        if return_code == 0:
            log_and_print("✅ 処理が完了しました", log_file)
        else:
            log_and_print(f"❌ 処理がエラーで終了しました（終了コード: {return_code}）", log_file)
        log_and_print(f"📝 ログファイル: {log_file_path}", log_file)
        log_and_print("=" * 60, log_file)
        
        log_file.close()
        sys.exit(return_code)
        
    except KeyboardInterrupt:
        log_and_print("", log_file)
        log_and_print("⚠️  ユーザーによって中断されました", log_file)
        log_file.close()
        sys.exit(130)
    except Exception as e:
        log_and_print(f"❌ エラー: {e}", log_file)
        log_file.close()
        sys.exit(1)


if __name__ == '__main__':
    main()
