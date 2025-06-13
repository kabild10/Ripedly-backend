from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from yt_dlp import YoutubeDL
import os
import re
import subprocess
import logging
import time
import threading
import urllib.request
from datetime import datetime

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Configuration
TEMP_FOLDER = "temp"
os.makedirs(TEMP_FOLDER, exist_ok=True)
COOKIES_FILE = "cookies.txt" if os.path.exists("cookies.txt") else None

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

def convert_to_seconds(time_str):
    """Convert mm:ss or hh:mm:ss to seconds"""
    parts = list(map(int, time_str.split(':')))
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    elif len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    raise ValueError("Invalid time format")

def get_streams(url):
    """Extract video stream URL using yt-dlp"""
    ydl_opts = {
        'quiet': True,
        'format': 'best[height<=720]',
        'socket_timeout': 30,
        'retries': 3,
        'cookiefile': COOKIES_FILE,
        'extractor_args': {'youtube': {'player_client': ['web']}}
    }
    
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        if not info.get('formats'):
            raise Exception("No formats found")
        
        # Find best format with both audio and video
        formats = [f for f in info['formats'] if f.get('vcodec') != 'none' and f.get('acodec') != 'none']
        if not formats:
            raise Exception("No suitable formats found")
            
        best_format = max(formats, key=lambda f: f.get('height', 0))
        return best_format['url'], info

def trim_video(input_url, start, end, output_path):
    """Trim video using FFmpeg"""
    duration = end - start
    cmd = [
        'ffmpeg',
        '-y', '-loglevel', 'error',
        '-ss', str(start), '-i', input_url,
        '-t', str(duration), '-c', 'copy',
        '-movflags', '+faststart',
        output_path
    ]
    
    try:
        subprocess.run(cmd, check=True, timeout=300)
        return True
    except subprocess.TimeoutExpired:
        logger.error("FFmpeg timeout")
        return False
    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg failed: {e}")
        return False

def cleanup_file(path, delay=600):
    """Delete file after delay"""
    def delete():
        time.sleep(delay)
        try:
            if os.path.exists(path):
                os.remove(path)
                logger.info(f"Deleted {path}")
        except Exception as e:
            logger.error(f"Error deleting {path}: {e}")
    
    threading.Thread(target=delete, daemon=True).start()

@app.route('/api/health')
def health_check():
    return jsonify({
        'status': 'ok',
        'time': datetime.now().isoformat()
    })

@app.route('/api/trim', methods=['POST'])
def trim_handler():
    try:
        data = request.json
        url = data['url']
        start = convert_to_seconds(data['startTime'])
        end = convert_to_seconds(data['endTime'])
        
        if end <= start:
            raise ValueError("End time must be after start time")
        
        video_url, info = get_streams(url)
        filename = f"trim_{start}_{end}.mp4"
        output_path = os.path.join(TEMP_FOLDER, filename)
        
        if not trim_video(video_url, start, end, output_path):
            raise RuntimeError("Video trimming failed")
        
        cleanup_file(output_path)
        return send_file(output_path, as_attachment=True)
        
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    logger.info("Starting server...")
    app.run(host='0.0.0.0', port=5001)
