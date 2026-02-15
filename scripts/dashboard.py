#!/usr/bin/env python3
"""
見守りハロ - ダッシュボード
リアルタイムで監視状態を表示
"""

from flask import Flask, render_template_string, jsonify
import json
from pathlib import Path
from datetime import datetime, timedelta
import os

app = Flask(__name__)

# パス設定
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
LOG_DIR = BASE_DIR / "logs"
CONFIG_FILE = BASE_DIR / "config" / "settings.json"

def load_config():
    """設定ファイルを読み込み"""
    try:
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except:
        pass
    return None

def load_today_data():
    """本日のデータを読み込み"""
    today = datetime.now().strftime("%Y-%m-%d")
    data_file = DATA_DIR / f"{today}.json"

    if data_file.exists():
        try:
            with open(data_file, 'r', encoding='utf-8') as f:
                content = f.read()
                # JSONが破損している場合も処理できるようにする
                if content.strip():
                    return json.loads(content)
        except json.JSONDecodeError as e:
            print(f"Warning: JSON decode error in {data_file}: {e}")
            # JSONが破損している場合、1日前のデータを試す
            yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            yesterday_file = DATA_DIR / f"{yesterday}.json"
            if yesterday_file.exists():
                try:
                    with open(yesterday_file, 'r', encoding='utf-8') as f:
                        return json.load(f)
                except:
                    pass
        except Exception as e:
            print(f"Warning: Error loading data file: {e}")
    return None

def load_recent_alerts():
    """最近のアラートを読み込み"""
    alerts = []
    current_month = datetime.now().strftime("%Y-%m")
    log_file = LOG_DIR / f"alerts_{current_month}.log"

    if log_file.exists():
        with open(log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            # 最新10件
            for line in lines[-10:]:
                alerts.append(line.strip())

    return alerts

def get_status_color(minutes_since_last):
    """最終活動からの経過時間に基づいてステータス色を返す"""
    if minutes_since_last is None:
        return "gray"
    elif minutes_since_last < 30:
        return "green"
    elif minutes_since_last < 120:
        return "yellow"
    else:
        return "red"

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>見守りハロ - ダッシュボード</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans JP', sans-serif;
            background: #f0f2f5;
            min-height: 100vh;
            padding: 20px;
        }

        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 16px;
            margin-bottom: 20px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }

        .header h1 {
            font-size: 2em;
            margin-bottom: 10px;
            display: flex;
            align-items: center;
            gap: 15px;
        }

        .header .subtitle {
            opacity: 0.9;
            font-size: 1em;
        }

        .header .last-update {
            margin-top: 10px;
            font-size: 0.9em;
            opacity: 0.8;
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
        }

        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }

        .card {
            background: white;
            border-radius: 12px;
            padding: 25px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            transition: transform 0.2s;
        }

        .card:hover {
            transform: translateY(-4px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }

        .card-title {
            font-size: 0.9em;
            color: #666;
            margin-bottom: 15px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            font-weight: 600;
        }

        .card-value {
            font-size: 2.5em;
            font-weight: 700;
            color: #333;
            margin-bottom: 10px;
        }

        .card-label {
            font-size: 0.9em;
            color: #999;
        }

        .status-indicator {
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 8px;
            animation: pulse 2s infinite;
        }

        .status-green { background: #28a745; }
        .status-yellow { background: #ffc107; }
        .status-red { background: #dc3545; }
        .status-gray { background: #6c757d; animation: none; }

        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }

        .chart-section {
            background: white;
            border-radius: 12px;
            padding: 25px;
            margin-bottom: 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }

        .chart-title {
            font-size: 1.2em;
            font-weight: 600;
            margin-bottom: 20px;
            color: #333;
        }

        .timeline {
            max-height: 400px;
            overflow-y: auto;
        }

        .timeline-item {
            padding: 15px;
            border-left: 3px solid #667eea;
            margin-bottom: 15px;
            background: #f8f9fa;
            border-radius: 4px;
        }

        .timeline-time {
            font-weight: 600;
            color: #667eea;
            margin-bottom: 5px;
        }

        .timeline-content {
            color: #666;
            font-size: 0.95em;
        }

        .timeline-posture {
            display: inline-block;
            padding: 3px 10px;
            border-radius: 12px;
            font-size: 0.85em;
            margin-top: 5px;
        }

        .posture-standing { background: #28a745; color: white; }
        .posture-sitting { background: #ffc107; color: #333; }
        .posture-lying { background: #dc3545; color: white; }

        .alert-box {
            background: #fff3cd;
            border: 2px solid #ffc107;
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 20px;
        }

        .alert-box.danger {
            background: #f8d7da;
            border-color: #dc3545;
        }

        .alert-box strong {
            color: #856404;
        }

        .alert-box.danger strong {
            color: #721c24;
        }

        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            margin-top: 15px;
        }

        .stat-item {
            text-align: center;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 8px;
        }

        .stat-value {
            font-size: 2em;
            font-weight: 700;
            color: #667eea;
        }

        .stat-label {
            font-size: 0.85em;
            color: #666;
            margin-top: 5px;
        }

        .no-data {
            text-align: center;
            padding: 40px;
            color: #999;
            font-size: 1.1em;
        }

        .refresh-btn {
            position: fixed;
            bottom: 30px;
            right: 30px;
            width: 60px;
            height: 60px;
            border-radius: 50%;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            font-size: 1.5em;
            cursor: pointer;
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
            transition: transform 0.2s;
        }

        .refresh-btn:hover {
            transform: scale(1.1);
        }

        .refresh-btn.spinning {
            animation: spin 1s linear;
        }

        @keyframes spin {
            from { transform: rotate(0deg); }
            to { transform: rotate(360deg); }
        }

        .activity-chart {
            display: flex;
            align-items: flex-end;
            height: 200px;
            gap: 5px;
            margin-top: 20px;
        }

        .activity-bar {
            flex: 1;
            background: #667eea;
            border-radius: 4px 4px 0 0;
            position: relative;
            min-height: 10px;
            transition: height 0.3s;
        }

        .activity-bar:hover {
            background: #764ba2;
        }

        .activity-bar-label {
            position: absolute;
            bottom: -25px;
            left: 50%;
            transform: translateX(-50%);
            font-size: 0.75em;
            color: #666;
            white-space: nowrap;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>
                <span>🤖</span>
                <span>見守りハロ</span>
            </h1>
            <div class="subtitle">リアルタイムダッシュボード</div>
            <div class="last-update" id="lastUpdate">最終更新: 読み込み中...</div>
        </div>

        <div id="alertContainer"></div>

        <div class="grid">
            <div class="card">
                <div class="card-title">現在の状態</div>
                <div class="card-value">
                    <span class="status-indicator" id="statusIndicator"></span>
                    <span id="currentStatus">読み込み中...</span>
                </div>
                <div class="card-label" id="statusLabel"></div>
            </div>

            <div class="card">
                <div class="card-title">本日の検出回数</div>
                <div class="card-value" id="totalDetections">-</div>
                <div class="card-label">活動検出</div>
            </div>

            <div class="card">
                <div class="card-title">初回活動時刻</div>
                <div class="card-value" id="firstActivity">-</div>
                <div class="card-label">起床時刻の目安</div>
            </div>

            <div class="card">
                <div class="card-title">最終活動時刻</div>
                <div class="card-value" id="lastActivity">-</div>
                <div class="card-label" id="lastActivityLabel">-</div>
            </div>
        </div>

        <div class="chart-section">
            <div class="chart-title">📊 本日の統計</div>
            <div class="stats-grid">
                <div class="stat-item">
                    <div class="stat-value" id="lyingEvents">0</div>
                    <div class="stat-label">横たわり検出</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value" id="alertCount">0</div>
                    <div class="stat-label">アラート</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value" id="activeHours">0</div>
                    <div class="stat-label">活動時間</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value" id="avgInterval">-</div>
                    <div class="stat-label">平均検出間隔</div>
                </div>
            </div>
        </div>

        <div class="chart-section">
            <div class="chart-title">📅 時間別活動グラフ</div>
            <div class="activity-chart" id="activityChart"></div>
        </div>

        <div class="chart-section">
            <div class="chart-title">📝 最近の検出履歴</div>
            <div class="timeline" id="timeline">
                <div class="no-data">データを読み込み中...</div>
            </div>
        </div>
    </div>

    <button class="refresh-btn" onclick="refreshData()" id="refreshBtn">🔄</button>

    <script>
        let autoRefreshInterval;

        async function refreshData() {
            const btn = document.getElementById('refreshBtn');
            btn.classList.add('spinning');

            try {
                const response = await fetch('/api/status');
                const data = await response.json();
                updateDashboard(data);
            } catch (error) {
                console.error('Error fetching data:', error);
            }

            setTimeout(() => btn.classList.remove('spinning'), 1000);
        }

        function updateDashboard(data) {
            // 最終更新時刻
            document.getElementById('lastUpdate').textContent =
                `最終更新: ${new Date().toLocaleTimeString('ja-JP')}`;

            // アラート表示
            const alertContainer = document.getElementById('alertContainer');
            alertContainer.innerHTML = '';

            if (data.alerts && data.alerts.length > 0) {
                data.alerts.forEach(alert => {
                    const alertBox = document.createElement('div');
                    alertBox.className = alert.type === 'danger' ? 'alert-box danger' : 'alert-box';
                    alertBox.innerHTML = `<strong>${alert.icon} ${alert.title}:</strong> ${alert.message}`;
                    alertContainer.appendChild(alertBox);
                });
            }

            // 現在の状態
            const statusIndicator = document.getElementById('statusIndicator');
            const statusClass = 'status-' + data.status_color;
            statusIndicator.className = 'status-indicator ' + statusClass;

            document.getElementById('currentStatus').textContent = data.current_status;
            document.getElementById('statusLabel').textContent = data.status_label;

            // 統計情報
            document.getElementById('totalDetections').textContent = data.total_detections || 0;
            document.getElementById('firstActivity').textContent = data.first_activity || '-';
            document.getElementById('lastActivity').textContent = data.last_activity || '-';
            document.getElementById('lastActivityLabel').textContent = data.last_activity_label || '-';
            document.getElementById('lyingEvents').textContent = data.lying_events || 0;
            document.getElementById('alertCount').textContent = data.alert_count || 0;
            document.getElementById('activeHours').textContent = data.active_hours || 0;
            document.getElementById('avgInterval').textContent = data.avg_interval || '-';

            // タイムライン
            const timeline = document.getElementById('timeline');
            if (data.recent_events && data.recent_events.length > 0) {
                timeline.innerHTML = data.recent_events.map(event => `
                    <div class="timeline-item">
                        <div class="timeline-time">${event.timestamp}</div>
                        <div class="timeline-content">
                            ${event.description}
                            <span class="timeline-posture posture-${event.posture}">${event.posture_label}</span>
                        </div>
                    </div>
                `).join('');
            } else {
                timeline.innerHTML = '<div class="no-data">本日のデータがありません</div>';
            }

            // 活動グラフ
            const activityChart = document.getElementById('activityChart');
            if (data.hourly_activity && data.hourly_activity.length > 0) {
                const maxCount = Math.max(...data.hourly_activity.map(h => h.count));
                activityChart.innerHTML = data.hourly_activity.map(hour => {
                    const height = maxCount > 0 ? (hour.count / maxCount * 100) : 0;
                    return `
                        <div class="activity-bar" style="height: ${height}%">
                            <div class="activity-bar-label">${hour.hour}時</div>
                        </div>
                    `;
                }).join('');
            } else {
                activityChart.innerHTML = '<div class="no-data">データがありません</div>';
            }
        }

        // 初回読み込み
        refreshData();

        // 自動更新（30秒ごと）
        autoRefreshInterval = setInterval(refreshData, 30000);
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    """ダッシュボードメインページ"""
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/status')
def get_status():
    """現在の状態をJSON形式で返す"""
    today_data = load_today_data()
    config = load_config()

    # デフォルト値
    status = {
        "current_status": "データなし",
        "status_color": "gray",
        "status_label": "監視データが見つかりません",
        "total_detections": 0,
        "first_activity": None,
        "last_activity": None,
        "last_activity_label": "-",
        "lying_events": 0,
        "alert_count": 0,
        "active_hours": 0,
        "avg_interval": "-",
        "recent_events": [],
        "hourly_activity": [],
        "alerts": []
    }

    if today_data:
        summary = today_data.get('summary', {})
        events = today_data.get('events', [])

        # 基本統計
        status['total_detections'] = summary.get('total_detections', 0)
        status['first_activity'] = summary.get('first_activity')
        status['last_activity'] = summary.get('last_activity')
        status['lying_events'] = summary.get('lying_events', 0)
        status['alert_count'] = len(summary.get('alerts', []))

        # 最終活動からの経過時間
        if status['last_activity']:
            try:
                last_time = datetime.strptime(status['last_activity'], "%Y-%m-%d %H:%M:%S")
                now = datetime.now()
                diff = now - last_time
                minutes = int(diff.total_seconds() / 60)

                if minutes < 60:
                    status['last_activity_label'] = f"{minutes}分前"
                else:
                    hours = minutes // 60
                    status['last_activity_label'] = f"{hours}時間前"

                status['status_color'] = get_status_color(minutes)

                if minutes < 30:
                    status['current_status'] = "活動中"
                    status['status_label'] = "正常に活動が検出されています"
                elif minutes < 120:
                    status['current_status'] = "様子見"
                    status['status_label'] = f"最後の検出から{minutes}分経過"
                else:
                    status['current_status'] = "要確認"
                    status['status_label'] = f"最後の検出から{minutes}分経過"
                    status['alerts'].append({
                        'type': 'warning',
                        'icon': '⚠️',
                        'title': '長時間未検出',
                        'message': f'最後の活動検出から{minutes}分経過しています'
                    })
            except:
                pass

        # 活動時間計算
        if status['first_activity'] and status['last_activity']:
            try:
                first = datetime.strptime(status['first_activity'], "%Y-%m-%d %H:%M:%S")
                last = datetime.strptime(status['last_activity'], "%Y-%m-%d %H:%M:%S")
                diff = last - first
                status['active_hours'] = round(diff.total_seconds() / 3600, 1)
            except:
                pass

        # 平均検出間隔
        if len(events) > 1:
            intervals = []
            for i in range(1, len(events)):
                try:
                    t1 = datetime.strptime(events[i-1]['timestamp'], "%Y-%m-%d %H:%M:%S")
                    t2 = datetime.strptime(events[i]['timestamp'], "%Y-%m-%d %H:%M:%S")
                    diff = (t2 - t1).total_seconds() / 60
                    intervals.append(diff)
                except:
                    pass

            if intervals:
                avg = sum(intervals) / len(intervals)
                status['avg_interval'] = f"{int(avg)}分"

        # 最近のイベント（最新20件）
        posture_labels = {
            'standing': '立位',
            'sitting': '座位',
            'lying': '臥位'
        }

        for event in reversed(events[-20:]):
            posture = event.get('posture', 'unknown')
            status['recent_events'].append({
                'timestamp': event.get('timestamp', ''),
                'description': f"カメラ角度: {event.get('camera_angle', 0)}°, 信頼度: {event.get('confidence', 0):.2f}",
                'posture': posture,
                'posture_label': posture_labels.get(posture, '不明')
            })

        # 時間別活動グラフ
        hourly_counts = {}
        for event in events:
            try:
                hour = datetime.strptime(event['timestamp'], "%Y-%m-%d %H:%M:%S").hour
                hourly_counts[hour] = hourly_counts.get(hour, 0) + 1
            except:
                pass

        # 0-23時のデータを生成
        for hour in range(24):
            status['hourly_activity'].append({
                'hour': hour,
                'count': hourly_counts.get(hour, 0)
            })

        # アラート
        if status['lying_events'] > 0:
            status['alerts'].append({
                'type': 'danger',
                'icon': '🚨',
                'title': '転倒検知',
                'message': f'本日{status["lying_events"]}件の横たわり姿勢を検出しました'
            })

    return jsonify(status)

if __name__ == '__main__':
    print("=" * 60)
    print("🤖 見守りハロ - ダッシュボード")
    print("=" * 60)
    print()
    print("ブラウザで以下のURLを開いてください:")
    print("  http://localhost:5001")
    print()
    print("または同じネットワーク上の他のデバイスから:")
    try:
        ip = os.popen('hostname -I').read().split()[0]
        print(f"  http://{ip}:5001")
    except:
        print("  (IPアドレス取得失敗)")
    print()
    print("ℹ️  ダッシュボードは30秒ごとに自動更新されます")
    print("=" * 60)
    print()

    app.run(host='0.0.0.0', port=5001, debug=False)
