#!/usr/bin/env python3
"""
SPARC (Systematic Parallel Agent Resource Coordination) Orchestrator

A sophisticated orchestration system that coordinates parallel agents for complex task execution.
Built on the existing Cowans infrastructure patterns.
"""

import asyncio
import json
import time
import uuid
import logging
from typing import Dict, List, Any, Optional, Callable, Set
from dataclasses import dataclass, asdict
from enum import Enum
from datetime import datetime, timedelta
import redis
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import websocket
import requests

# Import existing infrastructure
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web_dashboard.backend.job_manager import JobManager
from web_dashboard.backend.config import Config
from web_dashboard.backend.security import ParameterValidator, ScriptSandbox


class SPARCTaskStatus(Enum):
    QUEUED = "queued"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SPARCAgentStatus(Enum):
    IDLE = "idle"
    BUSY = "busy"
    OFFLINE = "offline"
    ERROR = "error"


class SPARCSessionStatus(Enum):
    INITIALIZING = "initializing"
    ACTIVE = "active"
    COMPLETING = "completing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class SPARCTask:
    id: str
    type: str
    parameters: Dict[str, Any]
    priority: int = 5
    status: SPARCTaskStatus = SPARCTaskStatus.QUEUED
    assigned_agent: Optional[str] = None
    created_at: datetime = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    dependencies: List[str] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.dependencies is None:
            self.dependencies = []


@dataclass
class SPARCAgent:
    id: str
    name: str
    capabilities: List[str]
    status: SPARCAgentStatus = SPARCAgentStatus.IDLE
    current_task: Optional[str] = None
    last_heartbeat: datetime = None
    performance_metrics: Dict[str, float] = None
    resource_limits: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.last_heartbeat is None:
            self.last_heartbeat = datetime.now()
        if self.performance_metrics is None:
            self.performance_metrics = {"tasks_completed": 0, "avg_execution_time": 0.0, "error_rate": 0.0}
        if self.resource_limits is None:
            self.resource_limits = {"max_concurrent_tasks": 1, "memory_limit_mb": 512, "cpu_limit_percent": 80}


@dataclass
class SPARCSession:
    id: str
    name: str
    status: SPARCSessionStatus = SPARCSessionStatus.INITIALIZING
    created_at: datetime = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    tasks: Dict[str, SPARCTask] = None
    agents: Dict[str, SPARCAgent] = None
    shared_context: Dict[str, Any] = None
    configuration: Dict[str, Any] = None
    progress: Dict[str, float] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.tasks is None:
            self.tasks = {}
        if self.agents is None:
            self.agents = {}
        if self.shared_context is None:
            self.shared_context = {}
        if self.configuration is None:
            self.configuration = {"max_agents": 10, "task_timeout": 3600, "retry_policy": "exponential"}
        if self.progress is None:
            self.progress = {"total_tasks": 0, "completed_tasks": 0, "failed_tasks": 0, "completion_percentage": 0.0}


class SPARCOrchestrator:
    """
    SPARC Orchestrator - Coordinates parallel agents for complex task execution
    
    Built on existing Cowans infrastructure patterns:
    - Redis for distributed state management (like JobManager)
    - WebSocket for real-time coordination (like existing WebSocket context)
    - Threading for parallel execution (like job execution patterns)
    - Configuration management (like existing Config pattern)
    """
    
    def __init__(self, redis_client: redis.Redis = None, config: Dict[str, Any] = None):
        self.redis = redis_client or self._setup_redis()
        self.config = config or self._load_default_config()
        self.sessions: Dict[str, SPARCSession] = {}
        self.active_sessions: Set[str] = set()
        self.task_queue = asyncio.Queue()
        self.result_handlers: Dict[str, Callable] = {}
        self.logger = self._setup_logging()
        self.websocket_clients: Dict[str, Any] = {}
        self.executor = ThreadPoolExecutor(max_workers=self.config.get("max_workers", 10))
        self._running = False
        self._coordinator_thread = None
        
        # Initialize task registry (based on existing script registry pattern)
        self.task_registry = self._initialize_task_registry()
        
        # Security and validation (using existing patterns)
        self.validator = ParameterValidator()
        self.sandbox = ScriptSandbox()
    
    def _setup_redis(self) -> redis.Redis:
        """Setup Redis connection using existing configuration patterns"""
        try:
            redis_client = redis.from_url(Config.REDIS_URL)
            redis_client.ping()
            return redis_client
        except Exception as e:
            self.logger.warning(f"Redis not available: {e}, using in-memory storage")
            return None
    
    def _load_default_config(self) -> Dict[str, Any]:
        """Load default SPARC configuration"""
        return {
            "max_workers": 10,
            "max_sessions": 100,
            "session_timeout": 3600,
            "task_timeout": 600,
            "heartbeat_interval": 30,
            "cleanup_interval": 300,
            "websocket_port": 8765,
            "enable_performance_monitoring": True,
            "retry_policy": "exponential",
            "max_retries": 3
        }
    
    def _setup_logging(self) -> logging.Logger:
        """Setup logging using existing patterns"""
        logger = logging.getLogger("sparc_orchestrator")
        logger.setLevel(logging.INFO)
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        return logger
    
    def _initialize_task_registry(self) -> Dict[str, Dict[str, Any]]:
        """Initialize task registry based on existing script registry pattern"""
        return {
            "data_processing": {
                "handler": "process_data",
                "required_params": ["input_data", "processing_type"],
                "capabilities": ["data_processing", "transformation"],
                "estimated_time": 120,
                "resource_requirements": {"memory_mb": 256, "cpu_percent": 50}
            },
            "shopify_upload": {
                "handler": "upload_to_shopify",
                "required_params": ["products", "shop_url", "access_token"],
                "capabilities": ["shopify_api", "upload"],
                "estimated_time": 300,
                "resource_requirements": {"memory_mb": 512, "cpu_percent": 30}
            },
            "cleanup_operation": {
                "handler": "cleanup_data",
                "required_params": ["cleanup_type", "target_data"],
                "capabilities": ["cleanup", "maintenance"],
                "estimated_time": 60,
                "resource_requirements": {"memory_mb": 128, "cpu_percent": 20}
            },
            "parallel_analysis": {
                "handler": "analyze_parallel",
                "required_params": ["data_chunks", "analysis_type"],
                "capabilities": ["analysis", "parallel_processing"],
                "estimated_time": 180,
                "resource_requirements": {"memory_mb": 1024, "cpu_percent": 80}
            }
        }
    
    def create_session(self, name: str, tasks: List[Dict[str, Any]], 
                      agents: List[Dict[str, Any]] = None, 
                      configuration: Dict[str, Any] = None) -> str:
        """
        Create a new SPARC session
        
        Args:
            name: Session name
            tasks: List of task definitions
            agents: List of agent definitions (optional)
            configuration: Session-specific configuration (optional)
        
        Returns:
            Session ID
        """
        session_id = str(uuid.uuid4())
        
        # Create session
        session = SPARCSession(
            id=session_id,
            name=name,
            configuration={**self.config, **(configuration or {})}
        )
        
        # Add tasks
        for i, task_def in enumerate(tasks):
            task_id = f"{session_id}_task_{i}"
            task = SPARCTask(
                id=task_id,
                type=task_def["type"],
                parameters=task_def.get("parameters", {}),
                priority=task_def.get("priority", 5),
                dependencies=task_def.get("dependencies", []),
                max_retries=task_def.get("max_retries", 3)
            )
            session.tasks[task_id] = task
        
        # Add agents (or create default ones)
        if agents:
            for agent_def in agents:
                agent = SPARCAgent(
                    id=agent_def["id"],
                    name=agent_def["name"],
                    capabilities=agent_def["capabilities"],
                    resource_limits=agent_def.get("resource_limits", {})
                )
                session.agents[agent.id] = agent
        else:
            # Create default agents based on task requirements
            self._create_default_agents(session)
        
        # Store session
        self.sessions[session_id] = session
        self._persist_session(session)
        
        self.logger.info(f"Created SPARC session: {session_id} with {len(session.tasks)} tasks and {len(session.agents)} agents")
        return session_id
    
    def _create_default_agents(self, session: SPARCSession):
        """Create default agents based on task requirements"""
        required_capabilities = set()
        for task in session.tasks.values():
            task_type = task.type
            if task_type in self.task_registry:
                required_capabilities.update(self.task_registry[task_type]["capabilities"])
        
        # Create agents for each capability
        for i, capability in enumerate(required_capabilities):
            agent_id = f"{session.id}_agent_{i}"
            agent = SPARCAgent(
                id=agent_id,
                name=f"Agent-{capability}",
                capabilities=[capability]
            )
            session.agents[agent_id] = agent
    
    def start_session(self, session_id: str) -> bool:
        """Start executing a SPARC session"""
        if session_id not in self.sessions:
            self.logger.error(f"Session {session_id} not found")
            return False
        
        session = self.sessions[session_id]
        if session.status != SPARCSessionStatus.INITIALIZING:
            self.logger.error(f"Session {session_id} is not in initializing state")
            return False
        
        session.status = SPARCSessionStatus.ACTIVE
        session.started_at = datetime.now()
        session.progress["total_tasks"] = len(session.tasks)
        
        self.active_sessions.add(session_id)
        self._persist_session(session)
        
        # Start coordination thread if not running
        if not self._running:
            self._start_coordination()
        
        self.logger.info(f"Started SPARC session: {session_id}")
        return True
    
    def _start_coordination(self):
        """Start the main coordination thread"""
        self._running = True
        self._coordinator_thread = threading.Thread(target=self._coordination_loop, daemon=True)
        self._coordinator_thread.start()
        self.logger.info("SPARC coordination started")
    
    def _coordination_loop(self):
        """Main coordination loop"""
        while self._running:
            try:
                # Process each active session
                for session_id in list(self.active_sessions):
                    self._process_session(session_id)
                
                # Cleanup completed sessions
                self._cleanup_sessions()
                
                # Brief pause to prevent CPU spinning
                time.sleep(1)
                
            except Exception as e:
                self.logger.error(f"Error in coordination loop: {e}")
                time.sleep(5)
    
    def _process_session(self, session_id: str):
        """Process a single session"""
        session = self.sessions.get(session_id)
        if not session:
            return
        
        # Update agent heartbeats
        self._update_agent_heartbeats(session)
        
        # Check for ready tasks
        ready_tasks = self._get_ready_tasks(session)
        
        # Assign tasks to available agents
        for task in ready_tasks:
            available_agent = self._find_available_agent(session, task)
            if available_agent:
                self._assign_task(session, task, available_agent)
        
        # Check for completed tasks and update progress
        self._update_session_progress(session)
        
        # Check if session is complete
        if self._is_session_complete(session):
            self._complete_session(session)
    
    def _get_ready_tasks(self, session: SPARCSession) -> List[SPARCTask]:
        """Get tasks that are ready to be executed"""
        ready_tasks = []
        for task in session.tasks.values():
            if task.status == SPARCTaskStatus.QUEUED:
                # Check if all dependencies are completed
                dependencies_met = all(
                    session.tasks.get(dep_id, {}).status == SPARCTaskStatus.COMPLETED
                    for dep_id in task.dependencies
                )
                if dependencies_met:
                    ready_tasks.append(task)
        
        # Sort by priority (higher number = higher priority)
        return sorted(ready_tasks, key=lambda t: t.priority, reverse=True)
    
    def _find_available_agent(self, session: SPARCSession, task: SPARCTask) -> Optional[SPARCAgent]:
        """Find an available agent capable of handling the task"""
        task_capabilities = self.task_registry.get(task.type, {}).get("capabilities", [])
        
        for agent in session.agents.values():
            if (agent.status == SPARCAgentStatus.IDLE and
                any(cap in agent.capabilities for cap in task_capabilities)):
                return agent
        
        return None
    
    def _assign_task(self, session: SPARCSession, task: SPARCTask, agent: SPARCAgent):
        """Assign a task to an agent"""
        task.status = SPARCTaskStatus.ASSIGNED
        task.assigned_agent = agent.id
        agent.status = SPARCAgentStatus.BUSY
        agent.current_task = task.id
        
        # Execute task in thread pool
        future = self.executor.submit(self._execute_task, session.id, task.id, agent.id)
        
        self.logger.info(f"Assigned task {task.id} to agent {agent.id}")
        self._persist_session(session)
    
    def _execute_task(self, session_id: str, task_id: str, agent_id: str):
        """Execute a task (runs in thread pool)"""
        session = self.sessions.get(session_id)
        if not session:
            return
        
        task = session.tasks.get(task_id)
        agent = session.agents.get(agent_id)
        if not task or not agent:
            return
        
        try:
            task.status = SPARCTaskStatus.IN_PROGRESS
            task.started_at = datetime.now()
            self._persist_session(session)
            
            # Execute the actual task based on type
            result = self._run_task_handler(task, session.shared_context)
            
            # Task completed successfully
            task.status = SPARCTaskStatus.COMPLETED
            task.completed_at = datetime.now()
            task.result = result
            
            # Update agent
            agent.status = SPARCAgentStatus.IDLE
            agent.current_task = None
            agent.performance_metrics["tasks_completed"] += 1
            
            self.logger.info(f"Task {task_id} completed successfully")
            
        except Exception as e:
            self.logger.error(f"Task {task_id} failed: {e}")
            
            task.status = SPARCTaskStatus.FAILED
            task.error = str(e)
            task.retry_count += 1
            
            # Check if we should retry
            if task.retry_count < task.max_retries:
                task.status = SPARCTaskStatus.QUEUED
                self.logger.info(f"Retrying task {task_id} (attempt {task.retry_count + 1})")
            
            # Update agent
            agent.status = SPARCAgentStatus.IDLE
            agent.current_task = None
            agent.performance_metrics["error_rate"] += 0.1
        
        finally:
            self._persist_session(session)
    
    def _run_task_handler(self, task: SPARCTask, shared_context: Dict[str, Any]) -> Dict[str, Any]:
        """Run the actual task handler based on task type"""
        task_type = task.type
        if task_type not in self.task_registry:
            raise ValueError(f"Unknown task type: {task_type}")
        
        handler_name = self.task_registry[task_type]["handler"]
        
        # Simulate task execution (in real implementation, this would call actual handlers)
        if handler_name == "process_data":
            return self._handle_data_processing(task, shared_context)
        elif handler_name == "upload_to_shopify":
            return self._handle_shopify_upload(task, shared_context)
        elif handler_name == "cleanup_data":
            return self._handle_cleanup(task, shared_context)
        elif handler_name == "analyze_parallel":
            return self._handle_parallel_analysis(task, shared_context)
        else:
            raise ValueError(f"Unknown handler: {handler_name}")
    
    def _handle_data_processing(self, task: SPARCTask, shared_context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle data processing task"""
        # Simulate processing time
        time.sleep(2)
        return {
            "processed_records": 1000,
            "processing_time": 2.0,
            "status": "success"
        }
    
    def _handle_shopify_upload(self, task: SPARCTask, shared_context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle Shopify upload task"""
        # Simulate upload time
        time.sleep(3)
        return {
            "uploaded_products": 50,
            "upload_time": 3.0,
            "status": "success"
        }
    
    def _handle_cleanup(self, task: SPARCTask, shared_context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle cleanup task"""
        # Simulate cleanup time
        time.sleep(1)
        return {
            "cleaned_items": 25,
            "cleanup_time": 1.0,
            "status": "success"
        }
    
    def _handle_parallel_analysis(self, task: SPARCTask, shared_context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle parallel analysis task"""
        # Simulate analysis time
        time.sleep(4)
        return {
            "analyzed_chunks": 10,
            "analysis_time": 4.0,
            "insights": ["pattern_detected", "anomaly_found"],
            "status": "success"
        }
    
    def _update_agent_heartbeats(self, session: SPARCSession):
        """Update agent heartbeats (simulate agent health)"""
        current_time = datetime.now()
        for agent in session.agents.values():
            # Simulate heartbeat updates
            agent.last_heartbeat = current_time
    
    def _update_session_progress(self, session: SPARCSession):
        """Update session progress metrics"""
        total_tasks = len(session.tasks)
        completed_tasks = sum(1 for task in session.tasks.values() if task.status == SPARCTaskStatus.COMPLETED)
        failed_tasks = sum(1 for task in session.tasks.values() if task.status == SPARCTaskStatus.FAILED)
        
        session.progress.update({
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "failed_tasks": failed_tasks,
            "completion_percentage": (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
        })
    
    def _is_session_complete(self, session: SPARCSession) -> bool:
        """Check if a session is complete"""
        if session.status != SPARCSessionStatus.ACTIVE:
            return False
        
        # Check if all tasks are in terminal states
        terminal_states = {SPARCTaskStatus.COMPLETED, SPARCTaskStatus.FAILED, SPARCTaskStatus.CANCELLED}
        return all(task.status in terminal_states for task in session.tasks.values())
    
    def _complete_session(self, session: SPARCSession):
        """Complete a session"""
        session.status = SPARCSessionStatus.COMPLETED
        session.completed_at = datetime.now()
        
        # Update all agents to idle
        for agent in session.agents.values():
            agent.status = SPARCAgentStatus.IDLE
            agent.current_task = None
        
        self.active_sessions.discard(session.id)
        self._persist_session(session)
        
        self.logger.info(f"Session {session.id} completed with {session.progress['completion_percentage']:.1f}% success rate")
    
    def _cleanup_sessions(self):
        """Cleanup completed sessions older than retention period"""
        current_time = datetime.now()
        retention_period = timedelta(seconds=self.config.get("session_retention", 3600))
        
        sessions_to_remove = []
        for session_id, session in self.sessions.items():
            if (session.status in {SPARCSessionStatus.COMPLETED, SPARCSessionStatus.FAILED} and
                session.completed_at and
                current_time - session.completed_at > retention_period):
                sessions_to_remove.append(session_id)
        
        for session_id in sessions_to_remove:
            del self.sessions[session_id]
            if self.redis:
                self.redis.delete(f"sparc:session:{session_id}")
            self.logger.info(f"Cleaned up expired session: {session_id}")
    
    def _persist_session(self, session: SPARCSession):
        """Persist session to Redis (using existing patterns)"""
        if self.redis:
            try:
                session_data = {
                    "id": session.id,
                    "name": session.name,
                    "status": session.status.value,
                    "created_at": session.created_at.isoformat(),
                    "started_at": session.started_at.isoformat() if session.started_at else None,
                    "completed_at": session.completed_at.isoformat() if session.completed_at else None,
                    "tasks": {tid: asdict(task) for tid, task in session.tasks.items()},
                    "agents": {aid: asdict(agent) for aid, agent in session.agents.items()},
                    "shared_context": session.shared_context,
                    "configuration": session.configuration,
                    "progress": session.progress
                }
                
                # Convert datetime objects to strings for serialization
                session_json = json.dumps(session_data, default=str)
                self.redis.setex(f"sparc:session:{session.id}", 3600, session_json)
                
            except Exception as e:
                self.logger.error(f"Failed to persist session {session.id}: {e}")
    
    def get_session_status(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get current session status"""
        session = self.sessions.get(session_id)
        if not session:
            return None
        
        return {
            "id": session.id,
            "name": session.name,
            "status": session.status.value,
            "progress": session.progress,
            "agents": {aid: {"id": agent.id, "name": agent.name, "status": agent.status.value}
                      for aid, agent in session.agents.items()},
            "task_summary": {
                "total": len(session.tasks),
                "queued": sum(1 for t in session.tasks.values() if t.status == SPARCTaskStatus.QUEUED),
                "in_progress": sum(1 for t in session.tasks.values() if t.status == SPARCTaskStatus.IN_PROGRESS),
                "completed": sum(1 for t in session.tasks.values() if t.status == SPARCTaskStatus.COMPLETED),
                "failed": sum(1 for t in session.tasks.values() if t.status == SPARCTaskStatus.FAILED)
            }
        }
    
    def stop_session(self, session_id: str) -> bool:
        """Stop a running session"""
        session = self.sessions.get(session_id)
        if not session:
            return False
        
        session.status = SPARCSessionStatus.CANCELLED
        session.completed_at = datetime.now()
        
        # Cancel all queued/assigned tasks
        for task in session.tasks.values():
            if task.status in {SPARCTaskStatus.QUEUED, SPARCTaskStatus.ASSIGNED}:
                task.status = SPARCTaskStatus.CANCELLED
        
        # Set all agents to idle
        for agent in session.agents.values():
            agent.status = SPARCAgentStatus.IDLE
            agent.current_task = None
        
        self.active_sessions.discard(session_id)
        self._persist_session(session)
        
        self.logger.info(f"Stopped session: {session_id}")
        return True
    
    def shutdown(self):
        """Shutdown the orchestrator"""
        self._running = False
        if self._coordinator_thread:
            self._coordinator_thread.join(timeout=5)
        self.executor.shutdown(wait=True)
        self.logger.info("SPARC Orchestrator shutdown complete")


if __name__ == "__main__":
    # Example usage
    orchestrator = SPARCOrchestrator()
    
    # Define tasks for a complex workflow
    tasks = [
        {
            "type": "data_processing",
            "parameters": {"input_data": "raw_products.csv", "processing_type": "filter"},
            "priority": 10
        },
        {
            "type": "parallel_analysis",
            "parameters": {"data_chunks": ["chunk1", "chunk2"], "analysis_type": "categorization"},
            "priority": 8,
            "dependencies": ["test_session_task_0"]
        },
        {
            "type": "shopify_upload",
            "parameters": {"shop_url": "test.myshopify.com", "access_token": "token"},
            "priority": 6,
            "dependencies": ["test_session_task_1"]
        },
        {
            "type": "cleanup_operation",
            "parameters": {"cleanup_type": "temp_files", "target_data": "uploads"},
            "priority": 2,
            "dependencies": ["test_session_task_2"]
        }
    ]
    
    # Create and start session
    session_id = orchestrator.create_session("Test SPARC Session", tasks)
    orchestrator.start_session(session_id)
    
    # Monitor progress
    import time
    for i in range(30):  # Monitor for 30 seconds
        status = orchestrator.get_session_status(session_id)
        if status:
            print(f"Progress: {status['progress']['completion_percentage']:.1f}% - "
                  f"Status: {status['status']} - "
                  f"Tasks: {status['task_summary']}")
        
        if status and status['status'] in ['completed', 'failed', 'cancelled']:
            break
        
        time.sleep(1)
    
    orchestrator.shutdown()