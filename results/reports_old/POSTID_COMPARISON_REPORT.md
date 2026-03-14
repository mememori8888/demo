# PostID比較分析レポート

**作成日**: 2025年12月3日  
**分析対象**: integrated_data_updated vs extracted

---

## 📊 エグゼクティブサマリー

2つのデータシート間でPostIDの照合を実施しました。結果、**extractedシートのデータの86.2%がintegrated_data_updatedシートに含まれている**ことが確認されました。

### 主要な発見事項

| 項目 | 件数 | 割合 |
|------|------|------|
| **extractedのデータがintegrated_data_updatedに存在** | 60,142件 | **86.2%** |
| extractedのみに存在（未統合） | 9,600件 | 13.8% |
| integrated_data_updatedのみに存在 | 14,141件 | 19.0% |

---

## 📈 詳細分析

### 1. データ概要

#### integrated_data_updated シート
- **総行数**: 74,291行
- **ユニークPostID数**: 74,283件
- **重複PostID**: 8件（0.01%）

#### extracted シート
- **総行数**: 69,742行
- **ユニークPostID数**: 69,742件
- **重複PostID**: 0件

### 2. 一致状況

```
extractedシートの全69,742件のうち:

✓ 60,142件 (86.2%) → integrated_data_updatedに存在
✗  9,600件 (13.8%) → integrated_data_updatedに未登録
```

**解釈**: extractedシートのデータの大部分（86.2%）は既にintegrated_data_updatedに統合済みです。

### 3. 差分分析

#### A. extractedのみに存在する9,600件について

これらは以下のいずれかに該当する可能性があります:

1. **新規データ**: extractedに新しく追加されたが、まだintegrated_data_updatedに統合されていない
2. **抽出条件の違い**: extractedの抽出条件により取得されたが、integrated_data_updatedには含まれない施設
3. **データ更新のタイムラグ**: データ更新のタイミングの違いによる一時的な差分

**推奨アクション**: これら9,600件のデータを確認し、integrated_data_updatedへの統合が必要か判断する

#### B. integrated_data_updatedのみに存在する14,141件について

これらは以下のケースが考えられます:

1. **過去データ**: 以前に統合されたが、extractedの最新抽出には含まれていない
2. **削除された施設**: extractedからは除外されたが、integrated_data_updatedには履歴として残っている
3. **別ソースからのデータ**: extractedとは異なるデータソースから統合された施設

**状況**: これらのデータはintegrated_data_updatedに存在するため、データの欠損ではありません

---

## 🎯 結論と推奨事項

### 結論

1. **データ統合率は良好**: 86.2%の一致率は高い統合度を示しています
2. **データ品質は安定**: integrated_data_updatedの重複はほぼゼロ（0.01%）で、データ品質は良好です
3. **未統合データが存在**: 9,600件のextractedデータが未統合です

### 推奨事項

#### 優先度：高
- [ ] **未統合9,600件の確認**: extractedのみに存在する9,600件のデータを確認
  - 新規データとして統合すべきか判断
  - 統合不要な理由があるか確認

#### 優先度：中
- [ ] **差分データの定期監視**: 今後も定期的にPostID比較を実施し、差分を監視
- [ ] **統合プロセスの見直し**: データ統合のタイミングやプロセスを最適化

#### 優先度：低
- [ ] **重複データの調査**: integrated_data_updatedの8件の重複PostIDを調査

---

## 📁 出力ファイル

詳細な比較結果は以下のファイルに保存されています:

**ファイル名**: `results/postid_comparison.csv`

### ファイル内容
| カラム | 説明 |
|--------|------|
| PostID | 施設のPostID |
| Status | データの存在状況（両方に存在/integrated_data_updatedのみ/extractedのみ） |
| in_integrated | integrated_data_updatedに存在するか（Yes/No） |
| in_extracted | extractedに存在するか（Yes/No） |

---

## 📞 お問い合わせ

本レポートに関するご質問やさらなる分析が必要な場合は、お気軽にお問い合わせください。

---

**分析実施日時**: 2025年12月3日 03:50  
**分析スクリプト**: `compare_postid.py`
