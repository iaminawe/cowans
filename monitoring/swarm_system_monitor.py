#!/usr/bin/env python3
"""
SWARM System Monitor

Comprehensive monitoring system for SWARM integration including:
- System resource monitoring
- SPARC orchestrator health
- API endpoint monitoring
- Memory coordinator status
- Performance metrics collection
- Alerting and notifications
"""

import asyncio
import json
import time
import psutil
import redis
import requests
import logging
import smtplib
import yaml
import threading
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, asdict
from email.mime.text import MimeText
from email.mime.multipart import MimeMultipart
import sqlite3
import schedule

# Add parent directories to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.orchestration.sparc_orchestrator import SPARCOrchestrator
from scripts.orchestration.sparc_memory import SPARCMemoryCoordinator


@dataclass
class MetricPoint:
    """Single metric measurement"""
    timestamp: datetime
    metric_name: str
    value: float
    tags: Dict[str, str] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = {}


@dataclass
class AlertRule:
    """Alert rule configuration"""
    name: str
    metric: str
    condition: str  # 'gt', 'lt', 'eq', 'ne'
    threshold: float
    duration: int  # seconds before alerting
    severity: str  # 'critical', 'warning', 'info'
    notification_channels: List[str]
    enabled: bool = True


@dataclass
class Alert:
    """Active alert"""
    rule_name: str
    metric: str
    current_value: float
    threshold: float
    severity: str
    first_triggered: datetime
    last_triggered: datetime
    acknowledged: bool = False


class MetricsCollector:
    """Collects various system and application metrics"""
    
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis = redis_client
        self.logger = logging.getLogger("metrics_collector")
        
    def collect_system_metrics(self) -> List[MetricPoint]:
        """Collect system resource metrics"""
        timestamp = datetime.now()
        metrics = []
        
        # CPU metrics
        cpu_percent = psutil.cpu_percent(interval=1)
        metrics.append(MetricPoint(timestamp, "system.cpu.percent", cpu_percent))
        
        cpu_count = psutil.cpu_count()
        metrics.append(MetricPoint(timestamp, "system.cpu.count", cpu_count))
        
        # Memory metrics
        memory = psutil.virtual_memory()
        metrics.append(MetricPoint(timestamp, "system.memory.percent", memory.percent))
        metrics.append(MetricPoint(timestamp, "system.memory.used_gb", memory.used / (1024**3)))
        metrics.append(MetricPoint(timestamp, "system.memory.available_gb", memory.available / (1024**3)))
        
        # Disk metrics
        disk = psutil.disk_usage('/')
        metrics.append(MetricPoint(timestamp, "system.disk.percent", disk.percent))
        metrics.append(MetricPoint(timestamp, "system.disk.used_gb", disk.used / (1024**3)))
        metrics.append(MetricPoint(timestamp, "system.disk.free_gb", disk.free / (1024**3)))
        
        # Network metrics
        try:
            network = psutil.net_io_counters()
            metrics.append(MetricPoint(timestamp, "system.network.bytes_sent", network.bytes_sent))
            metrics.append(MetricPoint(timestamp, "system.network.bytes_recv", network.bytes_recv))
            metrics.append(MetricPoint(timestamp, "system.network.packets_sent", network.packets_sent))
            metrics.append(MetricPoint(timestamp, "system.network.packets_recv", network.packets_recv))
        except:
            pass
        
        # Process metrics
        try:
            current_process = psutil.Process()
            metrics.append(MetricPoint(timestamp, "process.cpu.percent", current_process.cpu_percent()))
            metrics.append(MetricPoint(timestamp, "process.memory.rss_mb", current_process.memory_info().rss / (1024**2)))
            metrics.append(MetricPoint(timestamp, "process.threads", current_process.num_threads()))
        except:
            pass
        
        return metrics
    
    def collect_redis_metrics(self) -> List[MetricPoint]:
        """Collect Redis metrics"""
        if not self.redis:
            return []
        
        timestamp = datetime.now()
        metrics = []
        
        try:
            info = self.redis.info()
            
            # Memory metrics
            metrics.append(MetricPoint(timestamp, "redis.memory.used_mb", info.get('used_memory', 0) / (1024**2)))
            metrics.append(MetricPoint(timestamp, "redis.memory.peak_mb", info.get('used_memory_peak', 0) / (1024**2)))
            metrics.append(MetricPoint(timestamp, "redis.memory.fragmentation_ratio", info.get('mem_fragmentation_ratio', 0)))
            
            # Connection metrics
            metrics.append(MetricPoint(timestamp, "redis.connections.current", info.get('connected_clients', 0)))
            metrics.append(MetricPoint(timestamp, "redis.connections.total", info.get('total_connections_received', 0)))
            
            # Command metrics
            metrics.append(MetricPoint(timestamp, "redis.commands.processed", info.get('total_commands_processed', 0)))
            metrics.append(MetricPoint(timestamp, "redis.keyspace.hits", info.get('keyspace_hits', 0)))
            metrics.append(MetricPoint(timestamp, "redis.keyspace.misses", info.get('keyspace_misses', 0)))
            
            # Calculate hit rate
            hits = info.get('keyspace_hits', 0)
            misses = info.get('keyspace_misses', 0)
            total = hits + misses
            hit_rate = (hits / total * 100) if total > 0 else 0
            metrics.append(MetricPoint(timestamp, "redis.keyspace.hit_rate", hit_rate))
            
        except Exception as e:
            self.logger.error(f"Error collecting Redis metrics: {e}")
            metrics.append(MetricPoint(timestamp, "redis.health", 0))
        
        return metrics
    
    def collect_api_metrics(self, base_url: str = "http://localhost:3560") -> List[MetricPoint]:
        """Collect API health and performance metrics"""
        timestamp = datetime.now()
        metrics = []
        
        endpoints = [
            "/api/health",
            "/api/scripts",
            "/api/jobs",
            "/api/sync/history"
        ]
        
        for endpoint in endpoints:
            try:
                start_time = time.time()
                response = requests.get(f"{base_url}{endpoint}", timeout=10)
                response_time = time.time() - start_time
                
                # Response time metric
                metrics.append(MetricPoint(
                    timestamp, 
                    "api.response_time", 
                    response_time * 1000,  # Convert to milliseconds
                    {"endpoint": endpoint}
                ))
                
                # Status code metric
                metrics.append(MetricPoint(
                    timestamp,
                    "api.status_code",
                    response.status_code,
                    {"endpoint": endpoint}
                ))
                
                # Health metric (1 for success, 0 for failure)
                health = 1 if 200 <= response.status_code < 300 else 0
                metrics.append(MetricPoint(
                    timestamp,
                    "api.health",
                    health,
                    {"endpoint": endpoint}
                ))
                
            except Exception as e:
                self.logger.error(f"Error checking endpoint {endpoint}: {e}")
                metrics.append(MetricPoint(
                    timestamp,
                    "api.health",
                    0,
                    {"endpoint": endpoint}
                ))
                metrics.append(MetricPoint(
                    timestamp,
                    "api.response_time",
                    0,
                    {"endpoint": endpoint}
                ))
        
        return metrics
    
    def collect_sparc_metrics(self) -> List[MetricPoint]:
        """Collect SPARC orchestrator metrics"""
        timestamp = datetime.now()
        metrics = []
        
        try:
            # This would require SPARC to expose metrics
            # For now, we'll simulate based on Redis data
            if self.redis:
                # Count active sessions
                active_sessions = len(self.redis.smembers("sparc:sessions"))
                metrics.append(MetricPoint(timestamp, "sparc.sessions.active", active_sessions))
                
                # Count total tasks (would need to iterate through sessions)
                # This is a placeholder - actual implementation would depend on SPARC data structure
                metrics.append(MetricPoint(timestamp, "sparc.tasks.total", 0))
                metrics.append(MetricPoint(timestamp, "sparc.tasks.completed", 0))
                metrics.append(MetricPoint(timestamp, "sparc.tasks.failed", 0))
                
        except Exception as e:
            self.logger.error(f"Error collecting SPARC metrics: {e}")
            metrics.append(MetricPoint(timestamp, "sparc.health", 0))
        
        return metrics


class AlertManager:
    """Manages alert rules and notifications"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.alert_rules = self._load_alert_rules()
        self.active_alerts = {}
        self.logger = logging.getLogger("alert_manager")
        
    def _load_alert_rules(self) -> List[AlertRule]:
        """Load alert rules from configuration"""
        rules = []
        alert_config = self.config.get('alerts', {})
        
        # Default alert rules
        default_rules = [
            AlertRule(
                name="high_cpu_usage",
                metric="system.cpu.percent",
                condition="gt",
                threshold=alert_config.get('cpu_threshold', 80),
                duration=300,  # 5 minutes
                severity="warning",
                notification_channels=["email"]
            ),
            AlertRule(
                name="high_memory_usage",
                metric="system.memory.percent",
                condition="gt",
                threshold=alert_config.get('memory_threshold', 85),
                duration=300,
                severity="warning",
                notification_channels=["email"]
            ),
            AlertRule(
                name="high_disk_usage",
                metric="system.disk.percent",
                condition="gt",
                threshold=alert_config.get('disk_threshold', 90),
                duration=600,  # 10 minutes
                severity="critical",
                notification_channels=["email", "slack"]
            ),
            AlertRule(
                name="api_endpoint_down",
                metric="api.health",
                condition="lt",
                threshold=1,
                duration=120,  # 2 minutes
                severity="critical",
                notification_channels=["email", "slack"]
            ),
            AlertRule(
                name="slow_api_response",
                metric="api.response_time",
                condition="gt",
                threshold=alert_config.get('response_time_threshold', 5000),
                duration=300,
                severity="warning",
                notification_channels=["email"]
            ),
            AlertRule(
                name="redis_connection_lost",
                metric="redis.health",
                condition="lt",
                threshold=1,
                duration=60,
                severity="critical",
                notification_channels=["email", "slack"]
            )
        ]
        
        rules.extend(default_rules)
        return rules
    
    def evaluate_metrics(self, metrics: List[MetricPoint]):
        """Evaluate metrics against alert rules"""
        for metric in metrics:
            self._evaluate_metric_against_rules(metric)
    
    def _evaluate_metric_against_rules(self, metric: MetricPoint):
        """Evaluate a single metric against all applicable rules"""
        for rule in self.alert_rules:
            if not rule.enabled:
                continue
                
            if rule.metric == metric.metric_name:
                self._check_rule_condition(rule, metric)
    
    def _check_rule_condition(self, rule: AlertRule, metric: MetricPoint):
        """Check if metric violates rule condition"""
        condition_met = False
        
        if rule.condition == "gt" and metric.value > rule.threshold:
            condition_met = True
        elif rule.condition == "lt" and metric.value < rule.threshold:
            condition_met = True
        elif rule.condition == "eq" and metric.value == rule.threshold:
            condition_met = True
        elif rule.condition == "ne" and metric.value != rule.threshold:
            condition_met = True
        
        if condition_met:
            self._handle_alert_triggered(rule, metric)
        else:
            self._handle_alert_resolved(rule, metric)
    
    def _handle_alert_triggered(self, rule: AlertRule, metric: MetricPoint):
        """Handle alert being triggered"""
        alert_key = f"{rule.name}_{metric.tags.get('endpoint', '')}"
        
        if alert_key in self.active_alerts:
            # Update existing alert
            alert = self.active_alerts[alert_key]
            alert.last_triggered = metric.timestamp
            alert.current_value = metric.value
            
            # Check if duration threshold is met
            duration = (metric.timestamp - alert.first_triggered).total_seconds()
            if duration >= rule.duration and not alert.acknowledged:
                self._send_alert_notification(rule, alert)
                alert.acknowledged = True
        else:
            # Create new alert
            alert = Alert(
                rule_name=rule.name,
                metric=rule.metric,
                current_value=metric.value,
                threshold=rule.threshold,
                severity=rule.severity,
                first_triggered=metric.timestamp,
                last_triggered=metric.timestamp
            )
            self.active_alerts[alert_key] = alert
    
    def _handle_alert_resolved(self, rule: AlertRule, metric: MetricPoint):
        """Handle alert being resolved"""
        alert_key = f"{rule.name}_{metric.tags.get('endpoint', '')}"
        
        if alert_key in self.active_alerts:
            alert = self.active_alerts[alert_key]
            if alert.acknowledged:
                self._send_resolution_notification(rule, alert)
            del self.active_alerts[alert_key]
    
    def _send_alert_notification(self, rule: AlertRule, alert: Alert):
        """Send alert notification"""
        self.logger.warning(f"ALERT: {rule.name} - {alert.current_value} {rule.condition} {alert.threshold}")
        
        for channel in rule.notification_channels:
            try:
                if channel == "email":
                    self._send_email_alert(rule, alert)
                elif channel == "slack":
                    self._send_slack_alert(rule, alert)
            except Exception as e:
                self.logger.error(f"Failed to send alert via {channel}: {e}")
    
    def _send_resolution_notification(self, rule: AlertRule, alert: Alert):
        """Send alert resolution notification"""
        self.logger.info(f"RESOLVED: {rule.name}")
        
        for channel in rule.notification_channels:
            try:
                if channel == "email":
                    self._send_email_resolution(rule, alert)
                elif channel == "slack":
                    self._send_slack_resolution(rule, alert)
            except Exception as e:
                self.logger.error(f"Failed to send resolution via {channel}: {e}")
    
    def _send_email_alert(self, rule: AlertRule, alert: Alert):
        """Send email alert"""
        email_config = self.config.get('notifications', {}).get('email', {})
        if not email_config.get('enabled', False):
            return
        
        subject = f"ALERT: {rule.name} - {alert.severity.upper()}"
        body = f"""
Alert: {rule.name}
Severity: {alert.severity.upper()}
Metric: {alert.metric}
Current Value: {alert.current_value}
Threshold: {alert.threshold}
First Triggered: {alert.first_triggered}
Duration: {(alert.last_triggered - alert.first_triggered).total_seconds():.0f} seconds

Please investigate and take appropriate action.
        """
        
        self._send_email(subject, body, email_config)
    
    def _send_email_resolution(self, rule: AlertRule, alert: Alert):
        """Send email resolution"""
        email_config = self.config.get('notifications', {}).get('email', {})
        if not email_config.get('enabled', False):
            return
        
        subject = f"RESOLVED: {rule.name}"
        body = f"""
Alert Resolved: {rule.name}
Metric: {alert.metric}
Alert was active for: {(alert.last_triggered - alert.first_triggered).total_seconds():.0f} seconds

The condition is no longer met.
        """
        
        self._send_email(subject, body, email_config)
    
    def _send_email(self, subject: str, body: str, email_config: Dict[str, Any]):
        """Send email using SMTP"""
        try:
            msg = MimeMultipart()
            msg['From'] = email_config.get('from', 'noreply@cowans.com')
            msg['To'] = ', '.join(email_config.get('recipients', []))
            msg['Subject'] = subject
            
            msg.attach(MimeText(body, 'plain'))
            
            server = smtplib.SMTP(email_config.get('smtp_server', 'localhost'))
            if email_config.get('use_tls', True):
                server.starttls()
            
            username = email_config.get('username')
            password = email_config.get('password')
            if username and password:
                server.login(username, password)
            
            server.sendmail(
                email_config.get('from', 'noreply@cowans.com'),
                email_config.get('recipients', []),
                msg.as_string()
            )
            server.quit()
            
        except Exception as e:
            self.logger.error(f"Failed to send email: {e}")
    
    def _send_slack_alert(self, rule: AlertRule, alert: Alert):
        """Send Slack alert"""
        slack_config = self.config.get('notifications', {}).get('slack', {})
        if not slack_config.get('enabled', False):
            return
        
        webhook_url = slack_config.get('webhook_url')
        if not webhook_url:
            return
        
        color = "danger" if alert.severity == "critical" else "warning"
        
        payload = {
            "attachments": [
                {
                    "color": color,
                    "title": f"ALERT: {rule.name}",
                    "fields": [
                        {"title": "Severity", "value": alert.severity.upper(), "short": True},
                        {"title": "Metric", "value": alert.metric, "short": True},
                        {"title": "Current Value", "value": str(alert.current_value), "short": True},
                        {"title": "Threshold", "value": str(alert.threshold), "short": True}
                    ],
                    "timestamp": int(alert.first_triggered.timestamp())
                }
            ]
        }
        
        try:
            response = requests.post(webhook_url, json=payload, timeout=10)
            response.raise_for_status()
        except Exception as e:
            self.logger.error(f"Failed to send Slack alert: {e}")
    
    def _send_slack_resolution(self, rule: AlertRule, alert: Alert):
        """Send Slack resolution"""
        slack_config = self.config.get('notifications', {}).get('slack', {})
        if not slack_config.get('enabled', False):
            return
        
        webhook_url = slack_config.get('webhook_url')
        if not webhook_url:
            return
        
        payload = {
            "attachments": [
                {
                    "color": "good",
                    "title": f"RESOLVED: {rule.name}",
                    "fields": [
                        {"title": "Metric", "value": alert.metric, "short": True},
                        {"title": "Duration", "value": f"{(alert.last_triggered - alert.first_triggered).total_seconds():.0f}s", "short": True}
                    ],
                    "timestamp": int(alert.last_triggered.timestamp())
                }
            ]
        }
        
        try:
            response = requests.post(webhook_url, json=payload, timeout=10)
            response.raise_for_status()
        except Exception as e:
            self.logger.error(f"Failed to send Slack resolution: {e}")


class MetricsStorage:
    """Stores metrics in SQLite database"""
    
    def __init__(self, db_path: str = "/var/lib/cowans/metrics.db"):
        self.db_path = db_path
        self.logger = logging.getLogger("metrics_storage")
        self._init_database()
    
    def _init_database(self):
        """Initialize SQLite database"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    metric_name TEXT NOT NULL,
                    value REAL NOT NULL,
                    tags TEXT
                )
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_metrics_timestamp 
                ON metrics(timestamp)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_metrics_name 
                ON metrics(metric_name)
            """)
    
    def store_metrics(self, metrics: List[MetricPoint]):
        """Store metrics in database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                for metric in metrics:
                    tags_json = json.dumps(metric.tags) if metric.tags else None
                    conn.execute(
                        "INSERT INTO metrics (timestamp, metric_name, value, tags) VALUES (?, ?, ?, ?)",
                        (metric.timestamp.isoformat(), metric.metric_name, metric.value, tags_json)
                    )
        except Exception as e:
            self.logger.error(f"Failed to store metrics: {e}")
    
    def get_metrics(self, metric_name: str, start_time: datetime, end_time: datetime) -> List[MetricPoint]:
        """Retrieve metrics from database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT timestamp, metric_name, value, tags FROM metrics WHERE metric_name = ? AND timestamp BETWEEN ? AND ?",
                    (metric_name, start_time.isoformat(), end_time.isoformat())
                )
                
                metrics = []
                for row in cursor.fetchall():
                    tags = json.loads(row[3]) if row[3] else {}
                    metric = MetricPoint(
                        timestamp=datetime.fromisoformat(row[0]),
                        metric_name=row[1],
                        value=row[2],
                        tags=tags
                    )
                    metrics.append(metric)
                
                return metrics
        except Exception as e:
            self.logger.error(f"Failed to retrieve metrics: {e}")
            return []
    
    def cleanup_old_metrics(self, retention_days: int = 30):
        """Clean up old metrics"""
        cutoff_date = datetime.now() - timedelta(days=retention_days)
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                result = conn.execute(
                    "DELETE FROM metrics WHERE timestamp < ?",
                    (cutoff_date.isoformat(),)
                )
                deleted_count = result.rowcount
                self.logger.info(f"Cleaned up {deleted_count} old metric records")
        except Exception as e:
            self.logger.error(f"Failed to cleanup old metrics: {e}")


class SWARMSystemMonitor:
    """Main SWARM system monitoring class"""
    
    def __init__(self, config_file: str = "monitoring_config.yaml"):
        self.config = self._load_config(config_file)
        self.logger = self._setup_logging()
        
        # Initialize components
        self.redis_client = self._setup_redis()
        self.metrics_collector = MetricsCollector(self.redis_client)
        self.alert_manager = AlertManager(self.config)
        self.metrics_storage = MetricsStorage(self.config.get('metrics_db_path', '/var/lib/cowans/metrics.db'))
        
        # Monitoring state
        self.monitoring = False
        self.monitor_thread = None
        
    def _load_config(self, config_file: str) -> Dict[str, Any]:
        """Load monitoring configuration"""
        default_config = {
            'monitoring': {
                'enabled': True,
                'interval': 30,
                'metrics': [
                    'system_metrics',
                    'redis_metrics',
                    'api_metrics',
                    'sparc_metrics'
                ]
            },
            'alerts': {
                'cpu_threshold': 80,
                'memory_threshold': 85,
                'disk_threshold': 90,
                'error_rate_threshold': 5,
                'response_time_threshold': 5000
            },
            'notifications': {
                'email': {
                    'enabled': False,
                    'smtp_server': 'localhost',
                    'recipients': []
                },
                'slack': {
                    'enabled': False,
                    'webhook_url': ''
                }
            },
            'storage': {
                'retention_days': 30
            }
        }
        
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r') as f:
                    user_config = yaml.safe_load(f)
                    # Merge with defaults
                    self._deep_merge(default_config, user_config)
            except Exception as e:
                logging.error(f"Failed to load config file {config_file}: {e}")
        
        return default_config
    
    def _deep_merge(self, base_dict: Dict[str, Any], update_dict: Dict[str, Any]):
        """Deep merge two dictionaries"""
        for key, value in update_dict.items():
            if key in base_dict and isinstance(base_dict[key], dict) and isinstance(value, dict):
                self._deep_merge(base_dict[key], value)
            else:
                base_dict[key] = value
    
    def _setup_logging(self) -> logging.Logger:
        """Setup logging for system monitor"""
        logger = logging.getLogger("swarm_monitor")
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            # Console handler
            console_handler = logging.StreamHandler()
            console_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            console_handler.setFormatter(console_formatter)
            logger.addHandler(console_handler)
            
            # File handler
            log_dir = "/var/log/cowans"
            os.makedirs(log_dir, exist_ok=True)
            file_handler = logging.FileHandler(os.path.join(log_dir, "monitor.log"))
            file_handler.setFormatter(console_formatter)
            logger.addHandler(file_handler)
        
        return logger
    
    def _setup_redis(self) -> Optional[redis.Redis]:
        """Setup Redis connection"""
        try:
            redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
            client = redis.from_url(redis_url)
            client.ping()
            return client
        except Exception as e:
            self.logger.warning(f"Redis not available: {e}")
            return None
    
    def start_monitoring(self):
        """Start the monitoring system"""
        if self.monitoring:
            self.logger.warning("Monitoring already started")
            return
        
        self.logger.info("Starting SWARM system monitoring")
        self.monitoring = True
        
        # Start monitoring thread
        self.monitor_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.monitor_thread.start()
        
        # Schedule cleanup tasks
        schedule.every().day.at("02:00").do(self._daily_cleanup)
        
    def stop_monitoring(self):
        """Stop the monitoring system"""
        self.logger.info("Stopping SWARM system monitoring")
        self.monitoring = False
        
        if self.monitor_thread:
            self.monitor_thread.join(timeout=10)
    
    def _monitoring_loop(self):
        """Main monitoring loop"""
        interval = self.config['monitoring']['interval']
        
        while self.monitoring:
            try:
                start_time = time.time()
                
                # Collect all metrics
                all_metrics = []
                
                if 'system_metrics' in self.config['monitoring']['metrics']:
                    all_metrics.extend(self.metrics_collector.collect_system_metrics())
                
                if 'redis_metrics' in self.config['monitoring']['metrics']:
                    all_metrics.extend(self.metrics_collector.collect_redis_metrics())
                
                if 'api_metrics' in self.config['monitoring']['metrics']:
                    all_metrics.extend(self.metrics_collector.collect_api_metrics())
                
                if 'sparc_metrics' in self.config['monitoring']['metrics']:
                    all_metrics.extend(self.metrics_collector.collect_sparc_metrics())
                
                # Store metrics
                self.metrics_storage.store_metrics(all_metrics)
                
                # Evaluate alerts
                self.alert_manager.evaluate_metrics(all_metrics)
                
                # Log summary
                self.logger.debug(f"Collected {len(all_metrics)} metrics in {time.time() - start_time:.2f}s")
                
                # Run scheduled tasks
                schedule.run_pending()
                
                # Sleep until next interval
                elapsed = time.time() - start_time
                sleep_time = max(0, interval - elapsed)
                time.sleep(sleep_time)
                
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}")
                time.sleep(interval)
    
    def _daily_cleanup(self):
        """Daily cleanup tasks"""
        self.logger.info("Running daily cleanup tasks")
        
        try:
            # Cleanup old metrics
            retention_days = self.config.get('storage', {}).get('retention_days', 30)
            self.metrics_storage.cleanup_old_metrics(retention_days)
            
            # Cleanup old log files (if log rotation is not configured)
            self._cleanup_old_logs()
            
        except Exception as e:
            self.logger.error(f"Error in daily cleanup: {e}")
    
    def _cleanup_old_logs(self):
        """Cleanup old log files"""
        log_dir = "/var/log/cowans"
        if not os.path.exists(log_dir):
            return
        
        cutoff_time = time.time() - (30 * 24 * 3600)  # 30 days
        
        for filename in os.listdir(log_dir):
            filepath = os.path.join(log_dir, filename)
            if os.path.isfile(filepath) and filename.endswith('.log'):
                if os.path.getmtime(filepath) < cutoff_time:
                    try:
                        os.remove(filepath)
                        self.logger.info(f"Removed old log file: {filename}")
                    except Exception as e:
                        self.logger.error(f"Failed to remove log file {filename}: {e}")
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get current system status"""
        try:
            # Get latest metrics
            now = datetime.now()
            five_minutes_ago = now - timedelta(minutes=5)
            
            status = {
                'timestamp': now.isoformat(),
                'monitoring_active': self.monitoring,
                'active_alerts': len(self.alert_manager.active_alerts),
                'components': {}
            }
            
            # System status
            cpu_metrics = self.metrics_storage.get_metrics('system.cpu.percent', five_minutes_ago, now)
            memory_metrics = self.metrics_storage.get_metrics('system.memory.percent', five_minutes_ago, now)
            
            if cpu_metrics:
                latest_cpu = cpu_metrics[-1].value
                status['components']['system'] = {
                    'status': 'healthy' if latest_cpu < 80 else 'warning',
                    'cpu_percent': latest_cpu,
                    'memory_percent': memory_metrics[-1].value if memory_metrics else 0
                }
            
            # API status
            api_health_metrics = self.metrics_storage.get_metrics('api.health', five_minutes_ago, now)
            if api_health_metrics:
                api_healthy = all(m.value == 1 for m in api_health_metrics[-5:])  # Last 5 checks
                status['components']['api'] = {
                    'status': 'healthy' if api_healthy else 'unhealthy',
                    'latest_health': api_health_metrics[-1].value
                }
            
            # Redis status
            redis_metrics = self.metrics_storage.get_metrics('redis.health', five_minutes_ago, now)
            if redis_metrics:
                status['components']['redis'] = {
                    'status': 'healthy' if redis_metrics[-1].value == 1 else 'unhealthy'
                }
            
            return status
            
        except Exception as e:
            self.logger.error(f"Error getting system status: {e}")
            return {
                'timestamp': datetime.now().isoformat(),
                'error': str(e)
            }
    
    def generate_health_report(self, hours: int = 24) -> Dict[str, Any]:
        """Generate health report for specified time period"""
        try:
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=hours)
            
            report = {
                'period': {
                    'start': start_time.isoformat(),
                    'end': end_time.isoformat(),
                    'hours': hours
                },
                'summary': {},
                'metrics': {},
                'alerts': []
            }
            
            # System metrics summary
            cpu_metrics = self.metrics_storage.get_metrics('system.cpu.percent', start_time, end_time)
            memory_metrics = self.metrics_storage.get_metrics('system.memory.percent', start_time, end_time)
            
            if cpu_metrics:
                cpu_values = [m.value for m in cpu_metrics]
                report['metrics']['cpu'] = {
                    'avg': sum(cpu_values) / len(cpu_values),
                    'max': max(cpu_values),
                    'min': min(cpu_values)
                }
            
            if memory_metrics:
                memory_values = [m.value for m in memory_metrics]
                report['metrics']['memory'] = {
                    'avg': sum(memory_values) / len(memory_values),
                    'max': max(memory_values),
                    'min': min(memory_values)
                }
            
            # API metrics summary
            api_response_metrics = self.metrics_storage.get_metrics('api.response_time', start_time, end_time)
            if api_response_metrics:
                response_times = [m.value for m in api_response_metrics]
                report['metrics']['api_response_time'] = {
                    'avg': sum(response_times) / len(response_times),
                    'max': max(response_times),
                    'min': min(response_times)
                }
            
            # Alert summary
            alert_count = 0
            for alert in self.alert_manager.active_alerts.values():
                if alert.first_triggered >= start_time:
                    alert_count += 1
                    report['alerts'].append({
                        'rule_name': alert.rule_name,
                        'severity': alert.severity,
                        'triggered_at': alert.first_triggered.isoformat(),
                        'current_value': alert.current_value
                    })
            
            report['summary'] = {
                'total_alerts': alert_count,
                'system_availability': self._calculate_availability(start_time, end_time),
                'overall_health': self._calculate_overall_health(report['metrics'])
            }
            
            return report
            
        except Exception as e:
            self.logger.error(f"Error generating health report: {e}")
            return {'error': str(e)}
    
    def _calculate_availability(self, start_time: datetime, end_time: datetime) -> float:
        """Calculate system availability percentage"""
        # This is a simplified calculation based on API health checks
        api_health_metrics = self.metrics_storage.get_metrics('api.health', start_time, end_time)
        
        if not api_health_metrics:
            return 0.0
        
        healthy_checks = sum(1 for m in api_health_metrics if m.value == 1)
        total_checks = len(api_health_metrics)
        
        return (healthy_checks / total_checks * 100) if total_checks > 0 else 0.0
    
    def _calculate_overall_health(self, metrics: Dict[str, Any]) -> str:
        """Calculate overall system health"""
        issues = 0
        
        # Check CPU
        if 'cpu' in metrics and metrics['cpu']['avg'] > 80:
            issues += 1
        
        # Check memory
        if 'memory' in metrics and metrics['memory']['avg'] > 85:
            issues += 1
        
        # Check API response time
        if 'api_response_time' in metrics and metrics['api_response_time']['avg'] > 2000:
            issues += 1
        
        if issues == 0:
            return "excellent"
        elif issues == 1:
            return "good"
        elif issues == 2:
            return "fair"
        else:
            return "poor"


def create_default_config():
    """Create default monitoring configuration file"""
    config = {
        'monitoring': {
            'enabled': True,
            'interval': 30,
            'metrics': [
                'system_metrics',
                'redis_metrics', 
                'api_metrics',
                'sparc_metrics'
            ]
        },
        'alerts': {
            'cpu_threshold': 80,
            'memory_threshold': 85,
            'disk_threshold': 90,
            'error_rate_threshold': 5,
            'response_time_threshold': 5000
        },
        'notifications': {
            'email': {
                'enabled': False,
                'smtp_server': 'smtp.gmail.com',
                'port': 587,
                'use_tls': True,
                'username': '',
                'password': '',
                'from': 'noreply@cowans.com',
                'recipients': ['admin@yourcompany.com']
            },
            'slack': {
                'enabled': False,
                'webhook_url': ''
            }
        },
        'storage': {
            'retention_days': 30
        }
    }
    
    with open('monitoring_config.yaml', 'w') as f:
        yaml.dump(config, f, default_flow_style=False)
    
    print("Created default monitoring configuration: monitoring_config.yaml")


def main():
    """Main CLI entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="SWARM System Monitor")
    parser.add_argument('--config', '-c', default='monitoring_config.yaml',
                       help='Configuration file path')
    parser.add_argument('--create-config', action='store_true',
                       help='Create default configuration file')
    parser.add_argument('--daemon', '-d', action='store_true',
                       help='Run as daemon')
    parser.add_argument('--status', action='store_true',
                       help='Show current system status')
    parser.add_argument('--report', type=int, metavar='HOURS',
                       help='Generate health report for specified hours')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Verbose logging')
    
    args = parser.parse_args()
    
    # Configure logging
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create default config if requested
    if args.create_config:
        create_default_config()
        return
    
    # Create monitor
    monitor = SWARMSystemMonitor(args.config)
    
    try:
        if args.status:
            # Show status
            status = monitor.get_system_status()
            print(json.dumps(status, indent=2))
            
        elif args.report:
            # Generate report
            report = monitor.generate_health_report(args.report)
            print(json.dumps(report, indent=2))
            
        else:
            # Start monitoring
            monitor.start_monitoring()
            
            if args.daemon:
                # Run as daemon
                print("Starting SWARM system monitor in daemon mode...")
                try:
                    while True:
                        time.sleep(60)
                except KeyboardInterrupt:
                    print("\nStopping monitor...")
            else:
                # Interactive mode
                print("SWARM system monitor started. Press Ctrl+C to stop.")
                try:
                    while True:
                        command = input("Enter command (status/report/quit): ").strip().lower()
                        if command == 'quit':
                            break
                        elif command == 'status':
                            status = monitor.get_system_status()
                            print(json.dumps(status, indent=2))
                        elif command == 'report':
                            hours = int(input("Enter hours for report (default 24): ") or "24")
                            report = monitor.generate_health_report(hours)
                            print(json.dumps(report, indent=2))
                        else:
                            print("Unknown command. Available: status, report, quit")
                except KeyboardInterrupt:
                    print("\nStopping monitor...")
    
    finally:
        monitor.stop_monitoring()


if __name__ == '__main__':
    main()