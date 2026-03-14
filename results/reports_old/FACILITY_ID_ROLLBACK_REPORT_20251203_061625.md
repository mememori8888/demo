# 施設IDロールバックレポート

**作成日**: 2025年12月03日 06:20  
**実行スクリプト**: `rollback_facility_id.py`

---

## 📊 エグゼクティブサマリー

`update_facility_id_from_googlemap.py`で更新した施設IDを元の状態（空白）に戻しました。

### 主要な数値

| 項目 | 件数 |
|------|------|
| **更新ログに記録された件数** | 12,506件 |
| **実際にロールバックした件数** | 12,506件 |

---

## 📈 詳細

### ロールバック内容

更新ログファイル（`results/facility_id_update_log_20251203_055509.csv`）を使用して、以下の処理を実行しました:

1. 更新ログから施設GIDのリストを取得
2. integrated_data_updatedシートから該当する施設を検索
3. 施設ID列を空白に更新

### 対象施設（サンプル20件）

| PostID | 施設名 | 施設GID |
|--------|--------|---------|
| nan | 医療法人社団 北翔会 石田歯科クリニック | ChIJCX5GfVQoC18RhGxRpHCSHOI |
| nan | 北海道江別市-歯科江別診療室 | ChIJvYwKj2YtC18R5fWXwqeusCQ |
| nan | 北海道札幌市中央区-ラポール歯科医院 | ChIJLb4rZnApC18RQIAbYRXDjTI |
| nan | さわむら歯科 | ChIJte-kpqIoC18Ri3Fg6NjxUg0 |
| nan | 北海道札幌市中央区-宇治矯正歯科クリニック | ChIJc6HCQIMpC18R7fLTQru3rfQ |
| nan | 坂本歯科 | ChIJOSIcSIMpC18R_AX4greSfG8 |
| nan | 北海道室蘭市-みうら歯科医院 | ChIJG7XRROXbn18Rh6UtNae6gP0 |
| nan | 円山さくらぎ矯正歯科 | ChIJ6SygeuopC18R8mlwP18lDT8 |
| nan | ネオステラ歯科クリニック | ChIJH4L9UHsqC18RVjrVIjW6ajg |
| nan | 樋口歯科クリニック | ChIJ9Q6ZNScrC18RWdBWYngroAE |
| nan | 北海道札幌市豊平区-あさひまち歯科クリニック | ChIJc9xhVykqC18Rpx02KkFm17o |
| nan | 北海道札幌市豊平区-月寒中央歯科医院 | ChIJ9c6MuFYqC18RulGYOX2tW40 |
| nan | 手稲ホワイト歯科 | ChIJESlolq8nC18R7NBDQybod9A |
| nan | 北海道札幌市手稲区-あけぼの歯科医院 | ChIJi810f-QmC18RQZd-XOQ42PE |
| nan | 北海道札幌市清田区-イオンタウンかも歯科 | ChIJtyiS_iXVdF8RnRB6kiThBF0 |
| nan | 医療法人社団優歯会 なかさと歯科クリニック | ChIJlfzVHWTVCl8RcJ003kkGcog |
| nan | 医療法人社団 加藤歯科医院 | ChIJawe-JG8pC18R-AUFry7d6iQ |
| nan | 北海道旭川市-こばやし歯科クリニック（豊岡四条１０） | ChIJFVUTPgDnDF8R_IAA-RYfv3I |
| nan | 坂祝歯科医院 | ChIJp78LnDwQA2ARNSEoPx3JLy8 |
| nan | 北海道室蘭市-福田歯科 | ChIJN4v2ZBban18RWujaba3TgMs |

*全12,506件のうち20件を表示。*


---

## 🎯 結論

### 成功

✅ **12,506件の施設IDをロールバックしました**

施設ID列が空白に戻り、更新前の状態に復元されました。

---

## 📁 関連ファイル

### スプレッドシート
- **integrated_data_updated**: [スプレッドシート](https://docs.google.com/spreadsheets/d/1e5-_yU-zC6s8rvywalesuS__74TJTesDj02UPik2G38/edit)

### 入力ファイル
- **更新ログ**: `results/facility_id_update_log_20251203_055509.csv`

---

## 💡 推奨事項

1. **データ確認**: ロールバック後のデータが正しく元に戻っているか確認してください
2. **再更新時の注意**: 再度更新する場合は、照合ロジックを見直してから実行してください
3. **ログ保管**: 今回のロールバックログも保管しておくことを推奨します

---

**分析実施日時**: 2025年12月03日 06:20  
**分析スクリプト**: `rollback_facility_id.py`
