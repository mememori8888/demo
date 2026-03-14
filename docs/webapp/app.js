// GitHubリポジトリ情報
const GITHUB_OWNER = 'mememori8888';
const GITHUB_REPO = 'googlemap';
const GITHUB_BRANCH = 'main';

// グローバル変数
let issueData = {};
let currentWorkflow = '';
let fileCache = {
    settings: [],
    results: []
};

// プリセット設定
const PRESETS = {
    facility_heatmap: {
        'dental_batch': {
            name: '🦷 歯科バッチ実行（2000件）',
            description: '2000住所を処理（約30分）',
            params: {
                heatmap_facility_file: 'results/dental_heatmap_address.csv',
                heatmap_output_file: 'results/dental.csv',
                heatmap_start_line: '1',
                heatmap_process_count: '2000'
            }
        },
        'dental_test': {
            name: '🧪 テスト実行（10件）',
            description: '10住所を処理して動作確認（約5分）',
            params: {
                heatmap_facility_file: 'results/dental_heatmap_address.csv',
                heatmap_output_file: 'results/dental.csv',
                heatmap_start_line: '1',
                heatmap_process_count: '10'
            }
        }
    },
    facility: {
        'dental_full': {
            name: '🦷 歯科医院・全国取得',
            description: '全国の住所から歯科医院を検索（1973行 × 1req = 1973req）',
            params: {
                facility_custom_query: '歯科医院',
                facility_custom_address_csv: 'settings/address.csv',
                facility_custom_facility_file: 'results/dental.csv',
                facility_custom_exclude_gids_path: 'settings/exclude_gids.csv'
            }
        }
    },
    reviews: {
        'dental_full': {
            name: '🦷 歯科レビュー全件取得',
            description: '歯科医院FIDからレビュー全件取得（FID数 × 最大5req）',
            params: {
                fid_file: 'results/fid.csv',
                custom_review_file: 'results/dental_review.csv',
                start_line: '',
                process_count: ''
            }
        },
        'dental_test': {
            name: '🧪 テスト実行（100件）',
            description: '歯科医院レビュー取得テスト（100 × 最大5req = 最大500req）',
            params: {
                fid_file: 'results/fid.csv',
                custom_review_file: 'results/dental_review.csv',
                start_line: '1',
                process_count: '100'
            }
        }
    },
    reviews_auto_batch: {
        'dental_80k': {
            name: '🦷 歯科レビュー・8万件自動分割',
            description: '8万件の施設データを2並列バッチで処理（4.5時間）',
            params: {
                auto_batch_fid_file: 'results/dental_fid.csv',
                auto_batch_review_file: 'results/dental_review.csv',
                auto_batch_size: '10000',
                auto_batch_max_parallel: '2',
                auto_batch_workers: '10'
            }
        },
        'dental_80k_fast': {
            name: '🚀 歯科レビュー・8万件高速',
            description: '8万件を4並列バッチで高速処理（2.2時間）',
            params: {
                auto_batch_fid_file: 'results/dental_fid.csv',
                auto_batch_review_file: 'results/dental_review.csv',
                auto_batch_size: '10000',
                auto_batch_max_parallel: '4',
                auto_batch_workers: '15'
            }
        },
        'test_20k': {
            name: '🧪 テスト2万件',
            description: '2万件のデータでバッチ処理テスト（67分）',
            params: {
                auto_batch_fid_file: 'results/fid.csv',
                auto_batch_review_file: 'results/test_review.csv',
                auto_batch_size: '10000',
                auto_batch_max_parallel: '2',
                auto_batch_workers: '10'
            }
        }
    },
    generate_heatmap: {
        'dental': {
            name: '🦷 歯科ヒートマップ生成',
            description: '歯科施設データからヒートマップCSV作成（API呼び出しなし）',
            params: {
                generate_heatmap_facility_file: 'results/dental.csv'
            }
        }
    }
};

// GitHub APIでファイル一覧を取得
async function fetchGitHubFiles(path) {
    try {
        const url = `https://api.github.com/repos/${GITHUB_OWNER}/${GITHUB_REPO}/contents/${path}?ref=${GITHUB_BRANCH}`;
        const response = await fetch(url);
        if (!response.ok) {
            console.error(`Failed to fetch files from ${path}:`, response.status);
            return [];
        }
        const files = await response.json();
        return files.filter(file => file.type === 'file').map(file => file.name);
    } catch (error) {
        console.error(`Error fetching files from ${path}:`, error);
        return [];
    }
}

// ドロップダウンにオプションを追加
function populateDropdown(selectId, files, pathPrefix = '', allowNew = true) {
    const select = document.getElementById(selectId);
    if (!select) return;
    
    // デフォルトオプション以外をクリア
    while (select.options.length > 1) {
        select.remove(1);
    }
    
    // 新規ファイル作成オプションを追加
    if (allowNew) {
        const newOption = document.createElement('option');
        newOption.value = '__NEW_FILE__';
        newOption.textContent = '📝 新規ファイルを作成';
        select.appendChild(newOption);
    }
    
    // ファイルをオプションとして追加
    files.forEach(filename => {
        const option = document.createElement('option');
        const fullPath = pathPrefix ? `${pathPrefix}/${filename}` : filename;
        option.value = fullPath;
        option.textContent = filename;
        select.appendChild(option);
    });
}

// ファイル一覧を読み込み
async function loadFileOptions() {
    try {
        // 静的JSONファイルから読み込み（GitHub Actionsで生成）
        // キャッシュ回避のためにタイムスタンプを付与
        const response = await fetch('./files.json?t=' + new Date().getTime());
        if (response.ok) {
            const filesData = await response.json();
            fileCache.settings = filesData.settings || [];
            fileCache.results = filesData.results || [];
        } else {
            // フォールバック: GitHub APIから直接取得
            console.log('files.json not found, falling back to GitHub API');
            fileCache.settings = await fetchGitHubFiles('settings');
            fileCache.results = await fetchGitHubFiles('results');
        }
        
        // CSVファイルのみフィルタ
        const settingsCsvFiles = fileCache.settings.filter(f => f.endsWith('.csv'));
        const resultsCsvFiles = fileCache.results.filter(f => f.endsWith('.csv'));
        
        // 住所CSVファイル (settings/*.csv)
        populateDropdown('custom_address_csv', settingsCsvFiles, 'settings');
        
        // 施設ファイル (results/*.csv, 特定ファイル)
        const facilityFiles = resultsCsvFiles.filter(f => 
            f.includes('dental') || f.includes('marige') || f.includes('funeral')
        ).filter(f => !f.includes('review') && !f.includes('add'));
        populateDropdown('custom_facility_file', facilityFiles, 'results');
        
        // レビューファイル (results/*review.csv)
        const reviewFiles = resultsCsvFiles.filter(f => f.includes('review'));
        populateDropdown('custom_review_file', reviewFiles, 'results');
        
        // FIDファイル (results/*fid*.csv または add_data*.csv - FIDを含むファイルまたはadd_dataファイル)
        // resultsフォルダからfidという文字を含むファイル、またはadd_dataを含むファイルを動的に選択肢に表示
        const fidFiles = resultsCsvFiles.filter(f => {
            const lowerName = f.toLowerCase();
            return lowerName.includes('fid') || lowerName.includes('add_data');
        });
        populateDropdown('fid_file', fidFiles, 'results', false);
        
        // 更新施設ファイル (results/*add_data.csv)
        const addDataFiles = resultsCsvFiles.filter(f => f.includes('add_data'));
        populateDropdown('custom_update_facility_path', addDataFiles, 'results');
        
        // 更新レビューファイル (results/*add_review.csv)
        const addReviewFiles = resultsCsvFiles.filter(f => f.includes('add_review'));
        populateDropdown('custom_update_review_path', addReviewFiles, 'results');
        
        // 除外GIDファイル (settings/exclude_gids.csv)
        const excludeFiles = settingsCsvFiles.filter(f => f.includes('exclude'));
        populateDropdown('custom_exclude_gids_path', excludeFiles, 'settings');
        
        // ヒートマップファイル (results/*heatmap*.csv)
        const heatmapFiles = resultsCsvFiles.filter(f => f.includes('heatmap'));
        
        // Reviews workflow用のドロップダウンを設定
        populateDropdown('custom_review_file', reviewFiles, 'results', true);
        
        // Reviews Auto-Batch workflow用のドロップダウンを設定
        populateDropdown('auto_batch_fid_file', fidFiles, 'results', false);
        populateDropdown('auto_batch_review_file', reviewFiles, 'results', true);
        
        // Facility workflow用のドロップダウンを設定
        populateDropdown('facility_custom_address_csv', settingsCsvFiles, 'settings', true);
        // ヒートマップファイルも住所CSVとして選択できるようにする
        heatmapFiles.forEach(filename => {
            const option = document.createElement('option');
            option.value = `results/${filename}`;
            option.textContent = filename;
            document.getElementById('facility_custom_address_csv').appendChild(option);
        });

        populateDropdown('facility_custom_facility_file', facilityFiles, 'results', true);
        populateDropdown('facility_custom_exclude_gids_path', excludeFiles, 'settings', true);
        
        // Generate Heatmap workflow用のドロップダウンを設定
        populateDropdown('generate_heatmap_facility_file', facilityFiles, 'results', true);

        // Facility Heatmap workflow用のドロップダウンを設定
        // 施設ファイル名(入力): heatmapを含まない施設ファイル = 施設情報取得と同じロジック
        populateDropdown('heatmap_facility_file', facilityFiles, 'results', true);
        
        // 出力ファイル名: heatmapが含まれるファイルのみ表示
        const heatmapOnlyFiles = resultsCsvFiles.filter(f => f.includes('heatmap'));
        populateDropdown('heatmap_output_file', heatmapOnlyFiles, 'results', true);
        
        // Extract FID workflow用のドロップダウンを設定
        // すべてのresults/*.csvファイルを選択可能にする
        populateDropdown('extract_fid_input_file', resultsCsvFiles, 'results', false);
        populateDropdown('extract_fid_output_existing', resultsCsvFiles, 'results', false);
        
        console.log('✅ ファイルオプションの読み込み完了');
    } catch (error) {
        console.error('❌ ファイルオプションの読み込みエラー:', error);
    }
}

// プリセット適用
function applyPreset(presetKey) {
    const preset = PRESETS[currentWorkflow]?.[presetKey];
    if (!preset) return;
    
    // 現在のワークフローのすべてのフィールドをリセット
    const currentForm = document.getElementById(`form_${currentWorkflow}`);
    if (currentForm) {
        // すべてのinput/selectをクリア
        currentForm.querySelectorAll('input[type="text"], input[type="number"], textarea').forEach(input => {
            input.value = '';
        });
        currentForm.querySelectorAll('select').forEach(select => {
            select.selectedIndex = 0; // 最初のオプション（通常は「選択してください」）に戻す
        });
    }
    
    // プリセットのパラメータを適用
    console.log('🎯 Applying preset:', presetKey, preset.params);
    Object.entries(preset.params).forEach(([key, value]) => {
        const input = document.getElementById(key);
        console.log(`  Applying ${key} = ${value}, element:`, input);
        
        if (input) {
            // selectの場合
            if (input.tagName === 'SELECT') {
                // 値が空文字の場合は最初のオプションを選択
                if (value === '') {
                    input.selectedIndex = 0;
                    console.log(`    ✅ Set ${key} to first option (empty)`);
                } else {
                    // 指定された値のオプションを探して選択
                    const option = Array.from(input.options).find(opt => opt.value === value);
                    if (option) {
                        input.value = value;
                        console.log(`    ✅ Set ${key} = ${value}`);
                    } else {
                        console.warn(`    ❌ Option not found for ${key}: ${value}. Available:`, Array.from(input.options).map(o => o.value));
                    }
                }
            } else {
                // text/numberの場合はそのまま設定（空文字も含む）
                input.value = value;
                console.log(`    ✅ Set ${key} = ${value}`);
            }
        } else {
            console.warn(`  ❌ Element not found: ${key}`);
        }
    });
    
    alert(`✅ プリセット「${preset.name}」を適用しました`);
}

// プリセット選択UIを生成
function updatePresetOptions() {
    const presetContainer = document.getElementById('preset_container');
    if (!presetContainer) return;
    
    const presets = PRESETS[currentWorkflow];
    if (!presets) {
        presetContainer.style.display = 'none';
        return;
    }
    
    presetContainer.style.display = 'block';
    presetContainer.innerHTML = '<h3>📋 プリセット</h3>';
    
    Object.entries(presets).forEach(([key, preset]) => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'preset-btn';
        btn.innerHTML = `${preset.name}<br><small>${preset.description}</small>`;
        btn.onclick = () => applyPreset(key);
        presetContainer.appendChild(btn);
    });
}

// ワークフロー切り替え
function switchWorkflow() {
    const workflowType = document.getElementById('workflow_type').value;
    currentWorkflow = workflowType;
    
    // すべてのフォームを非表示 & required属性を無効化
    document.querySelectorAll('.workflow-form').forEach(form => {
        form.style.display = 'none';
        // 非表示フォーム内のrequired要素を無効化
        form.querySelectorAll('[required]').forEach(input => {
            input.disabled = true;
        });
    });
    
    // 選択されたフォームを表示 & required属性を有効化
    if (workflowType) {
        const targetForm = document.getElementById(`form_${workflowType}`);
        if (targetForm) {
            targetForm.style.display = 'block';
            // 表示フォーム内のrequired要素を有効化
            targetForm.querySelectorAll('[required]').forEach(input => {
                input.disabled = false;
            });
        }
    }
    
    // プリセットオプションを更新
    updatePresetOptions();
}

// 強化されたバリデーション
function validateFormEnhanced() {
    const errors = [];
    
    if (currentWorkflow === 'facility_heatmap') {
        const startIndex = parseInt(document.getElementById('heatmap_start_index')?.value || '0');
        const batchSize = parseInt(document.getElementById('heatmap_batch_size')?.value || '2000');
        const maxWorkers = parseInt(document.getElementById('heatmap_max_workers')?.value || '8');
        
        if (startIndex < 0) errors.push('開始インデックスは0以上を指定してください');
        if (batchSize < 1 || batchSize > 50000) errors.push('バッチサイズは1〜50000の範囲で指定してください');
        if (maxWorkers < 1 || maxWorkers > 16) errors.push('並列数は1〜16の範囲で指定してください');
        
        // 推定時間を表示
        const estimatedMinutes = Math.ceil(batchSize / (maxWorkers * 10));
        if (estimatedMinutes > 300) {
            errors.push(`⚠️ 推定時間: 約${estimatedMinutes}分 (5時間以上) - タイムアウトの可能性があります`);
        }
    }
    
    if (currentWorkflow === 'reviews') {
        const startLine = parseInt(document.getElementById('start_line')?.value || '0');
        const processCount = parseInt(document.getElementById('process_count')?.value || '0');
        
        if (startLine < 0) errors.push('開始行は0以上を指定してください');
        if (processCount < 0) errors.push('処理件数は0以上を指定してください');
    }
    
    if (errors.length > 0) {
        alert('❌ 入力エラー:\n\n' + errors.join('\n'));
        return false;
    }
    
    return true;
}

// フォーム送信処理
document.getElementById('jobForm').addEventListener('submit', function(e) {
    e.preventDefault();
    
    // ワークフローが選択されているか確認
    if (!currentWorkflow) {
        alert('⚠️ ワークフローを選択してください');
        return;
    }
    
    // バリデーション
    if (!validateForm() || !validateFormEnhanced()) {
        return;
    }
    
    // フォームデータを取得
    const formData = getFormData();
    
    // Issue本文を生成
    const issueBody = generateIssueBody(formData);
    
    // プレビューを表示
    showPreview(issueBody, formData);
});

// フォームデータ取得
function getFormData() {
    const data = { workflow: currentWorkflow };
    
    switch (currentWorkflow) {
        case 'reviews':
            const customSettings = {};
            const customReviewFile = document.getElementById('custom_review_file')?.value;
            const customReviewFileNew = document.getElementById('custom_review_file_new')?.value.trim();
            
            if (customReviewFile === '__NEW_FILE__' && customReviewFileNew) {
                // 新規ファイル作成: results/ パスを付ける
                customSettings.review_file = customReviewFileNew.startsWith('results/') 
                    ? customReviewFileNew 
                    : `results/${customReviewFileNew}`;
            } else if (customReviewFile && customReviewFile !== '__NEW_FILE__') {
                customSettings.review_file = customReviewFile;
            }
            
            data.config_file = 'settings/settings.json'; // 固定値
            data.fid_file = document.getElementById('fid_file').value;
            data.start_line = document.getElementById('start_line').value.trim();
            data.process_count = document.getElementById('process_count').value.trim();
            data.workers = document.getElementById('reviews_workers').value;
            data.custom_settings = Object.keys(customSettings).length > 0 ? customSettings : null;
            break;
            
        case 'reviews_auto_batch':
            data.config_file = 'settings/settings.json'; // 固定値
            data.fid_file = document.getElementById('auto_batch_fid_file').value;
            data.review_file = document.getElementById('auto_batch_review_file').value;
            data.batch_size = document.getElementById('auto_batch_size').value;
            data.max_parallel_jobs = document.getElementById('auto_batch_max_parallel').value;
            data.workers = document.getElementById('auto_batch_workers').value;
            break;
            
        case 'facility':
            const facilityCustomSettings = {};
            const facilityCustomQuery = document.getElementById('facility_custom_query')?.value.trim();
            const facilityCustomAddressCsv = document.getElementById('facility_custom_address_csv')?.value;
            const facilityCustomAddressCsvNew = document.getElementById('facility_custom_address_csv_new')?.value.trim();
            const facilityCustomFacilityFile = document.getElementById('facility_custom_facility_file')?.value;
            const facilityCustomFacilityFileNew = document.getElementById('facility_custom_facility_file_new')?.value.trim();
            const facilityCustomExcludeGidsPath = document.getElementById('facility_custom_exclude_gids_path')?.value;
            const facilityCustomExcludeGidsPathNew = document.getElementById('facility_custom_exclude_gids_path_new')?.value.trim();
            
            if (facilityCustomQuery) facilityCustomSettings.query = facilityCustomQuery;
            
            if (facilityCustomAddressCsv === '__NEW_FILE__' && facilityCustomAddressCsvNew) {
                facilityCustomSettings.address_csv_path = facilityCustomAddressCsvNew.startsWith('settings/') 
                    ? facilityCustomAddressCsvNew 
                    : `settings/${facilityCustomAddressCsvNew}`;
            } else if (facilityCustomAddressCsv && facilityCustomAddressCsv !== '__NEW_FILE__') {
                facilityCustomSettings.address_csv_path = facilityCustomAddressCsv;
            }
            
            if (facilityCustomFacilityFile === '__NEW_FILE__' && facilityCustomFacilityFileNew) {
                facilityCustomSettings.facility_file = facilityCustomFacilityFileNew.startsWith('results/') 
                    ? facilityCustomFacilityFileNew 
                    : `results/${facilityCustomFacilityFileNew}`;
            } else if (facilityCustomFacilityFile && facilityCustomFacilityFile !== '__NEW_FILE__') {
                facilityCustomSettings.facility_file = facilityCustomFacilityFile;
            }
            
            if (facilityCustomExcludeGidsPath === '__NEW_FILE__' && facilityCustomExcludeGidsPathNew) {
                facilityCustomSettings.exclude_gids_path = facilityCustomExcludeGidsPathNew.startsWith('settings/') 
                    ? facilityCustomExcludeGidsPathNew 
                    : `settings/${facilityCustomExcludeGidsPathNew}`;
            } else if (facilityCustomExcludeGidsPath && facilityCustomExcludeGidsPath !== '__NEW_FILE__') {
                facilityCustomSettings.exclude_gids_path = facilityCustomExcludeGidsPath;
            }
            
            data.custom_settings = Object.keys(facilityCustomSettings).length > 0 ? facilityCustomSettings : null;
            break;
            
        case 'generate_heatmap':
            const heatmapFile = document.getElementById('generate_heatmap_facility_file').value;
            const heatmapFileNew = document.getElementById('generate_heatmap_facility_file_new')?.value.trim();
            
            if (heatmapFile === '__NEW_FILE__' && heatmapFileNew) {
                data.facility_file = heatmapFileNew.startsWith('results/') 
                    ? heatmapFileNew 
                    : `results/${heatmapFileNew}`;
            } else if (heatmapFile && heatmapFile !== '__NEW_FILE__') {
                data.facility_file = heatmapFile;
            }
            data.heatmap_only = true;
            break;

        case 'facility_heatmap':
            // 入力ファイル（処理対象のheatmapファイル）
            const fhFile = document.getElementById('heatmap_facility_file').value;
            const fhFileNew = document.getElementById('heatmap_facility_file_new')?.value.trim();
            
            if (fhFile === '__NEW_FILE__' && fhFileNew) {
                data.input_file = fhFileNew.startsWith('results/') 
                    ? fhFileNew 
                    : `results/${fhFileNew}`;
            } else if (fhFile && fhFile !== '__NEW_FILE__') {
                data.input_file = fhFile;
            }
            
            // 出力ファイル（facility_file: settings.jsonの出力先）
            const outputFile = document.getElementById('heatmap_output_file').value;
            const outputFileNew = document.getElementById('heatmap_output_file_new')?.value.trim();
            
            if (outputFile === '__NEW_FILE__' && outputFileNew) {
                data.facility_file = outputFileNew.startsWith('results/') 
                    ? outputFileNew 
                    : `results/${outputFileNew}`;
            } else if (outputFile && outputFile !== '__NEW_FILE__') {
                data.facility_file = outputFile;
            }
            
            // バッチ処理パラメータ（Issue Opsと同じキー名を使用）
            const heatmapStartLine = document.getElementById('heatmap_start_line')?.value.trim();
            const heatmapProcessCount = document.getElementById('heatmap_process_count')?.value.trim();
            if (heatmapStartLine) data.start_line = heatmapStartLine;  // 文字列のまま
            if (heatmapProcessCount) data.process_count = heatmapProcessCount;  // 文字列のまま
            
            data.max_workers = 8; // 固定値
            data.execution_mode = 'batch'; // 固定値
            break;
            
        case 'extract_fid':
            data.input_file = document.getElementById('extract_fid_input_file').value;
            data.output_choice = document.getElementById('extract_fid_output_choice').value;
            
            if (data.output_choice === 'new') {
                data.output_file = document.getElementById('extract_fid_output_file').value.trim();
            } else {
                data.output_existing = document.getElementById('extract_fid_output_existing').value;
            }
            
            data.delay = document.getElementById('extract_fid_delay').value;
            data.workers = document.getElementById('extract_fid_workers').value;
            const limit = document.getElementById('extract_fid_limit').value.trim();
            if (limit) data.limit = limit;
            break;
    }
    
    return data;
}

// バリデーション
function validateForm() {
    if (currentWorkflow === 'reviews') {
        const startLine = document.getElementById('start_line').value;
        const processCount = document.getElementById('process_count').value;
        
        if (startLine && parseInt(startLine) < 1) {
            alert('⚠️ 開始行は1以上を指定してください');
            return false;
        }
        
        if (processCount) {
            const count = parseInt(processCount);
            if (count < 1 || count > 10000) {
                alert('⚠️ 処理件数は1〜10000の範囲で指定してください');
                return false;
            }
        }
    }
    
    if (currentWorkflow === 'facility_heatmap') {
        const startLine = document.getElementById('heatmap_start_line').value;
        const processCount = document.getElementById('heatmap_process_count').value;
        
        if (startLine && parseInt(startLine) < 1) {
            alert('⚠️ 開始行は1以上を指定してください');
            return false;
        }
        
        if (processCount) {
            const count = parseInt(processCount);
            if (count < 1 || count > 10000) {
                alert('⚠️ 処理件数は1〜10000の範囲で指定してください');
                return false;
            }
        }
    }
    
    return true;
}

// Issue本文生成
function generateIssueBody(data) {
    const commandMap = {
        'reviews': '/run-reviews',
        'reviews_auto_batch': '/run-reviews-auto-batch',
        'facility': '/run-facility',
        'facility_heatmap': '/run-facility-heatmap',
        'generate_heatmap': '/run-generate-heatmap',
        'extract_fid': '/run-extract-fid'
    };
    
    let body = `${commandMap[data.workflow]}\n\n`;
    body += `## ジョブパラメータ\n\n`;
    body += '```json\n';
    body += JSON.stringify(data, null, 2);
    body += '\n```\n\n';
    
    body += `## 実行内容\n\n`;
    
    switch (data.workflow) {
        case 'reviews':
            body += `### 📝 レビュー取得\n\n`;
            body += `- **設定ファイル**: \`${data.config_file}\`\n`;
            if (data.fid_file) {
                body += `- **FIDファイル**: \`${data.fid_file}\`\n`;
            }
            if (data.start_line && data.process_count) {
                body += `- **処理範囲**: ${data.start_line}行目から${data.process_count}件\n`;
            }
            if (data.workers) {
                body += `- **並列数**: ${data.workers}\n`;
            }
            if (data.custom_settings) {
                body += `\n### ⚙️ カスタム設定\n\n`;
                Object.entries(data.custom_settings).forEach(([key, value]) => {
                    body += `- **${key}**: \`${value}\`\n`;
                });
            }
            break;
            
        case 'reviews_auto_batch':
            body += `### 🚀 レビュー取得・自動分割実行\n\n`;
            body += `大量データを自動的にバッチ分割して5時間以内に完了させます。\n\n`;
            body += `#### 📊 設定内容\n\n`;
            body += `- **設定ファイル**: \`${data.config_file}\`\n`;
            if (data.fid_file) {
                body += `- **FIDファイル**: \`${data.fid_file}\`\n`;
            }
            if (data.review_file) {
                body += `- **レビューファイル**: \`${data.review_file}\`（バッチごとに番号付与）\n`;
            }
            body += `- **バッチサイズ**: ${data.batch_size}件/バッチ\n`;
            body += `- **最大並列バッチ数**: ${data.max_parallel_jobs}バッチ同時実行\n`;
            body += `- **バッチ内並列数**: ${data.workers}施設同時処理\n`;
            
            // 推定時間を計算（簡易版）
            const batchSize = parseInt(data.batch_size);
            const maxParallel = parseInt(data.max_parallel_jobs);
            const workers = parseInt(data.workers);
            const timePerBatch = Math.ceil(batchSize / workers / 10); // 10件/分/worker
            
            body += `\n#### ⏱️ 推定処理時間（データ件数による）\n\n`;
            body += `| データ件数 | バッチ数 | 推定時間 |\n`;
            body += `|-----------|---------|----------|\n`;
            body += `| 20,000件 | 2バッチ | 約${Math.ceil(timePerBatch * 2 / maxParallel)}分 |\n`;
            body += `| 40,000件 | 4バッチ | 約${Math.ceil(timePerBatch * 4 / maxParallel)}分 |\n`;
            body += `| 80,000件 | 8バッチ | 約${Math.ceil(timePerBatch * 8 / maxParallel)}分 |\n`;
            
            body += `\n#### 🎯 自動処理フロー\n\n`;
            body += `1. データ件数を自動カウント\n`;
            body += `2. 20,000件以上の場合、自動的にバッチ分割\n`;
            body += `3. ${maxParallel}バッチずつ並列実行\n`;
            body += `4. 各バッチの進捗をIssueに通知\n`;
            body += `5. 全バッチ完了後、結果を自動統合\n`;
            body += `6. 統合結果を\`results/\`フォルダに保存\n`;
            break;
            
        case 'facility':
            body += `### 🏢 施設データ取得\n\n`;
            body += `基本的な施設データを取得します\n`;
            if (data.custom_settings) {
                body += `\n### ⚙️ カスタム設定\n\n`;
                Object.entries(data.custom_settings).forEach(([key, value]) => {
                    body += `- **${key}**: \`${value}\`\n`;
                });
            }
            break;
            
        case 'generate_heatmap':
            body += `### 🗺️ ヒートマップ作成\n\n`;
            body += `- **施設ファイル**: \`${data.facility_file}\`\n`;
            body += `- **モード**: ヒートマップ用CSV作成のみ\n`;
            break;

        case 'facility_heatmap':
            body += `### 🗺️ ヒートマップ施設取得\n\n`;
            body += `- **入力ファイル**: \`${data.input_file || '設定ファイル参照'}\`\n`;
            body += `- **出力ファイル**: \`${data.facility_file || '設定ファイル参照'}\`\n`;
            if (data.start_line && data.process_count) {
                body += `- **処理範囲**: ${data.start_line}行目から${data.process_count}件\n`;
            }
            body += `- **並列処理数**: ${data.max_workers}（固定）\n`;
            break;
            
        case 'extract_fid':
            body += `### 🔑 FID抽出\n\n`;
            body += `- **入力ファイル**: \`${data.input_file}\`\n`;
            
            if (data.output_choice === 'new') {
                body += `- **出力方法**: 新規ファイル作成\n`;
                body += `- **出力ファイル**: \`results/${data.output_file}.csv\`\n`;
            } else {
                body += `- **出力方法**: 既存ファイルに上書き\n`;
                body += `- **出力ファイル**: \`${data.output_existing}\`\n`;
            }
            
            body += `- **待機時間**: ${data.delay}秒/件\n`;
            if (data.limit) {
                body += `- **処理件数**: ${data.limit}件（テストモード）\n`;
            } else {
                body += `- **処理件数**: 全件\n`;
            }
            break;
    }
    
    body += `\n---\n\n`;
    body += `⚠️ **管理者へ**: 内容を確認後、コメントに \`/承認\` と入力して承認してください。\n`;
    
    return body;
}

// プレビュー表示
function showPreview(issueBody, formData) {
    issueData = { body: issueBody, formData: formData };
    
    document.getElementById('previewText').textContent = issueBody;
    document.getElementById('jobForm').style.display = 'none';
    document.getElementById('preview').style.display = 'block';
    
    // ワークフロー選択も非表示
    document.getElementById('workflow_type').parentElement.style.display = 'none';
}

// プレビュー非表示
function hidePreview() {
    document.getElementById('preview').style.display = 'none';
    document.getElementById('jobForm').style.display = 'block';
    document.getElementById('workflow_type').parentElement.style.display = 'block';
}

// GitHubでIssueを開く
function openIssue() {
    console.log('🔵 openIssue() が呼ばれました');
    console.log('currentWorkflow:', currentWorkflow);
    console.log('issueData:', issueData);
    
    if (!issueData || !issueData.body) {
        console.error('❌ issueData が空です');
        alert('⚠️ エラー: Issue データが見つかりません。もう一度やり直してください。');
        return;
    }
    
    const workflowNames = {
        'reviews': 'Reviews Job',
        'reviews_auto_batch': 'Reviews Auto-Batch Job',
        'facility': 'Facility Job',
        'facility_heatmap': 'Facility Heatmap Job',
        'generate_heatmap': 'Generate Heatmap Job',
        'extract_fid': 'Extract FID Job'
    };
    
    const title = `[${workflowNames[currentWorkflow]}] ${new Date().toISOString().split('T')[0]}`;
    const body = encodeURIComponent(issueData.body);
    const url = `https://github.com/${GITHUB_OWNER}/${GITHUB_REPO}/issues/new?title=${encodeURIComponent(title)}&body=${body}`;
    
    console.log('🔗 生成されたURL:', url);
    console.log('🔗 URL長:', url.length);
    
    // Braveのポップアップブロック対策
    const newWindow = window.open(url, '_blank');
    
    if (!newWindow || newWindow.closed || typeof newWindow.closed === 'undefined') {
        console.warn('⚠️ ポップアップがブロックされました');
        alert('⚠️ ポップアップがブロックされました。\n\nBraveの設定で「このサイトのポップアップを許可」してください。\n\n以下のURLをコピーしてブラウザで開いてください:\n' + url);
        
        // クリップボードにコピーを試みる
        if (navigator.clipboard) {
            navigator.clipboard.writeText(url).then(() => {
                console.log('✅ URLをクリップボードにコピーしました');
            }).catch(err => {
                console.error('❌ クリップボードへのコピー失敗:', err);
            });
        }
    } else {
        console.log('✅ 新しいタブが開きました');
    }
}

// フォームリセット
function resetForm() {
    document.getElementById('jobForm').reset();
    document.getElementById('workflow_type').value = '';
    currentWorkflow = '';
    switchWorkflow();
    hidePreview();
}

// 新規ファイル作成の入力欄を表示/非表示
function toggleNewFileInput(selectId, inputId) {
    const select = document.getElementById(selectId);
    const container = document.getElementById(inputId + '_container');
    const input = document.getElementById(inputId);
    
    if (select && container && input) {
        if (select.value === '__NEW_FILE__') {
            container.style.display = 'block';
            input.required = true;
        } else {
            container.style.display = 'none';
            input.required = false;
            input.value = '';
        }
    }
}

// ページ読み込み時にファイルオプションを取得
document.addEventListener('DOMContentLoaded', function() {
    loadFileOptions();
    
    // 初期状態：すべての非表示フォームのrequired要素を無効化
    document.querySelectorAll('.workflow-form').forEach(form => {
        form.querySelectorAll('[required]').forEach(input => {
            input.disabled = true;
        });
    });
    
    // イベントリスナーを設定
    document.getElementById('workflow_type').addEventListener('change', switchWorkflow);
    
    // FID抽出の出力ファイル選択方法の切り替え
    document.getElementById('extract_fid_output_choice')?.addEventListener('change', function() {
        const newContainer = document.getElementById('extract_fid_output_new_container');
        const existingContainer = document.getElementById('extract_fid_output_existing_container');
        const newInput = document.getElementById('extract_fid_output_file');
        const existingSelect = document.getElementById('extract_fid_output_existing');
        
        if (this.value === 'new') {
            newContainer.style.display = 'block';
            existingContainer.style.display = 'none';
            newInput.required = true;
            existingSelect.required = false;
            existingSelect.value = '';
        } else {
            newContainer.style.display = 'none';
            existingContainer.style.display = 'block';
            newInput.required = false;
            existingSelect.required = true;
        }
    });
    
    document.getElementById('custom_review_file')?.addEventListener('change', function() {
        toggleNewFileInput('custom_review_file', 'custom_review_file_new');
    });
    document.getElementById('facility_custom_address_csv')?.addEventListener('change', function() {
        toggleNewFileInput('facility_custom_address_csv', 'facility_custom_address_csv_new');
    });
    document.getElementById('facility_custom_facility_file')?.addEventListener('change', function() {
        toggleNewFileInput('facility_custom_facility_file', 'facility_custom_facility_file_new');
    });
    document.getElementById('facility_custom_exclude_gids_path')?.addEventListener('change', function() {
        toggleNewFileInput('facility_custom_exclude_gids_path', 'facility_custom_exclude_gids_path_new');
    });
    document.getElementById('generate_heatmap_facility_file')?.addEventListener('change', function() {
        toggleNewFileInput('generate_heatmap_facility_file', 'generate_heatmap_facility_file_new');
    });
    document.getElementById('heatmap_facility_file')?.addEventListener('change', function() {
        toggleNewFileInput('heatmap_facility_file', 'heatmap_facility_file_new');
    });
    document.getElementById('heatmap_output_file')?.addEventListener('change', function() {
        toggleNewFileInput('heatmap_output_file', 'heatmap_output_file_new');
    });
    
    // ボタンのイベントリスナー
    document.getElementById('resetButton')?.addEventListener('click', resetForm);
    document.getElementById('openIssueButton')?.addEventListener('click', openIssue);
    document.getElementById('backButton')?.addEventListener('click', hidePreview);
});
