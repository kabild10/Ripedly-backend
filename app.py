from flask_cors import CORS
from flask import Flask, request, jsonify, send_file
from yt_dlp import YoutubeDL
import os
import re
import subprocess
import logging
import time
import threading
import json
import urllib.request
from datetime import datetime
import random

app = Flask(__name__)

# Enhanced CORS configuration for production
if os.environ.get('FLASK_ENV') == 'production':
    CORS(app, 
         origins=["*"],
         methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
         allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
         supports_credentials=True)
else:
    CORS(app, 
         origins="*",
         methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
         allow_headers=["Content-Type", "Authorization", "X-Requested-With"])

# Production-ready logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Temporary folder for storing processed videos
TEMP_FOLDER = "temp"
os.makedirs(TEMP_FOLDER, exist_ok=True)

# Cookies configuration for YouTube
COOKIES_FILE = "cookies.txt" if os.path.exists("cookies.txt") else None
BROWSER = None

# Improved proxy handling
PROXY_POOL = []  # Add your proxies here if needed
CURRENT_PROXY = None

def get_working_proxy():
    """Get a working proxy from the pool"""
    if not PROXY_POOL:
        return None
    
    for proxy in PROXY_POOL:
        try:
            if requests.get("http://example.com", 
                          proxies={"http": proxy, "https": proxy}, 
                          timeout=5).ok:
                return proxy
        except:
            continue
    return None

class YtDlpUpdater:
    def __init__(self):
        self.last_check_time = None
        self.current_version = None
        self.github_api_url = "https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest"
        self._get_current_version()

    def _get_current_version(self):
        try:
            result = subprocess.run(
                ['yt-dlp', '--version'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                self.current_version = result.stdout.strip()
                logger.info(f"📦 Current yt-dlp version: {self.current_version}")
            else:
                self.current_version = "unknown"
        except Exception as e:
            logger.error(f"❌ Error getting yt-dlp version: {e}")
            self.current_version = "unknown"

    def _get_latest_version(self):
        try:
            req = urllib.request.Request(self.github_api_url)
            req.add_header('User-Agent', 'video-trimmer-app')
            with urllib.request.urlopen(req, timeout=30) as response:
                data = json.loads(response.read().decode())
                return data['tag_name']
        except Exception as e:
            logger.error(f"❌ Error checking latest version: {e}")
            return None

    def _needs_update(self, latest_version):
        if not latest_version or self.current_version == "unknown":
            return False

        current_clean = self.current_version.replace('v', '').replace('.', '')
        latest_clean = latest_version.replace('v', '').replace('.', '')
        try:
            return int(latest_clean) > int(current_clean)
        except ValueError:
            return latest_version != self.current_version

    def _update_ytdlp(self):
        try:
            logger.info("🔄 Updating yt-dlp...")
            result = subprocess.run(
                ['pip', 'install', '--upgrade', 'yt-dlp'],
                capture_output=True,
                text=True,
                timeout=300
            )
            if result.returncode == 0:
                logger.info("✅ yt-dlp updated successfully")
                self._get_current_version()
                return True
            else:
                logger.error(f"❌ Update failed: {result.stderr}")
                return False
        except Exception as e:
            logger.error(f"❌ Error updating yt-dlp: {e}")
            return False

    def check_and_update(self):
        try:
            self.last_check_time = datetime.now().isoformat()
            latest_version = self._get_latest_version()
            if latest_version and self._needs_update(latest_version):
                logger.info(f"🔄 Update needed: {self.current_version} -> {latest_version}")
                return self._update_ytdlp()
            else:
                logger.info("✅ yt-dlp is up to date")
                return True
        except Exception as e:
            logger.error(f"❌ Error in update check: {e}")
            return False

# Initialize updater
updater = YtDlpUpdater()

def start_updater():
    time.sleep(10)
    while True:
        try:
            updater.check_and_update()
            time.sleep(3600)
        except Exception as e:
            logger.error(f"Error in updater thread: {e}")
            time.sleep(300)

if os.environ.get('FLASK_ENV') != 'production' or os.environ.get('ENABLE_UPDATER') == 'true':
    updater_thread = threading.Thread(target=start_updater, daemon=True)
    updater_thread.start()

@app.route('/api/health')
def health():
    logger.info("✅ Health check called")
    return jsonify({
        'status': 'ok',
        'message': 'Backend is running with enhanced trimming',
        'yt_dlp_version': updater.current_version,
        'environment': os.environ.get('FLASK_ENV', 'development'),
        'server': 'Gunicorn' if __name__ != '__main__' else 'Flask Dev Server'
    }), 200

@app.route('/api/test-connection')
def test_connection():
    logger.info("🔗 Connection test called")
    return jsonify({
        'status': 'success',
        'message': 'Frontend-Backend connection is working!',
        'timestamp': datetime.now().isoformat(),
        'server_type': 'Gunicorn' if __name__ != '__main__' else 'Flask Dev Server'
    }), 200

@app.route('/api/trim', methods=['POST'])
def trim_video_endpoint():
    logger.info("🔵 Received request to /api/trim")
    data = request.json
    url = data.get('url')
    start_time = data.get('startTime')
    end_time = data.get('endTime')

    logger.info(f"📥 Request data - URL: {url}, Start: {start_time}, End: {end_time}")

    # Validate inputs
    if not url or not start_time or not end_time:
        logger.error("❌ Missing required parameters")
        return jsonify({'error': 'Missing required parameters'}), 400

    if not re.match(r'^(https?\:\/\/)?(www\.youtube\.com|youtu\.?be)\/.+', url):
        logger.error(f"❌ Invalid YouTube URL: {url}")
        return jsonify({'error': 'Invalid YouTube URL'}), 400

    try:
        logger.info("⏳ Converting time inputs to seconds...")
        start_seconds = convert_to_seconds_enhanced(start_time)
        end_seconds = convert_to_seconds_enhanced(end_time)
        logger.info(f"⏱️ Converted times - Start: {start_seconds}s, End: {end_seconds}s")

        if end_seconds <= start_seconds:
            logger.error("❌ End time must be after start time")
            return jsonify({'error': 'End time must be after start time'}), 400

        duration = end_seconds - start_seconds
        if duration > 3600:
            logger.error("❌ Duration too long")
            return jsonify({'error': 'Maximum duration is 1 hour'}), 400

        logger.info(f"✂️ Trimming video from {start_seconds}s to {end_seconds}s")

        # Get video streams with improved reliability
        logger.info("🌐 Extracting video and audio URLs with enhanced validation...")
        video_url, audio_url, video_info = get_enhanced_streams(url)

        if not video_url or not audio_url:
            logger.error("❌ Could not extract suitable streams")
            return jsonify({'error': 'Could not extract suitable streams'}), 500

        logger.info(f"✅ Successfully extracted streams for video: {video_info.get('title', 'unknown')}")

        # Validate video duration
        video_duration = video_info.get('duration', 0)
        if end_seconds > video_duration:
            logger.error(f"❌ End time exceeds video duration ({video_duration}s)")
            return jsonify({'error': f'End time exceeds video duration ({video_duration}s)'}), 400

        # Generate output filename
        safe_start = start_time.replace(':', '_')
        safe_end = end_time.replace(':', '_')
        output_filename = f"Ripedly_{safe_start}_to_{safe_end}.mp4"
        output_path = os.path.join(TEMP_FOLDER, output_filename)
        logger.info(f"📁 Output will be saved to: {output_path}")

        # Trim video with improved reliability
        logger.info("🛠️ Starting enhanced video trimming with perfect sync...")
        if not trim_video_with_perfect_sync(video_url, audio_url, start_seconds, end_seconds, output_path, url):
            logger.error("❌ Enhanced trim video operation failed")
            return jsonify({'error': 'Failed to trim video'}), 500

        logger.info(f"✅ Successfully trimmed video: {output_path}")

        if not os.path.exists(output_path) or os.path.getsize(output_path) < 1000:
            logger.error("❌ Output file is missing or too small")
            return jsonify({'error': 'Generated video file is invalid'}), 500

        # Schedule cleanup
        logger.info(f"⏳ Scheduling cleanup of {output_path} in 10 minutes...")
        schedule_file_deletion(output_path, delay=600)

        logger.info("📤 Sending file to client...")
        return send_file(
            output_path,
            as_attachment=True,
            download_name=output_filename
        )

    except ValueError as e:
        logger.error(f"❌ Invalid time format: {e}")
        return jsonify({'error': 'Invalid time format. Use mm:ss or hh:mm:ss'}), 400
    except Exception as e:
        logger.error(f"❌ Error in trim endpoint: {e}")
        return jsonify({'error': str(e)}), 500

def convert_to_seconds_enhanced(time_str):
    """Enhanced time conversion with validation"""
    time_str = time_str.strip()
    if not re.match(r'^\d{1,2}:\d{2}(:\d{2})?$', time_str):
        raise ValueError("Invalid time format. Use mm:ss or hh:mm:ss")

    parts = list(map(int, time_str.split(':')))
    if len(parts) == 2:
        if parts[0] >= 60 or parts[1] >= 60:
            raise ValueError("Minutes and seconds must be less than 60")
        return parts[0] * 60 + parts[1]
    elif len(parts) == 3:
        if parts[1] >= 60 or parts[2] >= 60:
            raise ValueError("Minutes and seconds must be less than 60")
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    else:
        raise ValueError("Invalid time format. Use mm:ss or hh:mm:ss")

def get_enhanced_streams(youtube_url):
    """Improved stream extraction with better error handling"""
    logger.info(f"🔍 Enhanced analysis of YouTube URL: {youtube_url}")

    ydl_opts = {
        'quiet': True,
        'skip_download': True,
        'format': 'best[height<=720]/best',
        'noplaylist': True,
        'socket_timeout': 30,
        'retries': 3,
        'fragment_retries': 3,
        'extractor_retries': 3,
        'no_warnings': False,
        'cookiefile': COOKIES_FILE,
        'extractor_args': {
            'youtube': {
                'skip': ['hls', 'dash'],
                'player_client': ['web'],
                'throttledratelimit': 1000000
            }
        }
    }

    if CURRENT_PROXY:
        ydl_opts['proxy'] = CURRENT_PROXY

    try:
        with YoutubeDL(ydl_opts) as ydl:
            for attempt in range(3):
                try:
                    info = ydl.extract_info(youtube_url, download=False)
                    formats = info.get('formats', [])
                    
                    # Find best combined format
                    combined = [f for f in formats if f.get('vcodec') != 'none' and f.get('acodec') != 'none']
                    if combined:
                        best = max(combined, key=lambda f: f.get('height', 0))
                        logger.info(f"🏆 Using combined format: {best.get('height', '?')}p")
                        return best['url'], best['url'], info
                    
                    raise Exception("No suitable formats found")
                
                except Exception as e:
                    if attempt == 2:
                        raise
                    logger.warning(f"⚠️ Attempt {attempt+1} failed, retrying...")
                    time.sleep(2)
    
    except Exception as e:
        logger.error(f"❌ Stream extraction failed: {e}")
        raise

def trim_video_with_perfect_sync(video_url, audio_url, start_time, end_time, output_path, youtube_url=None, retries=3):
    """Improved video trimming with better reliability"""
    duration = end_time - start_time
    logger.info(f"🎬 Enhanced trimming with perfect sync - Duration: {duration} seconds")

    # Simplified FFmpeg command
    command = [
        'ffmpeg',
        '-y', '-loglevel', 'error',
        '-ss', str(start_time), '-i', video_url,
        '-t', str(duration), '-c', 'copy',
        '-movflags', '+faststart',
        output_path
    ]

    for attempt in range(retries):
        try:
            logger.info(f"🚀 FFmpeg attempt {attempt + 1}/{retries}")
            subprocess.run(
                command,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=300
            )
            logger.info("🎉 FFmpeg completed successfully")
            return True

        except subprocess.TimeoutExpired:
            logger.error(f"⏰ FFmpeg timeout on attempt {attempt + 1}")
            if attempt < retries - 1:
                time.sleep(5)
        except subprocess.CalledProcessError as e:
            logger.error(f"💥 FFmpeg failed on attempt {attempt + 1}: {e.returncode}")
            logger.error(f"FFmpeg stderr: {e.stderr.decode()}")
            if attempt < retries - 1:
                time.sleep(2)
        except Exception as e:
            logger.error(f"❌ Unexpected FFmpeg error: {e}")
            break

    return False

def schedule_file_deletion(path, delay=600):
    """Schedule a file for deletion after specified delay"""
    def delete_later():
        logger.info(f"⏳ Waiting {delay} seconds to delete: {path}")
        time.sleep(delay)
        try:
            if os.path.exists(path):
                os.remove(path)
                logger.info(f"🧹 Successfully deleted file: {path}")
            else:
                logger.warning(f"File not found for deletion: {path}")
        except Exception as e:
            logger.error(f"❌ Failed to delete {path}: {e}")

    threading.Thread(target=delete_later, daemon=True).start()

def initialize_app():
    """Initialize the application"""
    logger.info("🔧 Initializing application...")
    global CURRENT_PROXY
    CURRENT_PROXY = get_working_proxy()
    if CURRENT_PROXY:
        logger.info(f"🔌 Using proxy: {CURRENT_PROXY}")
    logger.info("✅ Application initialized successfully")

if __name__ == '__main__':
    initialize_app()
    logger.info("🚀 Starting Flask application in development mode on port 5001")
    app.run(host='0.0.0.0', port=5001, debug=True)
else:
    initialize_app()
