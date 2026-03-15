#!/usr/bin/env python3
"""
GitHub Actions用の設定ファイル更新スクリプト
環境変数からパラメータを取得し、JSON設定ファイルを更新する
"""
import json
import os
import sys


def load_json_env(env_name):
    raw_value = os.environ.get(env_name)
    if not raw_value or raw_value == 'null':
        return None

    try:
        return json.loads(raw_value)
    except json.JSONDecodeError as exc:
        print(f"❌ Error parsing {env_name}: {exc}")
        sys.exit(1)


def main():
    config_file = os.environ.get('CONFIG_FILE')
    address_csv = os.environ.get('ADDRESS_CSV', 'default')
    output_prefix = os.environ.get('OUTPUT_PREFIX', '')
    custom_settings = load_json_env('CUSTOM_SETTINGS')

    if not config_file:
        print("❌ Error: CONFIG_FILE environment variable is not set")
        sys.exit(1)

    # 設定ファイルを読み込み
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except Exception as e:
        print(f"❌ Error reading config file: {e}")
        sys.exit(1)

    # 配列の場合は最初の要素を編集
    if isinstance(config, list):
        config = config[0]

    if custom_settings is not None:
        if not isinstance(custom_settings, dict):
            print("❌ Error: CUSTOM_SETTINGS must be a JSON object")
            sys.exit(1)

        for key, value in custom_settings.items():
            config[key] = value
            print(f"✏️  {key}: {value}")

    # アドレスファイルの上書き
    if address_csv != 'default':
        config['address_csv_path'] = address_csv
        print(f"✏️  Address CSV: {address_csv}")

    # 出力ファイル名の上書き
    if output_prefix:
        if 'facility_file' in config:
            original = config['facility_file']
            config['facility_file'] = f"results/{output_prefix}.csv"
            print(f"✏️  Facility file: {original} → {config['facility_file']}")
        
        if 'review_file' in config:
            original = config['review_file']
            config['review_file'] = f"results/{output_prefix}_review.csv"
            print(f"✏️  Review file: {original} → {config['review_file']}")
        
        if 'fid_file' in config:
            original = config['fid_file']
            config['fid_file'] = f"results/fid_{output_prefix}.csv"
            print(f"✏️  FID file: {original} → {config['fid_file']}")

    # 設定を配列形式で保存
    try:
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump([config], f, ensure_ascii=False, indent=2)
        print("✅ Configuration updated successfully")
    except Exception as e:
        print(f"❌ Error writing config file: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
