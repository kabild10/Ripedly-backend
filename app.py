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
import random
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

# Enhanced user agents for better compatibility
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
]

def get_random_user_agent():
    """Get a random user agent to avoid detection"""
    return random.choice(USER_AGENTS)

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

@app.route('/api/test-ytdlp')
def test_ytdlp():
    """Test yt-dlp functionality with a simple video"""
    logger.info("🧪 Testing yt-dlp functionality")
    
    test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"  # Rick Roll - always available
    
    try:
        # Simple test configuration
        ydl_opts = {
            'quiet': True,
            'skip_download': True,
            'extract_flat': False,
            'noplaylist': True,
        }
        
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(test_url, download=False)
            
        return jsonify({
            'status': 'success',
            'message': 'yt-dlp is working correctly',
            'test_video_title': info.get('title', 'Unknown'),
            'test_video_duration': info.get('duration', 0),
            'available_formats': len(info.get('formats', [])),
            'yt_dlp_version': updater.current_version
        }), 200
        
    except Exception as e:
        logger.error(f"❌ yt-dlp test failed: {e}")
        return jsonify({
            'status': 'error',
            'message': f'yt-dlp test failed: {str(e)}',
            'yt_dlp_version': updater.current_version
        }), 500

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

def get_enhanced_streams(youtube_url):
    """Enhanced stream extraction with simplified configuration for reliability"""
    logger.info(f"🔍 Enhanced analysis of YouTube URL: {youtube_url}")

    # Test yt-dlp version first
    try:
        result = subprocess.run(['yt-dlp', '--version'], capture_output=True, text=True, timeout=10)
        logger.info(f"🔧 yt-dlp version check: {result.stdout.strip() if result.returncode == 0 else 'failed'}")
    except Exception as e:
        logger.warning(f"⚠️ Version check failed: {e}")

    # Simplified configuration without problematic tokens
    ydl_opts = {
        'quiet': True,
        'skip_download': True,
        'extract_flat': False,
        'format': 'best[height<=720]/best',
        'noplaylist': True,
        'geo_bypass': True,
        'socket_timeout': 60,
        'retries': 3,
        'fragment_retries': 3,
        'extractor_retries': 3,
        'http_chunk_size': 10485760,
        'no_warnings': False,
        # Simplified extractor args without problematic tokens
        'extractor_args': {
            'youtube': {
                'skip': ['hls', 'dash'],
                'player_client': ['android', 'ios', 'mweb', 'web'],
                'player_skip': ['configs'],
            }
        }
    }

    # Mobile-focused headers to bypass restrictions
    mobile_agents = [
        'Mozilla/5.0 (Linux; Android 11; SM-G973F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.120 Mobile Safari/537.36',
        'Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1',
        'Mozilla/5.0 (Linux; Android 10; SM-A205U) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.91 Mobile Safari/537.36',
    ]
    
    user_agent = random.choice(mobile_agents)
    logger.info(f"📱 Using mobile user agent for bypass")
    ydl_opts['http_headers'] = {
        'User-Agent': user_agent,
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Origin': 'https://www.youtube.com',
        'Referer': 'https://www.youtube.com/',
        'X-YouTube-Client-Name': '2',
        'X-YouTube-Client-Version': '2.20220405.01.00',
        'X-Goog-Visitor-Id': 'CgtKN2E3aktnRzBoQSiKgK2wBjIKCgJVUxIEGgAgOA%3D%3D',
    }



    # Authentication and rate limiting
    if COOKIES_FILE and os.path.exists(COOKIES_FILE):
        logger.info("🍪 Using cookies file for authentication")
        ydl_opts['cookiefile'] = COOKIES_FILE
    elif BROWSER:
        logger.info(f"🌐 Using cookies from browser: {BROWSER}")
        ydl_opts['cookiesfrombrowser'] = (BROWSER,)

    # Enhanced anti-detection measures
    ydl_opts.update({
        'sleep_interval': 2,  # Sleep between requests
        'max_sleep_interval': 5,  # Maximum sleep interval
        'sleep_interval_subtitles': 2,  # Sleep for subtitles
        'writesubtitles': False,
        'writeautomaticsub': False,
        'cachedir': False,  # Disable cache
    })

    # Simplified retry with basic client rotation
    max_attempts = 3
    info = None
    
    # Simple client rotation
    clients = [
        ['android'],
        ['ios'],
        ['mweb'],
    ]
    
    for attempt in range(max_attempts):
        try:
            # Use different clients for each attempt
            current_client = clients[attempt % len(clients)]
            ydl_opts['extractor_args']['youtube']['player_client'] = current_client
            ydl_opts['http_headers']['User-Agent'] = random.choice(mobile_agents)
            logger.info(f"🔄 Attempt {attempt + 1}: Using client {current_client}")

            with YoutubeDL(ydl_opts) as ydl:
                logger.info(f"📡 Fetching video information (attempt {attempt + 1}/{max_attempts})...")
                info = ydl.extract_info(youtube_url, download=False)
                logger.info("✅ Successfully extracted video information")
                break
                
        except Exception as e:
            error_msg = str(e).lower()
            logger.warning(f"⚠️ Attempt {attempt + 1} failed: {e}")
            
            # Handle specific YouTube errors
            if '429' in error_msg or 'too many requests' in error_msg:
                wait_time = (3 ** attempt) * random.uniform(2, 4)  # Longer wait for rate limits
                logger.info(f"🚫 Rate limited, waiting {wait_time:.1f}s...")
                time.sleep(wait_time)
            elif 'unavailable' in error_msg:
                if attempt < max_attempts - 1:
                    wait_time = random.uniform(3, 6)
                    logger.info(f"📵 Content unavailable, trying different client in {wait_time:.1f}s...")
                    time.sleep(wait_time)
                else:
                    logger.error("❌ Content truly unavailable after all client attempts")
                    raise Exception("Video is not available or may be private/restricted")
            else:
                if attempt < max_attempts - 1:
                    wait_time = (2 ** attempt) * random.uniform(1, 2)
                    logger.info(f"🔄 Waiting {wait_time:.1f}s before retry...")
                    time.sleep(wait_time)
                else:
                    logger.error("❌ All retry attempts failed")
                    raise e
    
    # If all attempts failed, try one more time with minimal configuration
    if info is None:
        logger.info("🔄 Final attempt with minimal configuration...")
        try:
            minimal_opts = {
                'quiet': True,
                'skip_download': True,
                'extract_flat': False,
                'noplaylist': True,
                'format': 'best',
            }
            
            with YoutubeDL(minimal_opts) as ydl:
                info = ydl.extract_info(youtube_url, download=False)
                logger.info("✅ Minimal configuration worked!")
        except Exception as e:
            logger.error(f"❌ Even minimal configuration failed: {e}")
            raise Exception("Failed to extract video information after all attempts including minimal config")

    if info is None:
        raise Exception("Failed to extract video information after all attempts")

    formats = info.get('formats', [])
        logger.info(f"ℹ️ Found {len(formats)} available formats")

        # More flexible video format filtering - remove strict requirements
        video_formats = [
            f for f in formats
            if (f.get('vcodec') != 'none' and 
                f.get('acodec') == 'none' and
                f.get('url') is not None)
        ]

        # More flexible audio format filtering - remove strict requirements  
        audio_formats = [
            f for f in formats
            if (f.get('acodec') != 'none' and
                f.get('vcodec') == 'none' and
                f.get('url') is not None)
        ]

        # If no separate streams found, try combined formats
        if not video_formats or not audio_formats:
            logger.warning("⚠️ No separate streams found, trying combined formats...")
            combined_formats = [
                f for f in formats
                if (f.get('vcodec') != 'none' and 
                    f.get('acodec') != 'none' and
                    f.get('url') is not None)
            ]

            if combined_formats:
                logger.info(f"📹 Found {len(combined_formats)} combined video+audio formats")
                # Use the same format for both video and audio
                best_combined = combined_formats[0]
                for fmt in combined_formats:
                    if fmt.get('height', 0) <= 720:  # Prefer 720p or lower
                        best_combined = fmt
                        break

                logger.info(f"🏆 Using combined format: {best_combined.get('height', '?')}p")
                return best_combined['url'], best_combined['url'], info

        logger.info(f"🎥 Found {len(video_formats)} suitable video formats")
        logger.info(f"🔊 Found {len(audio_formats)} suitable audio formats")

        if not video_formats or not audio_formats:
            logger.error("⚠️ No suitable video/audio streams found")
            raise Exception("Could not find suitable video/audio streams")

        # Enhanced format selection with compatibility priority
        video_formats.sort(key=lambda f: (
            1 if f.get('ext') == 'mp4' else 0,  # Prefer MP4
            f.get('height', 0),
            f.get('fps', 0),
            f.get('tbr', 0)
        ), reverse=True)

        audio_formats.sort(key=lambda f: (
            1 if f.get('ext') == 'm4a' else 0,  # Prefer M4A
            f.get('abr', 0)
        ), reverse=True)

        # Enhanced stream URL validation with multiple attempts
        validated_video = None
        validated_audio = None

        # Try multiple video formats if first one fails
        for video_format in video_formats[:3]:  # Try top 3 formats
            try:
                req = urllib.request.Request(video_format['url'], method='HEAD')
                req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
                with urllib.request.urlopen(req, timeout=15) as response:
                    if response.status == 200:
                        validated_video = video_format
                        logger.info(f"✅ Validated video stream: {video_format['height']}p")
                        break
            except Exception as e:
                logger.warning(f"⚠️ Video format {video_format.get('height', '?')}p failed validation: {e}")
                continue

        # Try multiple audio formats if first one fails
        for audio_format in audio_formats[:3]:  # Try top 3 formats
            try:
                req = urllib.request.Request(audio_format['url'], method='HEAD')
                req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
                with urllib.request.urlopen(req, timeout=15) as response:
                    if response.status == 200:
                        validated_audio = audio_format
                        logger.info(f"✅ Validated audio stream: {audio_format.get('abr', '?')}kbps")
                        break
            except Exception as e:
                logger.warning(f"⚠️ Audio format {audio_format.get('abr', '?')}kbps failed validation: {e}")
                continue

        # Use validated streams or fallback to first available
        best_video_format = validated_video or video_formats[0]
        best_audio_format = validated_audio or audio_formats[0]

        logger.info(f"🏆 Selected video: {best_video_format['height']}p ({best_video_format.get('ext', 'unknown')})")
        logger.info(f"🏆 Selected audio: {best_audio_format.get('abr', 'unknown')}kbps ({best_audio_format.get('ext', 'unknown')})")

        return best_video_format['url'], best_audio_format['url'], info

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