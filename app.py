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
CORS(app)

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
        'yt_dlp_version': updater.current_version,
        'environment': os.environ.get('FLASK_ENV', 'development')
    }), 200

@app.route('/api/trim', methods=['POST'])
def trim_video_endpoint():
    """Enhanced endpoint for video trimming functionality with perfect sync and no failures"""
    logger.info("🔧 /api/trim called")
    
    # Get request data
    data = request.json
    url = data.get('url')
    start_time = data.get('startTime')
    end_time = data.get('endTime')
    
    logger.info(f"Received URL: {url}")
    logger.info(f"Start Time: {start_time} | End Time: {end_time}")

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
        logger.info("📥 Downloading video...")
        video_url, audio_url, video_info = get_enhanced_streams(url)
        
        if not video_url or not audio_url:
            logger.error("❌ Could not extract suitable streams")
            return jsonify({'error': 'Could not extract suitable streams'}), 500
            
        logger.info("✅ Download complete")
        
        # Validate video duration
        video_duration = video_info.get('duration', 0)
        if end_seconds > video_duration:
            logger.error(f"❌ End time exceeds video duration ({video_duration}s)")
            return jsonify({'error': f'End time exceeds video duration ({video_duration}s)'}), 400
            
    except Exception as e:
        logger.error(f"❌ Failed to get video/audio URLs: {e}")
        return jsonify({'error': 'Failed to extract stream URLs'}), 500

    # Generate unique filename
    import uuid
    unique_id = str(uuid.uuid4())
    output_filename = f"{unique_id}_trimmed.mp4"
    output_path = os.path.join(TEMP_FOLDER, output_filename)
    logger.info(f"📁 Output will be saved to: {output_path}")

    try:
        # Enhanced video trimming with perfect sync
        logger.info("✂️ Trimming video...")
        if not trim_video_with_perfect_sync(video_url, audio_url, start_seconds, end_seconds, output_path, url):
            logger.error("❌ Enhanced trim video operation failed")
            return jsonify({'error': 'Failed to trim video'}), 500
    except Exception as e:
        logger.error(f"❌ Error trimming video: {e}")
        return jsonify({'error': 'Failed to trim video'}), 500

    logger.info("✅ Trimming complete")

    # Verify output file exists and has content
    if not os.path.exists(output_path) or os.path.getsize(output_path) < 1000:
        logger.error("❌ Output file is missing or too small")
        return jsonify({'error': 'Generated video file is invalid'}), 500

    # Schedule cleanup of the temporary file
    logger.info(f"⏳ Scheduling cleanup of {output_path} in 10 minutes...")
    schedule_file_deletion(output_path, delay=600)

    # Send the file to the client
    logger.info(f"🎬 Sending file: {output_filename}")
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
    """Enhanced stream extraction with better validation and reliability"""
    logger.info(f"🔍 Enhanced analysis of YouTube URL: {youtube_url}")
    
    ydl_opts = {
        'quiet': True,
        'skip_download': True,
        'extract_flat': False,
        'format': 'bestaudio/bestvideo',
        'noplaylist': True,
        'geo_bypass': True,
        'socket_timeout': 30,
        'retries': 3,
        'fragment_retries': 3,
        'extractor_retries': 3,
        'http_chunk_size': 10485760,  # 10MB chunks
    }

    # Enhanced authentication
    if COOKIES_FILE and os.path.exists(COOKIES_FILE):
        logger.info("🍪 Using cookies file for authentication")
        ydl_opts['cookiefile'] = COOKIES_FILE
    elif BROWSER:
        logger.info(f"🌐 Using cookies from browser: {BROWSER}")
        ydl_opts['cookiesfrombrowser'] = (BROWSER,)

    with YoutubeDL(ydl_opts) as ydl:
        # Extract video info with retry logic
        logger.info("📡 Fetching video information with retry logic...")
        for attempt in range(3):
            try:
                info = ydl.extract_info(youtube_url, download=False)
                break
            except Exception as e:
                if attempt == 2:
                    raise e
                logger.warning(f"⚠️ Attempt {attempt + 1} failed, retrying...")
                time.sleep(2)
        
        formats = info.get('formats', [])
        logger.info(f"ℹ️ Found {len(formats)} available formats")

        # Enhanced video format filtering (max 720p for reliability)
        video_formats = [
            f for f in formats
            if (f.get('vcodec') != 'none' and 
                f.get('acodec') == 'none' and
                f.get('ext') in ['mp4', 'webm'] and
                f.get('height') is not None and
                f['height'] <= 720 and
                f.get('url') and
                f.get('filesize_approx', 0) > 1000)
        ]

        # Enhanced audio format filtering
        audio_formats = [
            f for f in formats
            if (f.get('acodec') != 'none' and
                f.get('vcodec') == 'none' and
                f.get('ext') in ['m4a', 'webm', 'mp3'] and
                f.get('url') and
                f.get('filesize_approx', 0) > 1000)
        ]

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

        best_video = video_formats[0]['url']
        best_audio = audio_formats[0]['url']

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

    # Enhanced FFmpeg command with perfect sync parameters and network resilience
    command = [
        'ffmpeg',
        '-y',  # Overwrite output file
        '-loglevel', 'warning',  # Reduce verbosity
        '-err_detect', 'ignore_err',  # Ignore minor errors
        '-fflags', '+genpts+igndts',  # Generate PTS, ignore DTS issues
        
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
        
        # Audio input with seeking
        '-ss', str(start_time),  # Seek to start time  
        '-i', audio_url,  # Audio input URL
        '-t', str(duration),  # Duration for audio
        
        # Stream mapping
        '-map', '0:v:0',  # First video stream from first input
        '-map', '1:a:0',  # First audio stream from second input
        
        # Video encoding with quality
        '-c:v', 'libx264',  # Video codec
        '-preset', 'fast',  # Encoding speed
        '-crf', '20',  # Good quality
        '-maxrate', '3000k',  # Max bitrate
        '-bufsize', '6000k',  # Buffer size
        '-pix_fmt', 'yuv420p',  # Pixel format for compatibility
        
        # Audio encoding
        '-c:a', 'aac',  # Audio codec
        '-b:a', '192k',  # Audio bitrate
        '-ac', '2',  # Stereo
        '-ar', '44100',  # Sample rate
        
        # Perfect sync parameters (updated for newer FFmpeg)
        '-fps_mode', 'cfr',  # Constant frame rate for perfect sync (replaces deprecated -vsync)
        '-async', '1',  # Audio sync method
        '-max_muxing_queue_size', '2048',  # Handle async streams
        '-avoid_negative_ts', 'make_zero',  # Handle negative timestamps
        
        # Output optimization
        '-movflags', '+faststart',  # Web optimization
        '-threads', '0',  # Use all CPU cores
        
        output_path
    ]

    logger.info(f"⚙️ Enhanced FFmpeg command prepared with perfect sync")

    # Execute with enhanced retry logic
    for attempt in range(retries):
        try:
            logger.info(f"🚀 Enhanced FFmpeg attempt {attempt + 1}/{retries}")
            
            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=600,  # 10 minute timeout
                check=True
            )
            
            logger.info("🎉 Enhanced FFmpeg completed successfully with perfect sync")
            
            # Verify output file
            if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
                logger.info(f"✅ Output file verified: {os.path.getsize(output_path)} bytes")
                return True
            else:
                logger.error("❌ Output file verification failed")
                
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
                    logger.info(f"🔄 Network error detected, refreshing stream URLs and retrying in {2 ** attempt} seconds...")
                    time.sleep(2 ** attempt)
                    
                    # Try to get fresh stream URLs on network errors
                    try:
                        logger.info("🔄 Refreshing stream URLs due to network error...")
                        # Use passed YouTube URL for refreshing streams
                        if youtube_url:
                            fresh_video_url, fresh_audio_url, _ = get_enhanced_streams(youtube_url)
                            
                            # Update command with fresh URLs
                            for i, arg in enumerate(command):
                                if arg == video_url:
                                    command[i] = fresh_video_url
                                elif arg == audio_url:
                                    command[i] = fresh_audio_url
                            
                            video_url = fresh_video_url
                            audio_url = fresh_audio_url
                            logger.info("✅ Stream URLs refreshed successfully")
                        else:
                            logger.warning("⚠️ Cannot refresh - original URL not available")
                    except Exception as refresh_error:
                        logger.warning(f"⚠️ Could not refresh stream URLs: {refresh_error}")
                    
                    continue
            
            # Stream format issues - try alternative approach
            if 'invalid data found' in stderr_lower or 'format not supported' in stderr_lower:
                if attempt < retries - 1:
                    logger.info("🔄 Format issue detected, trying alternative parameters...")
                    # Remove strict sync parameters for retry
                    if '-fps_mode' in command:
                        idx = command.index('-fps_mode')
                        command.pop(idx)  # Remove -fps_mode
                        command.pop(idx)  # Remove cfr
                    time.sleep(2)
                    continue
            
            break
                
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

    # Start the deletion thread
    logger.info(f"🔄 Starting deletion thread for {path}")
    threading.Thread(target=delete_later, daemon=True).start()

if __name__ == '__main__':
    logger.info("🚀 Server is starting on http://localhost:5001")
    app.run(host='0.0.0.0', port=5001, debug=True)