"""
Analytics and Reporting Service for Sync Operations

This service provides comprehensive analytics and reporting capabilities for:
- Sync operation performance metrics
- Success/failure rate tracking
- Trend analysis over time
- Error pattern detection
- Resource usage monitoring
- Custom reporting dashboards
"""

import json
import logging
import redis
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from collections import defaultdict
import statistics
import asyncio

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Types of metrics we track."""
    SYNC_DURATION = "sync_duration"
    SYNC_SUCCESS = "sync_success"
    SYNC_FAILURE = "sync_failure"
    ITEMS_PROCESSED = "items_processed"
    ERROR_RATE = "error_rate"
    THROUGHPUT = "throughput"
    RESOURCE_USAGE = "resource_usage"
    CONFLICT_DETECTION = "conflict_detection"


class ReportPeriod(Enum):
    """Report time periods."""
    LAST_HOUR = "last_hour"
    LAST_24_HOURS = "last_24_hours"
    LAST_WEEK = "last_week"
    LAST_MONTH = "last_month"
    CUSTOM = "custom"


@dataclass
class SyncMetric:
    """Represents a single sync metric."""
    type: MetricType
    value: float
    timestamp: datetime
    operation_id: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)


@dataclass
class SyncReport:
    """Comprehensive sync analytics report."""
    period: ReportPeriod
    start_time: datetime
    end_time: datetime
    total_operations: int
    successful_operations: int
    failed_operations: int
    avg_duration: float
    total_items_processed: int
    error_rate: float
    throughput_per_hour: float
    top_errors: List[Dict[str, Any]]
    performance_trends: Dict[str, List[float]]
    resource_usage: Dict[str, float]
    conflict_stats: Dict[str, Any]
    recommendations: List[str]


class SyncAnalyticsService:
    """Service for tracking and analyzing sync operations."""
    
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        """Initialize analytics service."""
        if redis_client:
            self.redis_client = redis_client
        else:
            # Use Redis URL from environment, fallback to localhost for development
            import os
            redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
            self.redis_client = redis.from_url(redis_url, decode_responses=True)
        self.metrics_key_prefix = "analytics:sync:"
        self.reports_key_prefix = "reports:sync:"
        
    def track_sync_start(self, operation_id: str, operation_type: str, 
                        items_count: int, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Track the start of a sync operation."""
        try:
            metric_data = {
                'operation_id': operation_id,
                'operation_type': operation_type,
                'items_count': items_count,
                'start_time': datetime.utcnow().isoformat(),
                'status': 'started',
                'metadata': metadata or {}
            }
            
            key = f"{self.metrics_key_prefix}operation:{operation_id}"
            self.redis_client.setex(key, 3600, json.dumps(metric_data))  # Expire after 1 hour
            
            # Track operation count
            self.redis_client.incr(f"{self.metrics_key_prefix}count:total")
            self.redis_client.incr(f"{self.metrics_key_prefix}count:started")
            
            logger.info(f"Tracked sync start: {operation_id}")
            
        except Exception as e:
            logger.error(f"Failed to track sync start: {e}")
    
    def track_sync_progress(self, operation_id: str, items_processed: int, 
                           current_throughput: float, errors_count: int = 0) -> None:
        """Track progress of a sync operation."""
        try:
            # Update operation data
            key = f"{self.metrics_key_prefix}operation:{operation_id}"
            operation_data = self.redis_client.get(key)
            
            if operation_data:
                data = json.loads(operation_data)
                data.update({
                    'items_processed': items_processed,
                    'current_throughput': current_throughput,
                    'errors_count': errors_count,
                    'last_update': datetime.utcnow().isoformat()
                })
                
                self.redis_client.setex(key, 3600, json.dumps(data))
                
                # Track throughput metric
                self._record_metric(
                    MetricType.THROUGHPUT, 
                    current_throughput, 
                    operation_id,
                    {'items_processed': items_processed}
                )
                
                # Track items processed
                self._record_metric(
                    MetricType.ITEMS_PROCESSED, 
                    items_processed, 
                    operation_id
                )
                
        except Exception as e:
            logger.error(f"Failed to track sync progress: {e}")
    
    def track_sync_completion(self, operation_id: str, success: bool, 
                            total_items: int, duration: float, 
                            errors: List[Dict[str, Any]] = None) -> None:
        """Track completion of a sync operation."""
        try:
            # Update operation data
            key = f"{self.metrics_key_prefix}operation:{operation_id}"
            operation_data = self.redis_client.get(key)
            
            if operation_data:
                data = json.loads(operation_data)
                data.update({
                    'status': 'completed' if success else 'failed',
                    'success': success,
                    'total_items': total_items,
                    'duration': duration,
                    'errors': errors or [],
                    'end_time': datetime.utcnow().isoformat()
                })
                
                self.redis_client.setex(key, 86400, json.dumps(data))  # Keep for 24 hours
                
                # Track completion metrics
                if success:
                    self.redis_client.incr(f"{self.metrics_key_prefix}count:successful")
                    self._record_metric(MetricType.SYNC_SUCCESS, 1, operation_id)
                else:
                    self.redis_client.incr(f"{self.metrics_key_prefix}count:failed")
                    self._record_metric(MetricType.SYNC_FAILURE, 1, operation_id)
                
                # Track duration
                self._record_metric(
                    MetricType.SYNC_DURATION, 
                    duration, 
                    operation_id,
                    {'total_items': total_items}
                )
                
                # Track error rate
                if errors:
                    error_rate = len(errors) / total_items if total_items > 0 else 0
                    self._record_metric(MetricType.ERROR_RATE, error_rate, operation_id)
                    
                    # Store error details for analysis
                    self._store_error_details(operation_id, errors)
                
                logger.info(f"Tracked sync completion: {operation_id} (success: {success})")
                
        except Exception as e:
            logger.error(f"Failed to track sync completion: {e}")
    
    def track_conflict_detection(self, operation_id: str, conflicts_detected: int,
                               auto_resolved: int, manual_resolution_needed: int) -> None:
        """Track conflict detection metrics."""
        try:
            conflict_data = {
                'operation_id': operation_id,
                'conflicts_detected': conflicts_detected,
                'auto_resolved': auto_resolved,
                'manual_resolution_needed': manual_resolution_needed,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            # Store conflict metrics
            key = f"{self.metrics_key_prefix}conflicts:{operation_id}"
            self.redis_client.setex(key, 86400, json.dumps(conflict_data))
            
            # Track aggregate conflict stats
            self.redis_client.incrby(f"{self.metrics_key_prefix}conflicts:total", conflicts_detected)
            self.redis_client.incrby(f"{self.metrics_key_prefix}conflicts:auto_resolved", auto_resolved)
            self.redis_client.incrby(f"{self.metrics_key_prefix}conflicts:manual_needed", manual_resolution_needed)
            
            # Record conflict metric
            self._record_metric(
                MetricType.CONFLICT_DETECTION,
                conflicts_detected,
                operation_id,
                {
                    'auto_resolved': auto_resolved,
                    'manual_needed': manual_resolution_needed,
                    'resolution_rate': auto_resolved / conflicts_detected if conflicts_detected > 0 else 0
                }
            )
            
        except Exception as e:
            logger.error(f"Failed to track conflict detection: {e}")
    
    def _record_metric(self, metric_type: MetricType, value: float, 
                      operation_id: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Record a metric data point."""
        try:
            metric = SyncMetric(
                type=metric_type,
                value=value,
                timestamp=datetime.utcnow(),
                operation_id=operation_id,
                metadata=metadata or {}
            )
            
            # Store in time-series format
            timestamp_key = int(metric.timestamp.timestamp())
            key = f"{self.metrics_key_prefix}timeseries:{metric_type.value}:{timestamp_key}"
            
            metric_data = {
                'value': value,
                'operation_id': operation_id,
                'timestamp': metric.timestamp.isoformat(),
                'metadata': metadata or {}
            }
            
            self.redis_client.setex(key, 604800, json.dumps(metric_data))  # Keep for 7 days
            
            # Add to sorted set for efficient time-based queries
            timeseries_key = f"{self.metrics_key_prefix}ts:{metric_type.value}"
            self.redis_client.zadd(timeseries_key, {key: timestamp_key})
            
        except Exception as e:
            logger.error(f"Failed to record metric: {e}")
    
    def _store_error_details(self, operation_id: str, errors: List[Dict[str, Any]]) -> None:
        """Store detailed error information for analysis."""
        try:
            error_data = {
                'operation_id': operation_id,
                'errors': errors,
                'timestamp': datetime.utcnow().isoformat(),
                'error_count': len(errors)
            }
            
            key = f"{self.metrics_key_prefix}errors:{operation_id}"
            self.redis_client.setex(key, 604800, json.dumps(error_data))  # Keep for 7 days
            
            # Track error types
            for error in errors:
                error_type = error.get('type', 'unknown')
                self.redis_client.incr(f"{self.metrics_key_prefix}error_types:{error_type}")
                
        except Exception as e:
            logger.error(f"Failed to store error details: {e}")
    
    def generate_report(self, period: ReportPeriod, 
                       start_time: Optional[datetime] = None,
                       end_time: Optional[datetime] = None) -> SyncReport:
        """Generate a comprehensive sync analytics report."""
        try:
            # Determine time range
            if period == ReportPeriod.CUSTOM:
                if not start_time or not end_time:
                    raise ValueError("Custom period requires start_time and end_time")
            else:
                end_time = datetime.utcnow()
                if period == ReportPeriod.LAST_HOUR:
                    start_time = end_time - timedelta(hours=1)
                elif period == ReportPeriod.LAST_24_HOURS:
                    start_time = end_time - timedelta(days=1)
                elif period == ReportPeriod.LAST_WEEK:
                    start_time = end_time - timedelta(weeks=1)
                elif period == ReportPeriod.LAST_MONTH:
                    start_time = end_time - timedelta(days=30)
            
            # Collect metrics for the period
            metrics = self._collect_metrics_for_period(start_time, end_time)
            
            # Calculate aggregate statistics
            total_operations = len(metrics.get('operations', []))
            successful_operations = len([op for op in metrics.get('operations', []) 
                                       if op.get('success', False)])
            failed_operations = total_operations - successful_operations
            
            # Calculate average duration
            durations = [op.get('duration', 0) for op in metrics.get('operations', []) 
                        if op.get('duration')]
            avg_duration = statistics.mean(durations) if durations else 0
            
            # Calculate total items processed
            total_items = sum(op.get('total_items', 0) for op in metrics.get('operations', []))
            
            # Calculate error rate
            error_rate = (failed_operations / total_operations * 100) if total_operations > 0 else 0
            
            # Calculate throughput
            period_hours = (end_time - start_time).total_seconds() / 3600
            throughput_per_hour = total_items / period_hours if period_hours > 0 else 0
            
            # Get top errors
            top_errors = self._get_top_errors(start_time, end_time)
            
            # Get performance trends
            performance_trends = self._get_performance_trends(start_time, end_time)
            
            # Get resource usage
            resource_usage = self._get_resource_usage(start_time, end_time)
            
            # Get conflict statistics
            conflict_stats = self._get_conflict_stats(start_time, end_time)
            
            # Generate recommendations
            recommendations = self._generate_recommendations(
                error_rate, avg_duration, throughput_per_hour, conflict_stats
            )
            
            report = SyncReport(
                period=period,
                start_time=start_time,
                end_time=end_time,
                total_operations=total_operations,
                successful_operations=successful_operations,
                failed_operations=failed_operations,
                avg_duration=avg_duration,
                total_items_processed=total_items,
                error_rate=error_rate,
                throughput_per_hour=throughput_per_hour,
                top_errors=top_errors,
                performance_trends=performance_trends,
                resource_usage=resource_usage,
                conflict_stats=conflict_stats,
                recommendations=recommendations
            )
            
            # Cache the report
            self._cache_report(report)
            
            logger.info(f"Generated sync report for period {period.value}")
            return report
            
        except Exception as e:
            logger.error(f"Failed to generate report: {e}")
            raise
    
    def _collect_metrics_for_period(self, start_time: datetime, end_time: datetime) -> Dict[str, Any]:
        """Collect all metrics for a given time period."""
        try:
            start_timestamp = int(start_time.timestamp())
            end_timestamp = int(end_time.timestamp())
            
            # Get all operations in the period
            operations = []
            operation_keys = self.redis_client.keys(f"{self.metrics_key_prefix}operation:*")
            
            for key in operation_keys:
                operation_data = self.redis_client.get(key)
                if operation_data:
                    data = json.loads(operation_data)
                    op_timestamp = int(datetime.fromisoformat(data['start_time']).timestamp())
                    
                    if start_timestamp <= op_timestamp <= end_timestamp:
                        operations.append(data)
            
            return {
                'operations': operations,
                'period_start': start_time,
                'period_end': end_time
            }
            
        except Exception as e:
            logger.error(f"Failed to collect metrics: {e}")
            return {}
    
    def _get_top_errors(self, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        """Get the most common errors in the period."""
        try:
            error_counts = defaultdict(int)
            error_examples = {}
            
            # Get error type counts
            error_type_keys = self.redis_client.keys(f"{self.metrics_key_prefix}error_types:*")
            for key in error_type_keys:
                error_type = key.split(':')[-1]
                count = int(self.redis_client.get(key) or 0)
                error_counts[error_type] = count
            
            # Sort by count and return top errors
            sorted_errors = sorted(error_counts.items(), key=lambda x: x[1], reverse=True)
            
            return [
                {
                    'error_type': error_type,
                    'count': count,
                    'percentage': (count / sum(error_counts.values()) * 100) if sum(error_counts.values()) > 0 else 0
                }
                for error_type, count in sorted_errors[:10]  # Top 10 errors
            ]
            
        except Exception as e:
            logger.error(f"Failed to get top errors: {e}")
            return []
    
    def _get_performance_trends(self, start_time: datetime, end_time: datetime) -> Dict[str, List[float]]:
        """Get performance trends over time."""
        try:
            trends = {}
            
            # Get duration trends
            duration_key = f"{self.metrics_key_prefix}ts:{MetricType.SYNC_DURATION.value}"
            duration_data = self._get_timeseries_data(duration_key, start_time, end_time)
            trends['duration'] = [d['value'] for d in duration_data]
            
            # Get throughput trends
            throughput_key = f"{self.metrics_key_prefix}ts:{MetricType.THROUGHPUT.value}"
            throughput_data = self._get_timeseries_data(throughput_key, start_time, end_time)
            trends['throughput'] = [t['value'] for t in throughput_data]
            
            # Get error rate trends
            error_rate_key = f"{self.metrics_key_prefix}ts:{MetricType.ERROR_RATE.value}"
            error_rate_data = self._get_timeseries_data(error_rate_key, start_time, end_time)
            trends['error_rate'] = [e['value'] for e in error_rate_data]
            
            return trends
            
        except Exception as e:
            logger.error(f"Failed to get performance trends: {e}")
            return {}
    
    def _get_timeseries_data(self, key: str, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        """Get timeseries data for a specific metric."""
        try:
            start_timestamp = int(start_time.timestamp())
            end_timestamp = int(end_time.timestamp())
            
            # Get data points in the time range
            data_keys = self.redis_client.zrangebyscore(key, start_timestamp, end_timestamp)
            
            data_points = []
            for data_key in data_keys:
                data = self.redis_client.get(data_key)
                if data:
                    data_points.append(json.loads(data))
            
            return sorted(data_points, key=lambda x: x['timestamp'])
            
        except Exception as e:
            logger.error(f"Failed to get timeseries data: {e}")
            return []
    
    def _get_resource_usage(self, start_time: datetime, end_time: datetime) -> Dict[str, float]:
        """Get resource usage statistics."""
        try:
            # This is a placeholder - in a real implementation, you'd integrate with
            # system monitoring tools to get actual resource usage
            return {
                'cpu_usage_avg': 0.0,
                'memory_usage_avg': 0.0,
                'disk_io_avg': 0.0,
                'network_io_avg': 0.0
            }
            
        except Exception as e:
            logger.error(f"Failed to get resource usage: {e}")
            return {}
    
    def _get_conflict_stats(self, start_time: datetime, end_time: datetime) -> Dict[str, Any]:
        """Get conflict detection statistics."""
        try:
            total_conflicts = int(self.redis_client.get(f"{self.metrics_key_prefix}conflicts:total") or 0)
            auto_resolved = int(self.redis_client.get(f"{self.metrics_key_prefix}conflicts:auto_resolved") or 0)
            manual_needed = int(self.redis_client.get(f"{self.metrics_key_prefix}conflicts:manual_needed") or 0)
            
            return {
                'total_conflicts': total_conflicts,
                'auto_resolved': auto_resolved,
                'manual_resolution_needed': manual_needed,
                'auto_resolution_rate': (auto_resolved / total_conflicts * 100) if total_conflicts > 0 else 0,
                'pending_manual_resolution': manual_needed
            }
            
        except Exception as e:
            logger.error(f"Failed to get conflict stats: {e}")
            return {}
    
    def _generate_recommendations(self, error_rate: float, avg_duration: float, 
                                throughput: float, conflict_stats: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on metrics."""
        recommendations = []
        
        # Error rate recommendations
        if error_rate > 10:
            recommendations.append("High error rate detected. Consider reviewing error logs and improving data validation.")
        elif error_rate > 5:
            recommendations.append("Moderate error rate. Monitor closely and consider optimizing sync processes.")
        
        # Performance recommendations
        if avg_duration > 300:  # 5 minutes
            recommendations.append("Sync operations are taking longer than expected. Consider optimizing queries or implementing parallel processing.")
        
        # Throughput recommendations
        if throughput < 100:  # items per hour
            recommendations.append("Low throughput detected. Consider increasing batch sizes or optimizing processing logic.")
        
        # Conflict resolution recommendations
        auto_resolution_rate = conflict_stats.get('auto_resolution_rate', 0)
        if auto_resolution_rate < 70:
            recommendations.append("Low automatic conflict resolution rate. Consider improving conflict detection rules.")
        
        # If no issues found
        if not recommendations:
            recommendations.append("Sync operations are performing well. Continue monitoring for consistency.")
        
        return recommendations
    
    def _cache_report(self, report: SyncReport) -> None:
        """Cache the generated report."""
        try:
            report_data = {
                'period': report.period.value,
                'start_time': report.start_time.isoformat(),
                'end_time': report.end_time.isoformat(),
                'total_operations': report.total_operations,
                'successful_operations': report.successful_operations,
                'failed_operations': report.failed_operations,
                'avg_duration': report.avg_duration,
                'total_items_processed': report.total_items_processed,
                'error_rate': report.error_rate,
                'throughput_per_hour': report.throughput_per_hour,
                'top_errors': report.top_errors,
                'performance_trends': report.performance_trends,
                'resource_usage': report.resource_usage,
                'conflict_stats': report.conflict_stats,
                'recommendations': report.recommendations,
                'generated_at': datetime.utcnow().isoformat()
            }
            
            cache_key = f"{self.reports_key_prefix}{report.period.value}:{int(report.start_time.timestamp())}"
            self.redis_client.setex(cache_key, 3600, json.dumps(report_data))  # Cache for 1 hour
            
        except Exception as e:
            logger.error(f"Failed to cache report: {e}")
    
    def get_real_time_metrics(self) -> Dict[str, Any]:
        """Get real-time sync metrics."""
        try:
            # Get current counts
            total_ops = int(self.redis_client.get(f"{self.metrics_key_prefix}count:total") or 0)
            successful_ops = int(self.redis_client.get(f"{self.metrics_key_prefix}count:successful") or 0)
            failed_ops = int(self.redis_client.get(f"{self.metrics_key_prefix}count:failed") or 0)
            
            # Get active operations
            active_ops = []
            operation_keys = self.redis_client.keys(f"{self.metrics_key_prefix}operation:*")
            for key in operation_keys:
                op_data = self.redis_client.get(key)
                if op_data:
                    data = json.loads(op_data)
                    if data.get('status') == 'started':
                        active_ops.append({
                            'operation_id': data['operation_id'],
                            'operation_type': data['operation_type'],
                            'start_time': data['start_time'],
                            'items_processed': data.get('items_processed', 0),
                            'items_count': data.get('items_count', 0)
                        })
            
            return {
                'total_operations': total_ops,
                'successful_operations': successful_ops,
                'failed_operations': failed_ops,
                'success_rate': (successful_ops / total_ops * 100) if total_ops > 0 else 0,
                'active_operations': active_ops,
                'active_operations_count': len(active_ops),
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get real-time metrics: {e}")
            return {}
    
    def cleanup_old_metrics(self, days_to_keep: int = 7) -> None:
        """Clean up old metrics to prevent Redis from growing too large."""
        try:
            cutoff_time = datetime.utcnow() - timedelta(days=days_to_keep)
            cutoff_timestamp = int(cutoff_time.timestamp())
            
            # Clean up timeseries data
            for metric_type in MetricType:
                key = f"{self.metrics_key_prefix}ts:{metric_type.value}"
                # Remove old entries
                self.redis_client.zremrangebyscore(key, 0, cutoff_timestamp)
            
            # Clean up old operation data
            operation_keys = self.redis_client.keys(f"{self.metrics_key_prefix}operation:*")
            for key in operation_keys:
                op_data = self.redis_client.get(key)
                if op_data:
                    data = json.loads(op_data)
                    start_time = datetime.fromisoformat(data['start_time'])
                    if start_time < cutoff_time:
                        self.redis_client.delete(key)
            
            logger.info(f"Cleaned up metrics older than {days_to_keep} days")
            
        except Exception as e:
            logger.error(f"Failed to cleanup old metrics: {e}")


# Global analytics service instance
analytics_service = SyncAnalyticsService()