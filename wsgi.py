"""
WSGI Entry Point — Production Server
Use this instead of `python app.py` for production deployment.

Usage:
    pip install waitress
    python wsgi.py

Or with gunicorn (Linux/Mac):
    gunicorn wsgi:app -w 4 -b 0.0.0.0:5000
"""

from app import create_app
from config import Config

app = create_app()

if __name__ == '__main__':
    try:
        from waitress import serve
        print(f"Starting production server on {Config.HOST}:{Config.PORT}")
        serve(app, host=Config.HOST, port=Config.PORT, threads=4)
    except ImportError:
        print("waitress not installed, falling back to Flask dev server")
        print("Install with: pip install waitress")
        app.run(host=Config.HOST, port=Config.PORT)
