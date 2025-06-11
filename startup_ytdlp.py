
import subprocess
import logging
import sys

def ensure_latest_ytdlp():
    """Ensure we have the latest yt-dlp version to handle token issues"""
    try:
        print("🔄 Ensuring latest yt-dlp version...")
        result = subprocess.run(
            [sys.executable, '-m', 'pip', 'install', '--upgrade', 'yt-dlp'],
            capture_output=True,
            text=True,
            timeout=120
        )
        
        if result.returncode == 0:
            print("✅ yt-dlp is up to date")
            
            # Get version
            version_result = subprocess.run(
                ['yt-dlp', '--version'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if version_result.returncode == 0:
                print(f"📦 yt-dlp version: {version_result.stdout.strip()}")
            
            return True
        else:
            print(f"⚠️ yt-dlp update failed: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Error updating yt-dlp: {e}")
        return False

if __name__ == "__main__":
    ensure_latest_ytdlp()
