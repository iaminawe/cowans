# Gunicorn configuration file for production optimization
import multiprocessing
import os

# Server socket
bind = "0.0.0.0:3560"
backlog = 2048

# Worker processes - optimized for 2CPU/4GB server
workers = int(os.environ.get('GUNICORN_WORKERS', '1'))
worker_class = 'sync'  # Use sync workers instead of gevent to reduce CPU usage
worker_connections = int(os.environ.get('GUNICORN_WORKER_CONNECTIONS', '25'))  # Reduced from 50
threads = int(os.environ.get('GUNICORN_THREADS', '2'))
max_requests = 500  # Restart workers more frequently to prevent memory buildup
max_requests_jitter = 50
keepalive = 2

# Limit request sizes to prevent abuse
limit_request_line = 4096
limit_request_fields = 100
limit_request_field_size = 8190

# Timeout
timeout = 60
graceful_timeout = 30

# Logging
loglevel = 'warning'  # Reduce logging in production
accesslog = '-'
errorlog = '-'
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = 'cowans-backend'

# Server mechanics
daemon = False
user = None
group = None
tmp_upload_dir = None

# SSL
keyfile = None
certfile = None

# Pre-loading
preload_app = True  # Load app before forking workers to save memory

# Hooks
def when_ready(server):
    server.log.info("Server is ready. Spawning workers")

def worker_int(worker):
    worker.log.info("Worker received INT or QUIT signal")

def pre_fork(server, worker):
    server.log.info("Worker spawned (pid: %s)", worker.pid)

def pre_exec(server):
    server.log.info("Forked child, re-executing.")

def post_fork(server, worker):
    server.log.info("Worker spawned (pid: %s)", worker.pid)

def worker_abort(worker):
    worker.log.info("Worker received SIGABRT signal")