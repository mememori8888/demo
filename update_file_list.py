import glob
import json
import os
import re


SEQUENTIAL_EXCLUDED_KEYWORDS = {
    'review',
    'batch',
    'report',
    'fid',
    'heatmap',
    'duplicate',
    'analysis',
    'log',
    'error',
    'summary',
}

FACILITY_EXCLUDED_KEYWORDS = {
    'review',
    'batch',
    'report',
    'fid',
    'heatmap',
    'duplicate',
    'analysis',
    'log',
    'error',
    'summary',
    'add_',
}


def _get_extension(filename):
    return os.path.splitext(filename)[1].lower()


def classify_settings_file(filename):
    lower_name = filename.lower()
    ext = _get_extension(filename)
    purposes = []

    if ext == '.csv':
        purposes.append('settings_csv')
        if 'address' in lower_name or 'adress' in lower_name:
            purposes.append('address_input')
        if 'exclude' in lower_name:
            purposes.append('exclude_gids')
    elif ext == '.json':
        purposes.append('settings_json')
        if 'settings' in lower_name:
            purposes.append('config')

    return {
        'name': filename,
        'path': f'settings/{filename}',
        'extension': ext,
        'purposes': purposes,
    }


def classify_results_file(filename, size=0, mtime=0):
    lower_name = filename.lower()
    ext = _get_extension(filename)
    purposes = ['results_csv'] if ext == '.csv' else []

    if 'review' in lower_name:
        purposes.append('review_output')
    if 'fid' in lower_name or 'add_data' in lower_name:
        purposes.append('fid_input')
    if 'add_data' in lower_name:
        purposes.append('update_facility_output')
    if 'add_review' in lower_name:
        purposes.append('update_review_output')

    if ext == '.csv' and not any(keyword in lower_name for keyword in SEQUENTIAL_EXCLUDED_KEYWORDS):
        purposes.append('sequential_input')

    if ext == '.csv' and not any(keyword in lower_name for keyword in FACILITY_EXCLUDED_KEYWORDS):
        purposes.append('facility_output')

    return {
        'name': filename,
        'path': f'results/{filename}',
        'extension': ext,
        'purposes': sorted(set(purposes)),
        'size': size,
        'last_modified': mtime,
    }

def _detect_data_root():
    """
    データルートを検出する（フェイルセーフ設計）
    優先順位: PRIVATE_DATA_ROOT env > private-data/ > /workspaces/googlemap > カレントディレクトリ
    """
    import sys
    from pathlib import Path

    env_root = os.environ.get('PRIVATE_DATA_ROOT', '').strip()
    if env_root:
        p = Path(env_root)
        if p.exists() and (p / 'settings').exists():
            return str(p)
        print(f"⚠️  PRIVATE_DATA_ROOT='{env_root}' に settings/ が見つかりません", file=sys.stderr)

    for candidate in ['private-data', '/workspaces/googlemap']:
        p = Path(candidate)
        if p.exists() and (p / 'settings').exists():
            return str(p)

    # カレントディレクトリにフォールバック
    return '.'


def update_file_list():
    """
    resultsディレクトリ内のファイル一覧を更新し、webapp/files.jsonに保存する
    さらに、GitHub Actionsワークフローファイルの選択肢も自動更新する
    データはプライベートリポジトリ (PRIVATE_DATA_ROOT) から読み込む
    """
    data_root = _detect_data_root()
    results_dir = os.path.join(data_root, 'results')
    settings_dir = os.path.join(data_root, 'settings')
    output_file = 'docs/webapp/files.json'
    print(f"📁 データルート: {data_root}")
    workflow_file = '.github/workflows/brightdata_facility.yml'
    
    print(f"Updating file list from {results_dir} and {settings_dir} to {output_file}")
    
    # settingsディレクトリのCSVファイルを取得
    settings_csv_files = []
    settings_entries = []
    if os.path.exists(settings_dir):
        for file_path in glob.glob(os.path.join(settings_dir, '*.csv')):
            filename = os.path.basename(file_path)
            settings_csv_files.append(filename)
            settings_entries.append(classify_settings_file(filename))
    settings_csv_files.sort()
    
    # settingsディレクトリのJSONファイルを取得
    settings_json_files = []
    if os.path.exists(settings_dir):
        for file_path in glob.glob(os.path.join(settings_dir, '*.json')):
            filename = os.path.basename(file_path)
            settings_json_files.append(filename)
            settings_entries.append(classify_settings_file(filename))
    settings_json_files.sort()
    settings_entries.sort(key=lambda entry: entry['name'])
    
    # resultsディレクトリのCSVファイルを取得
    results_files = []
    if os.path.exists(results_dir):
        for file_path in glob.glob(os.path.join(results_dir, '*.csv')):
            filename = os.path.basename(file_path)
            size = os.path.getsize(file_path)
            mtime = os.path.getmtime(file_path)
            
            results_files.append(classify_results_file(filename, size=size, mtime=mtime))
    
    # 更新日時順にソート
    results_files.sort(key=lambda x: x['last_modified'], reverse=True)
    results_filenames = [f['name'] for f in results_files]
    
    # ディレクトリ作成
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    # files.jsonを保存
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                'settings': settings_entries,
                'results': results_files,
                'generated_by': 'update_file_list.py',
            }, f, indent=2, ensure_ascii=False)
        print(f"✅ File list saved to {output_file}")
        print(f"   - Settings CSV files: {len(settings_csv_files)}")
        print(f"   - Settings JSON files: {len(settings_json_files)}")
        print(f"   - Results files: {len(results_filenames)}")
    except Exception as e:
        print(f"❌ Error saving file list: {e}")
        return False
    
    # ワークフローファイルを更新
    should_update_workflow = os.getenv('UPDATE_WORKFLOW_CHOICES', '').lower() in {'1', 'true', 'yes'}

    if should_update_workflow and os.path.exists(workflow_file):
        print(f"\n📝 Updating workflow file: {workflow_file}")
        update_workflow_choices(workflow_file, settings_csv_files, settings_json_files, results_filenames)
    elif should_update_workflow:
        print(f"⚠️  Workflow file not found: {workflow_file}")
    else:
        print("ℹ️  Workflow choice update skipped")
    
    return True

def update_workflow_choices(workflow_file, settings_csv_files, settings_json_files, results_files):
    """
    ワークフローファイルの選択肢を自動更新する
    """
    try:
        with open(workflow_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # config_file の選択肢を更新
        config_options = "          - 'settings/settings.json'"
        for filename in settings_json_files:
            if filename != 'settings.json':  # デフォルトは最初に追加済み
                config_options += f"\n          - 'settings/{filename}'"
        config_options += "\n"
        
        # config_file セクションを置換
        config_pattern = r"(      config_file:[\s\S]*?options:\n)([\s\S]*?)(        default: 'settings/)"
        config_replacement = r"\1" + config_options + r"\3"
        content = re.sub(config_pattern, config_replacement, content)
        
        # address_csv の選択肢を更新
        address_options = "          - 'default'\n"
        for filename in settings_csv_files:
            address_options += f"          - 'settings/{filename}'\n"
        
        # address_csv セクションを置換
        address_pattern = r"(      address_csv:[\s\S]*?options:\n)([\s\S]*?)(        default: 'default')"
        address_replacement = r"\1" + address_options + r"\3"
        content = re.sub(address_pattern, address_replacement, content)
        
        # output_file の説明文を更新（既存ファイルリストを表示）
        output_description = "'出力ファイル名（既存ファイル選択または新規ファイル名入力）"
        if results_files:
            output_description += "\n\n          既存ファイル: " + ", ".join(results_files[:10])
            if len(results_files) > 10:
                output_description += f" ...他{len(results_files)-10}件"
        output_description += "'"
        
        # output_file の description を置換
        output_desc_pattern = r"(      output_file:\n        description: )['\"].*?['\"]"
        output_desc_replacement = r"\1" + output_description
        content = re.sub(output_desc_pattern, output_desc_replacement, content, flags=re.DOTALL)
        
        # ファイルに書き込み
        with open(workflow_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"✅ Workflow file updated successfully")
        print(f"   - Config file options: {len(settings_json_files)}")
        print(f"   - Address CSV options: {len(settings_csv_files)}")
        print(f"   - Output file description updated with {len(results_files)} files")
        
    except Exception as e:
        print(f"❌ Error updating workflow file: {e}")
        return False
    
    return True

if __name__ == "__main__":
    success = update_file_list()
    exit(0 if success else 1)
