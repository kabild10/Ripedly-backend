"""
WSGI entry point for Gunicorn production deployment
"""
import os
import sys
import logging
from app import app

# Configure logging for production
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

# Set production environment
os.environ['FLASK_ENV'] = 'production'

# Ensure proper initialization
from app import create_app

# Application instance for Gunicorn
application = create_app()

if __name__ == "__main__":
    application.run()