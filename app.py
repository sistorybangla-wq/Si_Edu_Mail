"""
app.py - Health Check for Railway
"""

from flask import Flask
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

@app.route('/')
def health_check():
    """Health check endpoint for Railway"""
    return {
        "status": "healthy",
        "service": "si-edu-mail-bot",
        "message": "Bot is running"
    }

@app.route('/health')
def health():
    """Health endpoint"""
    return {"status": "ok"}, 200

if __name__ == "__main__":
    logger.info("Starting health check server...")
    app.run(host='0.0.0.0', port=8080)

