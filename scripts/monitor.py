#!/usr/bin/env python3
"""
見守りハロ (Mimamori Halo) - メイン監視スクリプト
お父様の安全を見守ります
"""

import cv2
import numpy as np
import json
import time
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from onvif import ONVIFCamera
from ultralytics import YOLO
from skimage.metrics import structural_similarity as ssim

# 設定読み込み
CONFIG_PATH = Path(__file__).parent.parent / "config" / "settings.json"
with open(CONFIG_PATH, 'r') as f:
    CONFIG = json.load(f)

DATA_DIR = Path(__file__).parent.parent / "data"
LOG_DIR = Path(__file__).parent.parent / "logs"

class MimamoriHalo:
    """見守りハロ - メイン監視クラス"""
    
    def __init__(self):
        print("🤖 見守りハロを起動中...")
        
        # YOLOモデル
        self.yolo = YOLO('yolov8n.pt')
        
        # ONVIFカメラ
        self.camera = ONVIFCamera(
            CONFIG['camera']['host'],
            CONFIG['camera']['onvif_port'],
            CONFIG['camera']['username'],
            CONFIG['camera']['password']
        )
        self.ptz_service = self.camera.create_ptz_service()
        self.media_service = self.camera.create_media_service()
        self.ptz_token = self.media_service.GetProfiles()[0].token
        
        # 状態管理
        self.state = "not_detected"
        self.interval = CONFIG['scan_intervals']['not_detected']
        
        # 前回検出データ（メモリのみ、プライバシー配慮）
        self.previous_person_crop = None
        self.previous_bbox = None
        self.last_detection_time = None
        
        # 日次データ
        self.today_data = self.load_today_data()
        
        print("✅ 見守りハロ起動完了")
    
    def load_today_data(self):
        """本日のデータを読み込み"""
        today = datetime.now().strftime("%Y-%m-%d")
        data_file = DATA_DIR / f"{today}.json"
        
        if data_file.exists():
            with open(data_file, 'r') as f:
                return json.load(f)
        else:
            return {
                "date": today,
                "events": [],
                "summary": {
                    "first_activity": None,
                    "last_activity": None,
                    "total_detections": 0,
                    "lying_events": 0,
                    "alerts": []
                }
            }
    
    def save_today_data(self):
        """本日のデータを保存"""
        today = datetime.now().strftime("%Y-%m-%d")
        data_file = DATA_DIR / f"{today}.json"
        
        with open(data_file, 'w', encoding='utf-8') as f:
            json.dump(self.today_data, f, ensure_ascii=False, indent=2)
    
    def is_night_mode(self):
        """夜間モードかチェック"""
        if not CONFIG['night_mode']['enabled']:
            return False
        
        now = datetime.now().time()
        start = datetime.strptime(CONFIG['night_mode']['start_time'], "%H:%M").time()
        end = datetime.strptime(CONFIG['night_mode']['end_time'], "%H:%M").time()
        
        if start < end:
            return start <= now <= end
        else:  # 日をまたぐ場合
            return now >= start or now <= end
    
    def move_camera(self, angle):
        """カメラを指定角度に移動"""
        # 正規化された速度（-1 to 1）
        speed = 0.3 if angle > 0 else -0.3 if angle < 0 else 0
        
        if speed != 0:
            request = self.ptz_service.create_type('ContinuousMove')
            request.ProfileToken = self.ptz_token
            request.Velocity = {'PanTilt': {'x': speed, 'y': 0}}
            self.ptz_service.ContinuousMove(request)
            
            # 移動時間を計算（角度に応じて）
            move_time = abs(angle) / 30.0 * 0.5  # 30度で0.5秒
            time.sleep(move_time)
            
            # 停止
            stop_request = self.ptz_service.create_type('Stop')
            stop_request.ProfileToken = self.ptz_token
            self.ptz_service.Stop(stop_request)
        
        time.sleep(0.5)  # 安定待機
    
    def capture_snapshot(self):
        """カメラからスナップショット取得"""
        temp_file = "/tmp/mimamori_snapshot.jpg"
        
        subprocess.run([
            'ffmpeg', '-rtsp_transport', 'tcp',
            '-i', f"rtsp://{CONFIG['camera']['username']}:{CONFIG['camera']['password']}@{CONFIG['camera']['host']}:{CONFIG['camera']['rtsp_port']}/stream1",
            '-frames:v', '1', '-q:v', '2',
            temp_file, '-y'
        ], capture_output=True, timeout=10)
        
        img = cv2.imread(temp_file)
        return img
    
    def detect_person(self, image):
        """人物検出 + 姿勢推定"""
        results = self.yolo(image, verbose=False)
        detections = results[0].boxes
        
        persons = []
        for box in detections:
            cls_id = int(box.cls[0])
            if cls_id == 0:  # person
                conf = float(box.conf[0])
                bbox = box.xyxy[0].tolist()
                
                # 姿勢推定（簡易版：縦横比で判定）
                x1, y1, x2, y2 = bbox
                width = x2 - x1
                height = y2 - y1
                aspect_ratio = height / width if width > 0 else 0
                
                if aspect_ratio > 1.5:
                    posture = "standing"
                elif aspect_ratio > 0.8:
                    posture = "sitting"
                else:
                    posture = "lying"
                
                persons.append({
                    'bbox': bbox,
                    'confidence': conf,
                    'posture': posture,
                    'aspect_ratio': aspect_ratio
                })
        
        return persons
    
    def compare_with_previous(self, current_image, person):
        """前回検出と比較"""
        if self.previous_person_crop is None:
            # 初回検出
            self.save_current_detection(current_image, person['bbox'])
            return {
                'same_position': False,
                'similarity_ssim': 0,
                'position_diff': 0
            }
        
        # 現在の人物領域を切り出し
        x1, y1, x2, y2 = map(int, person['bbox'])
        current_crop = current_image[y1:y2, x1:x2]
        
        # サイズを前回と合わせる
        prev_h, prev_w = self.previous_person_crop.shape[:2]
        current_resized = cv2.resize(current_crop, (prev_w, prev_h))
        
        # SSIM計算
        gray1 = cv2.cvtColor(self.previous_person_crop, cv2.COLOR_BGR2GRAY)
        gray2 = cv2.cvtColor(current_resized, cv2.COLOR_BGR2GRAY)
        similarity, _ = ssim(gray1, gray2, full=True)
        
        # 位置変化
        center1_x = (self.previous_bbox[0] + self.previous_bbox[2]) / 2
        center1_y = (self.previous_bbox[1] + self.previous_bbox[3]) / 2
        center2_x = (person['bbox'][0] + person['bbox'][2]) / 2
        center2_y = (person['bbox'][1] + person['bbox'][3]) / 2
        position_diff = np.sqrt((center2_x - center1_x)**2 + (center2_y - center1_y)**2)
        
        # 判定
        same_position = (
            similarity > CONFIG['fall_detection']['similarity_threshold'] and
            position_diff < CONFIG['fall_detection']['position_tolerance']
        )
        
        # 現在の検出を保存
        self.save_current_detection(current_image, person['bbox'])
        
        return {
            'same_position': same_position,
            'similarity_ssim': similarity,
            'position_diff': position_diff
        }
    
    def save_current_detection(self, image, bbox):
        """現在の検出をメモリに保存"""
        x1, y1, x2, y2 = map(int, bbox)
        self.previous_person_crop = image[y1:y2, x1:x2].copy()
        self.previous_bbox = bbox
    
    def scan_area(self):
        """エリアスキャン"""
        positions = CONFIG['camera']['scan_positions']
        results = {}
        
        for angle in positions:
            self.move_camera(angle)
            image = self.capture_snapshot()
            persons = self.detect_person(image)
            
            results[angle] = {
                'detected': len(persons) > 0,
                'persons': persons
            }
            
            # 人が見つかったら終了
            if persons:
                return angle, image, persons[0]
            
            # 画像削除（プライバシー）
            del image
        
        # ホームポジションに戻る
        self.move_camera(CONFIG['camera']['home_position'])
        
        return None, None, None
    
    def handle_detection(self, angle, image, person):
        """人物検出時の処理"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 前回と比較
        comparison = self.compare_with_previous(image, person)
        
        # イベント記録
        event = {
            'timestamp': timestamp,
            'state': self.state,
            'camera_angle': angle,
            'posture': person['posture'],
            'confidence': person['confidence'],
            'same_position': comparison['same_position'],
            'similarity': comparison['similarity_ssim'],
            'position_diff': comparison['position_diff'],
            'next_interval': self.interval
        }
        
        self.today_data['events'].append(event)
        self.today_data['summary']['total_detections'] += 1
        self.today_data['summary']['last_activity'] = timestamp
        
        if self.today_data['summary']['first_activity'] is None:
            self.today_data['summary']['first_activity'] = timestamp
        
        # 状態遷移
        if comparison['same_position']:
            print(f"📍 同じ位置（類似度: {comparison['similarity_ssim']:.2f}）")
            
            if person['posture'] == 'lying':
                print("⚠️ 横たわっている姿勢を検出")
                self.handle_lying_detection(angle, person)
            else:
                # 正常
                self.state = "detected_active"
                self.interval = CONFIG['scan_intervals']['detected_active']
                print(f"✅ 正常（{person['posture']}）- 次回: {self.interval}秒後")
        else:
            print(f"🚶 移動検出（{person['posture']}）")
            self.state = "detected_once"
            self.interval = CONFIG['scan_intervals']['detected_once']
        
        self.last_detection_time = datetime.now()
        
        # 画像削除
        del image
    
    def handle_lying_detection(self, angle, person):
        """転倒検知処理"""
        print(f"⏳ {CONFIG['fall_detection']['recheck_delay']}秒後に再確認...")
        time.sleep(CONFIG['fall_detection']['recheck_delay'])
        
        # 再スキャン
        self.move_camera(angle)
        image = self.capture_snapshot()
        persons = self.detect_person(image)
        
        if persons and persons[0]['posture'] == 'lying':
            print("🚨 緊急アラート: 転倒の可能性！")
            self.send_emergency_alert("転倒検知", {
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'posture': 'lying',
                'recheck': True
            })
            self.today_data['summary']['lying_events'] += 1
            self.today_data['summary']['alerts'].append({
                'type': 'fall_detection',
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
        else:
            print("✅ 再確認: 正常")
        
        del image
    
    def send_emergency_alert(self, alert_type, data):
        """緊急アラート送信"""
        # TODO: メール送信実装
        print(f"\n{'='*60}")
        print(f"🚨 緊急アラート: {alert_type}")
        print(f"時刻: {data['timestamp']}")
        print(f"詳細: {json.dumps(data, ensure_ascii=False, indent=2)}")
        print(f"{'='*60}\n")
        
        # ログ記録
        log_file = LOG_DIR / f"alerts_{datetime.now().strftime('%Y-%m')}.log"
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(f"{data['timestamp']} - {alert_type}: {json.dumps(data, ensure_ascii=False)}\n")
    
    def run(self):
        """メインループ"""
        print("\n🏠 見守りハロ - 監視開始")
        print(f"間隔: {self.interval}秒")
        
        try:
            while True:
                # 夜間モードチェック
                if self.is_night_mode():
                    self.interval = CONFIG['scan_intervals']['night_mode']
                    print(f"🌙 夜間モード（{self.interval}秒間隔）")
                
                # スキャン実行
                print(f"\n🔍 スキャン開始 - {datetime.now().strftime('%H:%M:%S')}")
                angle, image, person = self.scan_area()
                
                if person:
                    self.handle_detection(angle, image, person)
                else:
                    print("❌ 未検出")
                    self.state = "not_detected"
                    self.interval = CONFIG['scan_intervals']['not_detected']
                    print(f"次回: {self.interval}秒後")
                
                # データ保存
                self.save_today_data()
                
                # 待機
                time.sleep(self.interval)
                
        except KeyboardInterrupt:
            print("\n\n⏹️ 見守りハロを停止します...")
            self.save_today_data()

if __name__ == "__main__":
    # ディレクトリ作成
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    
    # 実行
    halo = MimamoriHalo()
    halo.run()
