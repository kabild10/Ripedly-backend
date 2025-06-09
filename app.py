from flask_cors import CORS
from flask import Flask, request, jsonify, send_file
from yt_dlp import YoutubeDL
import os
import re
import subprocess
import logging
import time
import threading

app = Flask(__name__)
CORS(app)

# Logging configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Temporary folder for storing processed videos
TEMP_FOLDER = "temp"
if not os.path.exists(TEMP_FOLDER):
    os.makedirs(TEMP_FOLDER)

# Cookies configuration for YouTube (optional)
COOKIES_FILE = "cookies.txt"  # Set to your cookies file path
BROWSER = None  # Or set to "chrome", "firefox", etc.

@app.route('/api/health')
def health():
    """Health check endpoint to verify server is running"""
    return jsonify({'status': 'ok'}), 200

@app.route('/api/trim', methods=['POST'])
def trim_video_endpoint():
    """Main endpoint for video trimming functionality"""
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
        # Convert time inputs to seconds
        logger.info("⏳ Converting time inputs to seconds...")
        start_seconds = convert_to_seconds(start_time)
        end_seconds = convert_to_seconds(end_time)
        
        logger.info(f"⏱️ Converted times - Start: {start_seconds}s, End: {end_seconds}s")
        
        # Validate time range
        if end_seconds <= start_seconds:
            logger.error("❌ End time must be after start time")
            return jsonify({'error': 'End time must be after start time'}), 400
    except ValueError as e:
        logger.error(f"❌ Invalid time format: {e}")
        return jsonify({'error': 'Invalid time format. Use mm:ss or hh:mm:ss'}), 400

    logger.info(f"✂️ Trimming video from {start_seconds}s to {end_seconds}s")

    try:
        # Extract video and audio URLs from YouTube
        logger.info("🌐 Extracting video and audio URLs from YouTube...")
        video_url, audio_url, video_info = get_direct_video_url(url)
        
        if not video_url or not audio_url:
            logger.error("❌ Could not extract high-quality streams")
            return jsonify({'error': 'Could not extract high-quality streams'}), 500
            
        logger.info(f"✅ Successfully extracted streams for video: {video_info.get('title', 'unknown')}")
    except Exception as e:
        logger.error(f"❌ Failed to get video/audio URLs: {e}")
        return jsonify({'error': 'Failed to extract stream URLs'}), 500

    # Generate filename based on times (format: Ripedly_start_to_end.mp4)
    safe_start = start_time.replace(':', '_')
    safe_end = end_time.replace(':', '_')
    output_filename = f"Ripedly_{safe_start}_to_{safe_end}.mp4"
    output_path = os.path.join(TEMP_FOLDER, output_filename)
    logger.info(f"📁 Output will be saved to: {output_path}")

    try:
        # Perform the actual video trimming
        logger.info("🛠️ Starting video trimming process...")
        if not trim_video_from_url(video_url, audio_url, start_seconds, end_seconds, output_path):
            logger.error("❌ Trim video operation failed")
            return jsonify({'error': 'Failed to trim video'}), 500
    except Exception as e:
        logger.error(f"❌ Error trimming video: {e}")
        return jsonify({'error': 'Failed to trim video'}), 500

    logger.info(f"✅ Successfully trimmed video: {output_path}")

    # Schedule cleanup of the temporary file
    logger.info(f"⏳ Scheduling cleanup of {output_path} in 5 minutes...")
    schedule_file_deletion(output_path, delay=10)

    # Send the file to the client
    logger.info("📤 Sending file to client...")
    return send_file(
        output_path,
        as_attachment=True,
        download_name=output_filename
    )

def convert_to_seconds(time_str):
    """Convert time string (mm:ss or hh:mm:ss) to seconds"""
    logger.debug(f"Converting time string: {time_str}")
    parts = time_str.split(':')
    if len(parts) == 2:
        minutes, seconds = map(int, parts)
        return minutes * 60 + seconds
    elif len(parts) == 3:
        hours, minutes, seconds = map(int, parts)
        return hours * 3600 + minutes * 60 + seconds
    else:
        raise ValueError("Invalid time format. Use mm:ss or hh:mm:ss")

def get_direct_video_url(youtube_url):
    """Extract best video/audio URLs separately, limiting video to max 1080p."""
    logger.info(f"🔍 Analyzing YouTube URL: {youtube_url}")
    
    ydl_opts = {
        'quiet': True,
        'skip_download': True,
        'extract_flat': False,
        'format': 'bestaudio/bestvideo',  # Prefer the best audio and video quality
        'noplaylist': True,  # Do not download playlists
        'geo_bypass': True,  # Bypass geo-blocking
    }

    # Add cookies if available
    if COOKIES_FILE and os.path.exists(COOKIES_FILE):
        logger.info("🍪 Using cookies file for authentication")
        ydl_opts['cookiefile'] = COOKIES_FILE
    elif BROWSER:
        logger.info(f"🌐 Using cookies from browser: {BROWSER}")
        ydl_opts['cookiesfrombrowser'] = (BROWSER,)

    with YoutubeDL(ydl_opts) as ydl:
        # Extract video info
        logger.info("📡 Fetching video information from YouTube...")
        info = ydl.extract_info(youtube_url, download=False)
        formats = info.get('formats', [])
        logger.info(f"ℹ️ Found {len(formats)} available formats")

        # Filter for video-only formats (max 720p)
        video_formats = [
            f for f in formats
            if f.get('vcodec') != 'none'
            and f.get('acodec') == 'none'
            and f.get('ext') in ['mp4', 'webm']
            and f.get('height') is not None
            and f['height'] <= 720
        ]
        logger.info(f"🎥 Found {len(video_formats)} video-only formats")

        # Filter for audio-only formats
        audio_formats = [
            f for f in formats
            if f.get('acodec') != 'none'
            and f.get('vcodec') == 'none'
            and f.get('ext') in ['m4a', 'webm']
        ]
        logger.info(f"🔊 Found {len(audio_formats)} audio-only formats")

        if not video_formats or not audio_formats:
            logger.error("⚠️ No suitable video/audio streams found")
            raise Exception("Could not find suitable video/audio streams")

        # Sort formats by quality
        video_formats.sort(key=lambda f: (f['height'], f.get('fps', 0), f.get('tbr', 0)), reverse=True)
        audio_formats.sort(key=lambda f: f.get('tbr', 0), reverse=True)

        best_video = video_formats[0]['url']
        best_audio = audio_formats[0]['url']

        logger.info(f"🏆 Selected video: {video_formats[0]['height']}p")
        logger.info(f"🏆 Selected audio: {audio_formats[0].get('abr', 'unknown')}kbps")

        return best_video, best_audio, info

def trim_video_from_url(video_url, audio_url, start_time, end_time, output_path, retries=3, delay=1):
    """Trim video using FFmpeg with the specified start and end times, with automatic retries."""
    duration = end_time - start_time
    logger.info(f"🎬 Trimming to duration: {duration} seconds")

    # Build FFmpeg command
    command = [
        'ffmpeg',
        '-y',  # Overwrite output file without asking
        '-ss', str(start_time),  # Seek to start time for video
        '-i', video_url,  # Video input URL
        '-ss', str(start_time),  # Seek to start time for audio
        '-i', audio_url,  # Audio input URL
        '-t', str(duration),  # Set duration
        '-vf', 'scale=-2:720',  # Scale to 720p height
        '-c:v', 'libx264',  # Video codec
        '-preset', 'fast',  # Encoding speed/compression tradeoff
        '-crf', '18',  # Quality level (lower is better)
        '-pix_fmt', 'yuv420p',  # Pixel format for compatibility
        '-c:a', 'aac',  # Audio codec
        '-b:a', '192k',  # Audio bitrate
        '-map', '0:v:0',  # Use first video stream from first input
        '-map', '1:a:0',  # Use first audio stream from second input
        '-movflags', '+faststart',  # Enable streaming
        '-avoid_negative_ts', 'make_zero',  # Handle timestamps
        '-fflags', '+genpts',  # Generate missing PTS
        '-strict', 'experimental',  # Allow experimental codecs
        output_path  # Output file path
    ]

    logger.info(f"⚙️ FFmpeg command: {' '.join(command)}")

    attempt = 0
    while attempt < retries:
        try:
            logger.info("🚀 Starting FFmpeg process...")
            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True
            )
            logger.info("🎉 FFmpeg process completed successfully")
            logger.debug(f"FFmpeg stdout: {result.stdout}")
            logger.debug(f"FFmpeg stderr: {result.stderr}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"💥 FFmpeg failed with code {e.returncode}")
            logger.error(f"FFmpeg error output: {e.stderr}")
            if attempt < retries - 1:
                logger.info(f"Retrying ({attempt + 1}/{retries}) after {delay} seconds...")
                time.sleep(delay)
            attempt += 1
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

if __name__ == '__main__':
    logger.info("🚀 Starting Flask application")
    # Use environment PORT or default to 5000 for direct Flask runs
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

# For Gunicorn compatibility
def create_app():
    return app
