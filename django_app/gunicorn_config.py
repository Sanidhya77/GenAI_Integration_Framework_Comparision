"""
Gunicorn configuration for Django.

Uses default sync worker class (not gevent, not eventlet). Single worker to isolate framework-level behaviour from
multi-process scaling effects.

Run command:
  cd /home/sanidhya/experiment/django_app
  source ../venv/bin/activate
  gunicorn -c gunicorn_config.py config.wsgi:application
"""

import sys
import os

# Add project root to path so common/ is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Server socket
bind = "0.0.0.0:8000"

# Worker processes
workers = 1               # Single worker — isolate framework behaviour
worker_class = "sync"     # Default synchronous worker (WSGI)
threads = 1               # Single thread per worker

# Timeouts
timeout = 600             # Allow long GenAI inference responses
graceful_timeout = 30
keepalive = 5

# Logging
accesslog = "-"           # Log to stdout
errorlog = "-"            # Log to stderr
loglevel = "info"

# Server mechanics
preload_app = False