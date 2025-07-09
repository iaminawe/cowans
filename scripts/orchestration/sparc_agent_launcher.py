#!/usr/bin/env python3
"""
SPARC Agent Launcher

Launches and manages parallel agents for SPARC orchestrator.
Integrates with existing Cowans infrastructure for job execution and management.
"""

import os
import sys
import json
import time
import uuid
import logging
import subprocess
import threading
import multiprocessing
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, asdict
from enum import Enum
import signal
import psutil
from datetime import datetime, timedelta
import redis
import websocket
import requests

# Add parent directories to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web_dashboard.backend.config import Config
from web_dashboard.backend.security import ScriptSandbox, ParameterValidator
from orchestration.sparc_memory import SPARCMemoryCoordinator


class SPARCAgentLaunchMode(Enum):
    THREAD = "thread"
    PROCESS = "process"
    CONTAINER = "container"
    REMOTE = "remote"


class SPARCAgentType(Enum):
    WORKER = "worker"
    SPECIALIST = "specialist"
    COORDINATOR = "coordinator"
    MONITOR = "monitor"


@dataclass
class SPARCAgentConfig:
    id: str
    name: str
    type: SPARCAgentType
    launch_mode: SPARCAgentLaunchMode
    capabilities: List[str]
    resource_limits: Dict[str, Any]
    environment: Dict[str, str]
    startup_script: Optional[str] = None
    heartbeat_interval: int = 30
    max_tasks: int = 1
    auto_restart: bool = True
    startup_timeout: int = 60


@dataclass
class SPARCAgentProcess:
    config: SPARCAgentConfig
    process: Optional[subprocess.Popen] = None
    thread: Optional[threading.Thread] = None
    pid: Optional[int] = None
    started_at: Optional[datetime] = None
    last_heartbeat: Optional[datetime] = None
    status: str = "stopped"
    restart_count: int = 0
    performance_metrics: Dict[str, float] = None
    
    def __post_init__(self):
        if self.performance_metrics is None:
            self.performance_metrics = {
                "cpu_percent": 0.0,
                "memory_mb": 0.0,
                "tasks_completed": 0,
                "tasks_failed": 0,
                "uptime_seconds": 0.0
            }


class SPARCAgentLauncher:
    """
    SPARC Agent Launcher - Manages the lifecycle of parallel agents
    
    Features:
    - Multi-mode agent launching (thread, process, container)
    - Resource monitoring and management
    - Automatic restart and recovery
    - Health monitoring and heartbeat tracking
    - Dynamic scaling based on workload
    """
    
    def __init__(self, memory_coordinator: SPARCMemoryCoordinator, 
                 config: Dict[str, Any] = None):
        self.memory = memory_coordinator
        self.config = config or self._load_default_config()
        self.agents: Dict[str, SPARCAgentProcess] = {}
        self.logger = self._setup_logging()
        self.validator = ParameterValidator()
        self.sandbox = ScriptSandbox()
        
        # Resource monitoring
        self.resource_monitor_thread = None
        self.monitoring_enabled = True
        
        # Agent templates
        self.agent_templates = self._initialize_agent_templates()
        
        # Start monitoring
        self.start_resource_monitoring()
    
    def _setup_logging(self) -> logging.Logger:
        logger = logging.getLogger("sparc_agent_launcher")
        logger.setLevel(logging.INFO)
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        return logger
    
    def _load_default_config(self) -> Dict[str, Any]:
        return {
            "max_agents": 20,
            "default_launch_mode": "process",
            "resource_check_interval": 10,
            "heartbeat_timeout": 90,
            "restart_delay": 5,
            "max_restarts": 3,
            "agent_script_path": os.path.join(os.path.dirname(__file__), "sparc_agent_worker.py"),
            "log_level": "INFO",
            "enable_resource_monitoring": True
        }
    
    def _initialize_agent_templates(self) -> Dict[str, SPARCAgentConfig]:
        """Initialize pre-configured agent templates"""
        return {
            "data_processor": SPARCAgentConfig(
                id="template_data_processor",
                name="Data Processing Agent",
                type=SPARCAgentType.WORKER,
                launch_mode=SPARCAgentLaunchMode.PROCESS,
                capabilities=["data_processing", "csv_handling", "filtering"],
                resource_limits={"memory_mb": 512, "cpu_percent": 50},
                environment={"PYTHONPATH": Config.SCRIPTS_BASE_PATH},
                max_tasks=2
            ),
            "shopify_uploader": SPARCAgentConfig(
                id="template_shopify_uploader",
                name="Shopify Upload Agent",
                type=SPARCAgentType.SPECIALIST,
                launch_mode=SPARCAgentLaunchMode.PROCESS,
                capabilities=["shopify_api", "product_upload", "rate_limiting"],
                resource_limits={"memory_mb": 256, "cpu_percent": 30},
                environment={"PYTHONPATH": Config.SCRIPTS_BASE_PATH},
                max_tasks=1
            ),
            "cleanup_agent": SPARCAgentConfig(
                id="template_cleanup",
                name="Cleanup Agent",
                type=SPARCAgentType.WORKER,
                launch_mode=SPARCAgentLaunchMode.PROCESS,
                capabilities=["cleanup", "file_management", "duplicate_removal"],
                resource_limits={"memory_mb": 128, "cpu_percent": 20},
                environment={"PYTHONPATH": Config.SCRIPTS_BASE_PATH},
                max_tasks=3
            ),
            "parallel_analyzer": SPARCAgentConfig(
                id="template_analyzer",
                name="Parallel Analysis Agent",
                type=SPARCAgentType.SPECIALIST,
                launch_mode=SPARCAgentLaunchMode.PROCESS,
                capabilities=["analysis", "parallel_processing", "categorization"],
                resource_limits={"memory_mb": 1024, "cpu_percent": 80},
                environment={"PYTHONPATH": Config.SCRIPTS_BASE_PATH},
                max_tasks=1
            ),
            "monitor_agent": SPARCAgentConfig(
                id="template_monitor",
                name="System Monitor Agent",
                type=SPARCAgentType.MONITOR,
                launch_mode=SPARCAgentLaunchMode.THREAD,
                capabilities=["monitoring", "health_check", "metrics"],
                resource_limits={"memory_mb": 64, "cpu_percent": 10},
                environment={},
                max_tasks=5
            )
        }
    
    def create_agent_from_template(self, template_name: str, agent_id: str = None,
                                  customizations: Dict[str, Any] = None) -> SPARCAgentConfig:
        """Create an agent configuration from a template"""
        if template_name not in self.agent_templates:
            raise ValueError(f"Unknown agent template: {template_name}")
        
        template = self.agent_templates[template_name]
        
        # Create new config from template
        config_dict = asdict(template)
        config_dict["id"] = agent_id or f"{template_name}_{uuid.uuid4().hex[:8]}"
        
        # Apply customizations
        if customizations:
            for key, value in customizations.items():
                if key in config_dict:
                    if isinstance(config_dict[key], dict) and isinstance(value, dict):
                        config_dict[key].update(value)
                    else:
                        config_dict[key] = value
        
        return SPARCAgentConfig(**config_dict)
    
    def launch_agent(self, session_id: str, agent_config: SPARCAgentConfig) -> bool:
        """Launch a single agent"""
        try:
            # Validate configuration
            if not self._validate_agent_config(agent_config):
                return False
            
            # Check resource limits
            if not self._check_resource_availability(agent_config):
                self.logger.warning(f"Insufficient resources for agent {agent_config.id}")
                return False
            
            # Create agent process object
            agent_process = SPARCAgentProcess(config=agent_config)
            
            # Launch based on mode
            if agent_config.launch_mode == SPARCAgentLaunchMode.PROCESS:
                success = self._launch_process_agent(session_id, agent_process)
            elif agent_config.launch_mode == SPARCAgentLaunchMode.THREAD:
                success = self._launch_thread_agent(session_id, agent_process)
            elif agent_config.launch_mode == SPARCAgentLaunchMode.CONTAINER:
                success = self._launch_container_agent(session_id, agent_process)
            elif agent_config.launch_mode == SPARCAgentLaunchMode.REMOTE:
                success = self._launch_remote_agent(session_id, agent_process)
            else:
                self.logger.error(f"Unsupported launch mode: {agent_config.launch_mode}")
                return False
            
            if success:
                agent_process.started_at = datetime.now()
                agent_process.status = "starting"
                self.agents[agent_config.id] = agent_process
                
                # Register with memory coordinator
                agent_data = {
                    "id": agent_config.id,
                    "name": agent_config.name,
                    "type": agent_config.type.value,
                    "capabilities": agent_config.capabilities,
                    "status": "idle",
                    "resource_limits": agent_config.resource_limits,
                    "launched_at": datetime.now().isoformat()
                }
                
                self.memory.register_agent(session_id, agent_config.id, agent_data)
                
                self.logger.info(f"Launched agent {agent_config.id} in {agent_config.launch_mode.value} mode")
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Failed to launch agent {agent_config.id}: {e}")
            return False
    
    def _validate_agent_config(self, config: SPARCAgentConfig) -> bool:
        """Validate agent configuration"""
        try:
            # Check required fields
            required_fields = ["id", "name", "capabilities"]
            for field in required_fields:
                if not getattr(config, field):
                    self.logger.error(f"Missing required field: {field}")
                    return False
            
            # Check capabilities
            if not isinstance(config.capabilities, list) or not config.capabilities:
                self.logger.error("Capabilities must be a non-empty list")
                return False
            
            # Check resource limits
            if config.resource_limits:
                memory_mb = config.resource_limits.get("memory_mb", 0)
                cpu_percent = config.resource_limits.get("cpu_percent", 0)
                
                if memory_mb <= 0 or memory_mb > 8192:  # Max 8GB
                    self.logger.error(f"Invalid memory limit: {memory_mb}MB")
                    return False
                
                if cpu_percent <= 0 or cpu_percent > 100:
                    self.logger.error(f"Invalid CPU limit: {cpu_percent}%")
                    return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Config validation error: {e}")
            return False
    
    def _check_resource_availability(self, config: SPARCAgentConfig) -> bool:
        """Check if system has enough resources for the agent"""
        try:
            # Get system resources
            memory = psutil.virtual_memory()
            cpu_count = psutil.cpu_count()
            
            # Check memory
            required_memory_mb = config.resource_limits.get("memory_mb", 256)
            available_memory_mb = memory.available / 1024 / 1024
            
            if required_memory_mb > available_memory_mb * 0.8:  # Leave 20% buffer
                self.logger.warning(f"Insufficient memory: need {required_memory_mb}MB, have {available_memory_mb:.0f}MB")
                return False
            
            # Check if we're at agent limit
            active_agents = sum(1 for agent in self.agents.values() if agent.status in ["starting", "running"])
            if active_agents >= self.config["max_agents"]:
                self.logger.warning(f"Maximum agent limit reached: {active_agents}/{self.config['max_agents']}")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Resource check error: {e}")
            return False
    
    def _launch_process_agent(self, session_id: str, agent_process: SPARCAgentProcess) -> bool:
        """Launch agent as subprocess"""
        try:
            config = agent_process.config
            
            # Prepare environment
            env = os.environ.copy()
            env.update(config.environment)
            env.update({
                "SPARC_AGENT_ID": config.id,
                "SPARC_SESSION_ID": session_id,
                "SPARC_AGENT_NAME": config.name,
                "SPARC_CAPABILITIES": json.dumps(config.capabilities),
                "SPARC_HEARTBEAT_INTERVAL": str(config.heartbeat_interval),
                "SPARC_MAX_TASKS": str(config.max_tasks),
                "REDIS_URL": getattr(Config, 'REDIS_URL', 'redis://localhost:6379/0')
            })
            
            # Prepare command
            if config.startup_script:
                cmd = [sys.executable, config.startup_script]
            else:
                cmd = [sys.executable, self.config["agent_script_path"]]
            
            # Add resource limits if available
            if hasattr(os, 'setrlimit'):
                # Memory limit (in bytes)
                memory_limit = config.resource_limits.get("memory_mb", 512) * 1024 * 1024
                os.setrlimit(os.RLIMIT_AS, (memory_limit, memory_limit))
            
            # Launch process
            process = subprocess.Popen(
                cmd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                preexec_fn=os.setsid if hasattr(os, 'setsid') else None
            )
            
            agent_process.process = process
            agent_process.pid = process.pid
            
            # Wait a moment to check if process started successfully
            time.sleep(1)
            if process.poll() is not None:
                stdout, stderr = process.communicate()
                self.logger.error(f"Agent process failed to start: {stderr}")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to launch process agent: {e}")
            return False
    
    def _launch_thread_agent(self, session_id: str, agent_process: SPARCAgentProcess) -> bool:
        """Launch agent as thread (for lightweight monitoring agents)"""
        try:
            config = agent_process.config
            
            # Import and create agent worker
            from orchestration.sparc_agent_worker import SPARCAgentWorker
            
            worker = SPARCAgentWorker(
                agent_id=config.id,
                session_id=session_id,
                capabilities=config.capabilities,
                memory_coordinator=self.memory,
                heartbeat_interval=config.heartbeat_interval,
                max_tasks=config.max_tasks
            )
            
            # Start worker thread
            thread = threading.Thread(target=worker.run, daemon=True)
            thread.start()
            
            agent_process.thread = thread
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to launch thread agent: {e}")
            return False
    
    def _launch_container_agent(self, session_id: str, agent_process: SPARCAgentProcess) -> bool:
        """Launch agent in container (requires Docker)"""
        try:
            # This is a placeholder for container-based agent launching
            # In a full implementation, this would use Docker API
            self.logger.warning("Container-based agent launching not implemented")
            return False
            
        except Exception as e:
            self.logger.error(f"Failed to launch container agent: {e}")
            return False
    
    def _launch_remote_agent(self, session_id: str, agent_process: SPARCAgentProcess) -> bool:
        """Launch agent on remote machine (requires SSH or API)"""
        try:
            # This is a placeholder for remote agent launching
            # In a full implementation, this would use SSH or remote API
            self.logger.warning("Remote agent launching not implemented")
            return False
            
        except Exception as e:
            self.logger.error(f"Failed to launch remote agent: {e}")
            return False
    
    def launch_agent_swarm(self, session_id: str, swarm_config: Dict[str, Any]) -> List[str]:
        """Launch a swarm of agents based on configuration"""
        try:
            launched_agents = []
            
            # Parse swarm configuration
            agents_config = swarm_config.get("agents", [])
            auto_scale = swarm_config.get("auto_scale", False)
            target_capabilities = swarm_config.get("required_capabilities", [])
            
            # Launch configured agents
            for agent_spec in agents_config:
                if "template" in agent_spec:
                    # Use template
                    template_name = agent_spec["template"]
                    customizations = agent_spec.get("customizations", {})
                    
                    config = self.create_agent_from_template(template_name, 
                                                           customizations=customizations)
                else:
                    # Create from scratch
                    config = SPARCAgentConfig(**agent_spec)
                
                if self.launch_agent(session_id, config):
                    launched_agents.append(config.id)
            
            # Auto-scale if enabled
            if auto_scale and target_capabilities:
                additional_agents = self._auto_scale_agents(session_id, target_capabilities)
                launched_agents.extend(additional_agents)
            
            self.logger.info(f"Launched agent swarm: {len(launched_agents)} agents")
            return launched_agents
            
        except Exception as e:
            self.logger.error(f"Failed to launch agent swarm: {e}")
            return []
    
    def _auto_scale_agents(self, session_id: str, required_capabilities: List[str]) -> List[str]:
        """Auto-scale agents based on required capabilities"""
        launched_agents = []
        
        try:
            # Analyze current agents
            current_agents = self.memory.get_session_agents(session_id)
            current_capabilities = set()
            for agent in current_agents:
                current_capabilities.update(agent.get("capabilities", []))
            
            # Find missing capabilities
            missing_capabilities = set(required_capabilities) - current_capabilities
            
            # Launch agents for missing capabilities
            for capability in missing_capabilities:
                # Find best template for this capability
                template_name = self._find_template_for_capability(capability)
                if template_name:
                    config = self.create_agent_from_template(template_name)
                    if self.launch_agent(session_id, config):
                        launched_agents.append(config.id)
            
        except Exception as e:
            self.logger.error(f"Auto-scaling error: {e}")
        
        return launched_agents
    
    def _find_template_for_capability(self, capability: str) -> Optional[str]:
        """Find the best template for a given capability"""
        capability_map = {
            "data_processing": "data_processor",
            "csv_handling": "data_processor",
            "filtering": "data_processor",
            "shopify_api": "shopify_uploader",
            "product_upload": "shopify_uploader",
            "cleanup": "cleanup_agent",
            "file_management": "cleanup_agent",
            "analysis": "parallel_analyzer",
            "parallel_processing": "parallel_analyzer",
            "monitoring": "monitor_agent",
            "health_check": "monitor_agent"
        }
        
        return capability_map.get(capability)
    
    def stop_agent(self, agent_id: str) -> bool:
        """Stop a specific agent"""
        try:
            agent_process = self.agents.get(agent_id)
            if not agent_process:
                return False
            
            # Stop based on launch mode
            if agent_process.process:
                # Process-based agent
                try:
                    # Send SIGTERM first
                    os.killpg(os.getpgid(agent_process.process.pid), signal.SIGTERM)
                    
                    # Wait for graceful shutdown
                    try:
                        agent_process.process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        # Force kill if necessary
                        os.killpg(os.getpgid(agent_process.process.pid), signal.SIGKILL)
                        agent_process.process.wait()
                    
                except ProcessLookupError:
                    pass  # Process already terminated
                
            elif agent_process.thread:
                # Thread-based agent (can't force stop, but mark as stopped)
                pass
            
            agent_process.status = "stopped"
            self.logger.info(f"Stopped agent {agent_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to stop agent {agent_id}: {e}")
            return False
    
    def stop_all_agents(self) -> int:
        """Stop all agents and return count of stopped agents"""
        stopped_count = 0
        
        for agent_id in list(self.agents.keys()):
            if self.stop_agent(agent_id):
                stopped_count += 1
        
        self.logger.info(f"Stopped {stopped_count} agents")
        return stopped_count
    
    def restart_agent(self, session_id: str, agent_id: str) -> bool:
        """Restart a specific agent"""
        try:
            agent_process = self.agents.get(agent_id)
            if not agent_process:
                return False
            
            # Check restart count
            if agent_process.restart_count >= self.config["max_restarts"]:
                self.logger.error(f"Agent {agent_id} exceeded max restart count")
                return False
            
            # Stop current instance
            self.stop_agent(agent_id)
            
            # Wait for restart delay
            time.sleep(self.config["restart_delay"])
            
            # Relaunch
            agent_process.restart_count += 1
            success = self.launch_agent(session_id, agent_process.config)
            
            if success:
                self.logger.info(f"Restarted agent {agent_id} (attempt {agent_process.restart_count})")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Failed to restart agent {agent_id}: {e}")
            return False
    
    def get_agent_status(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed status of an agent"""
        agent_process = self.agents.get(agent_id)
        if not agent_process:
            return None
        
        status = {
            "id": agent_process.config.id,
            "name": agent_process.config.name,
            "type": agent_process.config.type.value,
            "launch_mode": agent_process.config.launch_mode.value,
            "status": agent_process.status,
            "capabilities": agent_process.config.capabilities,
            "resource_limits": agent_process.config.resource_limits,
            "started_at": agent_process.started_at.isoformat() if agent_process.started_at else None,
            "last_heartbeat": agent_process.last_heartbeat.isoformat() if agent_process.last_heartbeat else None,
            "restart_count": agent_process.restart_count,
            "performance_metrics": agent_process.performance_metrics,
            "pid": agent_process.pid
        }
        
        # Add process-specific info
        if agent_process.process:
            try:
                proc = psutil.Process(agent_process.pid)
                status["cpu_percent"] = proc.cpu_percent()
                status["memory_mb"] = proc.memory_info().rss / 1024 / 1024
                status["is_running"] = proc.is_running()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                status["is_running"] = False
        
        return status
    
    def list_agents(self) -> List[Dict[str, Any]]:
        """List all agents with their status"""
        return [self.get_agent_status(agent_id) for agent_id in self.agents.keys()]
    
    def start_resource_monitoring(self):
        """Start the resource monitoring thread"""
        if self.config.get("enable_resource_monitoring", True):
            self.resource_monitor_thread = threading.Thread(
                target=self._resource_monitoring_loop,
                daemon=True
            )
            self.resource_monitor_thread.start()
            self.logger.info("Started resource monitoring")
    
    def _resource_monitoring_loop(self):
        """Resource monitoring loop"""
        while self.monitoring_enabled:
            try:
                self._update_agent_metrics()
                self._check_agent_health()
                time.sleep(self.config["resource_check_interval"])
            except Exception as e:
                self.logger.error(f"Resource monitoring error: {e}")
                time.sleep(5)
    
    def _update_agent_metrics(self):
        """Update performance metrics for all agents"""
        for agent_id, agent_process in self.agents.items():
            try:
                if agent_process.pid and agent_process.status == "running":
                    proc = psutil.Process(agent_process.pid)
                    
                    agent_process.performance_metrics.update({
                        "cpu_percent": proc.cpu_percent(),
                        "memory_mb": proc.memory_info().rss / 1024 / 1024,
                        "uptime_seconds": (datetime.now() - agent_process.started_at).total_seconds()
                        if agent_process.started_at else 0
                    })
                    
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                agent_process.status = "stopped"
    
    def _check_agent_health(self):
        """Check health of all agents and restart if necessary"""
        current_time = datetime.now()
        timeout = timedelta(seconds=self.config["heartbeat_timeout"])
        
        for agent_id, agent_process in list(self.agents.items()):
            try:
                # Check heartbeat timeout
                if (agent_process.last_heartbeat and 
                    current_time - agent_process.last_heartbeat > timeout):
                    self.logger.warning(f"Agent {agent_id} heartbeat timeout")
                    
                    if agent_process.config.auto_restart:
                        # Try to restart (this will be handled by session management)
                        agent_process.status = "failed"
                
                # Check if process is still running
                if agent_process.process and agent_process.process.poll() is not None:
                    self.logger.warning(f"Agent {agent_id} process terminated unexpectedly")
                    agent_process.status = "failed"
                    
            except Exception as e:
                self.logger.error(f"Health check error for agent {agent_id}: {e}")
    
    def shutdown(self):
        """Shutdown the agent launcher"""
        self.logger.info("Shutting down SPARC Agent Launcher")
        
        # Stop monitoring
        self.monitoring_enabled = False
        if self.resource_monitor_thread:
            self.resource_monitor_thread.join(timeout=5)
        
        # Stop all agents
        self.stop_all_agents()
        
        self.logger.info("SPARC Agent Launcher shutdown complete")


if __name__ == "__main__":
    # Example usage
    import redis
    from orchestration.sparc_memory import SPARCMemoryCoordinator
    
    # Setup
    redis_client = redis.from_url("redis://localhost:6379/0")
    memory = SPARCMemoryCoordinator(redis_client)
    launcher = SPARCAgentLauncher(memory)
    
    # Create session
    session_id = "test_session_1"
    
    # Launch individual agent
    config = launcher.create_agent_from_template("data_processor")
    success = launcher.launch_agent(session_id, config)
    print(f"Agent launched: {success}")
    
    # Launch agent swarm
    swarm_config = {
        "agents": [
            {"template": "data_processor", "customizations": {"max_tasks": 3}},
            {"template": "shopify_uploader"},
            {"template": "cleanup_agent"}
        ],
        "auto_scale": True,
        "required_capabilities": ["data_processing", "shopify_api", "cleanup"]
    }
    
    swarm_agents = launcher.launch_agent_swarm(session_id, swarm_config)
    print(f"Swarm launched: {swarm_agents}")
    
    # Monitor for a bit
    time.sleep(10)
    
    # Check status
    agents = launcher.list_agents()
    for agent in agents:
        print(f"Agent {agent['id']}: {agent['status']}")
    
    # Shutdown
    launcher.shutdown()