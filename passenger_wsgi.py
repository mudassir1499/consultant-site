"""
Phusion Passenger WSGI entry point for cPanel hosting.

cPanel uses Passenger to serve Python apps. This file MUST be at the
application root (the directory you point the cPanel Python App to).

Passenger looks for an `application` callable in this file.
"""
import os
import sys

# ─── Path setup ──────────────────────────────────────────────────────
# The project directory (where manage.py lives).
# Adjust this path if your cPanel layout differs.
APP_DIR = os.path.dirname(os.path.abspath(__file__))

# Add the project directory to sys.path so Django can find your apps.
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

# If you installed packages into a virtualenv via cPanel "Setup Python App",
# Passenger normally activates it automatically. If not, uncomment below
# and set the correct path:
# VENV = os.path.join(os.path.dirname(APP_DIR), 'virtualenv', 'your-env', 'lib', 'python3.12', 'site-packages')
# sys.path.insert(0, VENV)

# ─── Django setup ────────────────────────────────────────────────────
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'main.settings')

# Load .env before Django reads settings
from dotenv import load_dotenv
load_dotenv(os.path.join(APP_DIR, '.env'))

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
