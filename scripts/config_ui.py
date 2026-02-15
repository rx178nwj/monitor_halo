#!/usr/bin/env python3
"""
見守りハロ - 設定UI
Webブラウザで設定ファイルを簡単に作成・編集
"""

from flask import Flask, render_template_string, request, jsonify
import json
from pathlib import Path
import os

app = Flask(__name__)

# パス設定
CONFIG_DIR = Path(__file__).parent.parent / "config"
CONFIG_FILE = CONFIG_DIR / "settings.json"
EXAMPLE_FILE = CONFIG_DIR / "settings.example.json"

# デフォルト設定
DEFAULT_CONFIG = {
    "camera": {
        "host": "192.168.1.100",
        "rtsp_port": 554,
        "onvif_port": 2020,
        "username": "",
        "password": "",
        "scan_positions": [-30, 0, 30],
        "home_position": 0
    },
    "scan_intervals": {
        "not_detected": 300,
        "detected_once": 600,
        "detected_active": 1200,
        "night_mode": 1800
    },
    "night_mode": {
        "enabled": True,
        "start_time": "23:00",
        "end_time": "06:00"
    },
    "tracking": {
        "enabled": True,
        "duration": 60,
        "center_tolerance": 0.1
    },
    "fall_detection": {
        "recheck_delay": 30,
        "lying_threshold": 60,
        "position_tolerance": 50,
        "similarity_threshold": 0.85
    },
    "alerts": {
        "morning_check_time": "10:00",
        "inactivity_hours": 6,
        "night_activity_start": "02:00",
        "night_activity_end": "05:00"
    },
    "notifications": {
        "email": {
            "enabled": True,
            "smtp_server": "smtp.gmail.com",
            "smtp_port": 587,
            "sender": "",
            "password": "",
            "recipient": ""
        },
        "daily_report_time": "21:00"
    },
    "privacy": {
        "save_images": False,
        "save_test_images": True,
        "test_image_path": str(Path(__file__).parent.parent / "data" / "test_images"),
        "data_retention_days": 30
    }
}

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>見守りハロ - 設定</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans JP', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }

        .container {
            max-width: 900px;
            margin: 0 auto;
            background: white;
            border-radius: 16px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
        }

        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }

        .header h1 {
            font-size: 2em;
            margin-bottom: 10px;
        }

        .header p {
            opacity: 0.9;
            font-size: 0.95em;
        }

        .content {
            padding: 30px;
        }

        .section {
            margin-bottom: 30px;
            padding: 20px;
            background: #f8f9fa;
            border-radius: 8px;
            border-left: 4px solid #667eea;
        }

        .section h2 {
            color: #333;
            margin-bottom: 20px;
            font-size: 1.3em;
            display: flex;
            align-items: center;
        }

        .section h2::before {
            content: "📋";
            margin-right: 10px;
        }

        .form-group {
            margin-bottom: 20px;
        }

        .form-row {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
        }

        label {
            display: block;
            margin-bottom: 8px;
            color: #555;
            font-weight: 500;
            font-size: 0.9em;
        }

        input[type="text"],
        input[type="number"],
        input[type="password"],
        input[type="time"] {
            width: 100%;
            padding: 12px;
            border: 2px solid #e0e0e0;
            border-radius: 6px;
            font-size: 0.95em;
            transition: border-color 0.3s;
        }

        input:focus {
            outline: none;
            border-color: #667eea;
        }

        input[type="checkbox"] {
            width: 20px;
            height: 20px;
            margin-right: 8px;
            cursor: pointer;
        }

        .checkbox-label {
            display: flex;
            align-items: center;
            cursor: pointer;
        }

        .help-text {
            font-size: 0.85em;
            color: #666;
            margin-top: 5px;
        }

        .button-group {
            display: flex;
            gap: 15px;
            margin-top: 30px;
            padding-top: 20px;
            border-top: 2px solid #e0e0e0;
        }

        button {
            flex: 1;
            padding: 15px 30px;
            font-size: 1em;
            font-weight: 600;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.3s;
        }

        .btn-save {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }

        .btn-save:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(102, 126, 234, 0.3);
        }

        .btn-test {
            background: #28a745;
            color: white;
        }

        .btn-test:hover {
            background: #218838;
            transform: translateY(-2px);
        }

        .status {
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 15px 25px;
            border-radius: 8px;
            color: white;
            font-weight: 600;
            display: none;
            animation: slideIn 0.3s;
            z-index: 1000;
        }

        .status.success {
            background: #28a745;
        }

        .status.error {
            background: #dc3545;
        }

        @keyframes slideIn {
            from {
                transform: translateX(400px);
                opacity: 0;
            }
            to {
                transform: translateX(0);
                opacity: 1;
            }
        }

        .warning-box {
            background: #fff3cd;
            border: 2px solid #ffc107;
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 20px;
        }

        .warning-box strong {
            color: #856404;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🤖 見守りハロ</h1>
            <p>設定ファイル編集</p>
        </div>

        <div class="content">
            <div class="warning-box">
                <strong>⚠️ セキュリティ注意:</strong> この画面にはカメラのパスワードやメール設定が含まれます。設定完了後はこのサーバーを停止してください。
            </div>

            <form id="configForm">
                <!-- カメラ設定 -->
                <div class="section">
                    <h2>カメラ設定</h2>
                    <div class="form-row">
                        <div class="form-group">
                            <label for="camera_host">カメラIPアドレス *</label>
                            <input type="text" id="camera_host" name="camera.host" required>
                            <div class="help-text">例: 192.168.1.100</div>
                        </div>
                        <div class="form-group">
                            <label for="camera_username">ユーザー名 *</label>
                            <input type="text" id="camera_username" name="camera.username" required>
                        </div>
                    </div>
                    <div class="form-row">
                        <div class="form-group">
                            <label for="camera_password">パスワード *</label>
                            <input type="password" id="camera_password" name="camera.password" required>
                        </div>
                        <div class="form-group">
                            <label for="camera_rtsp_port">RTSPポート</label>
                            <input type="number" id="camera_rtsp_port" name="camera.rtsp_port" value="554">
                        </div>
                    </div>
                    <div class="form-group">
                        <label for="camera_onvif_port">ONVIFポート</label>
                        <input type="number" id="camera_onvif_port" name="camera.onvif_port" value="2020">
                    </div>
                </div>

                <!-- メール通知設定 -->
                <div class="section">
                    <h2>メール通知設定</h2>
                    <div class="form-group">
                        <label class="checkbox-label">
                            <input type="checkbox" id="email_enabled" name="notifications.email.enabled" checked>
                            メール通知を有効化
                        </label>
                    </div>
                    <div class="form-row">
                        <div class="form-group">
                            <label for="email_sender">送信元メールアドレス *</label>
                            <input type="text" id="email_sender" name="notifications.email.sender" required>
                            <div class="help-text">例: your-email@gmail.com</div>
                        </div>
                        <div class="form-group">
                            <label for="email_password">アプリパスワード *</label>
                            <input type="password" id="email_password" name="notifications.email.password" required>
                            <div class="help-text">Gmailの場合はアプリパスワードを使用</div>
                        </div>
                    </div>
                    <div class="form-group">
                        <label for="email_recipient">送信先メールアドレス *</label>
                        <input type="text" id="email_recipient" name="notifications.email.recipient" required>
                    </div>
                    <div class="form-row">
                        <div class="form-group">
                            <label for="email_server">SMTPサーバー</label>
                            <input type="text" id="email_server" name="notifications.email.smtp_server" value="smtp.gmail.com">
                        </div>
                        <div class="form-group">
                            <label for="email_port">SMTPポート</label>
                            <input type="number" id="email_port" name="notifications.email.smtp_port" value="587">
                        </div>
                    </div>
                </div>

                <!-- スキャン間隔設定 -->
                <div class="section">
                    <h2>スキャン間隔設定（秒）</h2>
                    <div class="form-row">
                        <div class="form-group">
                            <label for="interval_not_detected">未検出時の間隔</label>
                            <input type="number" id="interval_not_detected" name="scan_intervals.not_detected" value="300">
                            <div class="help-text">デフォルト: 300秒（5分）</div>
                        </div>
                        <div class="form-group">
                            <label for="interval_detected">検出時の間隔</label>
                            <input type="number" id="interval_detected" name="scan_intervals.detected_once" value="600">
                            <div class="help-text">デフォルト: 600秒（10分）</div>
                        </div>
                    </div>
                    <div class="form-row">
                        <div class="form-group">
                            <label for="interval_active">活動中の間隔</label>
                            <input type="number" id="interval_active" name="scan_intervals.detected_active" value="1200">
                            <div class="help-text">デフォルト: 1200秒（20分）</div>
                        </div>
                        <div class="form-group">
                            <label for="interval_night">夜間モードの間隔</label>
                            <input type="number" id="interval_night" name="scan_intervals.night_mode" value="1800">
                            <div class="help-text">デフォルト: 1800秒（30分）</div>
                        </div>
                    </div>
                </div>

                <!-- 夜間モード設定 -->
                <div class="section">
                    <h2>夜間モード設定</h2>
                    <div class="form-group">
                        <label class="checkbox-label">
                            <input type="checkbox" id="night_enabled" name="night_mode.enabled" checked>
                            夜間モードを有効化
                        </label>
                    </div>
                    <div class="form-row">
                        <div class="form-group">
                            <label for="night_start">開始時刻</label>
                            <input type="time" id="night_start" name="night_mode.start_time" value="23:00">
                        </div>
                        <div class="form-group">
                            <label for="night_end">終了時刻</label>
                            <input type="time" id="night_end" name="night_mode.end_time" value="06:00">
                        </div>
                    </div>
                </div>

                <!-- 人物追尾設定 -->
                <div class="section">
                    <h2>人物追尾設定</h2>
                    <div class="form-group">
                        <label class="checkbox-label">
                            <input type="checkbox" id="tracking_enabled" name="tracking.enabled" checked>
                            人物追尾機能を有効化
                        </label>
                        <div class="help-text">人物を検出したら自動的に追尾します</div>
                    </div>
                    <div class="form-row">
                        <div class="form-group">
                            <label for="tracking_duration">追尾時間（秒）</label>
                            <input type="number" id="tracking_duration" name="tracking.duration" value="60">
                            <div class="help-text">人物を追尾する時間</div>
                        </div>
                        <div class="form-group">
                            <label for="tracking_tolerance">中心許容範囲（0-1）</label>
                            <input type="number" step="0.01" id="tracking_tolerance" name="tracking.center_tolerance" value="0.1">
                            <div class="help-text">画面中心の判定範囲（0.1 = 10%）</div>
                        </div>
                    </div>
                </div>

                <!-- 転倒検知設定 -->
                <div class="section">
                    <h2>転倒検知設定</h2>
                    <div class="form-row">
                        <div class="form-group">
                            <label for="fall_recheck">再確認までの待機時間（秒）</label>
                            <input type="number" id="fall_recheck" name="fall_detection.recheck_delay" value="30">
                        </div>
                        <div class="form-group">
                            <label for="fall_threshold">横たわり判定時間（秒）</label>
                            <input type="number" id="fall_threshold" name="fall_detection.lying_threshold" value="60">
                        </div>
                    </div>
                    <div class="form-row">
                        <div class="form-group">
                            <label for="fall_position">位置変化許容値（px）</label>
                            <input type="number" id="fall_position" name="fall_detection.position_tolerance" value="50">
                        </div>
                        <div class="form-group">
                            <label for="fall_similarity">画像類似度閾値（0-1）</label>
                            <input type="number" step="0.01" id="fall_similarity" name="fall_detection.similarity_threshold" value="0.85">
                        </div>
                    </div>
                </div>

                <!-- アラート設定 -->
                <div class="section">
                    <h2>アラート設定</h2>
                    <div class="form-row">
                        <div class="form-group">
                            <label for="alert_morning">朝の確認時刻</label>
                            <input type="time" id="alert_morning" name="alerts.morning_check_time" value="10:00">
                        </div>
                        <div class="form-group">
                            <label for="alert_inactivity">無活動アラート（時間）</label>
                            <input type="number" id="alert_inactivity" name="alerts.inactivity_hours" value="6">
                        </div>
                    </div>
                </div>

                <!-- プライバシー設定 -->
                <div class="section">
                    <h2>プライバシー設定</h2>
                    <div class="form-group">
                        <label class="checkbox-label">
                            <input type="checkbox" id="privacy_save" name="privacy.save_images">
                            画像を保存する（推奨: オフ）
                        </label>
                    </div>
                    <div class="form-group">
                        <label class="checkbox-label">
                            <input type="checkbox" id="privacy_test" name="privacy.save_test_images" checked>
                            テスト画像を保存する
                        </label>
                    </div>
                    <div class="form-group">
                        <label for="privacy_retention">データ保持期間（日）</label>
                        <input type="number" id="privacy_retention" name="privacy.data_retention_days" value="30">
                    </div>
                </div>

                <div class="button-group">
                    <button type="button" class="btn-test" onclick="testConnection()">接続テスト</button>
                    <button type="submit" class="btn-save">設定を保存</button>
                </div>
            </form>
        </div>
    </div>

    <div id="status" class="status"></div>

    <script>
        // 設定を読み込み
        fetch('/api/config')
            .then(res => res.json())
            .then(config => {
                loadConfig(config);
            });

        function loadConfig(config) {
            // フォームに値をセット
            const form = document.getElementById('configForm');
            const inputs = form.querySelectorAll('input');

            inputs.forEach(input => {
                const name = input.getAttribute('name');
                if (!name) return;

                const value = getNestedValue(config, name);

                if (input.type === 'checkbox') {
                    input.checked = value === true;
                } else if (input.type === 'time') {
                    input.value = value || '';
                } else {
                    input.value = value || '';
                }
            });
        }

        function getNestedValue(obj, path) {
            return path.split('.').reduce((prev, curr) => prev?.[curr], obj);
        }

        function setNestedValue(obj, path, value) {
            const keys = path.split('.');
            const lastKey = keys.pop();
            const target = keys.reduce((prev, curr) => {
                if (!prev[curr]) prev[curr] = {};
                return prev[curr];
            }, obj);
            target[lastKey] = value;
        }

        // フォーム送信
        document.getElementById('configForm').addEventListener('submit', async (e) => {
            e.preventDefault();

            const formData = new FormData(e.target);
            const config = {};

            // フォームデータを構造化
            for (const [name, value] of formData.entries()) {
                let finalValue = value;

                // 型変換
                const input = document.querySelector(`[name="${name}"]`);
                if (input.type === 'number') {
                    finalValue = parseFloat(value);
                } else if (input.type === 'checkbox') {
                    finalValue = input.checked;
                }

                setNestedValue(config, name, finalValue);
            }

            // 固定値を追加
            config.camera.scan_positions = [-30, 0, 30];
            config.camera.home_position = 0;
            config.notifications.daily_report_time = "21:00";
            config.alerts.night_activity_start = "02:00";
            config.alerts.night_activity_end = "05:00";

            // サーバーに送信
            try {
                const response = await fetch('/api/config', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(config)
                });

                const result = await response.json();

                if (result.success) {
                    showStatus('設定を保存しました！', 'success');
                } else {
                    showStatus('保存に失敗しました: ' + result.error, 'error');
                }
            } catch (error) {
                showStatus('エラー: ' + error.message, 'error');
            }
        });

        function showStatus(message, type) {
            const status = document.getElementById('status');
            status.textContent = message;
            status.className = 'status ' + type;
            status.style.display = 'block';

            setTimeout(() => {
                status.style.display = 'none';
            }, 3000);
        }

        async function testConnection() {
            showStatus('接続テスト中...', 'success');
            // TODO: 実装
            setTimeout(() => {
                showStatus('接続テスト機能は開発中です', 'error');
            }, 1000);
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    """メインページ"""
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/config', methods=['GET'])
def get_config():
    """現在の設定を取得"""
    try:
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
        elif EXAMPLE_FILE.exists():
            with open(EXAMPLE_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
        else:
            config = DEFAULT_CONFIG

        return jsonify(config)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/config', methods=['POST'])
def save_config():
    """設定を保存"""
    try:
        config = request.get_json()

        # ディレクトリ作成
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)

        # 保存
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == '__main__':
    print("=" * 60)
    print("🤖 見守りハロ - 設定UI")
    print("=" * 60)
    print()
    print("ブラウザで以下のURLを開いてください:")
    print("  http://localhost:5000")
    print()
    print("または同じネットワーク上の他のデバイスから:")
    print(f"  http://{os.popen('hostname -I').read().split()[0]}:5000")
    print()
    print("⚠️  設定完了後は Ctrl+C でこのサーバーを停止してください")
    print("=" * 60)
    print()

    app.run(host='0.0.0.0', port=5000, debug=False)
