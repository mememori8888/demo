// GitHubリポジトリ情報
const GITHUB_OWNER = 'mememori8888';
const GITHUB_REPO = 'demo';
const GITHUB_BRANCH = 'main';
const DATA_REPO = 'googlemap';
const DATA_BRANCH = 'main';

// グローバル変数
let issueData = {};
let currentWorkflow = '';
const ALLOWED_WEBAPP_WORKFLOWS = ['reviews', 'reviews_sequential', 'reviews_recent_relevance', 'facility'];
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
    const isBatchReviewFile = /^reviews_batch_\d+\.csv$/.test(lowerName);
    if (lowerName.includes('review') && !isBatchReviewFile) {
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

function shouldHideFromWebapp(entry) {
    const name = (entry?.name || '').toLowerCase();
    return name === 'dental_duplicate_analysis_adress_small_stats.csv' || /^reviews_batch_\d+\.csv$/.test(name);
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

function mergeFileEntries(primaryEntries, secondaryEntries) {
    const merged = new Map();

    [...(primaryEntries || []), ...(secondaryEntries || [])].forEach(entry => {
        if (!entry || !entry.path) return;

        const existing = merged.get(entry.path);
        if (!existing) {
            merged.set(entry.path, entry);
            return;
        }

        merged.set(entry.path, {
            ...existing,
            ...entry,
            purposes: [...new Set([...(existing.purposes || []), ...(entry.purposes || [])])]
        });
    });

    return Array.from(merged.values()).sort((left, right) => left.name.localeCompare(right.name, 'ja'));
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
        'care_home': {
            name: '🏥 老人ホームレビュー取得',
            description: '老人ホーム施設データからレビューを逐次取得',
            params: {
                sequential_csv_file: 'results/care_roujin-home.csv',
                sequential_output_file: 'results/care_roujin-home_reviews.csv',
                sequential_days_back: '10',
                sequential_start_from_batch: '1',
                sequential_rows_per_batch: '500',
                sequential_max_parallel_jobs: '3',
                sequential_batch_wait: '120',
                sequential_api_batch_size: '50',
                sequential_max_wait_minutes: '90',
                sequential_dataset_id: 'gd_luzfs1dn2oa0teb81',
                sequential_skip_column: 'web',
                sequential_report_days: '10'
            }
        },
        'dental_clinic': {
            name: '🦷 歯科医院レビュー取得',
            description: '歯科医院データからレビューを逐次取得',
            params: {
                sequential_csv_file: 'results/dental_new.csv',
                sequential_output_file: 'results/dental_reviews.csv',
                sequential_days_back: '10',
                sequential_start_from_batch: '1',
                sequential_rows_per_batch: '500',
                sequential_max_parallel_jobs: '3',
                sequential_batch_wait: '120',
                sequential_api_batch_size: '50',
                sequential_max_wait_minutes: '90',
                sequential_dataset_id: 'gd_luzfs1dn2oa0teb81',
                sequential_skip_column: 'web',
                sequential_report_days: '10'
            }
        },
        'marriage_consultation': {
            name: '💍 結婚相談所レビュー取得',
            description: '結婚相談所データからレビューを逐次取得',
            params: {
                sequential_csv_file: 'results/add_data_marriage_kihon.csv',
                sequential_output_file: 'results/add_marriage_kihon_reviews.csv',
                sequential_days_back: '10',
                sequential_start_from_batch: '1',
                sequential_rows_per_batch: '500',
                sequential_max_parallel_jobs: '3',
                sequential_batch_wait: '120',
                sequential_api_batch_size: '50',
                sequential_max_wait_minutes: '90',
                sequential_dataset_id: 'gd_luzfs1dn2oa0teb81',
                sequential_skip_column: 'GoogleMap',
                sequential_report_days: '10'
            }
        },
        'funeral_home': {
            name: '⚰️ 葬儀施設レビュー取得',
            description: '葬儀施設データからレビューを逐次取得',
            params: {
                sequential_csv_file: 'results/funeral.csv',
                sequential_output_file: 'results/funeral_review.csv',
                sequential_days_back: '10',
                sequential_start_from_batch: '1',
                sequential_rows_per_batch: '500',
                sequential_max_parallel_jobs: '3',
                sequential_batch_wait: '120',
                sequential_api_batch_size: '50',
                sequential_max_wait_minutes: '90',
                sequential_dataset_id: 'gd_luzfs1dn2oa0teb81',
                sequential_skip_column: 'web',
                sequential_report_days: '10'
            }
        }
    },
    reviews_recent_relevance: {
        'dental_clinic': {
            name: '🦷 歯科医院・30日関連度ランク',
            description: '直近30日の歯科レビューを取得し、関連度上位10位までを照合',
            params: {
                sequential_csv_file: 'results/dental_new.csv',
                sequential_output_file: 'results/dental_reviews.csv',
                sequential_days_back: '30',
                sequential_start_from_batch: '1',
                sequential_rows_per_batch: '500',
                sequential_max_parallel_jobs: '3',
                sequential_batch_wait: '120',
                sequential_api_batch_size: '50',
                sequential_max_wait_minutes: '90',
                sequential_dataset_id: 'gd_luzfs1dn2oa0teb81',
                sequential_skip_column: 'web',
                sequential_relevance_rank_limit: '10',
                sequential_serp_max_workers: '3',
                sequential_serp_zone_name: 'serp_api2',
                sequential_summary_file: 'results/dental_relevance_rank_summary.csv',
                sequential_report_days: '30'
            }
        },
        'marriage_consultation': {
            name: '💍 婚活相談所・30日関連度ランク',
            description: '直近30日の婚活相談所レビューを取得し、関連度上位10位までを照合',
            params: {
                sequential_csv_file: 'results/add_data_marriage_kihon.csv',
                sequential_output_file: 'results/add_marriage_kihon_reviews.csv',
                sequential_days_back: '30',
                sequential_start_from_batch: '1',
                sequential_rows_per_batch: '500',
                sequential_max_parallel_jobs: '3',
                sequential_batch_wait: '120',
                sequential_api_batch_size: '50',
                sequential_max_wait_minutes: '90',
                sequential_dataset_id: 'gd_luzfs1dn2oa0teb81',
                sequential_skip_column: 'GoogleMap',
                sequential_relevance_rank_limit: '10',
                sequential_serp_max_workers: '3',
                sequential_serp_zone_name: 'serp_api2',
                sequential_summary_file: 'results/marriage_relevance_rank_summary.csv',
                sequential_report_days: '30'
            }
        },
        'funeral_home': {
            name: '⚰️ 葬儀施設・30日関連度ランク',
            description: '直近30日の葬儀施設レビューを取得し、関連度上位10位までを照合',
            params: {
                sequential_csv_file: 'results/funeral.csv',
                sequential_output_file: 'results/funeral_review.csv',
                sequential_days_back: '30',
                sequential_start_from_batch: '1',
                sequential_rows_per_batch: '500',
                sequential_max_parallel_jobs: '3',
                sequential_batch_wait: '120',
                sequential_api_batch_size: '50',
                sequential_max_wait_minutes: '90',
                sequential_dataset_id: 'gd_luzfs1dn2oa0teb81',
                sequential_skip_column: 'web',
                sequential_relevance_rank_limit: '10',
                sequential_serp_max_workers: '3',
                sequential_serp_zone_name: 'serp_api2',
                sequential_summary_file: 'results/funeral_relevance_rank_summary.csv',
                sequential_report_days: '30'
            }
        },
        'care_facility': {
            name: '🏥 介護施設・30日関連度ランク',
            description: '直近30日の介護施設レビューを取得し、関連度上位10位までを照合',
            params: {
                sequential_csv_file: 'results/care_roujin-home.csv',
                sequential_output_file: 'results/care_roujin-home_reviews.csv',
                sequential_days_back: '30',
                sequential_start_from_batch: '1',
                sequential_rows_per_batch: '500',
                sequential_max_parallel_jobs: '3',
                sequential_batch_wait: '120',
                sequential_api_batch_size: '50',
                sequential_max_wait_minutes: '90',
                sequential_dataset_id: 'gd_luzfs1dn2oa0teb81',
                sequential_skip_column: 'web',
                sequential_relevance_rank_limit: '10',
                sequential_serp_max_workers: '3',
                sequential_serp_zone_name: 'serp_api2',
                sequential_summary_file: 'results/care_relevance_rank_summary.csv',
                sequential_report_days: '30'
            }
        }
    }
};

const SEQUENTIAL_INPUT_OUTPUT_PRESETS = [
    {
        label: '老人ホーム',
        input: 'results/care_roujin-home.csv',
        output: 'results/care_roujin-home_reviews.csv'
    },
    {
        label: '歯科医院',
        input: 'results/dental_new.csv',
        output: 'results/dental_reviews.csv'
    },
    {
        label: '結婚相談所',
        input: 'results/add_data_marriage_kihon.csv',
        output: 'results/add_marriage_kihon_reviews.csv'
    },
    {
        label: '葬儀施設',
        input: 'results/funeral.csv',
        output: 'results/funeral_review.csv'
    }
];

// GitHub APIでファイル一覧を取得
async function fetchGitHubFileEntries(path, inferPurposes) {
    try {
        const url = `https://api.github.com/repos/${GITHUB_OWNER}/${DATA_REPO}/contents/${path}?ref=${DATA_BRANCH}&t=${Date.now()}`;
        const response = await fetch(url);
        if (!response.ok) {
            console.warn(`Failed to fetch latest files from ${DATA_REPO}/${path}:`, response.status);
            return [];
        }
        const files = await response.json();
        return normalizeFileEntries(
            files
                .filter(file => file.type === 'file')
                .map(file => ({
                    name: file.name,
                    path: file.path,
                    size: file.size
                })),
            path,
            inferPurposes
        );
    } catch (error) {
        console.warn(`Error fetching latest files from ${DATA_REPO}/${path}:`, error);
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
    const fromPurpose = resultEntries
        .filter(entry => hasPurpose(entry, 'sequential_input'))
        .map(entry => entry.name);

    const fallback = resultEntries
        .filter(entry => entry.extension === '.csv')
        .filter(entry => !hasPurpose(entry, 'review_output'))
        .filter(entry => !hasPurpose(entry, 'fid_input'))
        .map(entry => entry.name);

    const merged = new Set([
        ...SEQUENTIAL_INPUT_OUTPUT_PRESETS.map(preset => preset.input.replace(/^results\//, '')),
        ...(fromPurpose.length > 0 ? fromPurpose : fallback)
    ]);

    return Array.from(merged);
}

function buildSequentialOutputCandidates(selectedInputPath = '') {
    const reviewFilesByPurpose = fileCache.results
        .filter(entry => hasPurpose(entry, 'review_output'))
        .map(entry => entry.name);
    const existingReviewFiles = reviewFilesByPurpose.length > 0
        ? reviewFilesByPurpose
        : fileCache.results
            .filter(entry => entry.extension === '.csv')
            .map(entry => entry.name)
            .filter(name => name.toLowerCase().includes('review'));

    const candidates = [];
    const seen = new Set();

    const pushCandidate = (value, label) => {
        if (!value || seen.has(value)) return;
        seen.add(value);
        candidates.push({ value, label });
    };

    if (selectedInputPath) {
        SEQUENTIAL_INPUT_OUTPUT_PRESETS
            .filter(preset => preset.input === selectedInputPath)
            .forEach(preset => {
                pushCandidate(preset.output, `⭐ ${preset.label}: ${preset.output.replace(/^results\//, '')}`);
            });

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

    SEQUENTIAL_INPUT_OUTPUT_PRESETS.forEach(preset => {
        pushCandidate(preset.output, `${preset.label}: ${preset.output.replace(/^results\//, '')}`);
    });

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
        let staticSettings = [];
        let staticResults = [];

        // files.json から読み込み（GitHub Actionsでプライベートリポジトリのデータから生成）
        // キャッシュ回避のためにタイムスタンプを付与
        const response = await fetch('./files.json?t=' + new Date().getTime());
        if (response.ok) {
            const filesData = await response.json();
            const settingsEntries = filesData.settings || filesData.settings_csv || [];
            const resultEntries = filesData.results || [];
            staticSettings = normalizeFileEntries(settingsEntries, 'settings', inferSettingsPurposes);
            staticResults = normalizeFileEntries(resultEntries, 'results', inferResultsPurposes);
        }

        const [liveSettings, liveResults] = await Promise.all([
            fetchGitHubFileEntries('settings', inferSettingsPurposes),
            fetchGitHubFileEntries('results', inferResultsPurposes)
        ]);

        fileCache.settings = mergeFileEntries(liveSettings, staticSettings);
        fileCache.results = mergeFileEntries(liveResults, staticResults)
            .filter(entry => !shouldHideFromWebapp(entry));
        
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
        const reviewFilesByPurpose = fileCache.results.filter(entry => hasPurpose(entry, 'review_output')).map(entry => entry.name);
        const reviewFiles = reviewFilesByPurpose.length > 0
            ? reviewFilesByPurpose
            : resultsCsvFiles.filter(name => name.toLowerCase().includes('review'));
        populateDropdown('custom_review_file', reviewFiles, 'results');
        
        // FIDファイル
        const fidFilesByPurpose = fileCache.results.filter(entry => hasPurpose(entry, 'fid_input')).map(entry => entry.name);
        const fidFiles = fidFilesByPurpose.length > 0
            ? fidFilesByPurpose
            : resultsCsvFiles.filter(name => {
                const lowerName = name.toLowerCase();
                return lowerName.includes('fid') || lowerName.includes('add_data');
            });
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
        
        // Facility workflow用のドロップダウンを設定
        populateDropdown('facility_custom_address_csv', settingsCsvFiles, 'settings', true);
        populateDropdown('facility_custom_facility_file', facilityFiles, 'results', true);
        populateDropdown('facility_custom_exclude_gids_path', excludeFiles, 'settings', true);
        
    } catch (error) {
        console.error('ファイルオプションの読み込みエラー:', error);
    }
}

// プリセット適用
function applyPreset(presetKey) {
    const preset = PRESETS[currentWorkflow]?.[presetKey];
    if (!preset) return;
    
    // 現在のワークフローのすべてのフィールドをリセット
    const currentForm = document.getElementById(getFormIdForWorkflow(currentWorkflow));
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
    Object.entries(preset.params).forEach(([key, value]) => {
        const input = document.getElementById(key);
        
        if (input) {
            // selectの場合
            if (input.tagName === 'SELECT') {
                // 値が空文字の場合は最初のオプションを選択
                if (value === '') {
                    input.selectedIndex = 0;
                } else {
                    // 指定された値のオプションを探して選択
                    const option = Array.from(input.options).find(opt => opt.value === value);
                    if (option) {
                        input.value = value;
                    }
                }
            } else {
                // text/numberの場合はそのまま設定（空文字も含む）
                input.value = value;
            }
        }
    });
    
    alert(`✅ プリセット「${preset.name}」を適用しました`);
}

function getFormIdForWorkflow(workflow) {
    if (workflow === 'reviews_recent_relevance') {
        return 'form_reviews_sequential';
    }
    return `form_${workflow}`;
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
        btn.setAttribute('aria-label', `プリセット: ${preset.name}。${preset.description}`);
        presetContainer.appendChild(btn);
    });
}

// ワークフロー切り替え
function switchWorkflow() {
    const workflowType = document.getElementById('workflow_type').value;
    if (workflowType && !ALLOWED_WEBAPP_WORKFLOWS.includes(workflowType)) {
        alert('⚠️ このワークフローはWebAppからは選択できません');
        document.getElementById('workflow_type').value = '';
        currentWorkflow = '';
        return;
    }
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
        const targetForm = document.getElementById(getFormIdForWorkflow(workflowType));
        if (targetForm) {
            targetForm.style.display = 'block';
            // 表示フォーム内のrequired要素を有効化
            targetForm.querySelectorAll('[required]').forEach(input => {
                input.disabled = false;
            });
        }
    }

    const relevanceSection = document.getElementById('relevance_settings_section');
    if (relevanceSection) {
        relevanceSection.style.display = workflowType === 'reviews_recent_relevance' ? 'block' : 'none';
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

    if (currentWorkflow === 'reviews_sequential' || currentWorkflow === 'reviews_recent_relevance') {
        const csvFile = document.getElementById('sequential_csv_file')?.value || '';
        const outputFile = document.getElementById('sequential_output_file')?.value || '';
        const outputFileNew = document.getElementById('sequential_output_file_new')?.value.trim() || '';
        const daysBack = parseInt(document.getElementById('sequential_days_back')?.value || '0');
        const startFromBatch = parseInt(document.getElementById('sequential_start_from_batch')?.value || '0');
        const rowsPerBatch = parseInt(document.getElementById('sequential_rows_per_batch')?.value || '0');
        const sequentialMaxParallel = parseInt(document.getElementById('sequential_max_parallel_jobs')?.value || '0');
        const batchWait = parseInt(document.getElementById('sequential_batch_wait')?.value || '0');
        const apiBatchSize = parseInt(document.getElementById('sequential_api_batch_size')?.value || '0');
        const maxWaitMinutes = parseInt(document.getElementById('sequential_max_wait_minutes')?.value || '0');
        const datasetId = document.getElementById('sequential_dataset_id')?.value.trim() || '';
        const skipColumn = document.getElementById('sequential_skip_column')?.value.trim() || '';
        const relevanceRankLimit = parseInt(document.getElementById('sequential_relevance_rank_limit')?.value || '0');
        const serpMaxWorkers = parseInt(document.getElementById('sequential_serp_max_workers')?.value || '0');
        const serpZoneName = document.getElementById('sequential_serp_zone_name')?.value.trim() || '';
        const summaryFile = document.getElementById('sequential_summary_file')?.value.trim() || '';

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
        if (!Number.isInteger(sequentialMaxParallel) || sequentialMaxParallel < 1 || sequentialMaxParallel > 3) {
            errors.push('max_parallel_jobs は1〜3の整数を指定してください');
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
        if (currentWorkflow === 'reviews_recent_relevance') {
            if (!Number.isInteger(relevanceRankLimit) || relevanceRankLimit < 1) {
                errors.push('relevance_rank_limit は1以上の整数を指定してください');
            }
            if (!Number.isInteger(serpMaxWorkers) || serpMaxWorkers < 1 || serpMaxWorkers > 3) {
                errors.push('serp_max_workers は1〜3の整数を指定してください');
            }
            if (!serpZoneName) {
                errors.push('serp_zone_name を入力してください');
            }
            if (!summaryFile) {
                errors.push('summary_file を入力してください');
            }
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

    if (!ALLOWED_WEBAPP_WORKFLOWS.includes(currentWorkflow)) {
        alert('⚠️ このワークフローはWebAppからは実行できません');
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
        case 'reviews_recent_relevance':
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
            data.max_parallel_jobs = document.getElementById('sequential_max_parallel_jobs').value;
            data.batch_wait = document.getElementById('sequential_batch_wait').value;
            data.api_batch_size = document.getElementById('sequential_api_batch_size').value;
            data.max_wait_minutes = document.getElementById('sequential_max_wait_minutes').value;
            data.dataset_id = document.getElementById('sequential_dataset_id').value.trim();
            data.skip_column = document.getElementById('sequential_skip_column').value.trim();
            data.generate_report = document.getElementById('sequential_generate_report').checked;
            const reportDaysValue = document.getElementById('sequential_report_days').value.trim();
            data.report_days = reportDaysValue || null; // 空の場合はnull（全期間を意味する）
            if (currentWorkflow === 'reviews_recent_relevance') {
                data.relevance_rank_limit = document.getElementById('sequential_relevance_rank_limit').value;
                data.serp_max_workers = document.getElementById('sequential_serp_max_workers').value;
                data.serp_zone_name = document.getElementById('sequential_serp_zone_name').value.trim();
                const summaryFileValue = document.getElementById('sequential_summary_file').value.trim();
                data.summary_file = summaryFileValue.startsWith('results/') ? summaryFileValue : `results/${summaryFileValue}`;
            }
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

    if (currentWorkflow === 'reviews_sequential' || currentWorkflow === 'reviews_recent_relevance') {
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
        'reviews_recent_relevance': '/run-reviews-relevance',
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
        case 'reviews_recent_relevance':
            body += data.workflow === 'reviews_recent_relevance'
                ? `### ⭐ レビュー取得・30日関連度ランク付き\n\n`
                : `### ⚡ レビュー取得・新仕様逐次実行\n\n`;
            body += `- **入力CSV**: \`${data.csv_file}\`\n`;
            body += `- **出力CSV**: \`${data.output_file}\`\n`;
            body += `- **Days back**: ${data.days_back}日\n`;
            body += `- **開始バッチ**: ${data.start_from_batch}\n`;
            body += `- **1バッチ行数**: ${data.rows_per_batch}\n`;
            body += `- **最大並列バッチ数**: ${data.max_parallel_jobs}バッチ同時実行\n`;
            body += `- **バッチ間待機**: ${data.batch_wait}秒\n`;
            body += `- **API Batch Size**: ${data.api_batch_size}\n`;
            body += `- **待機時間上限**: ${data.max_wait_minutes}分\n`;
            body += `- **Dataset ID**: \`${data.dataset_id}\`\n`;
            body += `- **Skip column**: \`${data.skip_column}\`\n`;
            if (data.workflow === 'reviews_recent_relevance') {
                body += `- **関連度ランク上限**: ${data.relevance_rank_limit}位\n`;
                body += `- **SERP API並列数**: ${data.serp_max_workers}\n`;
                body += `- **SERP Zone**: \`${data.serp_zone_name}\`\n`;
                body += `- **サマリーCSV**: \`${data.summary_file}\`\n`;
            }
            body += `- **レポート生成**: ${data.generate_report ? '有効' : '無効'}\n`;
            if (data.report_days) {
                body += `- **レポート日数**: ${data.report_days}日\n`;
            }
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
    if (!issueData || !issueData.body) {
        alert('⚠️ エラー: Issue データが見つかりません。もう一度やり直してください。');
        return;
    }
    
    const workflowNames = {
        'reviews': 'Reviews Job',
        'reviews_sequential': 'Reviews Sequential Job',
        'reviews_recent_relevance': 'Reviews Relevance Job',
        'facility': 'Facility Job'
    };
    
    const title = `[${workflowNames[currentWorkflow]}] ${new Date().toISOString().split('T')[0]}`;
    const body = encodeURIComponent(issueData.body);
    const url = `https://github.com/${GITHUB_OWNER}/${GITHUB_REPO}/issues/new?title=${encodeURIComponent(title)}&body=${body}`;
    
    // ポップアップを開く
    const newWindow = window.open(url, '_blank');
    
    if (!newWindow || newWindow.closed || typeof newWindow.closed === 'undefined') {
        alert('⚠️ ポップアップがブロックされました。\n\nBraveの設定で「このサイトのポップアップを許可」してください。\n\n以下のURLをコピーしてブラウザで開いてください:\n' + url);
        
        // クリップボードにコピーを試みる
        if (navigator.clipboard) {
            navigator.clipboard.writeText(url).catch(err => {
                console.error('クリップボードへのコピー失敗');
            });
        }
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
