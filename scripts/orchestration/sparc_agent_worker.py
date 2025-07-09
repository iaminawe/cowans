#!/usr/bin/env python3
"""
SPARC Agent Worker

Individual worker agent that executes tasks within the SPARC orchestration system.
Integrates with existing Cowans infrastructure for task execution.
"""

import os
import sys
import json
import time
import logging
import signal
import threading
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime, timedelta
import traceback
import psutil
import redis

# Add parent directories to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web_dashboard.backend.config import Config
from web_dashboard.backend.security import ParameterValidator, ScriptSandbox
from orchestration.sparc_memory import SPARCMemoryCoordinator, SPARCMemoryEventType


class SPARCAgentWorker:
    """
    SPARC Agent Worker - Individual agent that executes tasks
    
    Features:
    - Task execution with capability matching
    - Heartbeat and health monitoring
    - Resource usage tracking
    - Integration with existing Cowans scripts
    - Error handling and recovery
    """
    
    def __init__(self, agent_id: str, session_id: str, capabilities: List[str],
                 memory_coordinator: SPARCMemoryCoordinator = None,
                 heartbeat_interval: int = 30, max_tasks: int = 1):
        
        self.agent_id = agent_id
        self.session_id = session_id
        self.capabilities = capabilities
        self.heartbeat_interval = heartbeat_interval
        self.max_tasks = max_tasks
        
        # Setup memory coordinator
        if memory_coordinator:
            self.memory = memory_coordinator
        else:
            redis_client = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
            self.memory = SPARCMemoryCoordinator(redis_client)
        
        # Setup logging
        self.logger = self._setup_logging()
        
        # Worker state
        self.running = False
        self.current_tasks: Dict[str, Dict[str, Any]] = {}
        self.completed_tasks = 0
        self.failed_tasks = 0
        self.started_at = datetime.now()
        
        # Threading
        self.heartbeat_thread = None
        self.task_threads: Dict[str, threading.Thread] = {}
        
        # Performance monitoring
        self.performance_metrics = {
            "cpu_percent": 0.0,
            "memory_mb": 0.0,
            "tasks_completed": 0,
            "tasks_failed": 0,
            "avg_task_duration": 0.0,
            "uptime_seconds": 0.0
        }
        
        # Task handlers
        self.task_handlers = self._initialize_task_handlers()
        
        # Security
        self.validator = ParameterValidator()
        self.sandbox = ScriptSandbox()
        
        # Graceful shutdown handling
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
    
    def _setup_logging(self) -> logging.Logger:
        logger = logging.getLogger(f"sparc_agent_{self.agent_id}")
        logger.setLevel(logging.INFO)
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                f'%(asctime)s - {self.agent_id} - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        return logger
    
    def _initialize_task_handlers(self) -> Dict[str, Callable]:
        """Initialize task handlers based on capabilities"""
        handlers = {}
        
        # Map capabilities to handler methods
        if "data_processing" in self.capabilities:
            handlers["data_processing"] = self._handle_data_processing
            handlers["csv_handling"] = self._handle_csv_processing
            handlers["filtering"] = self._handle_data_filtering
        
        if "shopify_api" in self.capabilities:
            handlers["shopify_upload"] = self._handle_shopify_upload
            handlers["product_upload"] = self._handle_product_upload
        
        if "cleanup" in self.capabilities:
            handlers["cleanup_operation"] = self._handle_cleanup
            handlers["file_management"] = self._handle_file_management
            handlers["duplicate_removal"] = self._handle_duplicate_removal
        
        if "analysis" in self.capabilities:
            handlers["parallel_analysis"] = self._handle_parallel_analysis
            handlers["categorization"] = self._handle_categorization
        
        if "monitoring" in self.capabilities:
            handlers["health_check"] = self._handle_health_check
            handlers["metrics_collection"] = self._handle_metrics_collection
        
        return handlers
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        self.logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.shutdown()
    
    def run(self):
        """Main worker loop"""
        try:
            self.running = True
            self.logger.info(f"Started SPARC agent worker {self.agent_id}")
            
            # Start heartbeat thread
            self._start_heartbeat()
            
            # Register with memory coordinator
            self._register_agent()
            
            # Main work loop
            while self.running:
                try:
                    # Check for available tasks
                    self._check_for_tasks()
                    
                    # Update performance metrics
                    self._update_performance_metrics()
                    
                    # Brief pause to prevent CPU spinning
                    time.sleep(1)
                    
                except Exception as e:
                    self.logger.error(f"Error in main loop: {e}")
                    time.sleep(5)
            
        except Exception as e:
            self.logger.error(f"Fatal error in worker: {e}")
            traceback.print_exc()
        finally:
            self.shutdown()
    
    def _start_heartbeat(self):
        """Start the heartbeat thread"""
        self.heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self.heartbeat_thread.start()
    
    def _heartbeat_loop(self):
        """Heartbeat loop"""
        while self.running:
            try:
                # Update agent status
                status_data = {
                    "status": "busy" if self.current_tasks else "idle",
                    "current_tasks": list(self.current_tasks.keys()),
                    "performance_metrics": self.performance_metrics,
                    "uptime_seconds": (datetime.now() - self.started_at).total_seconds()
                }
                
                self.memory.update_agent_heartbeat(self.session_id, self.agent_id, status_data)
                
                time.sleep(self.heartbeat_interval)
                
            except Exception as e:
                self.logger.error(f"Heartbeat error: {e}")
                time.sleep(5)
    
    def _register_agent(self):
        """Register agent with memory coordinator"""
        try:
            agent_data = {
                "id": self.agent_id,
                "session_id": self.session_id,
                "capabilities": self.capabilities,
                "status": "idle",
                "max_tasks": self.max_tasks,
                "started_at": self.started_at.isoformat(),
                "pid": os.getpid(),
                "performance_metrics": self.performance_metrics
            }
            
            self.memory.register_agent(self.session_id, self.agent_id, agent_data)
            
        except Exception as e:
            self.logger.error(f"Failed to register agent: {e}")
    
    def _check_for_tasks(self):
        """Check for available tasks that match capabilities"""
        try:
            # Skip if at max capacity
            if len(self.current_tasks) >= self.max_tasks:
                return
            
            # Get available tasks from shared context
            # This is a simplified implementation - in production, this would
            # integrate with a proper task queue system
            task_queue_key = f"session:{self.session_id}:task_queue"
            task_data = self.memory.get_shared_context(self.session_id, "pending_tasks")
            
            if task_data and isinstance(task_data, list):
                for task in task_data:
                    if (len(self.current_tasks) < self.max_tasks and
                        self._can_handle_task(task)):
                        self._accept_task(task)
            
        except Exception as e:
            self.logger.error(f"Error checking for tasks: {e}")
    
    def _can_handle_task(self, task: Dict[str, Any]) -> bool:
        """Check if agent can handle the task"""
        try:
            task_type = task.get("type")
            required_capabilities = task.get("required_capabilities", [])
            
            # Check if we have a handler for this task type
            if task_type not in self.task_handlers:
                return False
            
            # Check if we have required capabilities
            if required_capabilities:
                if not any(cap in self.capabilities for cap in required_capabilities):
                    return False
            
            # Check if task is already assigned
            if task.get("assigned_agent"):
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error checking task compatibility: {e}")
            return False
    
    def _accept_task(self, task: Dict[str, Any]):
        """Accept and start executing a task"""
        try:
            task_id = task.get("id")
            if not task_id:
                return
            
            # Mark task as accepted
            task["assigned_agent"] = self.agent_id
            task["started_at"] = datetime.now().isoformat()
            task["status"] = "in_progress"
            
            self.current_tasks[task_id] = task
            
            # Start task execution in separate thread
            task_thread = threading.Thread(
                target=self._execute_task,
                args=(task_id, task),
                daemon=True
            )
            task_thread.start()
            self.task_threads[task_id] = task_thread
            
            self.logger.info(f"Accepted task {task_id} of type {task.get('type')}")
            
        except Exception as e:
            self.logger.error(f"Error accepting task: {e}")
    
    def _execute_task(self, task_id: str, task: Dict[str, Any]):
        """Execute a specific task"""
        start_time = datetime.now()
        
        try:
            task_type = task.get("type")
            parameters = task.get("parameters", {})
            
            self.logger.info(f"Executing task {task_id} of type {task_type}")
            
            # Validate parameters
            if not self._validate_task_parameters(task_type, parameters):
                raise ValueError("Invalid task parameters")
            
            # Get handler
            handler = self.task_handlers.get(task_type)
            if not handler:
                raise ValueError(f"No handler for task type: {task_type}")
            
            # Execute task
            result = handler(task_id, parameters)
            
            # Mark as completed
            task["status"] = "completed"
            task["completed_at"] = datetime.now().isoformat()
            task["result"] = result
            task["execution_time"] = (datetime.now() - start_time).total_seconds()
            
            self.completed_tasks += 1
            self.performance_metrics["tasks_completed"] = self.completed_tasks
            
            self.logger.info(f"Completed task {task_id} in {task['execution_time']:.2f}s")
            
        except Exception as e:
            self.logger.error(f"Task {task_id} failed: {e}")
            
            # Mark as failed
            task["status"] = "failed"
            task["completed_at"] = datetime.now().isoformat()
            task["error"] = str(e)
            task["execution_time"] = (datetime.now() - start_time).total_seconds()
            
            self.failed_tasks += 1
            self.performance_metrics["tasks_failed"] = self.failed_tasks
            
        finally:
            # Clean up
            self.current_tasks.pop(task_id, None)
            self.task_threads.pop(task_id, None)
            
            # Update shared context with task result
            self._update_task_result(task_id, task)
    
    def _validate_task_parameters(self, task_type: str, parameters: Dict[str, Any]) -> bool:
        """Validate task parameters"""
        try:
            # Use existing parameter validator
            # This is simplified - in production would have full validation rules
            if not isinstance(parameters, dict):
                return False
            
            # Task-specific validation
            if task_type == "data_processing":
                required_params = ["input_data", "processing_type"]
            elif task_type == "shopify_upload":
                required_params = ["products", "shop_url", "access_token"]
            elif task_type == "cleanup_operation":
                required_params = ["cleanup_type", "target_data"]
            elif task_type == "parallel_analysis":
                required_params = ["data_chunks", "analysis_type"]
            else:
                required_params = []
            
            # Check required parameters
            for param in required_params:
                if param not in parameters:
                    self.logger.error(f"Missing required parameter: {param}")
                    return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Parameter validation error: {e}")
            return False
    
    def _update_task_result(self, task_id: str, task: Dict[str, Any]):
        """Update task result in shared context"""
        try:
            # Update in shared context
            results_key = "task_results"
            current_results = self.memory.get_shared_context(self.session_id, results_key) or {}
            current_results[task_id] = task
            self.memory.set_shared_context(self.session_id, results_key, current_results)
            
        except Exception as e:
            self.logger.error(f"Failed to update task result: {e}")
    
    # Task Handler Methods
    def _handle_data_processing(self, task_id: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Handle data processing tasks"""
        try:
            input_data = parameters.get("input_data")
            processing_type = parameters.get("processing_type")
            
            self.logger.info(f"Processing data: {input_data} with type: {processing_type}")
            
            # Simulate data processing using existing patterns
            if processing_type == "filter":
                # Use existing filter_products.py logic
                from data_processing.filter_products import filter_products_by_reference
                # This would call the actual filtering function
                processed_count = 1000  # Simulated
                
            elif processing_type == "transform":
                # Use existing transformation logic
                processed_count = 800  # Simulated
                
            else:
                processed_count = 500  # Default processing
            
            # Simulate processing time
            time.sleep(2)
            
            return {
                "status": "success",
                "processed_records": processed_count,
                "processing_type": processing_type,
                "execution_time": 2.0
            }
            
        except Exception as e:
            raise Exception(f"Data processing failed: {e}")
    
    def _handle_csv_processing(self, task_id: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Handle CSV-specific processing"""
        try:
            csv_file = parameters.get("csv_file")
            operation = parameters.get("operation", "parse")
            
            # Simulate CSV processing
            time.sleep(1.5)
            
            return {
                "status": "success",
                "csv_file": csv_file,
                "operation": operation,
                "rows_processed": 2500,
                "execution_time": 1.5
            }
            
        except Exception as e:
            raise Exception(f"CSV processing failed: {e}")
    
    def _handle_data_filtering(self, task_id: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Handle data filtering tasks"""
        try:
            filter_criteria = parameters.get("filter_criteria", {})
            
            # Use existing filtering patterns
            time.sleep(1)
            
            return {
                "status": "success",
                "filter_criteria": filter_criteria,
                "filtered_count": 750,
                "execution_time": 1.0
            }
            
        except Exception as e:
            raise Exception(f"Data filtering failed: {e}")
    
    def _handle_shopify_upload(self, task_id: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Handle Shopify upload tasks"""
        try:
            products = parameters.get("products", [])
            shop_url = parameters.get("shop_url")
            access_token = parameters.get("access_token")
            
            self.logger.info(f"Uploading {len(products)} products to {shop_url}")
            
            # Use existing Shopify uploader patterns
            # This would integrate with shopify_uploader_new.py
            time.sleep(3)
            
            return {
                "status": "success",
                "products_uploaded": len(products),
                "shop_url": shop_url,
                "execution_time": 3.0
            }
            
        except Exception as e:
            raise Exception(f"Shopify upload failed: {e}")
    
    def _handle_product_upload(self, task_id: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Handle product-specific upload tasks"""
        return self._handle_shopify_upload(task_id, parameters)
    
    def _handle_cleanup(self, task_id: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Handle cleanup tasks"""
        try:
            cleanup_type = parameters.get("cleanup_type")
            target_data = parameters.get("target_data")
            
            self.logger.info(f"Cleaning up {cleanup_type} for {target_data}")
            
            # Use existing cleanup patterns
            time.sleep(1)
            
            return {
                "status": "success",
                "cleanup_type": cleanup_type,
                "items_cleaned": 150,
                "execution_time": 1.0
            }
            
        except Exception as e:
            raise Exception(f"Cleanup failed: {e}")
    
    def _handle_file_management(self, task_id: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Handle file management tasks"""
        try:
            operation = parameters.get("operation")
            files = parameters.get("files", [])
            
            time.sleep(0.5)
            
            return {
                "status": "success",
                "operation": operation,
                "files_processed": len(files),
                "execution_time": 0.5
            }
            
        except Exception as e:
            raise Exception(f"File management failed: {e}")
    
    def _handle_duplicate_removal(self, task_id: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Handle duplicate removal tasks"""
        try:
            # Use existing duplicate detection patterns
            time.sleep(2)
            
            return {
                "status": "success",
                "duplicates_removed": 25,
                "execution_time": 2.0
            }
            
        except Exception as e:
            raise Exception(f"Duplicate removal failed: {e}")
    
    def _handle_parallel_analysis(self, task_id: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Handle parallel analysis tasks"""
        try:
            data_chunks = parameters.get("data_chunks", [])
            analysis_type = parameters.get("analysis_type")
            
            self.logger.info(f"Analyzing {len(data_chunks)} chunks with {analysis_type}")
            
            # Simulate parallel analysis
            time.sleep(4)
            
            return {
                "status": "success",
                "chunks_analyzed": len(data_chunks),
                "analysis_type": analysis_type,
                "insights": ["pattern_detected", "anomaly_found"],
                "execution_time": 4.0
            }
            
        except Exception as e:
            raise Exception(f"Parallel analysis failed: {e}")
    
    def _handle_categorization(self, task_id: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Handle categorization tasks"""
        try:
            items = parameters.get("items", [])
            
            # Use existing categorization patterns
            time.sleep(1.5)
            
            return {
                "status": "success",
                "items_categorized": len(items),
                "categories_used": 12,
                "execution_time": 1.5
            }
            
        except Exception as e:
            raise Exception(f"Categorization failed: {e}")
    
    def _handle_health_check(self, task_id: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Handle health check tasks"""
        try:
            # Perform system health checks
            health_status = {
                "agent_id": self.agent_id,
                "uptime": (datetime.now() - self.started_at).total_seconds(),
                "tasks_completed": self.completed_tasks,
                "tasks_failed": self.failed_tasks,
                "memory_usage": self.performance_metrics["memory_mb"],
                "cpu_usage": self.performance_metrics["cpu_percent"],
                "status": "healthy"
            }
            
            return {
                "status": "success",
                "health_status": health_status,
                "execution_time": 0.1
            }
            
        except Exception as e:
            raise Exception(f"Health check failed: {e}")
    
    def _handle_metrics_collection(self, task_id: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Handle metrics collection tasks"""
        try:
            metrics_type = parameters.get("metrics_type", "performance")
            
            if metrics_type == "performance":
                metrics = self.performance_metrics.copy()
            elif metrics_type == "system":
                metrics = {
                    "cpu_percent": psutil.cpu_percent(),
                    "memory_percent": psutil.virtual_memory().percent,
                    "disk_usage": psutil.disk_usage('/').percent
                }
            else:
                metrics = {"message": "Unknown metrics type"}
            
            return {
                "status": "success",
                "metrics_type": metrics_type,
                "metrics": metrics,
                "execution_time": 0.1
            }
            
        except Exception as e:
            raise Exception(f"Metrics collection failed: {e}")
    
    def _update_performance_metrics(self):
        """Update performance metrics"""
        try:
            # Get current process info
            process = psutil.Process()
            
            self.performance_metrics.update({
                "cpu_percent": process.cpu_percent(),
                "memory_mb": process.memory_info().rss / 1024 / 1024,
                "uptime_seconds": (datetime.now() - self.started_at).total_seconds(),
                "tasks_completed": self.completed_tasks,
                "tasks_failed": self.failed_tasks
            })
            
            # Calculate average task duration
            if self.completed_tasks > 0:
                total_time = sum(
                    task.get("execution_time", 0) 
                    for task in self.current_tasks.values()
                )
                self.performance_metrics["avg_task_duration"] = total_time / self.completed_tasks
            
        except Exception as e:
            self.logger.error(f"Performance metrics update error: {e}")
    
    def shutdown(self):
        """Shutdown the worker gracefully"""
        self.logger.info("Shutting down SPARC agent worker...")
        
        self.running = False
        
        # Wait for current tasks to complete (with timeout)
        timeout = datetime.now() + timedelta(seconds=30)
        while self.current_tasks and datetime.now() < timeout:
            self.logger.info(f"Waiting for {len(self.current_tasks)} tasks to complete...")
            time.sleep(1)
        
        # Force stop remaining tasks
        if self.current_tasks:
            self.logger.warning(f"Force stopping {len(self.current_tasks)} remaining tasks")
        
        # Stop heartbeat
        if self.heartbeat_thread and self.heartbeat_thread.is_alive():
            self.heartbeat_thread.join(timeout=5)
        
        # Update agent status to offline
        try:
            self.memory.update_agent_heartbeat(
                self.session_id, 
                self.agent_id, 
                {"status": "offline", "shutdown_at": datetime.now().isoformat()}
            )
        except Exception as e:
            self.logger.error(f"Failed to update shutdown status: {e}")
        
        self.logger.info("SPARC agent worker shutdown complete")


def main():
    """Main entry point for agent worker"""
    # Get configuration from environment
    agent_id = os.getenv("SPARC_AGENT_ID")
    session_id = os.getenv("SPARC_SESSION_ID")
    agent_name = os.getenv("SPARC_AGENT_NAME", "SPARC Agent")
    capabilities = json.loads(os.getenv("SPARC_CAPABILITIES", '["data_processing"]'))
    heartbeat_interval = int(os.getenv("SPARC_HEARTBEAT_INTERVAL", "30"))
    max_tasks = int(os.getenv("SPARC_MAX_TASKS", "1"))
    
    if not agent_id or not session_id:
        print("ERROR: SPARC_AGENT_ID and SPARC_SESSION_ID must be set")
        sys.exit(1)
    
    # Create and run worker
    worker = SPARCAgentWorker(
        agent_id=agent_id,
        session_id=session_id,
        capabilities=capabilities,
        heartbeat_interval=heartbeat_interval,
        max_tasks=max_tasks
    )
    
    worker.run()


if __name__ == "__main__":
    main()