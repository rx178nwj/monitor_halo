# 🤖 見守りハロ (Mimamori Halo)

プライバシー重視の高齢者見守りシステム

## 📋 概要

**見守りハロ**は、Tapo C220カメラとYOLOv8を使用した、一人暮らしの方の安全を見守るシステムです。

### 特徴

- ✅ **プライバシー重視** - 画像は保存せず、検出データのみ記録
- ✅ **適応的スキャン** - 検出状況に応じて間隔を自動調整
- ✅ **転倒検知** - 横たわっている姿勢を検出し、緊急アラート
- ✅ **画像比較** - 前回検出と比較して同じ位置かを精密判定
- ✅ **夜間モード** - 指定時間帯は監視間隔を延長

## 🎯 機能

### 検知機能

1. **活動検知**
   - 10分おきにエリアスキャン
   - 人物の位置と姿勢を記録
   - 1日の活動パターンを分析

2. **転倒検知**
   - 横たわっている姿勢を検出
   - 30秒後に再確認
   - 継続していれば緊急アラート

3. **異常検知**
   - 6時間以上の無活動
   - 朝10時までの未活動
   - 深夜2-5時の異常な活動

### スキャンロジック

```
状態1: 未検出モード（5分間隔）
  └─ 人検出 → 状態2へ

状態2: 活動確認モード（10分間隔）
  ├─ 移動検出 → 継続
  └─ 同じ位置 → 姿勢チェック
      ├─ 立っている/座っている → 状態3へ
      └─ 横たわっている → 転倒検知

状態3: 正常活動モード（20分間隔）
  └─ 通常監視

夜間モード（23:00-6:00）: 30分間隔
```

## 🚀 使い方

### 1. 依存関係のインストール

```bash
pip install -r requirements.txt
```

### 2. YOLOv8モデルのダウンロード

```bash
# YOLOv8 nanoモデルを自動ダウンロード（初回実行時）
# または手動でダウンロード
wget https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8n.pt
```

### 3. 設定ファイルの作成

**方法1: Web UIで設定（推奨）**

```bash
# 設定UIを起動
python3 scripts/config_ui.py

# ブラウザで http://localhost:5000 を開く
# フォームに必要な情報を入力して保存
```

**方法2: 手動で設定**

```bash
cp config/settings.example.json config/settings.json
nano config/settings.json
```

**必須設定項目:**
- カメラ設定（`camera`）
  - `host`: カメラのIPアドレス
  - `username`: カメラのユーザー名
  - `password`: カメラのパスワード
- メール通知設定（`notifications.email`）
  - `sender`: 送信元メールアドレス
  - `password`: アプリパスワード（Gmailの場合）
  - `recipient`: 送信先メールアドレス

### 4. 監視を開始

```bash
python3 scripts/monitor.py
```

### 5. ダッシュボードで状態確認（オプション）

監視システムとは別に、Webダッシュボードで現在の状態を確認できます。

```bash
# ダッシュボードを起動
python3 scripts/dashboard.py

# ブラウザで http://localhost:5001 を開く
```

**ダッシュボードの機能:**
- 📊 リアルタイムの監視状態表示
- 📈 本日の活動統計（検出回数、活動時間など）
- 📅 時間別活動グラフ
- 📝 最近の検出履歴
- 🔔 アラート表示
- 🔄 自動更新（30秒ごと）

### 6. バックグラウンド実行（systemd）

```bash
# サービスファイル作成
sudo nano /etc/systemd/system/mimamori-halo.service
```

```ini
[Unit]
Description=Mimamori Halo - Guardian System
After=network.target

[Service]
Type=simple
User=YOUR_USERNAME
WorkingDirectory=/path/to/mimamori_halo
ExecStart=/usr/bin/python3 /path/to/mimamori_halo/scripts/monitor.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# サービス有効化
sudo systemctl enable mimamori-halo
sudo systemctl start mimamori-halo

# 状態確認
sudo systemctl status mimamori-halo

# ログ確認
sudo journalctl -u mimamori-halo -f
```

## 📊 データ構造

### 日次データファイル

`data/YYYY-MM-DD.json`:
```json
{
  "date": "2026-02-14",
  "events": [
    {
      "timestamp": "08:30:15",
      "state": "detected_once",
      "camera_angle": 0,
      "posture": "sitting",
      "confidence": 0.89,
      "same_position": false,
      "similarity": 0.75,
      "position_diff": 120.5
    }
  ],
  "summary": {
    "first_activity": "08:30:15",
    "last_activity": "20:15:30",
    "total_detections": 145,
    "lying_events": 0,
    "alerts": []
  }
}
```

## 🔔 通知

### 緊急アラート（即座）

- 転倒検知
- 6時間以上の無活動
- 朝10時までの未活動

### 日次レポート（21時）

- 本日の活動サマリー
- 初回活動時刻
- 最終活動時刻
- アラートがあれば詳細

## 🔒 プライバシー配慮

- ❌ 画像ファイルは保存しない
- ✅ 検出データ（時刻、姿勢）のみ記録
- ✅ 画像比較用データはメモリ上のみ（最大100KB）
- ✅ テスト時のみ画像保存可能（設定で制御）

## 📁 ディレクトリ構成

```
mimamori_halo/
├── config/
│   ├── settings.json           # 設定ファイル（gitignoreされます）
│   └── settings.example.json   # 設定ファイルのサンプル
├── scripts/
│   ├── monitor.py              # メイン監視スクリプト
│   ├── config_ui.py            # Web設定UI（ポート5000）
│   └── dashboard.py            # Webダッシュボード（ポート5001）
├── data/                       # 日次データ（gitignoreされます）
│   └── YYYY-MM-DD.json
├── logs/                       # ログファイル（gitignoreされます）
│   └── alerts_YYYY-MM.log
├── yolov8n.pt                  # YOLOモデル（初回実行時に自動ダウンロード）
├── requirements.txt
├── .gitignore
├── LICENSE
└── README.md
```

## 🛠️ 必要環境

- Python 3.8以上
- FFmpeg（動画処理用）
- ONVIF対応のネットワークカメラ（Tapo C220など）

### インストール

```bash
# FFmpegのインストール（Ubuntu/Debian）
sudo apt-get install ffmpeg

# Pythonパッケージ
pip install -r requirements.txt
```

## ✨ Web UI機能

### 設定UI（ポート5000）
- カメラ設定の入力フォーム
- メール通知設定
- スキャン間隔・夜間モード設定
- 転倒検知パラメータ調整
- プライバシー設定

### ダッシュボード（ポート5001）
- リアルタイム監視状態表示
- 本日の検出回数・活動時間
- 時間別活動グラフ
- 最近の検出履歴タイムライン
- アラート通知
- 30秒ごとの自動更新

## 📝 TODO

- [ ] メール通知システム実装
- [ ] 日次レポート自動送信
- [ ] 挨拶機能（TTS + Tapo音声）
- [x] Webダッシュボード
- [ ] 複数カメラ対応

## ⚠️ 注意事項

- このシステムは監視カメラを使用します。プライバシーに十分配慮して使用してください
- 本システムは補助的な見守りツールであり、医療機器ではありません
- 緊急時の対応は適切な医療・介護サービスと併用してください

## 🤝 コントリビューション

バグ報告や機能提案は、GitHubのIssuesでお願いします。

## 📄 ライセンス

MIT License - 詳細は [LICENSE](LICENSE) ファイルを参照してください。

---

**注意:** カメラの認証情報やメール設定などの機密情報は、`config/settings.json`に保存され、Gitには含まれません。
