#!/usr/bin/env python3
"""利用可能なデータセット一覧を取得"""

import requests
import json

API_TOKEN = '51396ae0-f0b3-4897-87e9-de2441a65976'

headers = {"Authorization": f"Bearer {API_TOKEN}"}

# データセット一覧を取得
url = "https://api.brightdata.com/datasets/v3"
resp = requests.get(url, headers=headers)

print("=" * 60)
print("📋 利用可能なデータセット一覧")
print("=" * 60)

if resp.status_code == 200:
    datasets = resp.json()
    
    # Google Maps関連のみフィルタ
    for ds in datasets:
        name = ds.get('name', '')
        dataset_id = ds.get('id', '')
        if 'maps' in name.lower() or 'google' in name.lower():
            print(f"\n📌 {name}")
            print(f"   ID: {dataset_id}")
            print(f"   Type: {ds.get('type', 'N/A')}")
else:
    print(f"エラー: {resp.status_code}")
    print(resp.text)
