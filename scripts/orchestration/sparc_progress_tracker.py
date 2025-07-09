#!/usr/bin/env python3
"""
SPARC Progress Tracker and Result Aggregator

Provides comprehensive progress tracking and result aggregation for SPARC orchestrator.
Integrates with existing WebSocket patterns for real-time updates.
"""

import json
import time
import uuid
import threading
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, asdict
from enum import Enum
from datetime import datetime, timedelta
import logging
import statistics
from collections import defaultdict, deque
import redis

# Import existing infrastructure
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from orchestration.sparc_memory import SPARCMemoryCoordinator, SPARCMemoryEventType


class SPARCProgressStage(Enum):
    INITIALIZATION = "initialization"
    AGENT_DEPLOYMENT = "agent_deployment"
    TASK_DISTRIBUTION = "task_distribution"
    EXECUTION = "execution"
    RESULT_AGGREGATION = "result_aggregation"
    CLEANUP = "cleanup"
    COMPLETED = "completed"


class SPARCMetricType(Enum):
    THROUGHPUT = "throughput"
    LATENCY = "latency"
    SUCCESS_RATE = "success_rate"
    RESOURCE_UTILIZATION = "resource_utilization"
    AGENT_PERFORMANCE = "agent_performance"
    ERROR_RATE = "error_rate"


@dataclass
class SPARCProgressSnapshot:
    session_id: str
    timestamp: datetime
    stage: SPARCProgressStage
    overall_progress_percent: float
    tasks_total: int
    tasks_completed: int
    tasks_failed: int
    tasks_in_progress: int
    agents_active: int
    agents_total: int
    performance_metrics: Dict[str, float]
    estimated_completion_time: Optional[datetime] = None
    stage_durations: Dict[str, float] = None
    
    def __post_init__(self):
        if self.stage_durations is None:
            self.stage_durations = {}


@dataclass
class SPARCResultAggregation:
    session_id: str
    aggregated_at: datetime
    total_execution_time: float
    task_results: Dict[str, Any]
    performance_summary: Dict[str, Any]
    error_summary: Dict[str, List[str]]
    agent_contributions: Dict[str, Dict[str, Any]]
    success_metrics: Dict[str, float]
    recommendations: List[str]


class SPARCProgressTracker:
    """
    SPARC Progress Tracker - Monitors and tracks session progress
    
    Features:
    - Real-time progress monitoring
    - Performance metrics collection
    - Predictive completion estimation
    - Stage-based progress tracking
    - WebSocket integration for live updates
    """
    
    def __init__(self, memory_coordinator: SPARCMemoryCoordinator, 
                 websocket_handler: Optional[Callable] = None):
        self.memory = memory_coordinator
        self.websocket_handler = websocket_handler
        self.logger = self._setup_logging()
        
        # Progress tracking state
        self.session_snapshots: Dict[str, List[SPARCProgressSnapshot]] = defaultdict(list)
        self.session_metrics: Dict[str, Dict[str, deque]] = defaultdict(lambda: defaultdict(lambda: deque(maxlen=1000)))
        self.stage_estimations: Dict[str, Dict[str, float]] = {}
        
        # Real-time monitoring
        self.monitoring_enabled = True
        self.monitor_thread = None
        self.update_interval = 5  # seconds
        
        # Performance baselines (learned from historical data)
        self.performance_baselines = self._initialize_baselines()
        
        # Start monitoring
        self.start_monitoring()
    
    def _setup_logging(self) -> logging.Logger:
        logger = logging.getLogger("sparc_progress_tracker")
        logger.setLevel(logging.INFO)
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        return logger
    
    def _initialize_baselines(self) -> Dict[str, Dict[str, float]]:
        """Initialize performance baselines based on task types"""
        return {
            "data_processing": {
                "avg_duration": 120.0,  # seconds
                "throughput": 1000.0,   # records per second
                "success_rate": 0.95,
                "memory_usage": 256.0   # MB
            },
            "shopify_upload": {
                "avg_duration": 300.0,
                "throughput": 2.0,      # products per second
                "success_rate": 0.98,
                "memory_usage": 128.0
            },
            "cleanup_operation": {
                "avg_duration": 60.0,
                "throughput": 5.0,      # items per second
                "success_rate": 0.99,
                "memory_usage": 64.0
            },
            "parallel_analysis": {
                "avg_duration": 180.0,
                "throughput": 10.0,     # chunks per second
                "success_rate": 0.92,
                "memory_usage": 512.0
            }
        }
    
    def start_session_tracking(self, session_id: str) -> bool:
        """Start tracking progress for a session"""
        try:
            # Initialize tracking state
            self.session_snapshots[session_id] = []
            self.session_metrics[session_id] = defaultdict(lambda: deque(maxlen=1000))
            self.stage_estimations[session_id] = {}
            
            # Create initial snapshot
            snapshot = self._create_progress_snapshot(session_id, SPARCProgressStage.INITIALIZATION)
            self.session_snapshots[session_id].append(snapshot)
            
            # Store in memory coordinator
            self.memory.set_shared_context(
                session_id, 
                "progress_tracking", 
                {"started_at": datetime.now().isoformat(), "status": "tracking"}
            )
            
            self.logger.info(f"Started progress tracking for session: {session_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start session tracking: {e}")
            return False
    
    def update_stage(self, session_id: str, stage: SPARCProgressStage) -> bool:
        """Update the current stage of a session"""
        try:
            # Create snapshot for new stage
            snapshot = self._create_progress_snapshot(session_id, stage)
            self.session_snapshots[session_id].append(snapshot)
            
            # Update stage duration estimation
            self._update_stage_estimation(session_id, stage)
            
            # Store in memory coordinator
            self.memory.set_shared_context(
                session_id,
                "current_stage",
                {"stage": stage.value, "updated_at": datetime.now().isoformat()}
            )
            
            # Send WebSocket update
            if self.websocket_handler:
                self._send_websocket_update(session_id, snapshot)
            
            self.logger.info(f"Session {session_id} moved to stage: {stage.value}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to update stage: {e}")
            return False
    
    def _create_progress_snapshot(self, session_id: str, stage: SPARCProgressStage) -> SPARCProgressSnapshot:
        """Create a progress snapshot for the current session state"""
        try:
            # Get session data
            session_data = self.memory.get_session(session_id)
            if not session_data:
                raise ValueError(f"Session {session_id} not found")
            
            # Get task progress
            task_progress = self._calculate_task_progress(session_id)
            
            # Get agent status
            agents = self.memory.get_session_agents(session_id)
            agents_active = sum(1 for agent in agents if agent.get("status") != "offline")
            agents_total = len(agents)
            
            # Calculate overall progress
            overall_progress = self._calculate_overall_progress(session_id, stage, task_progress)
            
            # Get performance metrics
            performance_metrics = self._collect_performance_metrics(session_id)
            
            # Estimate completion time
            estimated_completion = self._estimate_completion_time(session_id, stage, overall_progress)
            
            # Calculate stage durations
            stage_durations = self._calculate_stage_durations(session_id)
            
            return SPARCProgressSnapshot(
                session_id=session_id,
                timestamp=datetime.now(),
                stage=stage,
                overall_progress_percent=overall_progress,
                tasks_total=task_progress["total"],
                tasks_completed=task_progress["completed"],
                tasks_failed=task_progress["failed"],
                tasks_in_progress=task_progress["in_progress"],
                agents_active=agents_active,
                agents_total=agents_total,
                performance_metrics=performance_metrics,
                estimated_completion_time=estimated_completion,
                stage_durations=stage_durations
            )
            
        except Exception as e:
            self.logger.error(f"Failed to create progress snapshot: {e}")
            # Return minimal snapshot
            return SPARCProgressSnapshot(
                session_id=session_id,
                timestamp=datetime.now(),
                stage=stage,
                overall_progress_percent=0.0,
                tasks_total=0,
                tasks_completed=0,
                tasks_failed=0,
                tasks_in_progress=0,
                agents_active=0,
                agents_total=0,
                performance_metrics={}
            )
    
    def _calculate_task_progress(self, session_id: str) -> Dict[str, int]:
        """Calculate task progress from session data"""
        try:
            session_data = self.memory.get_session(session_id)
            if not session_data or "tasks" not in session_data:
                return {"total": 0, "completed": 0, "failed": 0, "in_progress": 0}
            
            tasks = session_data["tasks"]
            total = len(tasks)
            completed = sum(1 for task in tasks.values() if task.get("status") == "completed")
            failed = sum(1 for task in tasks.values() if task.get("status") == "failed")
            in_progress = sum(1 for task in tasks.values() if task.get("status") == "in_progress")
            
            return {
                "total": total,
                "completed": completed,
                "failed": failed,
                "in_progress": in_progress
            }
            
        except Exception as e:
            self.logger.error(f"Failed to calculate task progress: {e}")
            return {"total": 0, "completed": 0, "failed": 0, "in_progress": 0}
    
    def _calculate_overall_progress(self, session_id: str, stage: SPARCProgressStage, 
                                  task_progress: Dict[str, int]) -> float:
        """Calculate overall session progress percentage"""
        try:
            # Stage-based progress weights
            stage_weights = {
                SPARCProgressStage.INITIALIZATION: 5.0,
                SPARCProgressStage.AGENT_DEPLOYMENT: 10.0,
                SPARCProgressStage.TASK_DISTRIBUTION: 5.0,
                SPARCProgressStage.EXECUTION: 70.0,
                SPARCProgressStage.RESULT_AGGREGATION: 5.0,
                SPARCProgressStage.CLEANUP: 3.0,
                SPARCProgressStage.COMPLETED: 2.0
            }
            
            # Calculate base progress from completed stages
            base_progress = 0.0
            for s in SPARCProgressStage:
                if s.value < stage.value or (s == stage and stage == SPARCProgressStage.COMPLETED):
                    base_progress += stage_weights[s]
                elif s == stage:
                    # Calculate progress within current stage
                    if stage == SPARCProgressStage.EXECUTION:
                        # Execution progress based on task completion
                        total_tasks = task_progress["total"]
                        if total_tasks > 0:
                            task_completion_rate = task_progress["completed"] / total_tasks
                            stage_progress = task_completion_rate * stage_weights[stage]
                        else:
                            stage_progress = 0.0
                    else:
                        # Assume 50% progress for non-execution stages
                        stage_progress = stage_weights[stage] * 0.5
                    
                    base_progress += stage_progress
                    break
            
            return min(100.0, base_progress)
            
        except Exception as e:
            self.logger.error(f"Failed to calculate overall progress: {e}")
            return 0.0
    
    def _collect_performance_metrics(self, session_id: str) -> Dict[str, float]:
        """Collect current performance metrics"""
        try:
            metrics = {}
            
            # Get agent performance data
            agents = self.memory.get_session_agents(session_id)
            if agents:
                cpu_usage = [agent.get("performance_metrics", {}).get("cpu_percent", 0) for agent in agents]
                memory_usage = [agent.get("performance_metrics", {}).get("memory_mb", 0) for agent in agents]
                
                if cpu_usage:
                    metrics["avg_cpu_percent"] = statistics.mean(cpu_usage)
                    metrics["max_cpu_percent"] = max(cpu_usage)
                
                if memory_usage:
                    metrics["avg_memory_mb"] = statistics.mean(memory_usage)
                    metrics["max_memory_mb"] = max(memory_usage)
                
                # Task completion metrics
                tasks_completed = sum(agent.get("performance_metrics", {}).get("tasks_completed", 0) for agent in agents)
                tasks_failed = sum(agent.get("performance_metrics", {}).get("tasks_failed", 0) for agent in agents)
                
                total_tasks = tasks_completed + tasks_failed
                if total_tasks > 0:
                    metrics["success_rate"] = tasks_completed / total_tasks
                    metrics["error_rate"] = tasks_failed / total_tasks
                
                # Throughput calculation
                session_data = self.memory.get_session(session_id)
                if session_data and session_data.get("started_at"):
                    start_time = datetime.fromisoformat(session_data["started_at"])
                    elapsed_time = (datetime.now() - start_time).total_seconds()
                    if elapsed_time > 0:
                        metrics["tasks_per_second"] = tasks_completed / elapsed_time
            
            return metrics
            
        except Exception as e:
            self.logger.error(f"Failed to collect performance metrics: {e}")
            return {}
    
    def _estimate_completion_time(self, session_id: str, stage: SPARCProgressStage, 
                                progress_percent: float) -> Optional[datetime]:
        """Estimate session completion time"""
        try:
            if progress_percent <= 0:
                return None
            
            # Get session start time
            session_data = self.memory.get_session(session_id)
            if not session_data or not session_data.get("started_at"):
                return None
            
            start_time = datetime.fromisoformat(session_data["started_at"])
            elapsed_time = (datetime.now() - start_time).total_seconds()
            
            # Calculate remaining time based on current progress rate
            if progress_percent > 0:
                time_per_percent = elapsed_time / progress_percent
                remaining_percent = 100.0 - progress_percent
                remaining_time = remaining_percent * time_per_percent
                
                estimated_completion = datetime.now() + timedelta(seconds=remaining_time)
                
                # Apply stage-specific adjustments
                stage_factors = {
                    SPARCProgressStage.INITIALIZATION: 1.1,
                    SPARCProgressStage.AGENT_DEPLOYMENT: 1.2,
                    SPARCProgressStage.TASK_DISTRIBUTION: 1.0,
                    SPARCProgressStage.EXECUTION: 1.0,
                    SPARCProgressStage.RESULT_AGGREGATION: 0.8,
                    SPARCProgressStage.CLEANUP: 0.7,
                    SPARCProgressStage.COMPLETED: 0.0
                }
                
                factor = stage_factors.get(stage, 1.0)
                adjusted_completion = datetime.now() + timedelta(seconds=remaining_time * factor)
                
                return adjusted_completion
            
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to estimate completion time: {e}")
            return None
    
    def _calculate_stage_durations(self, session_id: str) -> Dict[str, float]:
        """Calculate duration of completed stages"""
        try:
            snapshots = self.session_snapshots[session_id]
            if len(snapshots) < 2:
                return {}
            
            durations = {}
            for i in range(1, len(snapshots)):
                prev_snapshot = snapshots[i-1]
                curr_snapshot = snapshots[i]
                
                stage_name = prev_snapshot.stage.value
                duration = (curr_snapshot.timestamp - prev_snapshot.timestamp).total_seconds()
                durations[stage_name] = duration
            
            return durations
            
        except Exception as e:
            self.logger.error(f"Failed to calculate stage durations: {e}")
            return {}
    
    def _update_stage_estimation(self, session_id: str, stage: SPARCProgressStage):
        """Update stage time estimation based on historical data"""
        try:
            if session_id not in self.stage_estimations:
                self.stage_estimations[session_id] = {}
            
            # This would learn from historical data in a production system
            # For now, use baseline estimations
            stage_estimates = {
                SPARCProgressStage.INITIALIZATION: 30,      # seconds
                SPARCProgressStage.AGENT_DEPLOYMENT: 60,
                SPARCProgressStage.TASK_DISTRIBUTION: 20,
                SPARCProgressStage.EXECUTION: 600,
                SPARCProgressStage.RESULT_AGGREGATION: 40,
                SPARCProgressStage.CLEANUP: 30,
                SPARCProgressStage.COMPLETED: 0
            }
            
            self.stage_estimations[session_id][stage.value] = stage_estimates.get(stage, 60)
            
        except Exception as e:
            self.logger.error(f"Failed to update stage estimation: {e}")
    
    def _send_websocket_update(self, session_id: str, snapshot: SPARCProgressSnapshot):
        """Send progress update via WebSocket"""
        try:
            if self.websocket_handler:
                update_data = {
                    "type": "progress_update",
                    "session_id": session_id,
                    "timestamp": snapshot.timestamp.isoformat(),
                    "stage": snapshot.stage.value,
                    "progress_percent": snapshot.overall_progress_percent,
                    "tasks": {
                        "total": snapshot.tasks_total,
                        "completed": snapshot.tasks_completed,
                        "failed": snapshot.tasks_failed,
                        "in_progress": snapshot.tasks_in_progress
                    },
                    "agents": {
                        "active": snapshot.agents_active,
                        "total": snapshot.agents_total
                    },
                    "performance": snapshot.performance_metrics,
                    "estimated_completion": snapshot.estimated_completion_time.isoformat() 
                                          if snapshot.estimated_completion_time else None
                }
                
                self.websocket_handler(session_id, update_data)
                
        except Exception as e:
            self.logger.error(f"Failed to send WebSocket update: {e}")
    
    def start_monitoring(self):
        """Start the monitoring thread"""
        if not self.monitor_thread:
            self.monitor_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
            self.monitor_thread.start()
            self.logger.info("Started SPARC progress monitoring")
    
    def _monitoring_loop(self):
        """Main monitoring loop"""
        while self.monitoring_enabled:
            try:
                # Update progress for all active sessions
                for session_id in list(self.session_snapshots.keys()):
                    self._update_session_progress(session_id)
                
                time.sleep(self.update_interval)
                
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}")
                time.sleep(5)
    
    def _update_session_progress(self, session_id: str):
        """Update progress for a specific session"""
        try:
            # Get current session status
            session_data = self.memory.get_session(session_id)
            if not session_data:
                return
            
            status = session_data.get("status", "unknown")
            if status in ["completed", "failed", "cancelled"]:
                return  # No need to update completed sessions
            
            # Determine current stage
            current_stage = self._determine_current_stage(session_id, session_data)
            
            # Create new snapshot
            snapshot = self._create_progress_snapshot(session_id, current_stage)
            self.session_snapshots[session_id].append(snapshot)
            
            # Limit snapshot history
            if len(self.session_snapshots[session_id]) > 1000:
                self.session_snapshots[session_id] = self.session_snapshots[session_id][-500:]
            
            # Update metrics
            self._update_session_metrics(session_id, snapshot)
            
            # Send WebSocket update
            if self.websocket_handler:
                self._send_websocket_update(session_id, snapshot)
            
        except Exception as e:
            self.logger.error(f"Failed to update session progress: {e}")
    
    def _determine_current_stage(self, session_id: str, session_data: Dict[str, Any]) -> SPARCProgressStage:
        """Determine the current stage based on session state"""
        try:
            status = session_data.get("status", "initializing")
            
            if status == "completed":
                return SPARCProgressStage.COMPLETED
            elif status == "active":
                # Check task and agent states to determine stage
                tasks = session_data.get("tasks", {})
                agents = self.memory.get_session_agents(session_id)
                
                # If no agents are deployed yet
                if not agents:
                    return SPARCProgressStage.AGENT_DEPLOYMENT
                
                # If tasks haven't started
                tasks_in_progress = sum(1 for task in tasks.values() if task.get("status") == "in_progress")
                tasks_completed = sum(1 for task in tasks.values() if task.get("status") == "completed")
                
                if tasks_in_progress == 0 and tasks_completed == 0:
                    return SPARCProgressStage.TASK_DISTRIBUTION
                
                # If tasks are running
                if tasks_in_progress > 0:
                    return SPARCProgressStage.EXECUTION
                
                # If all tasks are done but session not complete
                if tasks_completed == len(tasks):
                    return SPARCProgressStage.RESULT_AGGREGATION
            
            return SPARCProgressStage.INITIALIZATION
            
        except Exception as e:
            self.logger.error(f"Failed to determine current stage: {e}")
            return SPARCProgressStage.INITIALIZATION
    
    def _update_session_metrics(self, session_id: str, snapshot: SPARCProgressSnapshot):
        """Update session metrics with new snapshot data"""
        try:
            metrics = self.session_metrics[session_id]
            
            # Store metrics time series
            metrics["progress_percent"].append((snapshot.timestamp, snapshot.overall_progress_percent))
            metrics["tasks_completed"].append((snapshot.timestamp, snapshot.tasks_completed))
            metrics["agents_active"].append((snapshot.timestamp, snapshot.agents_active))
            
            # Store performance metrics
            for metric_name, value in snapshot.performance_metrics.items():
                metrics[metric_name].append((snapshot.timestamp, value))
            
        except Exception as e:
            self.logger.error(f"Failed to update session metrics: {e}")
    
    def get_session_progress(self, session_id: str) -> Optional[SPARCProgressSnapshot]:
        """Get current progress for a session"""
        try:
            snapshots = self.session_snapshots.get(session_id, [])
            return snapshots[-1] if snapshots else None
            
        except Exception as e:
            self.logger.error(f"Failed to get session progress: {e}")
            return None
    
    def get_session_history(self, session_id: str, limit: int = 100) -> List[SPARCProgressSnapshot]:
        """Get progress history for a session"""
        try:
            snapshots = self.session_snapshots.get(session_id, [])
            return snapshots[-limit:] if snapshots else []
            
        except Exception as e:
            self.logger.error(f"Failed to get session history: {e}")
            return []
    
    def get_performance_metrics(self, session_id: str, metric_type: SPARCMetricType,
                              time_range: int = 3600) -> List[tuple]:
        """Get performance metrics for a session within time range"""
        try:
            metrics = self.session_metrics.get(session_id, {})
            metric_name = metric_type.value
            
            if metric_name not in metrics:
                return []
            
            # Filter by time range
            cutoff_time = datetime.now() - timedelta(seconds=time_range)
            filtered_metrics = [
                (timestamp, value) for timestamp, value in metrics[metric_name]
                if timestamp >= cutoff_time
            ]
            
            return filtered_metrics
            
        except Exception as e:
            self.logger.error(f"Failed to get performance metrics: {e}")
            return []
    
    def stop_session_tracking(self, session_id: str) -> bool:
        """Stop tracking progress for a session"""
        try:
            if session_id in self.session_snapshots:
                # Create final snapshot
                final_snapshot = self._create_progress_snapshot(session_id, SPARCProgressStage.COMPLETED)
                self.session_snapshots[session_id].append(final_snapshot)
                
                # Update memory coordinator
                self.memory.set_shared_context(
                    session_id,
                    "progress_tracking",
                    {"completed_at": datetime.now().isoformat(), "status": "completed"}
                )
                
                self.logger.info(f"Stopped progress tracking for session: {session_id}")
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Failed to stop session tracking: {e}")
            return False
    
    def shutdown(self):
        """Shutdown the progress tracker"""
        self.monitoring_enabled = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        self.logger.info("SPARC Progress Tracker shutdown complete")


class SPARCResultAggregator:
    """
    SPARC Result Aggregator - Collects and aggregates results from completed sessions
    """
    
    def __init__(self, memory_coordinator: SPARCMemoryCoordinator):
        self.memory = memory_coordinator
        self.logger = self._setup_logging()
    
    def _setup_logging(self) -> logging.Logger:
        logger = logging.getLogger("sparc_result_aggregator")
        logger.setLevel(logging.INFO)
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        return logger
    
    def aggregate_session_results(self, session_id: str) -> Optional[SPARCResultAggregation]:
        """Aggregate all results from a completed session"""
        try:
            # Get session data
            session_data = self.memory.get_session(session_id)
            if not session_data:
                return None
            
            # Calculate total execution time
            start_time = datetime.fromisoformat(session_data.get("started_at", datetime.now().isoformat()))
            end_time = datetime.fromisoformat(session_data.get("completed_at", datetime.now().isoformat()))
            total_execution_time = (end_time - start_time).total_seconds()
            
            # Aggregate task results
            task_results = self._aggregate_task_results(session_id, session_data)
            
            # Aggregate performance metrics
            performance_summary = self._aggregate_performance_metrics(session_id)
            
            # Aggregate errors
            error_summary = self._aggregate_errors(session_id, session_data)
            
            # Analyze agent contributions
            agent_contributions = self._analyze_agent_contributions(session_id)
            
            # Calculate success metrics
            success_metrics = self._calculate_success_metrics(session_data, performance_summary)
            
            # Generate recommendations
            recommendations = self._generate_recommendations(session_data, performance_summary, error_summary)
            
            return SPARCResultAggregation(
                session_id=session_id,
                aggregated_at=datetime.now(),
                total_execution_time=total_execution_time,
                task_results=task_results,
                performance_summary=performance_summary,
                error_summary=error_summary,
                agent_contributions=agent_contributions,
                success_metrics=success_metrics,
                recommendations=recommendations
            )
            
        except Exception as e:
            self.logger.error(f"Failed to aggregate session results: {e}")
            return None
    
    def _aggregate_task_results(self, session_id: str, session_data: Dict[str, Any]) -> Dict[str, Any]:
        """Aggregate results from all tasks"""
        try:
            tasks = session_data.get("tasks", {})
            
            aggregated_results = {
                "total_tasks": len(tasks),
                "completed_tasks": 0,
                "failed_tasks": 0,
                "task_types": defaultdict(int),
                "execution_times": [],
                "results_by_type": defaultdict(list)
            }
            
            for task_id, task in tasks.items():
                task_type = task.get("type", "unknown")
                task_status = task.get("status", "unknown")
                
                aggregated_results["task_types"][task_type] += 1
                
                if task_status == "completed":
                    aggregated_results["completed_tasks"] += 1
                    
                    execution_time = task.get("execution_time", 0)
                    if execution_time > 0:
                        aggregated_results["execution_times"].append(execution_time)
                    
                    result = task.get("result", {})
                    if result:
                        aggregated_results["results_by_type"][task_type].append(result)
                
                elif task_status == "failed":
                    aggregated_results["failed_tasks"] += 1
            
            # Calculate statistics
            if aggregated_results["execution_times"]:
                times = aggregated_results["execution_times"]
                aggregated_results["avg_execution_time"] = statistics.mean(times)
                aggregated_results["min_execution_time"] = min(times)
                aggregated_results["max_execution_time"] = max(times)
                aggregated_results["median_execution_time"] = statistics.median(times)
            
            return dict(aggregated_results)
            
        except Exception as e:
            self.logger.error(f"Failed to aggregate task results: {e}")
            return {}
    
    def _aggregate_performance_metrics(self, session_id: str) -> Dict[str, Any]:
        """Aggregate performance metrics from agents"""
        try:
            agents = self.memory.get_session_agents(session_id)
            
            performance_summary = {
                "total_agents": len(agents),
                "avg_cpu_percent": 0.0,
                "avg_memory_mb": 0.0,
                "total_tasks_completed": 0,
                "total_tasks_failed": 0,
                "agent_uptimes": [],
                "throughput_metrics": []
            }
            
            cpu_values = []
            memory_values = []
            
            for agent in agents:
                metrics = agent.get("performance_metrics", {})
                
                cpu_percent = metrics.get("cpu_percent", 0)
                memory_mb = metrics.get("memory_mb", 0)
                tasks_completed = metrics.get("tasks_completed", 0)
                tasks_failed = metrics.get("tasks_failed", 0)
                uptime = metrics.get("uptime_seconds", 0)
                
                if cpu_percent > 0:
                    cpu_values.append(cpu_percent)
                if memory_mb > 0:
                    memory_values.append(memory_mb)
                
                performance_summary["total_tasks_completed"] += tasks_completed
                performance_summary["total_tasks_failed"] += tasks_failed
                
                if uptime > 0:
                    performance_summary["agent_uptimes"].append(uptime)
                    
                    # Calculate throughput
                    if uptime > 0:
                        throughput = tasks_completed / uptime
                        performance_summary["throughput_metrics"].append(throughput)
            
            # Calculate averages
            if cpu_values:
                performance_summary["avg_cpu_percent"] = statistics.mean(cpu_values)
            if memory_values:
                performance_summary["avg_memory_mb"] = statistics.mean(memory_values)
            
            # Calculate overall throughput
            if performance_summary["throughput_metrics"]:
                performance_summary["avg_throughput"] = statistics.mean(performance_summary["throughput_metrics"])
            
            return performance_summary
            
        except Exception as e:
            self.logger.error(f"Failed to aggregate performance metrics: {e}")
            return {}
    
    def _aggregate_errors(self, session_id: str, session_data: Dict[str, Any]) -> Dict[str, List[str]]:
        """Aggregate errors by type"""
        try:
            tasks = session_data.get("tasks", {})
            error_summary = defaultdict(list)
            
            for task_id, task in tasks.items():
                if task.get("status") == "failed":
                    task_type = task.get("type", "unknown")
                    error_message = task.get("error", "Unknown error")
                    error_summary[task_type].append(error_message)
            
            return dict(error_summary)
            
        except Exception as e:
            self.logger.error(f"Failed to aggregate errors: {e}")
            return {}
    
    def _analyze_agent_contributions(self, session_id: str) -> Dict[str, Dict[str, Any]]:
        """Analyze individual agent contributions"""
        try:
            agents = self.memory.get_session_agents(session_id)
            contributions = {}
            
            for agent in agents:
                agent_id = agent.get("id", "unknown")
                metrics = agent.get("performance_metrics", {})
                
                contributions[agent_id] = {
                    "name": agent.get("name", "Unknown Agent"),
                    "capabilities": agent.get("capabilities", []),
                    "tasks_completed": metrics.get("tasks_completed", 0),
                    "tasks_failed": metrics.get("tasks_failed", 0),
                    "uptime_seconds": metrics.get("uptime_seconds", 0),
                    "avg_cpu_percent": metrics.get("cpu_percent", 0),
                    "avg_memory_mb": metrics.get("memory_mb", 0)
                }
                
                # Calculate success rate
                total_tasks = contributions[agent_id]["tasks_completed"] + contributions[agent_id]["tasks_failed"]
                if total_tasks > 0:
                    contributions[agent_id]["success_rate"] = contributions[agent_id]["tasks_completed"] / total_tasks
                else:
                    contributions[agent_id]["success_rate"] = 0.0
            
            return contributions
            
        except Exception as e:
            self.logger.error(f"Failed to analyze agent contributions: {e}")
            return {}
    
    def _calculate_success_metrics(self, session_data: Dict[str, Any], 
                                 performance_summary: Dict[str, Any]) -> Dict[str, float]:
        """Calculate overall success metrics"""
        try:
            tasks = session_data.get("tasks", {})
            total_tasks = len(tasks)
            
            if total_tasks == 0:
                return {"success_rate": 0.0, "efficiency_score": 0.0, "performance_score": 0.0}
            
            completed_tasks = sum(1 for task in tasks.values() if task.get("status") == "completed")
            success_rate = completed_tasks / total_tasks
            
            # Calculate efficiency score based on execution times
            execution_times = [task.get("execution_time", 0) for task in tasks.values() 
                             if task.get("status") == "completed" and task.get("execution_time")]
            
            efficiency_score = 1.0
            if execution_times:
                avg_time = statistics.mean(execution_times)
                # Compare against baseline (this would be learned from historical data)
                baseline_time = 180  # seconds
                efficiency_score = min(1.0, baseline_time / avg_time) if avg_time > 0 else 1.0
            
            # Calculate performance score based on resource utilization
            performance_score = 1.0
            avg_cpu = performance_summary.get("avg_cpu_percent", 0)
            if avg_cpu > 0:
                # Optimal CPU usage is around 70-80%
                if avg_cpu < 70:
                    performance_score = avg_cpu / 70
                elif avg_cpu > 90:
                    performance_score = max(0.5, (100 - avg_cpu) / 10)
            
            return {
                "success_rate": success_rate,
                "efficiency_score": efficiency_score,
                "performance_score": performance_score,
                "overall_score": (success_rate + efficiency_score + performance_score) / 3
            }
            
        except Exception as e:
            self.logger.error(f"Failed to calculate success metrics: {e}")
            return {"success_rate": 0.0, "efficiency_score": 0.0, "performance_score": 0.0}
    
    def _generate_recommendations(self, session_data: Dict[str, Any], 
                                performance_summary: Dict[str, Any],
                                error_summary: Dict[str, List[str]]) -> List[str]:
        """Generate recommendations for future sessions"""
        try:
            recommendations = []
            
            # Analyze success rate
            tasks = session_data.get("tasks", {})
            if tasks:
                total_tasks = len(tasks)
                completed_tasks = sum(1 for task in tasks.values() if task.get("status") == "completed")
                success_rate = completed_tasks / total_tasks
                
                if success_rate < 0.9:
                    recommendations.append("Consider improving error handling and retry logic")
                
                if success_rate < 0.7:
                    recommendations.append("Review task parameters and agent capabilities matching")
            
            # Analyze performance
            avg_cpu = performance_summary.get("avg_cpu_percent", 0)
            if avg_cpu < 50:
                recommendations.append("Consider increasing agent workload or reducing agent count")
            elif avg_cpu > 90:
                recommendations.append("Consider adding more agents or optimizing resource usage")
            
            # Analyze errors
            if error_summary:
                most_common_error_type = max(error_summary.keys(), key=lambda k: len(error_summary[k]))
                recommendations.append(f"Focus on resolving {most_common_error_type} task errors")
            
            # Analyze throughput
            throughput = performance_summary.get("avg_throughput", 0)
            if throughput < 0.1:  # Less than 0.1 tasks per second
                recommendations.append("Consider optimizing task execution or agent performance")
            
            return recommendations
            
        except Exception as e:
            self.logger.error(f"Failed to generate recommendations: {e}")
            return ["Unable to generate recommendations due to analysis error"]


if __name__ == "__main__":
    # Example usage
    import redis
    from orchestration.sparc_memory import SPARCMemoryCoordinator
    
    # Setup
    redis_client = redis.from_url("redis://localhost:6379/0")
    memory = SPARCMemoryCoordinator(redis_client)
    
    # Create progress tracker
    tracker = SPARCProgressTracker(memory)
    
    # Create result aggregator
    aggregator = SPARCResultAggregator(memory)
    
    # Example session tracking
    session_id = "test_session_1"
    tracker.start_session_tracking(session_id)
    
    # Simulate stage updates
    stages = [
        SPARCProgressStage.AGENT_DEPLOYMENT,
        SPARCProgressStage.TASK_DISTRIBUTION,
        SPARCProgressStage.EXECUTION,
        SPARCProgressStage.RESULT_AGGREGATION,
        SPARCProgressStage.COMPLETED
    ]
    
    for stage in stages:
        tracker.update_stage(session_id, stage)
        time.sleep(2)
        
        # Get current progress
        progress = tracker.get_session_progress(session_id)
        if progress:
            print(f"Stage: {progress.stage.value}, Progress: {progress.overall_progress_percent:.1f}%")
    
    # Get final results
    results = aggregator.aggregate_session_results(session_id)
    if results:
        print(f"Session completed in {results.total_execution_time:.1f}s")
        print(f"Success rate: {results.success_metrics.get('success_rate', 0):.1%}")
        print(f"Recommendations: {results.recommendations}")
    
    tracker.shutdown()