"""
Sync Performance Monitor

Real-time monitoring and analytics for Shopify sync operations with:
- Performance metrics tracking
- Bottleneck detection
- Resource utilization monitoring
- Predictive analytics for sync duration
- Alert system for performance issues
"""

import time
import logging
import statistics
from typing import Dict, List, Optional, Any, Tuple, Deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict, deque
from enum import Enum
import threading
import psutil
import json

from memory_optimizer import MemoryMonitor, get_memory_stats

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Types of performance metrics."""
    OPERATION_TIME = "operation_time"
    QUEUE_DEPTH = "queue_depth"
    THROUGHPUT = "throughput"
    ERROR_RATE = "error_rate"
    MEMORY_USAGE = "memory_usage"
    CPU_USAGE = "cpu_usage"
    API_LATENCY = "api_latency"
    CACHE_HIT_RATE = "cache_hit_rate"


class AlertLevel(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class PerformanceMetric:
    """Represents a single performance metric."""
    metric_type: MetricType
    value: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class PerformanceAlert:
    """Represents a performance alert."""
    id: str
    level: AlertLevel
    metric_type: MetricType
    message: str
    threshold_value: float
    actual_value: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    resolved: bool = False
    resolved_at: Optional[datetime] = None


@dataclass
class SyncPerformanceStats:
    """Aggregated performance statistics."""
    period_start: datetime
    period_end: datetime
    total_operations: int
    successful_operations: int
    failed_operations: int
    average_operation_time: float
    p95_operation_time: float
    p99_operation_time: float
    operations_per_second: float
    average_queue_depth: float
    peak_queue_depth: int
    average_memory_usage: float
    peak_memory_usage: float
    average_cpu_usage: float
    api_calls: int
    api_errors: int
    cache_hits: int
    cache_misses: int


class PerformanceThresholds:
    """Configurable performance thresholds."""
    
    def __init__(self):
        self.thresholds = {
            MetricType.OPERATION_TIME: {
                AlertLevel.WARNING: 5.0,    # 5 seconds
                AlertLevel.ERROR: 10.0,     # 10 seconds
                AlertLevel.CRITICAL: 30.0   # 30 seconds
            },
            MetricType.QUEUE_DEPTH: {
                AlertLevel.WARNING: 100,
                AlertLevel.ERROR: 500,
                AlertLevel.CRITICAL: 1000
            },
            MetricType.ERROR_RATE: {
                AlertLevel.WARNING: 0.05,   # 5%
                AlertLevel.ERROR: 0.10,     # 10%
                AlertLevel.CRITICAL: 0.25   # 25%
            },
            MetricType.MEMORY_USAGE: {
                AlertLevel.WARNING: 512,    # MB
                AlertLevel.ERROR: 768,
                AlertLevel.CRITICAL: 1024
            },
            MetricType.CPU_USAGE: {
                AlertLevel.WARNING: 70,     # %
                AlertLevel.ERROR: 85,
                AlertLevel.CRITICAL: 95
            },
            MetricType.API_LATENCY: {
                AlertLevel.WARNING: 1.0,    # seconds
                AlertLevel.ERROR: 2.0,
                AlertLevel.CRITICAL: 5.0
            }
        }
    
    def check_threshold(self, metric_type: MetricType, value: float) -> Optional[AlertLevel]:
        """Check if a metric value exceeds any threshold."""
        if metric_type not in self.thresholds:
            return None
        
        thresholds = self.thresholds[metric_type]
        
        # Check from highest to lowest severity
        if value >= thresholds.get(AlertLevel.CRITICAL, float('inf')):
            return AlertLevel.CRITICAL
        elif value >= thresholds.get(AlertLevel.ERROR, float('inf')):
            return AlertLevel.ERROR
        elif value >= thresholds.get(AlertLevel.WARNING, float('inf')):
            return AlertLevel.WARNING
        
        return None


class MetricsCollector:
    """Collects and stores performance metrics."""
    
    def __init__(self, retention_hours: int = 24):
        self.retention_hours = retention_hours
        self.metrics: Dict[MetricType, Deque[PerformanceMetric]] = defaultdict(
            lambda: deque(maxlen=10000)
        )
        self.lock = threading.Lock()
        
        # Start cleanup thread
        self.cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self.cleanup_thread.start()
    
    def record(self, metric_type: MetricType, value: float, tags: Optional[Dict[str, str]] = None):
        """Record a metric value."""
        metric = PerformanceMetric(
            metric_type=metric_type,
            value=value,
            tags=tags or {}
        )
        
        with self.lock:
            self.metrics[metric_type].append(metric)
    
    def get_metrics(self, 
                   metric_type: MetricType,
                   start_time: Optional[datetime] = None,
                   end_time: Optional[datetime] = None,
                   tags: Optional[Dict[str, str]] = None) -> List[PerformanceMetric]:
        """Get metrics within a time range with optional tag filtering."""
        with self.lock:
            metrics = list(self.metrics.get(metric_type, []))
        
        # Filter by time range
        if start_time:
            metrics = [m for m in metrics if m.timestamp >= start_time]
        if end_time:
            metrics = [m for m in metrics if m.timestamp <= end_time]
        
        # Filter by tags
        if tags:
            metrics = [
                m for m in metrics
                if all(m.tags.get(k) == v for k, v in tags.items())
            ]
        
        return metrics
    
    def get_latest(self, metric_type: MetricType) -> Optional[PerformanceMetric]:
        """Get the latest metric value."""
        with self.lock:
            metrics = self.metrics.get(metric_type, [])
            return metrics[-1] if metrics else None
    
    def _cleanup_loop(self):
        """Remove old metrics periodically."""
        while True:
            try:
                cutoff = datetime.utcnow() - timedelta(hours=self.retention_hours)
                
                with self.lock:
                    for metric_type, metrics in self.metrics.items():
                        # Remove metrics older than retention period
                        while metrics and metrics[0].timestamp < cutoff:
                            metrics.popleft()
                
                # Sleep for 1 hour
                time.sleep(3600)
                
            except Exception as e:
                logger.error(f"Metrics cleanup error: {e}")


class SyncPerformanceMonitor:
    """Monitors and analyzes sync performance in real-time."""
    
    def __init__(self,
                 alert_callback: Optional[callable] = None,
                 metrics_interval: int = 60):
        """Initialize performance monitor."""
        self.alert_callback = alert_callback
        self.metrics_interval = metrics_interval
        
        # Components
        self.collector = MetricsCollector()
        self.thresholds = PerformanceThresholds()
        self.memory_monitor = MemoryMonitor()
        
        # Alert tracking
        self.active_alerts: Dict[str, PerformanceAlert] = {}
        self.alert_history: List[PerformanceAlert] = []
        
        # Performance tracking
        self.operation_times: deque = deque(maxlen=1000)
        self.start_times: Dict[str, float] = {}
        
        # Background monitoring
        self.monitoring_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.monitoring_thread.start()
        
        self.logger = logging.getLogger(__name__)
    
    def start_operation(self, operation_id: str):
        """Mark the start of an operation."""
        self.start_times[operation_id] = time.time()
    
    def end_operation(self, operation_id: str, success: bool = True):
        """Mark the end of an operation and record metrics."""
        if operation_id not in self.start_times:
            return
        
        duration = time.time() - self.start_times[operation_id]
        del self.start_times[operation_id]
        
        # Record operation time
        self.collector.record(MetricType.OPERATION_TIME, duration, {
            'operation_id': operation_id,
            'success': str(success)
        })
        
        self.operation_times.append(duration)
        
        # Check for performance issues
        alert_level = self.thresholds.check_threshold(MetricType.OPERATION_TIME, duration)
        if alert_level:
            self._create_alert(
                metric_type=MetricType.OPERATION_TIME,
                level=alert_level,
                actual_value=duration,
                message=f"Operation {operation_id} took {duration:.2f}s"
            )
    
    def record_queue_depth(self, depth: int):
        """Record current queue depth."""
        self.collector.record(MetricType.QUEUE_DEPTH, float(depth))
        
        # Check threshold
        alert_level = self.thresholds.check_threshold(MetricType.QUEUE_DEPTH, float(depth))
        if alert_level:
            self._create_alert(
                metric_type=MetricType.QUEUE_DEPTH,
                level=alert_level,
                actual_value=float(depth),
                message=f"Queue depth is {depth}"
            )
    
    def record_error(self, error_type: str = "general"):
        """Record an error occurrence."""
        self.collector.record(MetricType.ERROR_RATE, 1.0, {'error_type': error_type})
    
    def record_api_call(self, latency: float, success: bool = True):
        """Record API call metrics."""
        self.collector.record(MetricType.API_LATENCY, latency, {
            'success': str(success)
        })
        
        if not success:
            self.record_error("api_error")
    
    def record_cache_access(self, hit: bool):
        """Record cache access."""
        self.collector.record(MetricType.CACHE_HIT_RATE, 1.0 if hit else 0.0)
    
    def get_current_stats(self) -> Dict[str, Any]:
        """Get current performance statistics."""
        # Calculate operation metrics
        if self.operation_times:
            recent_times = list(self.operation_times)
            avg_time = statistics.mean(recent_times)
            p95_time = statistics.quantiles(recent_times, n=20)[18] if len(recent_times) > 20 else max(recent_times)
            ops_per_second = 1.0 / avg_time if avg_time > 0 else 0
        else:
            avg_time = p95_time = ops_per_second = 0
        
        # Get memory stats
        memory_stats = get_memory_stats()
        
        # Get CPU usage
        cpu_percent = psutil.cpu_percent(interval=0.1)
        
        # Get queue depth
        queue_metric = self.collector.get_latest(MetricType.QUEUE_DEPTH)
        queue_depth = int(queue_metric.value) if queue_metric else 0
        
        # Calculate error rate
        recent_errors = self.collector.get_metrics(
            MetricType.ERROR_RATE,
            start_time=datetime.utcnow() - timedelta(minutes=5)
        )
        error_count = len(recent_errors)
        total_ops = len(self.collector.get_metrics(
            MetricType.OPERATION_TIME,
            start_time=datetime.utcnow() - timedelta(minutes=5)
        ))
        error_rate = (error_count / total_ops * 100) if total_ops > 0 else 0
        
        return {
            'average_operation_time': round(avg_time, 3),
            'p95_operation_time': round(p95_time, 3),
            'operations_per_second': round(ops_per_second, 2),
            'queue_depth': queue_depth,
            'error_rate': round(error_rate, 2),
            'memory_usage_mb': memory_stats['rss_mb'],
            'cpu_usage_percent': round(cpu_percent, 1),
            'active_alerts': len(self.active_alerts),
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def get_performance_report(self, 
                              start_time: datetime,
                              end_time: datetime) -> SyncPerformanceStats:
        """Generate a performance report for a time period."""
        # Get all metrics for the period
        op_metrics = self.collector.get_metrics(
            MetricType.OPERATION_TIME,
            start_time=start_time,
            end_time=end_time
        )
        
        queue_metrics = self.collector.get_metrics(
            MetricType.QUEUE_DEPTH,
            start_time=start_time,
            end_time=end_time
        )
        
        memory_metrics = self.collector.get_metrics(
            MetricType.MEMORY_USAGE,
            start_time=start_time,
            end_time=end_time
        )
        
        cpu_metrics = self.collector.get_metrics(
            MetricType.CPU_USAGE,
            start_time=start_time,
            end_time=end_time
        )
        
        cache_metrics = self.collector.get_metrics(
            MetricType.CACHE_HIT_RATE,
            start_time=start_time,
            end_time=end_time
        )
        
        # Calculate statistics
        if op_metrics:
            op_times = [m.value for m in op_metrics]
            avg_op_time = statistics.mean(op_times)
            p95_op_time = statistics.quantiles(op_times, n=20)[18] if len(op_times) > 20 else max(op_times)
            p99_op_time = statistics.quantiles(op_times, n=100)[98] if len(op_times) > 100 else max(op_times)
            
            successful_ops = len([m for m in op_metrics if m.tags.get('success') == 'True'])
            failed_ops = len(op_metrics) - successful_ops
            
            duration = (end_time - start_time).total_seconds()
            ops_per_second = len(op_metrics) / duration if duration > 0 else 0
        else:
            avg_op_time = p95_op_time = p99_op_time = 0
            successful_ops = failed_ops = 0
            ops_per_second = 0
        
        # Queue statistics
        if queue_metrics:
            queue_depths = [m.value for m in queue_metrics]
            avg_queue_depth = statistics.mean(queue_depths)
            peak_queue_depth = int(max(queue_depths))
        else:
            avg_queue_depth = peak_queue_depth = 0
        
        # Memory statistics
        if memory_metrics:
            memory_values = [m.value for m in memory_metrics]
            avg_memory = statistics.mean(memory_values)
            peak_memory = max(memory_values)
        else:
            avg_memory = peak_memory = 0
        
        # CPU statistics
        if cpu_metrics:
            cpu_values = [m.value for m in cpu_metrics]
            avg_cpu = statistics.mean(cpu_values)
        else:
            avg_cpu = 0
        
        # Cache statistics
        cache_hits = len([m for m in cache_metrics if m.value == 1.0])
        cache_misses = len(cache_metrics) - cache_hits
        
        # API statistics
        api_metrics = self.collector.get_metrics(
            MetricType.API_LATENCY,
            start_time=start_time,
            end_time=end_time
        )
        api_calls = len(api_metrics)
        api_errors = len([m for m in api_metrics if m.tags.get('success') == 'False'])
        
        return SyncPerformanceStats(
            period_start=start_time,
            period_end=end_time,
            total_operations=len(op_metrics),
            successful_operations=successful_ops,
            failed_operations=failed_ops,
            average_operation_time=avg_op_time,
            p95_operation_time=p95_op_time,
            p99_operation_time=p99_op_time,
            operations_per_second=ops_per_second,
            average_queue_depth=avg_queue_depth,
            peak_queue_depth=peak_queue_depth,
            average_memory_usage=avg_memory,
            peak_memory_usage=peak_memory,
            average_cpu_usage=avg_cpu,
            api_calls=api_calls,
            api_errors=api_errors,
            cache_hits=cache_hits,
            cache_misses=cache_misses
        )
    
    def predict_sync_duration(self, operation_count: int) -> Dict[str, Any]:
        """Predict sync duration based on historical data."""
        if not self.operation_times:
            return {
                'estimated_duration': None,
                'confidence': 0,
                'error': 'Insufficient historical data'
            }
        
        # Calculate average operation time
        recent_times = list(self.operation_times)[-100:]  # Last 100 operations
        avg_time = statistics.mean(recent_times)
        std_dev = statistics.stdev(recent_times) if len(recent_times) > 1 else 0
        
        # Calculate estimate with confidence interval
        estimated_duration = avg_time * operation_count
        confidence_interval = 1.96 * std_dev * operation_count  # 95% confidence
        
        # Factor in current performance
        current_stats = self.get_current_stats()
        performance_factor = 1.0
        
        # Adjust for queue depth
        if current_stats['queue_depth'] > 100:
            performance_factor *= 1.2  # 20% slower when queue is backed up
        
        # Adjust for error rate
        if current_stats['error_rate'] > 5:
            performance_factor *= 1.1  # 10% slower with high error rate
        
        estimated_duration *= performance_factor
        
        return {
            'estimated_duration_seconds': round(estimated_duration, 1),
            'confidence_interval_seconds': round(confidence_interval, 1),
            'estimated_completion': (datetime.utcnow() + timedelta(seconds=estimated_duration)).isoformat(),
            'confidence': min(100, max(0, 100 - int(std_dev * 10))),  # Simple confidence score
            'based_on_operations': len(recent_times)
        }
    
    def _monitoring_loop(self):
        """Background monitoring loop."""
        while True:
            try:
                # Collect system metrics
                memory_stats = get_memory_stats()
                self.collector.record(MetricType.MEMORY_USAGE, memory_stats['rss_mb'])
                
                cpu_percent = psutil.cpu_percent(interval=1)
                self.collector.record(MetricType.CPU_USAGE, cpu_percent)
                
                # Check for threshold violations
                self._check_thresholds()
                
                # Sleep
                time.sleep(self.metrics_interval)
                
            except Exception as e:
                logger.error(f"Monitoring loop error: {e}")
    
    def _check_thresholds(self):
        """Check all metrics against thresholds."""
        # Check memory
        memory_metric = self.collector.get_latest(MetricType.MEMORY_USAGE)
        if memory_metric:
            alert_level = self.thresholds.check_threshold(
                MetricType.MEMORY_USAGE,
                memory_metric.value
            )
            if alert_level:
                self._create_alert(
                    metric_type=MetricType.MEMORY_USAGE,
                    level=alert_level,
                    actual_value=memory_metric.value,
                    message=f"Memory usage is {memory_metric.value:.1f} MB"
                )
        
        # Check CPU
        cpu_metric = self.collector.get_latest(MetricType.CPU_USAGE)
        if cpu_metric:
            alert_level = self.thresholds.check_threshold(
                MetricType.CPU_USAGE,
                cpu_metric.value
            )
            if alert_level:
                self._create_alert(
                    metric_type=MetricType.CPU_USAGE,
                    level=alert_level,
                    actual_value=cpu_metric.value,
                    message=f"CPU usage is {cpu_metric.value:.1f}%"
                )
    
    def _create_alert(self,
                     metric_type: MetricType,
                     level: AlertLevel,
                     actual_value: float,
                     message: str):
        """Create or update an alert."""
        alert_id = f"{metric_type.value}_{level.value}"
        
        # Check if alert already exists
        if alert_id in self.active_alerts:
            # Update existing alert
            alert = self.active_alerts[alert_id]
            alert.actual_value = actual_value
            alert.timestamp = datetime.utcnow()
        else:
            # Create new alert
            threshold_value = self.thresholds.thresholds[metric_type][level]
            
            alert = PerformanceAlert(
                id=alert_id,
                level=level,
                metric_type=metric_type,
                message=message,
                threshold_value=threshold_value,
                actual_value=actual_value
            )
            
            self.active_alerts[alert_id] = alert
            self.alert_history.append(alert)
            
            # Trigger callback
            if self.alert_callback:
                self.alert_callback(alert)
            
            self.logger.warning(f"Performance alert: {message} (threshold: {threshold_value})")
    
    def resolve_alert(self, alert_id: str):
        """Manually resolve an alert."""
        if alert_id in self.active_alerts:
            alert = self.active_alerts[alert_id]
            alert.resolved = True
            alert.resolved_at = datetime.utcnow()
            del self.active_alerts[alert_id]
    
    def get_active_alerts(self) -> List[PerformanceAlert]:
        """Get all active alerts."""
        return list(self.active_alerts.values())
    
    def get_alert_history(self, hours: int = 24) -> List[PerformanceAlert]:
        """Get alert history for the specified number of hours."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        return [
            alert for alert in self.alert_history
            if alert.timestamp >= cutoff
        ]