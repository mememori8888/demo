"""
Dental Reviews Sequential Batch Processor - Local Runner
GitHub Actions workflow dental_new_reviews_sequential.yml をローカルで実行

★ GitHub Actionsと同じ設定値（デフォルト）:
    CSV_BATCH_SIZE=500          → --csv-batch-size 500
    WAIT_TIME=120               → --wait-time 120
    API_BATCH_SIZE=50           → --api-batch-size 50
    MAX_WAIT_MINUTES=90         → --max-wait-minutes 90
    DATASET_ID=gd_luzfs1dn...   → --dataset-id gd_luzfs1dn2oa0teb81
    START_BATCH=1               → --start-from-batch 1

使用例（PowerShell対応 - 1行で実行）:
    python run_dental_reviews_sequential.py --input results/dental_new_hokkaido.csv --output results/dental_new_reviews_hokkaido.csv --token YOUR_TOKEN
    python run_dental_reviews_sequential.py --input results/dental_new.csv --output results/dental_new_reviews.csv --token YOUR_TOKEN --retry 3 --start-from-batch 1
    python run_dental_reviews_sequential.py --input results/dental_new_hokkaido.csv --output results/dental_new_reviews_hokkaido.csv --token YOUR_TOKEN --csv-batch-size 500 --wait-time 120
    python run_dental_reviews_sequential.py --input results/dental_new.csv --output results/dental_new_reviews.csv --token YOUR_TOKEN --start-from-batch 5 --retry 3
    python run_dental_reviews_sequential.py --settings settings/dental_reviews.json --token YOUR_TOKEN --retry 3
"""

import os
import sys
import json
import argparse
import subprocess
import time
import signal
from pathlib import Path
from datetime import datetime
import logging
import threading

logger = logging.getLogger(__name__)


class DentalReviewsSequentialRunner:
    """Dental Reviews Sequential Batch Processorを実行するクラス"""
    
    def __init__(self, args):
        """初期化"""
        self.input_csv = args.input
        self.output_csv = args.output
        self.brightdata_token = args.token or os.getenv('BRIGHTDATA_API_TOKEN')
        self.zone_name = args.zone or os.getenv('BRIGHTDATA_ZONE_NAME', 'serp_api1')
        
        # バッチ処理設定
        self.csv_batch_size = args.csv_batch_size
        self.wait_time = args.wait_time
        self.api_batch_size = args.api_batch_size
        self.max_wait_minutes = args.max_wait_minutes
        self.dataset_id = args.dataset_id
        self.days_back = args.days_back
        self.skip_column = args.skip_column
        self.start_from_batch = args.start_from_batch
        
        # リトライとタイムアウト
        self.retry = args.retry
        self.timeout = args.timeout
        self.max_workers = args.max_workers
        
        # その他のオプション
        self.merge_to_all = args.merge_to_all
        self.all_regions_file = args.all_regions_file
        self.generate_report = args.generate_report
        self.report_days = args.report_days
        self.verbose = args.verbose
        self.quiet = args.quiet
        self.dry_run = args.dry_run
        
        # 自動保存設定
        self.auto_save_interval = args.auto_save_interval
        self.auto_save_enabled = self.auto_save_interval > 0
        
        # 統計情報
        self.success_count = 0
        self.error_count = 0
        self.skip_count = 0
        self.current_batch = 0
        self.total_batches = 0
        
        # バックグラウンドプロセス
        self.auto_save_thread = None
        self.timeout_watcher_thread = None
        self.stop_background_threads = False
        
        # ロギング設定
        self._setup_logging()
        
        # ディレクトリ作成
        Path('results/logs').mkdir(parents=True, exist_ok=True)
        Path('results/reports').mkdir(parents=True, exist_ok=True)
    
    def _setup_logging(self):
        """ロギングの設定"""
        log_level = logging.WARNING if self.quiet else (logging.DEBUG if self.verbose else logging.INFO)
        log_format = '%(asctime)s - %(levelname)s - %(message)s' if self.verbose else '%(message)s'
        
        log_file = f'results/logs/dental_reviews_local_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
        
        logging.basicConfig(
            level=log_level,
            format=log_format,
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler(log_file, encoding='utf-8')
            ],
            force=True
        )
    
    def validate_environment(self):
        """環境の検証"""
        logger.info("🔍 環境検証中...")
        
        # APIトークンの確認
        if not self.brightdata_token:
            logger.error("❌ BRIGHTDATA_API_TOKEN が設定されていません")
            logger.info("   環境変数 BRIGHTDATA_API_TOKEN を設定するか、--token オプションで指定してください")
            if not self.dry_run:
                sys.exit(1)
        logger.info("✅ APIトークン: 設定済み")
        
        # 入力CSVファイルの確認
        if not Path(self.input_csv).exists():
            logger.error(f"❌ 入力CSVファイルが見つかりません: {self.input_csv}")
            sys.exit(1)
        logger.info(f"✅ 入力CSV: {self.input_csv}")
        
        # 行数確認
        with open(self.input_csv, 'r', encoding='utf-8') as f:
            total_rows = sum(1 for _ in f)
        logger.info(f"✅ 総行数: {total_rows}行（ヘッダー含む）")
        self.total_rows = total_rows - 1  # ヘッダー除く
        
        # Pythonスクリプトの確認
        if not Path('get_reviews_from_dental_new.py').exists():
            logger.error("❌ get_reviews_from_dental_new.py が見つかりません")
            sys.exit(1)
        logger.info("✅ スクリプト: get_reviews_from_dental_new.py")
        
        logger.info("✅ 環境検証完了 - 処理を開始します\n")
    
    def setup_environment_variables(self, batch_num, start_row, end_row):
        """環境変数の設定"""
        update_csv = f"results/dental_new_reviews_batch_{batch_num}.csv"
        
        env_vars = {
            'BRIGHTDATA_API_TOKEN': self.brightdata_token,
            'ZONE_NAME': self.zone_name,
            'INPUT_CSV': self.input_csv,
            'OUTPUT_CSV': self.output_csv,
            'UPDATE_CSV': update_csv,
            'START_ROW': str(start_row),
            'END_ROW': str(end_row),
            'BATCH_SIZE': str(self.api_batch_size),
            'DAYS_BACK': str(self.days_back),
            'MAX_WAIT_MINUTES': str(self.max_wait_minutes),
            'BRIGHTDATA_DATASET_ID': self.dataset_id,
            'SKIP_COLUMN': self.skip_column,
        }
        
        for key, value in env_vars.items():
            os.environ[key] = value
        
        return update_csv
    
    def auto_save_worker(self):
        """定期自動保存のワーカースレッド"""
        save_count = 0
        while not self.stop_background_threads:
            time.sleep(self.auto_save_interval)
            
            if self.stop_background_threads:
                break
            
            save_count += 1
            logger.info("\n" + "="*60)
            logger.info(f"💾 定期自動保存 #{save_count} ({self.auto_save_interval}秒ごと)")
            logger.info("="*60)
            
            # 出力ファイルが存在する場合
            if Path(self.output_csv).exists():
                logger.info(f"✅ 出力ファイル確認: {self.output_csv}")
                logger.info(f"📊 現在のバッチ: {self.current_batch}/{self.total_batches}")
            else:
                logger.info(f"⚠️ 出力ファイルがまだ作成されていません")
            
            logger.info("="*60 + "\n")
    
    def timeout_watcher_worker(self):
        """タイムアウト監視のワーカースレッド"""
        if self.timeout <= 0:
            return
        
        # タイムアウトの5分前に警告
        warning_time = max(self.timeout - 300, 0)
        time.sleep(warning_time)
        
        if not self.stop_background_threads:
            logger.warning("\n" + "⏰"*20)
            logger.warning("⚠️  タイムアウト5分前に達しました - 次のバッチ後に強制終了します")
            logger.warning("⏰"*20 + "\n")
            Path('/tmp/workflow_timeout_warning').touch()
    
    def run_batch(self, batch_num, start_row, end_row):
        """バッチ処理の実行"""
        logger.info("="*60)
        logger.info(f"🚀 バッチ {batch_num}/{self.total_batches} 開始")
        logger.info(f"   範囲: 行{start_row}～{end_row}")
        logger.info("="*60)
        
        # 環境変数設定
        update_csv = self.setup_environment_variables(batch_num, start_row, end_row)
        
        logger.info(f"🔍 スキップ判定列: [{self.skip_column}]")
        
        # リトライループ
        batch_success = False
        for retry_count in range(self.retry + 1):
            if retry_count > 0:
                logger.info(f"🔄 リトライ {retry_count}/{self.retry}")
            
            try:
                # Pythonスクリプトを実行
                log_file = f'results/logs/batch_{batch_num}.log'
                with open(log_file, 'w', encoding='utf-8') as log_f:
                    result = subprocess.run(
                        [sys.executable, 'get_reviews_from_dental_new.py'],
                        stdout=log_f,
                        stderr=subprocess.STDOUT,
                        timeout=self.max_wait_minutes * 60 if self.max_wait_minutes > 0 else None
                    )
                
                if result.returncode == 0:
                    batch_success = True
                    logger.info(f"✅ バッチ {batch_num} 完了")
                    break
                else:
                    logger.error(f"❌ バッチ {batch_num} でエラー発生 (終了コード: {result.returncode})")
                    
                    if retry_count < self.retry:
                        wait_retry = 30 * (retry_count + 1)
                        logger.info(f"⏳ {wait_retry}秒後にリトライ...")
                        time.sleep(wait_retry)
            
            except subprocess.TimeoutExpired:
                logger.error(f"⏱️ バッチ {batch_num} タイムアウト ({self.max_wait_minutes}分)")
                if retry_count < self.retry:
                    wait_retry = 30 * (retry_count + 1)
                    logger.info(f"⏳ {wait_retry}秒後にリトライ...")
                    time.sleep(wait_retry)
            
            except Exception as e:
                logger.error(f"❌ バッチ {batch_num} 実行エラー: {e}")
                if retry_count < self.retry:
                    wait_retry = 30 * (retry_count + 1)
                    logger.info(f"⏳ {wait_retry}秒後にリトライ...")
                    time.sleep(wait_retry)
        
        return batch_success
    
    def run_sequential_batches(self):
        """バッチ処理のシーケンシャル実行"""
        # 総バッチ数の計算
        self.total_batches = (self.total_rows + self.csv_batch_size - 1) // self.csv_batch_size
        
        logger.info("\n" + "="*70)
        logger.info("📊 処理概要（GitHub Actions互換設定）:")
        logger.info("="*70)
        logger.info(f"  - 総行数: {self.total_rows}")
        logger.info(f"  - CSVバッチサイズ: {self.csv_batch_size}行 [GitHub: CSV_BATCH_SIZE]")
        logger.info(f"  - 総バッチ数: {self.total_batches}")
        logger.info(f"  - バッチ間待機: {self.wait_time}秒 [GitHub: WAIT_TIME]")
        logger.info(f"  - 開始バッチ: {self.start_from_batch} [GitHub: START_BATCH]")
        logger.info(f"  - Dataset ID: {self.dataset_id}")
        logger.info(f"  - API Batch Size: {self.api_batch_size}件/回 [GitHub: API_BATCH_SIZE]")
        logger.info(f"  - API待機時間: {self.max_wait_minutes}分 [GitHub: MAX_WAIT_MINUTES]")
        logger.info(f"  - Days back: {self.days_back}")
        logger.info(f"  - Skip column: {self.skip_column}")
        logger.info(f"  - リトライ回数: {self.retry}")
        if self.auto_save_enabled:
            logger.info(f"  - 💾 定期自動保存: 有効（{self.auto_save_interval}秒間隔）")
        if self.timeout > 0:
            logger.info(f"  - ⏰ タイムアウト監視: 有効（{self.timeout}秒）")
        logger.info("="*70 + "\n")
        
        if self.dry_run:
            logger.info("🧪 ドライランモード: 実際の実行はスキップします")
            return
        
        # バックグラウンドスレッドの起動
        if self.auto_save_enabled:
            self.auto_save_thread = threading.Thread(target=self.auto_save_worker, daemon=True)
            self.auto_save_thread.start()
            logger.info(f"💾 定期自動保存を開始しました（{self.auto_save_interval}秒間隔）\n")
        
        if self.timeout > 0:
            self.timeout_watcher_thread = threading.Thread(target=self.timeout_watcher_worker, daemon=True)
            self.timeout_watcher_thread.start()
            logger.info(f"⏰ タイムアウト監視を開始しました（{self.timeout}秒）\n")
        
        # バッチループ
        for batch in range(self.start_from_batch, self.total_batches + 1):
            self.current_batch = batch
            
            start_row = (batch - 1) * self.csv_batch_size + 1
            end_row = min(batch * self.csv_batch_size, self.total_rows)
            
            # バッチ実行
            batch_success = self.run_batch(batch, start_row, end_row)
            
            if batch_success:
                self.success_count += 1
            else:
                self.error_count += 1
                logger.error(f"❌ バッチ {batch} でエラー発生（{self.retry} 回リトライ後）")
                
                # エラーが連続3回以上なら処理を中断
                if self.error_count >= 3 and self.success_count == 0:
                    logger.error("❌ 連続エラーが多すぎます。処理を中断します。")
                    break
            
            # タイムアウト警告チェック
            if Path('/tmp/workflow_timeout_warning').exists():
                logger.warning("\n" + "⏰"*20)
                logger.warning("⚠️  タイムアウト警告検出 - 処理を安全に終了します")
                logger.warning("⏰"*20)
                logger.info(f"📊 処理済みバッチ: {batch}/{self.total_batches}")
                logger.info(f"💾 次回は --start-from-batch {batch + 1} で再開してください")
                break
            
            # 最後のバッチでなければ待機
            if batch < self.total_batches:
                logger.info(f"⏳ {self.wait_time}秒待機中（API制限対策）...\n")
                time.sleep(self.wait_time)
        
        # バックグラウンドスレッドの停止
        self.stop_background_threads = True
        if self.auto_save_thread:
            logger.info("✅ 定期自動保存を停止しました")
        if self.timeout_watcher_thread:
            logger.info("✅ タイムアウト監視を停止しました")
    
    def merge_to_all_regions(self):
        """全地域ファイルへのマージ"""
        if not self.merge_to_all:
            return
        
        logger.info("\n" + "="*60)
        logger.info("🔄 全地域ファイルへのマージ処理")
        logger.info("="*60)
        
        logger.info(f"地域別ファイル: {self.output_csv}")
        logger.info(f"統合先ファイル: {self.all_regions_file}")
        
        if not Path(self.output_csv).exists():
            logger.warning(f"⚠️ 地域別ファイルが見つかりません: {self.output_csv}")
            return
        
        # マージ処理
        import csv
        from collections import OrderedDict
        
        # 既存の全地域ファイルを読み込み
        existing_reviews = OrderedDict()
        if Path(self.all_regions_file).exists():
            with open(self.all_regions_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                fieldnames = reader.fieldnames
                for row in reader:
                    gid = row.get('レビューGID', '')
                    if gid:
                        existing_reviews[gid] = row
            logger.info(f"📊 既存レビュー: {len(existing_reviews)}件")
        else:
            fieldnames = None
        
        # 新しい地域別ファイルを読み込んでマージ
        new_count = 0
        update_count = 0
        with open(self.output_csv, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            if fieldnames is None:
                fieldnames = reader.fieldnames
            
            for row in reader:
                gid = row.get('レビューGID', '')
                if gid:
                    if gid in existing_reviews:
                        existing_reviews[gid] = row
                        update_count += 1
                    else:
                        existing_reviews[gid] = row
                        new_count += 1
        
        logger.info(f"✅ 新規追加: {new_count}件")
        logger.info(f"🔄 更新: {update_count}件")
        
        # マージ結果を書き込み
        Path(self.all_regions_file).parent.mkdir(parents=True, exist_ok=True)
        with open(self.all_regions_file, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(existing_reviews.values())
        
        total = len(existing_reviews)
        logger.info(f"📄 統合後の総レビュー数: {total}件")
        logger.info(f"💾 保存先: {self.all_regions_file}")
        logger.info("="*60)
    
    def generate_review_report(self):
        """レビューレポートの生成"""
        if not self.generate_report:
            return
        
        logger.info("\n" + "="*60)
        logger.info("📊 レビューレポート自動生成")
        logger.info("="*60)
        
        if not Path('generate_review_report.py').exists():
            logger.warning("⚠️ generate_review_report.py が見つかりません - レポート生成をスキップします")
            return
        
        if not Path(self.output_csv).exists():
            logger.warning(f"⚠️ レビューファイルが見つかりません: {self.output_csv}")
            return
        
        # レポート生成コマンド
        cmd = [
            sys.executable,
            'generate_review_report.py',
            '--reviews', self.output_csv,
            '--facilities', self.input_csv
        ]
        
        if self.report_days:
            cmd.extend(['--days', str(self.report_days)])
            logger.info(f"期間: 過去{self.report_days}日間")
        else:
            logger.info("期間: 全期間")
        
        try:
            subprocess.run(cmd, check=True)
            logger.info("✅ レポート生成完了")
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ レポート生成エラー: {e}")
        
        logger.info("="*60)
    
    def show_summary(self):
        """最終サマリーの表示"""
        logger.info("\n" + "="*60)
        logger.info("📊 処理完了サマリー")
        logger.info("="*60)
        logger.info(f"✅ 成功バッチ: {self.success_count}/{self.total_batches}")
        logger.info(f"❌ エラーバッチ: {self.error_count}/{self.total_batches}")
        logger.info(f"📝 スキップバッチ: {self.skip_count}/{self.total_batches}")
        
        # 成功率
        if self.total_batches > 0:
            success_rate = self.success_count * 100 // self.total_batches
            logger.info(f"📊 成功率: {success_rate}%")
        
        # 出力ファイルの確認
        if Path(self.output_csv).exists():
            with open(self.output_csv, 'r', encoding='utf-8') as f:
                output_lines = sum(1 for _ in f)
            output_reviews = output_lines - 1
            logger.info(f"📄 出力レビュー数: {output_reviews}件")
            logger.info(f"📁 出力ファイル: {self.output_csv}")
        
        logger.info("="*60)
    
    def run(self):
        """メイン実行"""
        try:
            # 環境検証
            self.validate_environment()
            
            # バッチ処理実行
            self.run_sequential_batches()
            
            # 全地域へのマージ
            if not self.dry_run:
                self.merge_to_all_regions()
            
            # レポート生成
            if not self.dry_run:
                self.generate_review_report()
            
            # サマリー表示
            self.show_summary()
            
            logger.info("\n🎉 すべての処理が完了しました")
            return 0
        
        except KeyboardInterrupt:
            logger.warning("\n⚠️ ユーザーによって中断されました")
            self.stop_background_threads = True
            return 130
        
        except Exception as e:
            logger.error(f"\n❌ 予期しないエラー: {e}", exc_info=True)
            self.stop_background_threads = True
            return 1


def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(
        description='Dental Reviews Sequential Batch Processor - ローカル実行版（GitHub Actions互換）',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
★ GitHub Actionsと同じデフォルト設定:
  --csv-batch-size 500      (GitHub: CSV_BATCH_SIZE=500)
  --wait-time 120           (GitHub: WAIT_TIME=120)
  --api-batch-size 50       (GitHub: API_BATCH_SIZE=50)
  --max-wait-minutes 90     (GitHub: MAX_WAIT_MINUTES=90)
  --start-from-batch 1      (GitHub: START_BATCH=1)

使用例（すべて1行で実行）:
  # 基本的な実行
  python run_dental_reviews_sequential.py --input results/dental_new_hokkaido.csv --output results/dental_new_reviews_hokkaido.csv --token YOUR_TOKEN
  
  # 開始バッチを指定（バッチ5から再開）
  python run_dental_reviews_sequential.py --input results/dental_new.csv --output results/dental_new_reviews.csv --token YOUR_TOKEN --start-from-batch 5
  
  # バッチサイズと待機時間をカスタマイズ
  python run_dental_reviews_sequential.py --input results/dental_new.csv --output results/dental_new_reviews.csv --token YOUR_TOKEN --csv-batch-size 300 --wait-time 60
  
  # リトライ付き実行（推奨）
  python run_dental_reviews_sequential.py --input results/dental_new_hokkaido.csv --output results/dental_new_reviews_hokkaido.csv --token YOUR_TOKEN --retry 3 --verbose
  
  # 全機能版
  python run_dental_reviews_sequential.py --input results/dental_new.csv --output results/dental_new_reviews.csv --token YOUR_TOKEN --retry 3 --merge-to-all --generate-report

短縮オプション:
  python run_dental_reviews_sequential.py -i results/dental_new.csv -o results/dental_new_reviews.csv -t YOUR_TOKEN -r 3 -v
        '''
    )
    
    # 必須引数
    parser.add_argument(
        '--input', '-i',
        type=str,
        required=False,
        help='入力CSVファイル (例: results/dental_new_hokkaido.csv)'
    )
    
    parser.add_argument(
        '--output', '-o',
        type=str,
        required=False,
        help='出力CSVファイル (例: results/dental_new_reviews_hokkaido.csv)'
    )
    
    # 設定ファイルオプション（今後の拡張用）
    parser.add_argument(
        '--settings', '-s',
        type=str,
        default=None,
        help='設定JSONファイル（今後の拡張用）'
    )
    
    # APIキー
    parser.add_argument(
        '--token', '-t',
        type=str,
        default=None,
        help='BrightData APIトークン (環境変数 BRIGHTDATA_API_TOKEN でも指定可能)'
    )
    
    parser.add_argument(
        '--zone',
        type=str,
        default='serp_api1',
        help='BrightData ゾーン名 (デフォルト: serp_api1)'
    )
    
    # バッチ処理設定（GitHub Actions互換）
    parser.add_argument(
        '--csv-batch-size',
        type=int,
        default=500,
        help='CSVバッチサイズ（何行ずつ処理するか） [GitHub: CSV_BATCH_SIZE=500] (デフォルト: 500行)'
    )
    
    parser.add_argument(
        '--wait-time',
        type=int,
        default=120,
        help='バッチ間の待機時間（秒）API制限対策 [GitHub: WAIT_TIME=120] (デフォルト: 120秒)'
    )
    
    parser.add_argument(
        '--api-batch-size',
        type=int,
        default=50,
        help='API呼び出しのバッチサイズ（何件ずつAPIリクエストするか） [GitHub: API_BATCH_SIZE=50] (デフォルト: 50件/回)'
    )
    
    parser.add_argument(
        '--max-wait-minutes',
        type=int,
        default=90,
        help='API待機時間の最大値（分）タイムアウト対策 [GitHub: MAX_WAIT_MINUTES=90] (デフォルト: 90分)'
    )
    
    parser.add_argument(
        '--dataset-id',
        type=str,
        default='gd_luzfs1dn2oa0teb81',
        help='BrightData Dataset ID [GitHub: DATASET_ID=gd_luzfs1dn2oa0teb81] (デフォルト: gd_luzfs1dn2oa0teb81)'
    )
    
    parser.add_argument(
        '--days-back',
        type=int,
        default=10,
        help='何日前までのレビューを取得するか [GitHub: DAYS_BACK] (デフォルト: 10日)'
    )
    
    parser.add_argument(
        '--skip-column',
        type=str,
        default='web',
        help='スキップ判定に使う列名（この列が空の行は処理しない） [GitHub: SKIP_COLUMN] (デフォルト: web)'
    )
    
    parser.add_argument(
        '--start-from-batch',
        type=int,
        default=1,
        help='開始するバッチ番号（再開用・途中から実行する場合に指定） [GitHub: START_BATCH] (デフォルト: 1)'
    )
    
    # リトライとタイムアウト
    parser.add_argument(
        '--retry', '-r',
        type=int,
        default=3,
        help='バッチ失敗時のリトライ回数 (デフォルト: 3)'
    )
    
    parser.add_argument(
        '--timeout',
        type=int,
        default=0,
        help='全体のタイムアウト時間（秒、0=無制限） (デフォルト: 0)'
    )
    
    parser.add_argument(
        '--max-workers',
        '-w',
        type=int,
        default=1,
        help='並列ワーカー数（将来の拡張用、現在は1のみ） (デフォルト: 1)'
    )
    
    # マージとレポート
    parser.add_argument(
        '--merge-to-all',
        action='store_true',
        help='完了後に全地域ファイルにマージする'
    )
    
    parser.add_argument(
        '--all-regions-file',
        type=str,
        default='results/dental_new_reviews_all_regions.csv',
        help='全地域ファイルのパス (デフォルト: results/dental_new_reviews_all_regions.csv)'
    )
    
    parser.add_argument(
        '--generate-report',
        action='store_true',
        help='完了後にレビュー増減レポートを生成する'
    )
    
    parser.add_argument(
        '--report-days',
        type=int,
        default=None,
        help='レポート分析期間（日数、空欄=全期間）'
    )
    
    # 自動保存
    parser.add_argument(
        '--auto-save-interval',
        type=int,
        default=1800,
        help='定期自動保存の間隔（秒、0=無効） (デフォルト: 1800秒=30分)'
    )
    
    # その他
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='詳細ログを出力'
    )
    
    parser.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='最小限のログのみ出力'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='ドライラン: 設定の検証のみ行い、実際の実行はしない'
    )
    
    args = parser.parse_args()
    
    # 設定ファイルからの読み込み（今後の拡張用）
    if args.settings:
        if not Path(args.settings).exists():
            print(f"❌ 設定ファイルが見つかりません: {args.settings}")
            sys.exit(1)
        
        with open(args.settings, 'r', encoding='utf-8') as f:
            settings = json.load(f)
        
        # 設定ファイルから値を読み込み（コマンドライン引数で上書き可能）
        if not args.input and 'input_csv' in settings:
            args.input = settings['input_csv']
        if not args.output and 'output_csv' in settings:
            args.output = settings['output_csv']
        # 他の設定も同様に読み込み可能
    
    # 必須引数のチェック
    if not args.input or not args.output:
        parser.error("--input と --output は必須です（または --settings で指定してください）")
    
    # 実行
    runner = DentalReviewsSequentialRunner(args)
    exit_code = runner.run()
    sys.exit(exit_code)


if __name__ == '__main__':
    main()
