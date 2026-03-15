// GitHubリポジトリ情報
const GITHUB_OWNER = 'mememori8888';
const GITHUB_REPO = 'demo';
const GITHUB_BRANCH = 'main';

// グローバル変数
let issueData = {};
let currentWorkflow = '';
let fileCache = {
    settings: [],
    results: []
};

function inferSettingsPurposes(filename) {
    const lowerName = filename.toLowerCase();
    const purposes = [];

    if (filename.toLowerCase().endsWith('.csv')) {
        purposes.push('settings_csv');
        if (lowerName.includes('address') || lowerName.includes('adress')) {
            purposes.push('address_input');
        }
        if (lowerName.includes('exclude')) {
            purposes.push('exclude_gids');
        }
    }

    if (filename.toLowerCase().endsWith('.json')) {
        purposes.push('settings_json');
        if (lowerName.includes('settings')) {
            purposes.push('config');
        }
    }

    return purposes;
}

function inferResultsPurposes(filename) {
    const lowerName = filename.toLowerCase();
    const purposes = [];
    const sequentialExcludedKeywords = ['review', 'batch', 'report', 'fid', 'heatmap', 'duplicate', 'analysis', 'log', 'error', 'summary'];
    const facilityExcludedKeywords = ['review', 'batch', 'report', 'fid', 'heatmap', 'duplicate', 'analysis', 'log', 'error', 'summary', 'add_'];

    if (filename.toLowerCase().endsWith('.csv')) {
        purposes.push('results_csv');
    }
    if (lowerName.includes('review')) {
        purposes.push('review_output');
    }
    if (lowerName.includes('fid') || lowerName.includes('add_data')) {
        purposes.push('fid_input');
    }
    if (lowerName.includes('add_data')) {
        purposes.push('update_facility_output');
    }
    if (lowerName.includes('add_review')) {
        purposes.push('update_review_output');
    }
    if (!sequentialExcludedKeywords.some(keyword => lowerName.includes(keyword))) {
        purposes.push('sequential_input');
    }
    if (!facilityExcludedKeywords.some(keyword => lowerName.includes(keyword))) {
        purposes.push('facility_output');
    }

    return [...new Set(purposes)];
}

function normalizeFileEntries(entries, basePath, inferPurposes) {
    return (entries || []).map(entry => {
        if (typeof entry === 'string') {
            return {
                name: entry,
                path: `${basePath}/${entry}`,
                extension: entry.includes('.') ? `.${entry.split('.').pop().toLowerCase()}` : '',
                purposes: inferPurposes(entry)
            };
        }

        return {
            name: entry.name,
            path: entry.path || `${basePath}/${entry.name}`,
            extension: entry.extension || (entry.name.includes('.') ? `.${entry.name.split('.').pop().toLowerCase()}` : ''),
            purposes: Array.isArray(entry.purposes) ? entry.purposes : inferPurposes(entry.name)
        };
    });
}

function hasPurpose(entry, purpose) {
    return Array.isArray(entry.purposes) && entry.purposes.includes(purpose);
}

// プリセット設定
const PRESETS = {
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
    reviews_sequential: {
        'dental_new_default': {
            name: '⚡ 新仕様・標準実行',
            description: 'dental_new.csv を 500 行ずつ逐次処理',
            params: {
                sequential_csv_file: 'results/dental_new.csv',
                sequential_output_file: 'results/dental_new_reviews.csv',
                sequential_days_back: '10',
                sequential_start_from_batch: '1',
                sequential_rows_per_batch: '500',
                sequential_batch_wait: '120',
                sequential_api_batch_size: '50',
                sequential_max_wait_minutes: '90',
                sequential_dataset_id: 'gd_luzfs1dn2oa0teb81',
                sequential_skip_column: 'web',
                sequential_report_days: '10'
            }
        },
        'dental_new_hokkaido': {
            name: '🦷 北海道レビュー取得',
            description: '北海道の dental_new 系 CSV を逐次処理',
            params: {
                sequential_csv_file: 'results/dental_new_hokkaido.csv',
                sequential_output_file: 'results/dental_new_reviews_hokkaido.csv',
                sequential_days_back: '10',
                sequential_start_from_batch: '1',
                sequential_rows_per_batch: '500',
                sequential_batch_wait: '120',
                sequential_api_batch_size: '50',
                sequential_max_wait_minutes: '90',
                sequential_dataset_id: 'gd_luzfs1dn2oa0teb81',
                sequential_skip_column: 'web',
                sequential_report_days: '10'
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

function getSequentialInputFiles(resultEntries) {
    return resultEntries
        .filter(entry => hasPurpose(entry, 'sequential_input'))
        .map(entry => entry.name);
}

function buildSequentialOutputCandidates(selectedInputPath = '') {
    const existingReviewFiles = fileCache.results
        .filter(entry => hasPurpose(entry, 'review_output'))
        .map(entry => entry.name);

    const candidates = [];
    const seen = new Set();

    const pushCandidate = (value, label) => {
        if (!value || seen.has(value)) return;
        seen.add(value);
        candidates.push({ value, label });
    };

    if (selectedInputPath) {
        const inputFilename = selectedInputPath.split('/').pop() || '';
        let suggestedFilename = inputFilename.replace(/\.csv$/i, '_reviews.csv');

        // *_new.csv は *_new_reviews.csv の形にして読みやすくする
        if (/_new\.csv$/i.test(inputFilename)) {
            suggestedFilename = inputFilename.replace(/_new\.csv$/i, '_new_reviews.csv');
        }

        if (suggestedFilename && suggestedFilename !== inputFilename) {
            pushCandidate(`results/${suggestedFilename}`, `✨ 推奨: ${suggestedFilename}`);
        }
    }

    existingReviewFiles.forEach(filename => {
        pushCandidate(`results/${filename}`, filename);
    });

    return candidates;
}

function refreshSequentialOutputOptions() {
    const outputSelect = document.getElementById('sequential_output_file');
    const inputSelect = document.getElementById('sequential_csv_file');
    if (!outputSelect || !inputSelect) return;

    const previousValue = outputSelect.value;
    const selectedInput = inputSelect.value;
    const candidates = buildSequentialOutputCandidates(selectedInput);

    while (outputSelect.options.length > 1) {
        outputSelect.remove(1);
    }

    const newOption = document.createElement('option');
    newOption.value = '__NEW_FILE__';
    newOption.textContent = '📝 新規ファイルを作成';
    outputSelect.appendChild(newOption);

    candidates.forEach(candidate => {
        const option = document.createElement('option');
        option.value = candidate.value;
        option.textContent = candidate.label;
        outputSelect.appendChild(option);
    });

    if (previousValue && Array.from(outputSelect.options).some(option => option.value === previousValue)) {
        outputSelect.value = previousValue;
    } else if (candidates.length > 0) {
        outputSelect.value = candidates[0].value;
    } else {
        outputSelect.selectedIndex = 0;
    }

    toggleNewFileInput('sequential_output_file', 'sequential_output_file_new');
}

// ファイル一覧を読み込み
async function loadFileOptions() {
    try {
        // 静的JSONファイルから読み込み（GitHub Actionsで生成）
        // キャッシュ回避のためにタイムスタンプを付与
        const response = await fetch('./files.json?t=' + new Date().getTime());
        if (response.ok) {
            const filesData = await response.json();
            const settingsEntries = filesData.settings || filesData.settings_csv || [];
            const resultEntries = filesData.results || [];
            fileCache.settings = normalizeFileEntries(settingsEntries, 'settings', inferSettingsPurposes);
            fileCache.results = normalizeFileEntries(resultEntries, 'results', inferResultsPurposes);
        } else {
            // フォールバック: GitHub APIから直接取得
            console.log('files.json not found, falling back to GitHub API');
            fileCache.settings = normalizeFileEntries(await fetchGitHubFiles('settings'), 'settings', inferSettingsPurposes);
            fileCache.results = normalizeFileEntries(await fetchGitHubFiles('results'), 'results', inferResultsPurposes);
        }
        
        // CSVファイルのみフィルタ
        const settingsCsvFiles = fileCache.settings.filter(entry => entry.extension === '.csv').map(entry => entry.name);
        const resultsCsvFiles = fileCache.results.filter(entry => entry.extension === '.csv').map(entry => entry.name);
        
        // 住所CSVファイル (settings/*.csv)
        const addressFiles = fileCache.settings.filter(entry => hasPurpose(entry, 'address_input')).map(entry => entry.name);
        populateDropdown('custom_address_csv', addressFiles.length > 0 ? addressFiles : settingsCsvFiles, 'settings');
        
        // 施設ファイル
        const facilityFiles = fileCache.results.filter(entry => hasPurpose(entry, 'facility_output')).map(entry => entry.name);
        populateDropdown('custom_facility_file', facilityFiles, 'results');
        
        // レビューファイル
        const reviewFiles = fileCache.results.filter(entry => hasPurpose(entry, 'review_output')).map(entry => entry.name);
        populateDropdown('custom_review_file', reviewFiles, 'results');
        
        // FIDファイル
        const fidFiles = fileCache.results.filter(entry => hasPurpose(entry, 'fid_input')).map(entry => entry.name);
        populateDropdown('fid_file', fidFiles, 'results', false);
        
        // 更新施設ファイル (results/*add_data.csv)
        const addDataFiles = fileCache.results.filter(entry => hasPurpose(entry, 'update_facility_output')).map(entry => entry.name);
        populateDropdown('custom_update_facility_path', addDataFiles, 'results');
        
        // 更新レビューファイル (results/*add_review.csv)
        const addReviewFiles = fileCache.results.filter(entry => hasPurpose(entry, 'update_review_output')).map(entry => entry.name);
        populateDropdown('custom_update_review_path', addReviewFiles, 'results');
        
        // 除外GIDファイル (settings/exclude_gids.csv)
        const excludeFiles = fileCache.settings.filter(entry => hasPurpose(entry, 'exclude_gids')).map(entry => entry.name);
        populateDropdown('custom_exclude_gids_path', excludeFiles, 'settings');
        
        // Reviews workflow用のドロップダウンを設定
        populateDropdown('custom_review_file', reviewFiles, 'results', true);

        // Reviews Sequential workflow用のドロップダウンを設定
        const sequentialInputFiles = getSequentialInputFiles(fileCache.results);
        populateDropdown('sequential_csv_file', sequentialInputFiles, 'results', false);
        refreshSequentialOutputOptions();
        // Reviews Auto-Batch workflow用のドロップダウンを設定
        populateDropdown('auto_batch_fid_file', fidFiles, 'results', false);
        populateDropdown('auto_batch_review_file', reviewFiles, 'results', true);
        
        // Facility workflow用のドロップダウンを設定
        populateDropdown('facility_custom_address_csv', settingsCsvFiles, 'settings', true);
        populateDropdown('facility_custom_facility_file', facilityFiles, 'results', true);
        populateDropdown('facility_custom_exclude_gids_path', excludeFiles, 'settings', true);
        
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
    
    if (currentWorkflow === 'reviews') {
        const startLine = parseInt(document.getElementById('start_line')?.value || '0');
        const processCount = parseInt(document.getElementById('process_count')?.value || '0');
        
        if (startLine < 0) errors.push('開始行は0以上を指定してください');
        if (processCount < 0) errors.push('処理件数は0以上を指定してください');
    }

    if (currentWorkflow === 'reviews_auto_batch') {
        const batchSize = parseInt(document.getElementById('auto_batch_size')?.value || '0');
        const maxParallel = parseInt(document.getElementById('auto_batch_max_parallel')?.value || '0');
        const workers = parseInt(document.getElementById('auto_batch_workers')?.value || '0');

        if (!Number.isInteger(batchSize) || batchSize < 5000 || batchSize > 20000) {
            errors.push('バッチサイズは5,000〜20,000の範囲で指定してください');
        }
        if (!Number.isInteger(maxParallel) || maxParallel < 1 || maxParallel > 8) {
            errors.push('最大並列バッチ数は1〜8の範囲で指定してください');
        }
        if (!Number.isInteger(workers) || workers < 5 || workers > 20) {
            errors.push('並列実行数（バッチ内）は5〜20の範囲で指定してください');
        }
    }

    if (currentWorkflow === 'reviews_sequential') {
        const csvFile = document.getElementById('sequential_csv_file')?.value || '';
        const outputFile = document.getElementById('sequential_output_file')?.value || '';
        const outputFileNew = document.getElementById('sequential_output_file_new')?.value.trim() || '';
        const daysBack = parseInt(document.getElementById('sequential_days_back')?.value || '0');
        const startFromBatch = parseInt(document.getElementById('sequential_start_from_batch')?.value || '0');
        const rowsPerBatch = parseInt(document.getElementById('sequential_rows_per_batch')?.value || '0');
        const batchWait = parseInt(document.getElementById('sequential_batch_wait')?.value || '0');
        const apiBatchSize = parseInt(document.getElementById('sequential_api_batch_size')?.value || '0');
        const maxWaitMinutes = parseInt(document.getElementById('sequential_max_wait_minutes')?.value || '0');
        const datasetId = document.getElementById('sequential_dataset_id')?.value.trim() || '';
        const skipColumn = document.getElementById('sequential_skip_column')?.value.trim() || '';

        if (!csvFile) {
            errors.push('入力CSVファイルを選択してください');
        }
        if (!outputFile || (outputFile === '__NEW_FILE__' && !outputFileNew)) {
            errors.push('出力レビューCSVを指定してください');
        }
        if (!Number.isInteger(daysBack) || daysBack < 1) {
            errors.push('days_back は1以上の整数を指定してください');
        }
        if (!Number.isInteger(startFromBatch) || startFromBatch < 1) {
            errors.push('start_from_batch は1以上の整数を指定してください');
        }
        if (!Number.isInteger(rowsPerBatch) || rowsPerBatch < 1) {
            errors.push('rows_per_batch は1以上の整数を指定してください');
        }
        if (!Number.isInteger(batchWait) || batchWait < 1) {
            errors.push('batch_wait は1以上の整数を指定してください');
        }
        if (!Number.isInteger(apiBatchSize) || apiBatchSize < 1) {
            errors.push('api_batch_size は1以上の整数を指定してください');
        }
        if (!Number.isInteger(maxWaitMinutes) || maxWaitMinutes < 1) {
            errors.push('max_wait_minutes は1以上の整数を指定してください');
        }
        if (!datasetId) {
            errors.push('dataset_id を入力してください');
        }
        if (!skipColumn) {
            errors.push('skip_column を入力してください');
        }
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

        case 'reviews_sequential':
            const sequentialOutputFile = document.getElementById('sequential_output_file')?.value;
            const sequentialOutputFileNew = document.getElementById('sequential_output_file_new')?.value.trim();

            data.csv_file = document.getElementById('sequential_csv_file').value;
            data.output_file = sequentialOutputFile === '__NEW_FILE__'
                ? (sequentialOutputFileNew.startsWith('results/') ? sequentialOutputFileNew : `results/${sequentialOutputFileNew}`)
                : sequentialOutputFile;
            data.merge_to_all_regions = false;
            data.days_back = document.getElementById('sequential_days_back').value;
            data.start_from_batch = document.getElementById('sequential_start_from_batch').value;
            data.rows_per_batch = document.getElementById('sequential_rows_per_batch').value;
            data.batch_wait = document.getElementById('sequential_batch_wait').value;
            data.api_batch_size = document.getElementById('sequential_api_batch_size').value;
            data.max_wait_minutes = document.getElementById('sequential_max_wait_minutes').value;
            data.dataset_id = document.getElementById('sequential_dataset_id').value.trim();
            data.skip_column = document.getElementById('sequential_skip_column').value.trim();
            data.generate_report = document.getElementById('sequential_generate_report').checked;
            data.report_days = document.getElementById('sequential_report_days').value.trim();
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

    if (currentWorkflow === 'reviews_sequential') {
        const reportDays = document.getElementById('sequential_report_days')?.value;
        if (reportDays && parseInt(reportDays) < 1) {
            alert('⚠️ report_days は1以上を指定してください');
            return false;
        }
    }
    
    return true;
}

// Issue本文生成
function generateIssueBody(data) {
    const commandMap = {
        'reviews': '/run-reviews',
        'reviews_sequential': '/run-reviews-sequential',
        'reviews_auto_batch': '/run-reviews-auto-batch',
        'facility': '/run-facility'
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

        case 'reviews_sequential':
            body += `### ⚡ レビュー取得・新仕様逐次実行\n\n`;
            body += `- **入力CSV**: \`${data.csv_file}\`\n`;
            body += `- **出力CSV**: \`${data.output_file}\`\n`;
            body += `- **Days back**: ${data.days_back}日\n`;
            body += `- **開始バッチ**: ${data.start_from_batch}\n`;
            body += `- **1バッチ行数**: ${data.rows_per_batch}\n`;
            body += `- **バッチ間待機**: ${data.batch_wait}秒\n`;
            body += `- **API Batch Size**: ${data.api_batch_size}\n`;
            body += `- **待機時間上限**: ${data.max_wait_minutes}分\n`;
            body += `- **Dataset ID**: \`${data.dataset_id}\`\n`;
            body += `- **Skip column**: \`${data.skip_column}\`\n`;
            body += `- **レポート生成**: ${data.generate_report ? '有効' : '無効'}\n`;
            if (data.report_days) {
                body += `- **レポート日数**: ${data.report_days}日\n`;
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
        'reviews_sequential': 'Reviews Sequential Job',
        'reviews_auto_batch': 'Reviews Auto-Batch Job',
        'facility': 'Facility Job'
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
    
    document.getElementById('custom_review_file')?.addEventListener('change', function() {
        toggleNewFileInput('custom_review_file', 'custom_review_file_new');
    });
    document.getElementById('sequential_csv_file')?.addEventListener('change', function() {
        refreshSequentialOutputOptions();
    });
    document.getElementById('sequential_output_file')?.addEventListener('change', function() {
        toggleNewFileInput('sequential_output_file', 'sequential_output_file_new');
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
    
    // ボタンのイベントリスナー
    document.getElementById('resetButton')?.addEventListener('click', resetForm);
    document.getElementById('openIssueButton')?.addEventListener('click', openIssue);
    document.getElementById('backButton')?.addEventListener('click', hidePreview);
});
