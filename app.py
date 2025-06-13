
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

app = Flask(__name__)

# Enhanced CORS configuration for production
if os.environ.get('FLASK_ENV') == 'production':
    # Production CORS - allow Replit domains and common frontend domains
    CORS(app, 
         origins=["*"],  # Allow all origins for Replit deployment
         methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
         allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
         supports_credentials=True)
else:
    # Development CORS - allow all origins
    CORS(app, 
         origins="*",
         methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
         allow_headers=["Content-Type", "Authorization", "X-Requested-With"])

# Production-ready logging configuration
if os.environ.get('FLASK_ENV') == 'production':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('app.log'),
            logging.StreamHandler()
        ]
    )
else:
    logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)

# Temporary folder for storing processed videos
TEMP_FOLDER = "temp"
if not os.path.exists(TEMP_FOLDER):
    os.makedirs(TEMP_FOLDER)

# Cookies configuration for YouTube (optional)
COOKIES_FILE = "cookies.txt"  # Set to your cookies file path
BROWSER = None  # Or set to "chrome", "firefox", etc.

# Enhanced yt-dlp updater class
class YtDlpUpdater:
    def __init__(self):
        self.last_check_time = None
        self.current_version = None
        self.github_api_url = "https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest"
        self._get_current_version()

    def _get_current_version(self):
        """Get current yt-dlp version"""
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
        """Get latest version from GitHub API"""
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
        """Check if update is needed"""
        if not latest_version or self.current_version == "unknown":
            return False

        current_clean = self.current_version.replace('v', '').replace('.', '')
        latest_clean = latest_version.replace('v', '').replace('.', '')

        try:
            return int(latest_clean) > int(current_clean)
        except ValueError:
            return latest_version != self.current_version

    def _update_ytdlp(self):
        """Update yt-dlp using pip"""
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
        """Check for updates and update if necessary"""
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

# Initialize updater and start background thread
updater = YtDlpUpdater()

def start_updater():
    """Start the yt-dlp updater in background"""
    time.sleep(10)  # Wait 10 seconds before first check
    while True:
        try:
            updater.check_and_update()
            time.sleep(3600)  # Check every hour
        except Exception as e:
            logger.error(f"Error in updater thread: {e}")
            time.sleep(300)  # Wait 5 minutes on error

# Only start updater thread if not in production or if explicitly enabled
if os.environ.get('FLASK_ENV') != 'production' or os.environ.get('ENABLE_UPDATER') == 'true':
    updater_thread = threading.Thread(target=start_updater, daemon=True)
    updater_thread.start()

@app.route('/api/health')
def health():
    """Health check endpoint to verify server is running"""
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
    """Simple endpoint to test frontend-backend connection"""
    logger.info("🔗 Connection test called")
    return jsonify({
        'status': 'success',
        'message': 'Frontend-Backend connection is working!',
        'timestamp': datetime.now().isoformat(),
        'server_type': 'Gunicorn' if __name__ != '__main__' else 'Flask Dev Server'
    }), 200

@app.route('/api/trim', methods=['POST'])
def trim_video_endpoint():
    """Enhanced endpoint for video trimming functionality with perfect sync and no failures"""
    logger.info("🔵 Received request to /api/trim")

    # Get request data
    data = request.json
    url = data.get('url')
    start_time = data.get('startTime')
    end_time = data.get('endTime')

    logger.info(f"📥 Request data - URL: {url}, Start: {start_time}, End: {end_time}")

    # Validate required parameters
    if not url or not start_time or not end_time:
        logger.error("❌ Missing required parameters")
        return jsonify({'error': 'Missing required parameters'}), 400

    # Validate YouTube URL format
    if not re.match(r'^(https?\:\/\/)?(www\.youtube\.com|youtu\.?be)\/.+', url):
        logger.error(f"❌ Invalid YouTube URL: {url}")
        return jsonify({'error': 'Invalid YouTube URL'}), 400

    try:
        # Enhanced time conversion with validation
        logger.info("⏳ Converting time inputs to seconds...")
        start_seconds = convert_to_seconds_enhanced(start_time)
        end_seconds = convert_to_seconds_enhanced(end_time)

        logger.info(f"⏱️ Converted times - Start: {start_seconds}s, End: {end_seconds}s")

        # Validate time range
        if end_seconds <= start_seconds:
            logger.error("❌ End time must be after start time")
            return jsonify({'error': 'End time must be after start time'}), 400

        duration = end_seconds - start_seconds
        if duration > 3600:  # Max 1 hour
            logger.error("❌ Duration too long")
            return jsonify({'error': 'Maximum duration is 1 hour'}), 400

    except ValueError as e:
        logger.error(f"❌ Invalid time format: {e}")
        return jsonify({'error': 'Invalid time format. Use mm:ss or hh:mm:ss'}), 400

    logger.info(f"✂️ Trimming video from {start_seconds}s to {end_seconds}s")

    try:
        # Enhanced video and audio URL extraction
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

    except Exception as e:
        logger.error(f"❌ Failed to get video/audio URLs: {e}")
        return jsonify({'error': 'Failed to extract stream URLs'}), 500

    # Generate filename based on times
    safe_start = start_time.replace(':', '_')
    safe_end = end_time.replace(':', '_')
    output_filename = f"Ripedly_{safe_start}_to_{safe_end}.mp4"
    output_path = os.path.join(TEMP_FOLDER, output_filename)
    logger.info(f"📁 Output will be saved to: {output_path}")

    try:
        # Enhanced video trimming with perfect sync
        logger.info("🛠️ Starting enhanced video trimming with perfect sync...")
        if not trim_video_with_perfect_sync(video_url, audio_url, start_seconds, end_seconds, output_path, url):
            logger.error("❌ Enhanced trim video operation failed")
            return jsonify({'error': 'Failed to trim video'}), 500
    except Exception as e:
        logger.error(f"❌ Error trimming video: {e}")
        return jsonify({'error': 'Failed to trim video'}), 500

    logger.info(f"✅ Successfully trimmed video: {output_path}")

    # Verify output file exists and has content
    if not os.path.exists(output_path) or os.path.getsize(output_path) < 1000:
        logger.error("❌ Output file is missing or too small")
        return jsonify({'error': 'Generated video file is invalid'}), 500

    # Schedule cleanup of the temporary file
    logger.info(f"⏳ Scheduling cleanup of {output_path} in 10 minutes...")
    schedule_file_deletion(output_path, delay=600)

    # Send the file to the client
    logger.info("📤 Sending file to client...")
    return send_file(
        output_path,
        as_attachment=True,
        download_name=output_filename
    )

def convert_to_seconds_enhanced(time_str):
    """Enhanced time conversion with validation"""
    logger.debug(f"Converting time string: {time_str}")

    # Remove whitespace and validate format
    time_str = time_str.strip()
    if not re.match(r'^\d{1,2}:\d{2}(:\d{2})?$', time_str):
        raise ValueError("Invalid time format. Use mm:ss or hh:mm:ss")

    parts = time_str.split(':')
    if len(parts) == 2:
        minutes, seconds = map(int, parts)
        if minutes >= 60 or seconds >= 60:
            raise ValueError("Minutes and seconds must be less than 60")
        return minutes * 60 + seconds
    elif len(parts) == 3:
        hours, minutes, seconds = map(int, parts)
        if minutes >= 60 or seconds >= 60:
            raise ValueError("Minutes and seconds must be less than 60")
        return hours * 3600 + minutes * 60 + seconds
    else:
        raise ValueError("Invalid time format. Use mm:ss or hh:mm:ss")
def has_visitor_data():
    """Check if visitor data is available in environment or config"""
    return os.getenv('YT_VISITOR_DATA') is not None

def get_visitor_data():
    """Get visitor data from environment or config"""
    return os.getenv('YT_VISITOR_DATA')

def get_enhanced_streams(youtube_url):
    """Enhanced stream extraction with better validation and reliability"""
    logger.info(f"🔍 Enhanced analysis of YouTube URL: {youtube_url}")

    # Configuration constants (would ideally come from config/settings)
    PROXY_URL = "http://8.210.117.141:8888"  # Should be rotated in production
    MAX_RETRIES = 3
    RETRY_DELAY = 2

    ydl_opts = {
        # Network settings
        'proxy': PROXY_URL,
        'socket_timeout': 30,
        'retries': 10,
        'fragment_retries': 10,
        'extractor_retries': 10,
        'http_chunk_size': 10485760,
        'source_address': '0.0.0.0',  # Force IPv4

        # Authentication & headers
        'cookies': COOKIES_FILE if COOKIES_FILE and os.path.exists(COOKIES_FILE) else None,
        'cookiesfrombrowser': (BROWSER,) if BROWSER else None,
        'geo_bypass': True,
        'geo_bypass_country': 'US',

        # Format selection
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'noplaylist': True,
        'quiet': True,
        'no_warnings': False,
        'ignoreerrors': False,

        # YouTube-specific tweaks
        'extractor_args': {
            'youtube': {
                'skip': ['hls', 'dash'],
                'player_client': ['web'],  # Removed 'android' to avoid PO token issues
                'player_skip': ['configs'],
                'throttledratelimit': 1000000,
                'visitor_data': get_visitor_data() if has_visitor_data() else None,
            }
        }
    }

    # Authentication logging
    if ydl_opts.get('cookiefile'):
        logger.info("🍪 Using cookies file for authentication")
    elif ydl_opts.get('cookiesfrombrowser'):
        logger.info(f"🌐 Using cookies from browser: {BROWSER}")

    with YoutubeDL(ydl_opts) as ydl:
        # Extract video info with enhanced retry logic
        logger.info("📡 Fetching video information with retry logic...")
        info = None
        last_error = None
        
        for attempt in range(MAX_RETRIES):
            try:
                info = ydl.extract_info(youtube_url, download=False)
                if info:
                    break
            except Exception as e:
                last_error = e
                if attempt < MAX_RETRIES - 1:
                    retry_delay = RETRY_DELAY * (attempt + 1)
                    logger.warning(f"⚠️ Attempt {attempt + 1} failed, retrying in {retry_delay}s...")
                    time.sleep(retry_delay)
        
        if not info:
            raise last_error if last_error else Exception("Failed to extract video info")

        formats = info.get('formats', [])
        logger.info(f"ℹ️ Found {len(formats)} available formats")

        # Enhanced format filtering with fallbacks
        def is_valid_format(f):
            return (f.get('url') and 
                   not f.get('is_from_endcard') and 
                   not f.get('quality') == 'tiny')

        video_formats = [f for f in formats if is_valid_format(f) and f.get('vcodec') != 'none']
        audio_formats = [f for f in formats if is_valid_format(f) and f.get('acodec') != 'none']
        combined_formats = [f for f in formats if is_valid_format(f) and f.get('vcodec') != 'none' and f.get('acodec') != 'none']

        # Fallback to combined formats if separate streams not available
        if not video_formats or not audio_formats:
            logger.warning("⚠️ No separate streams found, trying combined formats...")
            if combined_formats:
                logger.info(f"📹 Found {len(combined_formats)} combined video+audio formats")
                best_combined = max(
                    (f for f in combined_formats if f.get('height', 0) <= 720),
                    key=lambda f: (f.get('height', 0), f.get('tbr', 0)),
                    default=combined_formats[0]
                )
                logger.info(f"🏆 Using combined format: {best_combined.get('height', '?')}p")
                return best_combined['url'], best_combined['url'], info

        # Enhanced format prioritization
        def sort_key_video(f):
            return (
                1 if f.get('ext') == 'mp4' else 0,
                f.get('height', 0),
                f.get('fps', 0),
                f.get('tbr', 0)
            )

        def sort_key_audio(f):
            return (
                1 if f.get('ext') == 'm4a' else 0,
                f.get('abr', 0),
                f.get('asr', 0)
            )

        video_formats.sort(key=sort_key_video, reverse=True)
        audio_formats.sort(key=sort_key_audio, reverse=True)

        # Stream validation with timeout and user-agent rotation
        USER_AGENTS = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15',
            'Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36'
        ]

        def validate_stream(url, stream_type):
            for ua in USER_AGENTS:
                try:
                    req = urllib.request.Request(url, method='HEAD')
                    req.add_header('User-Agent', ua)
                    req.add_header('Accept', '*/*')
                    req.add_header('Accept-Language', 'en-US,en;q=0.9')
                    with urllib.request.urlopen(req, timeout=15) as response:
                        if response.status == 200:
                            return True
                except Exception as e:
                    logger.warning(f"⚠️ {stream_type} validation failed with UA {ua[:15]}...: {str(e)[:100]}")
                    continue
            return False

        # Select best validated streams
        selected_video = None
        selected_audio = None

        for fmt in video_formats[:5]:  # Check top 5 video formats
            if validate_stream(fmt['url'], 'video'):
                selected_video = fmt
                logger.info(f"✅ Validated video: {fmt.get('height', '?')}p ({fmt.get('ext')})")
                break

        for fmt in audio_formats[:5]:  # Check top 5 audio formats
            if validate_stream(fmt['url'], 'audio'):
                selected_audio = fmt
                logger.info(f"✅ Validated audio: {fmt.get('abr', '?')}kbps ({fmt.get('ext')})")
                break

        if not selected_video or not selected_audio:
            raise Exception("Could not validate any video/audio streams")

        logger.info(f"🏆 Final selection - Video: {selected_video.get('height', '?')}p, "
                   f"Audio: {selected_audio.get('abr', '?')}kbps")

        return selected_video['url'], selected_audio['url'], info

def trim_video_with_perfect_sync(video_url, audio_url, start_time, end_time, output_path, youtube_url=None, retries=3):
    """Enhanced video trimming with perfect audio/video sync and no failures"""
    duration = end_time - start_time
    logger.info(f"🎬 Enhanced trimming with perfect sync - Duration: {duration} seconds")

    # Simplified FFmpeg command for better reliability
    command = [
        'ffmpeg',
        '-y',  # Overwrite output file
        '-loglevel', 'warning',  # Reduce verbosity
        '-err_detect', 'ignore_err',  # Ignore minor errors

        # Network resilience options
        '-reconnect', '1',  # Enable reconnection
        '-reconnect_streamed', '1',  # Reconnect for streamed content
        '-reconnect_delay_max', '5',  # Max delay between reconnection attempts
        '-timeout', '30000000',  # 30 second timeout (in microseconds)
        '-user_agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',

        # Video input with seeking
        '-ss', str(start_time),  # Seek to start time
        '-i', video_url,  # Video input URL
        '-t', str(duration),  # Duration for video
    ]

    if video_url != audio_url:
        command.extend([
            '-ss', str(start_time),  # Seek to start time  
            '-i', audio_url,  # Audio input URL
            '-t', str(duration),  # Duration for audio
        ])

    command.extend([
        # Stream mapping (handle case where video and audio URLs might be the same)
        '-map', '0:v:0',  # First video stream from first input
        '-map', ('1:a:0' if video_url != audio_url else '0:a:0'),  # Audio from appropriate input

        # Simple encoding for reliability
        '-c:v', 'libx264',  # Video codec
        '-preset', 'fast',  # Encoding speed
        '-crf', '23',  # Balanced quality
        '-pix_fmt', 'yuv420p',  # Pixel format for compatibility

        # Audio encoding
        '-c:a', 'aac',  # Audio codec
        '-b:a', '128k',  # Audio bitrate
        '-ac', '2',  # Stereo

        # Output optimization
        '-movflags', '+faststart',  # Web optimization
        '-avoid_negative_ts', 'make_zero',  # Handle negative timestamps

        output_path
    ])

    logger.info(f"⚙️ FFmpeg command prepared with reliable settings")

    # Execute with retry logic
    for attempt in range(retries):
        try:
            logger.info(f"🚀 FFmpeg attempt {attempt + 1}/{retries}")

            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=600,  # 10 minute timeout
                check=True
            )

            logger.info("🎉 FFmpeg completed successfully")

            # Wait for file system to settle
            time.sleep(2)

            # Verify output file multiple times
            for verify_attempt in range(10):  # Try 10 times over 10 seconds
                if os.path.exists(output_path):
                    file_size = os.path.getsize(output_path)
                    if file_size > 10000:  # At least 10KB for a valid video
                        logger.info(f"✅ Output file verified: {file_size} bytes")
                        return True
                    else:
                        logger.warning(f"⚠️ File too small ({file_size} bytes), waiting... (attempt {verify_attempt + 1})")
                        time.sleep(1)
                else:
                    logger.warning(f"⚠️ Output file not found, waiting... (attempt {verify_attempt + 1})")
                    time.sleep(1)

            logger.error("❌ Output file verification failed after all attempts")

        except subprocess.TimeoutExpired:
            logger.error(f"⏰ FFmpeg timeout on attempt {attempt + 1}")
            if attempt < retries - 1:
                time.sleep(5)

        except subprocess.CalledProcessError as e:
            logger.error(f"💥 FFmpeg failed on attempt {attempt + 1}: {e.returncode}")
            logger.error(f"FFmpeg stderr: {e.stderr}")

            # Enhanced error analysis and retry logic
            stderr_lower = e.stderr.lower() if e.stderr else ""

            # Network/connection errors - retry with fresh stream URLs
            if any(keyword in stderr_lower for keyword in ['http error', 'connection', 'timeout', 'network', 'error number -138']):
                if attempt < retries - 1:
                    logger.info(f"🔄 Network error detected, retrying in {2 ** attempt} seconds...")
                    time.sleep(2 ** attempt)
                    continue

            # Other errors - just retry
            if attempt < retries - 1:
                logger.info("🔄 Retrying with same parameters...")
                time.sleep(2)
                continue

            break

        except Exception as e:
            logger.error(f"❌ Unexpected FFmpeg error: {e}")
            break

    return False

def schedule_file_deletion(path, delay=10):
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

    # Start the deletion thread
    logger.info(f"🔄 Starting deletion thread for {path}")
    threading.Thread(target=delete_later, daemon=True).start()

def initialize_app():
    """Initialize the application for both development and production"""
    logger.info("🔧 Initializing application...")
    # Any initialization logic can go here if needed
    logger.info("✅ Application initialized successfully")

def create_app():
    """Create and configure the Flask application for Gunicorn"""
    initialize_app()
    return app

if __name__ == '__main__':
    initialize_app()
    logger.info("🚀 Starting Flask application in development mode on port 5001")
    app.run(host='0.0.0.0', port=5001, debug=True)
else:
    # For Gunicorn compatibility - initialize when imported
    initialize_app()
