"""Health check endpoints for monitoring."""
import os
import time
import psutil
from datetime import datetime
from typing import Dict, Any, List, Optional
from flask import Blueprint, jsonify
from sqlalchemy import text

from database import db_session_scope

health_bp = Blueprint('health', __name__, url_prefix='/api/health')


def check_database() -> Dict[str, Any]:
    """Check database connectivity and performance."""
    start_time = time.time()
    try:
        with db_session_scope() as session:
            # Test basic connectivity
            result = session.execute(text("SELECT 1"))
            result.fetchone()
            
            # Get database stats
            stats = {}
            
            # Count tables (PostgreSQL specific)
            table_count = session.execute(
                text("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public'")
            ).scalar()
            stats['table_count'] = table_count
            
            # Count products (if table exists)
            try:
                product_count = session.execute(text("SELECT COUNT(*) FROM products")).scalar()
                stats['product_count'] = product_count
            except Exception:
                stats['product_count'] = 0
            
            # Count categories (if table exists)
            try:
                category_count = session.execute(text("SELECT COUNT(*) FROM categories")).scalar()
                stats['category_count'] = category_count
            except Exception:
                stats['category_count'] = 0
            
            response_time = (time.time() - start_time) * 1000  # ms
            
            return {
                'status': 'healthy',
                'response_time_ms': round(response_time, 2),
                'stats': stats
            }
    except Exception as e:
        return {
            'status': 'unhealthy',
            'error': str(e),
            'response_time_ms': (time.time() - start_time) * 1000
        }


def check_redis() -> Dict[str, Any]:
    """Check Redis connectivity."""
    try:
        import redis
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
        client = redis.from_url(redis_url)
        
        start_time = time.time()
        client.ping()
        response_time = (time.time() - start_time) * 1000
        
        # Get Redis info
        info = client.info()
        
        return {
            'status': 'healthy',
            'response_time_ms': round(response_time, 2),
            'version': info.get('redis_version'),
            'connected_clients': info.get('connected_clients', 0),
            'used_memory_human': info.get('used_memory_human', 'N/A')
        }
    except Exception as e:
        return {
            'status': 'unhealthy',
            'error': 'Redis not available or connection failed'
        }


def check_disk_space() -> Dict[str, Any]:
    """Check available disk space."""
    try:
        disk_usage = psutil.disk_usage('/')
        return {
            'status': 'healthy' if disk_usage.percent < 90 else 'warning',
            'total_gb': round(disk_usage.total / (1024**3), 2),
            'used_gb': round(disk_usage.used / (1024**3), 2),
            'free_gb': round(disk_usage.free / (1024**3), 2),
            'percent_used': disk_usage.percent
        }
    except Exception as e:
        return {
            'status': 'unhealthy',
            'error': str(e)
        }


def check_memory() -> Dict[str, Any]:
    """Check memory usage."""
    try:
        memory = psutil.virtual_memory()
        return {
            'status': 'healthy' if memory.percent < 90 else 'warning',
            'total_mb': round(memory.total / (1024**2), 2),
            'available_mb': round(memory.available / (1024**2), 2),
            'percent_used': memory.percent
        }
    except Exception as e:
        return {
            'status': 'unhealthy',
            'error': str(e)
        }


def check_cpu() -> Dict[str, Any]:
    """Check CPU usage."""
    try:
        cpu_percent = psutil.cpu_percent(interval=1)
        return {
            'status': 'healthy' if cpu_percent < 80 else 'warning',
            'percent_used': cpu_percent,
            'cpu_count': psutil.cpu_count()
        }
    except Exception as e:
        return {
            'status': 'unhealthy',
            'error': str(e)
        }


def check_external_services() -> Dict[str, Any]:
    """Check external service connectivity."""
    services = {}
    
    # Check Shopify API (if configured)
    shop_url = os.getenv('SHOPIFY_SHOP_URL')
    if shop_url:
        try:
            import requests
            response = requests.get(f"https://{shop_url}/admin/api/2024-01/shop.json", 
                                  headers={'X-Shopify-Access-Token': os.getenv('SHOPIFY_ACCESS_TOKEN', '')},
                                  timeout=5)
            services['shopify'] = {
                'status': 'healthy' if response.status_code == 200 else 'unhealthy',
                'response_code': response.status_code
            }
        except Exception as e:
            services['shopify'] = {
                'status': 'unhealthy',
                'error': 'Connection failed'
            }
    
    # Check OpenAI API (if configured)
    openai_key = os.getenv('OPENAI_API_KEY')
    if openai_key:
        services['openai'] = {
            'status': 'healthy' if len(openai_key) > 20 else 'unhealthy',
            'configured': True
        }
    
    return services


@health_bp.route('/', methods=['GET'])
def health_check():
    """Basic health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'service': 'product-feed-dashboard',
        'version': os.getenv('APP_VERSION', '1.0.0')
    })


@health_bp.route('/live', methods=['GET'])
def liveness_check():
    """Kubernetes liveness probe endpoint."""
    return jsonify({'status': 'alive'}), 200


@health_bp.route('/ready', methods=['GET'])
def readiness_check():
    """Kubernetes readiness probe endpoint."""
    # Check if critical services are ready
    db_check = check_database()
    
    if db_check['status'] == 'healthy':
        return jsonify({'status': 'ready'}), 200
    else:
        return jsonify({
            'status': 'not ready',
            'reason': 'Database unhealthy'
        }), 503


@health_bp.route('/detailed', methods=['GET'])
def detailed_health_check():
    """Detailed health check with all subsystem statuses."""
    start_time = time.time()
    
    # Run all health checks
    checks = {
        'database': check_database(),
        'redis': check_redis(),
        'disk': check_disk_space(),
        'memory': check_memory(),
        'cpu': check_cpu(),
        'external_services': check_external_services()
    }
    
    # Determine overall health
    overall_status = 'healthy'
    unhealthy_count = 0
    warning_count = 0
    
    for check_name, check_result in checks.items():
        if check_result.get('status') == 'unhealthy':
            overall_status = 'unhealthy'
            unhealthy_count += 1
        elif check_result.get('status') == 'warning':
            if overall_status == 'healthy':
                overall_status = 'degraded'
            warning_count += 1
    
    total_time = (time.time() - start_time) * 1000
    
    return jsonify({
        'status': overall_status,
        'timestamp': datetime.utcnow().isoformat(),
        'service': 'product-feed-dashboard',
        'version': os.getenv('APP_VERSION', '1.0.0'),
        'environment': os.getenv('FLASK_ENV', 'development'),
        'checks': checks,
        'summary': {
            'total_checks': len(checks),
            'healthy': len(checks) - unhealthy_count - warning_count,
            'warnings': warning_count,
            'unhealthy': unhealthy_count
        },
        'response_time_ms': round(total_time, 2)
    }), 200 if overall_status == 'healthy' else 503


@health_bp.route('/metrics', methods=['GET'])
def metrics():
    """Prometheus-compatible metrics endpoint."""
    metrics_lines = []
    
    # Add timestamp
    timestamp = int(time.time() * 1000)
    
    # Database metrics
    db_check = check_database()
    if db_check['status'] == 'healthy':
        metrics_lines.append(f'database_healthy 1 {timestamp}')
        metrics_lines.append(f'database_response_time_ms {db_check["response_time_ms"]} {timestamp}')
        if 'stats' in db_check:
            metrics_lines.append(f'database_product_count {db_check["stats"]["product_count"]} {timestamp}')
            metrics_lines.append(f'database_category_count {db_check["stats"]["category_count"]} {timestamp}')
    else:
        metrics_lines.append(f'database_healthy 0 {timestamp}')
    
    # System metrics
    cpu_check = check_cpu()
    memory_check = check_memory()
    disk_check = check_disk_space()
    
    metrics_lines.append(f'system_cpu_percent {cpu_check.get("percent_used", 0)} {timestamp}')
    metrics_lines.append(f'system_memory_percent {memory_check.get("percent_used", 0)} {timestamp}')
    metrics_lines.append(f'system_disk_percent {disk_check.get("percent_used", 0)} {timestamp}')
    
    return '\n'.join(metrics_lines), 200, {'Content-Type': 'text/plain'}