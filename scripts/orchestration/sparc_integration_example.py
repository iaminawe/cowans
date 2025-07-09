#!/usr/bin/env python3
"""
SPARC Integration Example

Demonstrates how to integrate and use the SPARC orchestrator system
with the existing Cowans infrastructure for common workflows.
"""

import os
import sys
import json
import time
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import redis

# Add parent directories to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# SPARC imports
from orchestration.sparc_orchestrator import SPARCOrchestrator, SPARCTaskStatus, SPARCSessionStatus
from orchestration.sparc_memory import SPARCMemoryCoordinator
from orchestration.sparc_agent_launcher import SPARCAgentLauncher
from orchestration.sparc_progress_tracker import SPARCProgressTracker, SPARCResultAggregator, SPARCProgressStage

# Existing infrastructure imports
from web_dashboard.backend.config import Config


class SPARCWorkflowIntegration:
    """
    SPARC Workflow Integration - Provides integration patterns for common Cowans workflows
    
    This class demonstrates how to integrate SPARC orchestration with existing
    Cowans infrastructure for typical product import and management workflows.
    """
    
    def __init__(self, redis_url: str = None):
        self.redis_url = redis_url or Config.REDIS_URL
        self.logger = self._setup_logging()
        
        # Initialize SPARC components
        self.redis_client = redis.from_url(self.redis_url)
        self.memory = SPARCMemoryCoordinator(self.redis_client)
        self.launcher = SPARCAgentLauncher(self.memory)
        self.orchestrator = SPARCOrchestrator(self.redis_client)
        self.progress_tracker = SPARCProgressTracker(self.memory, self._websocket_handler)
        self.result_aggregator = SPARCResultAggregator(self.memory)
        
        self.logger.info("SPARC Workflow Integration initialized")
    
    def _setup_logging(self) -> logging.Logger:
        logger = logging.getLogger("sparc_integration")
        logger.setLevel(logging.INFO)
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        return logger
    
    def _websocket_handler(self, session_id: str, data: Dict[str, Any]):
        """WebSocket handler for progress updates"""
        # In a real implementation, this would send to actual WebSocket clients
        self.logger.info(f"WebSocket update for session {session_id}: {data['type']}")
    
    def run_full_product_import_workflow(self, workflow_config: Dict[str, Any]) -> str:
        """
        Run a complete product import workflow using SPARC orchestration
        
        This demonstrates the full Cowans product import pipeline:
        1. FTP Download
        2. Data Processing and Filtering
        3. Metafield Generation
        4. Shopify Upload
        5. Cleanup Operations
        """
        try:
            session_name = workflow_config.get("session_name", "Product Import Workflow")
            self.logger.info(f"Starting SPARC workflow: {session_name}")
            
            # Define the workflow tasks
            tasks = self._create_product_import_tasks(workflow_config)
            
            # Define agent swarm configuration
            swarm_config = self._create_product_import_swarm_config()
            
            # Create SPARC session
            session_id = self.orchestrator.create_session(
                name=session_name,
                tasks=tasks,
                configuration=workflow_config.get("sparc_config", {})
            )
            
            # Start progress tracking
            self.progress_tracker.start_session_tracking(session_id)
            self.progress_tracker.update_stage(session_id, SPARCProgressStage.INITIALIZATION)
            
            # Launch agent swarm
            self.progress_tracker.update_stage(session_id, SPARCProgressStage.AGENT_DEPLOYMENT)
            launched_agents = self.launcher.launch_agent_swarm(session_id, swarm_config)
            
            if not launched_agents:
                raise Exception("Failed to launch required agents")
            
            self.logger.info(f"Launched {len(launched_agents)} agents: {launched_agents}")
            
            # Start orchestration
            self.progress_tracker.update_stage(session_id, SPARCProgressStage.TASK_DISTRIBUTION)
            success = self.orchestrator.start_session(session_id)
            
            if not success:
                raise Exception("Failed to start orchestration session")
            
            self.progress_tracker.update_stage(session_id, SPARCProgressStage.EXECUTION)
            
            # Monitor execution
            self._monitor_workflow_execution(session_id, workflow_config.get("timeout", 3600))
            
            # Aggregate results
            self.progress_tracker.update_stage(session_id, SPARCProgressStage.RESULT_AGGREGATION)
            results = self.result_aggregator.aggregate_session_results(session_id)
            
            # Cleanup
            self.progress_tracker.update_stage(session_id, SPARCProgressStage.CLEANUP)
            self._cleanup_workflow_session(session_id)
            
            self.progress_tracker.update_stage(session_id, SPARCProgressStage.COMPLETED)
            
            # Log results
            if results:
                self.logger.info(f"Workflow completed: {results.success_metrics}")
                self.logger.info(f"Recommendations: {results.recommendations}")
            
            return session_id
            
        except Exception as e:
            self.logger.error(f"Workflow execution failed: {e}")
            raise
    
    def _create_product_import_tasks(self, config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Create tasks for the product import workflow"""
        tasks = []
        
        # Task 1: FTP Download
        if not config.get("skip_download", False):
            tasks.append({
                "type": "ftp_download",
                "parameters": {
                    "ftp_host": config.get("ftp_host", os.getenv("FTP_HOST")),
                    "ftp_username": config.get("ftp_username", os.getenv("FTP_USERNAME")),
                    "ftp_password": config.get("ftp_password", os.getenv("FTP_PASSWORD")),
                    "remote_directory": config.get("remote_directory", "/"),
                    "local_directory": config.get("local_directory", "./data"),
                    "file_patterns": config.get("file_patterns", ["*.csv"])
                },
                "priority": 10,
                "required_capabilities": ["ftp_handling", "file_management"]
            })
        
        # Task 2: Data Processing and Filtering
        if not config.get("skip_filter", False):
            filter_task = {
                "type": "data_processing",
                "parameters": {
                    "input_file": config.get("input_file", "data/products.csv"),
                    "reference_file": config.get("reference_file", "data/reference.csv"),
                    "processing_type": "filter",
                    "output_file": config.get("filtered_output", "data/filtered_products.csv")
                },
                "priority": 9,
                "required_capabilities": ["data_processing", "csv_handling"]
            }
            
            # Add dependency on download task if not skipped
            if not config.get("skip_download", False):
                filter_task["dependencies"] = [f"task_0"]  # FTP download task
            
            tasks.append(filter_task)
        
        # Task 3: Metafield Generation
        if not config.get("skip_metafields", False):
            metafield_task = {
                "type": "metafield_generation",
                "parameters": {
                    "input_file": config.get("filtered_output", "data/filtered_products.csv"),
                    "output_file": config.get("metafield_output", "data/products_with_metafields.csv")
                },
                "priority": 8,
                "required_capabilities": ["data_processing", "metafield_handling"]
            }
            
            # Add dependency on filter task
            if not config.get("skip_filter", False):
                dependency_index = 1 if not config.get("skip_download", False) else 0
                metafield_task["dependencies"] = [f"task_{dependency_index}"]
            
            tasks.append(metafield_task)
        
        # Task 4: Shopify Upload
        if not config.get("skip_upload", False):
            upload_task = {
                "type": "shopify_upload",
                "parameters": {
                    "input_file": config.get("metafield_output", "data/products_with_metafields.csv"),
                    "shop_url": config.get("shop_url", os.getenv("SHOPIFY_SHOP_URL")),
                    "access_token": config.get("access_token", os.getenv("SHOPIFY_ACCESS_TOKEN")),
                    "batch_size": config.get("batch_size", 25),
                    "skip_images": config.get("skip_images", False)
                },
                "priority": 7,
                "required_capabilities": ["shopify_api", "product_upload"]
            }
            
            # Add dependency on metafield task
            if not config.get("skip_metafields", False):
                dependency_index = len(tasks) - 1
                upload_task["dependencies"] = [f"task_{dependency_index}"]
            
            tasks.append(upload_task)
        
        # Task 5: Cleanup Operations
        tasks.append({
            "type": "cleanup_operation",
            "parameters": {
                "cleanup_types": ["temp_files", "logs"],
                "retention_days": config.get("retention_days", 7)
            },
            "priority": 5,
            "required_capabilities": ["cleanup", "file_management"],
            "dependencies": [f"task_{len(tasks) - 1}"] if tasks else []
        })
        
        return tasks
    
    def _create_product_import_swarm_config(self) -> Dict[str, Any]:
        """Create agent swarm configuration for product import"""
        return {
            "agents": [
                {
                    "template": "data_processor",
                    "customizations": {
                        "name": "FTP Download Agent",
                        "capabilities": ["ftp_handling", "file_management", "data_processing"],
                        "max_tasks": 1
                    }
                },
                {
                    "template": "data_processor",
                    "customizations": {
                        "name": "Data Filter Agent",
                        "capabilities": ["data_processing", "csv_handling", "filtering"],
                        "max_tasks": 2
                    }
                },
                {
                    "template": "data_processor",
                    "customizations": {
                        "name": "Metafield Generator Agent",
                        "capabilities": ["data_processing", "metafield_handling"],
                        "max_tasks": 1
                    }
                },
                {
                    "template": "shopify_uploader",
                    "customizations": {
                        "name": "Shopify Upload Agent",
                        "max_tasks": 1
                    }
                },
                {
                    "template": "cleanup_agent",
                    "customizations": {
                        "name": "Cleanup Agent",
                        "max_tasks": 3
                    }
                },
                {
                    "template": "monitor_agent",
                    "customizations": {
                        "name": "Workflow Monitor",
                        "max_tasks": 5
                    }
                }
            ],
            "auto_scale": True,
            "required_capabilities": [
                "ftp_handling", "data_processing", "csv_handling", 
                "filtering", "metafield_handling", "shopify_api", 
                "product_upload", "cleanup", "file_management"
            ]
        }
    
    def _monitor_workflow_execution(self, session_id: str, timeout: int):
        """Monitor workflow execution with timeout"""
        start_time = datetime.now()
        timeout_time = start_time + timedelta(seconds=timeout)
        
        self.logger.info(f"Monitoring workflow execution (timeout: {timeout}s)")
        
        while datetime.now() < timeout_time:
            # Get current session status
            status = self.orchestrator.get_session_status(session_id)
            
            if not status:
                self.logger.error("Failed to get session status")
                break
            
            session_status = status.get("status", "unknown")
            progress = status.get("progress", {})
            
            completion_percentage = progress.get("completion_percentage", 0)
            
            self.logger.info(f"Workflow progress: {completion_percentage:.1f}% - Status: {session_status}")
            
            # Check if completed
            if session_status in ["completed", "failed", "cancelled"]:
                self.logger.info(f"Workflow finished with status: {session_status}")
                break
            
            # Brief pause before next check
            time.sleep(10)
        
        # Check for timeout
        if datetime.now() >= timeout_time:
            self.logger.warning("Workflow execution timed out")
            self.orchestrator.stop_session(session_id)
    
    def _cleanup_workflow_session(self, session_id: str):
        """Cleanup workflow session resources"""
        try:
            # Stop all agents for this session
            self.launcher.stop_all_agents()
            
            # Clean up temporary files (would integrate with actual cleanup logic)
            self.logger.info(f"Cleaned up session resources for: {session_id}")
            
        except Exception as e:
            self.logger.error(f"Failed to cleanup session: {e}")
    
    def run_parallel_analysis_workflow(self, analysis_config: Dict[str, Any]) -> str:
        """
        Run a parallel analysis workflow for large datasets
        
        This demonstrates how to use SPARC for compute-intensive analysis tasks
        with dynamic load balancing and parallel processing.
        """
        try:
            session_name = analysis_config.get("session_name", "Parallel Analysis Workflow")
            self.logger.info(f"Starting parallel analysis workflow: {session_name}")
            
            # Create analysis tasks
            tasks = self._create_parallel_analysis_tasks(analysis_config)
            
            # Create specialized analysis swarm
            swarm_config = self._create_analysis_swarm_config(analysis_config)
            
            # Create and run session
            session_id = self.orchestrator.create_session(
                name=session_name,
                tasks=tasks,
                configuration={
                    "max_agents": analysis_config.get("max_agents", 10),
                    "task_timeout": analysis_config.get("task_timeout", 1800)
                }
            )
            
            # Execute workflow
            self.progress_tracker.start_session_tracking(session_id)
            self.progress_tracker.update_stage(session_id, SPARCProgressStage.AGENT_DEPLOYMENT)
            
            launched_agents = self.launcher.launch_agent_swarm(session_id, swarm_config)
            self.logger.info(f"Launched {len(launched_agents)} analysis agents")
            
            self.progress_tracker.update_stage(session_id, SPARCProgressStage.EXECUTION)
            self.orchestrator.start_session(session_id)
            
            # Monitor with shorter intervals for analysis workloads
            self._monitor_workflow_execution(session_id, analysis_config.get("timeout", 7200))
            
            # Aggregate and return results
            results = self.result_aggregator.aggregate_session_results(session_id)
            self.progress_tracker.update_stage(session_id, SPARCProgressStage.COMPLETED)
            
            return session_id
            
        except Exception as e:
            self.logger.error(f"Analysis workflow failed: {e}")
            raise
    
    def _create_parallel_analysis_tasks(self, config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Create tasks for parallel analysis workflow"""
        tasks = []
        
        # Split data into chunks for parallel processing
        data_chunks = config.get("data_chunks", ["chunk1", "chunk2", "chunk3"])
        analysis_type = config.get("analysis_type", "categorization")
        
        # Create a task for each data chunk
        for i, chunk in enumerate(data_chunks):
            tasks.append({
                "type": "parallel_analysis",
                "parameters": {
                    "data_chunk": chunk,
                    "analysis_type": analysis_type,
                    "chunk_index": i,
                    "total_chunks": len(data_chunks)
                },
                "priority": 10 - i,  # Higher priority for earlier chunks
                "required_capabilities": ["analysis", "parallel_processing"]
            })
        
        # Add result aggregation task
        tasks.append({
            "type": "result_aggregation",
            "parameters": {
                "total_chunks": len(data_chunks),
                "analysis_type": analysis_type,
                "output_file": config.get("output_file", "analysis_results.json")
            },
            "priority": 5,
            "required_capabilities": ["analysis", "data_processing"],
            "dependencies": [f"task_{i}" for i in range(len(data_chunks))]
        })
        
        return tasks
    
    def _create_analysis_swarm_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Create agent swarm configuration for analysis workflow"""
        num_workers = min(config.get("max_workers", 5), len(config.get("data_chunks", [])))
        
        agents = []
        
        # Create worker agents for parallel processing
        for i in range(num_workers):
            agents.append({
                "template": "parallel_analyzer",
                "customizations": {
                    "name": f"Analysis Worker {i+1}",
                    "max_tasks": 1,
                    "resource_limits": {
                        "memory_mb": config.get("worker_memory_mb", 1024),
                        "cpu_percent": config.get("worker_cpu_percent", 80)
                    }
                }
            })
        
        # Add coordinator agent
        agents.append({
            "template": "data_processor",
            "customizations": {
                "name": "Analysis Coordinator",
                "capabilities": ["analysis", "data_processing", "coordination"],
                "max_tasks": 1
            }
        })
        
        # Add monitor agent
        agents.append({
            "template": "monitor_agent",
            "customizations": {
                "name": "Analysis Monitor",
                "max_tasks": 10
            }
        })
        
        return {
            "agents": agents,
            "auto_scale": True,
            "required_capabilities": ["analysis", "parallel_processing", "data_processing"]
        }
    
    def run_shopify_maintenance_workflow(self, maintenance_config: Dict[str, Any]) -> str:
        """
        Run a Shopify maintenance workflow for cleanup and optimization
        
        This demonstrates using SPARC for ongoing maintenance tasks like
        duplicate cleanup, image optimization, and data synchronization.
        """
        try:
            session_name = maintenance_config.get("session_name", "Shopify Maintenance Workflow")
            self.logger.info(f"Starting maintenance workflow: {session_name}")
            
            # Create maintenance tasks
            tasks = self._create_maintenance_tasks(maintenance_config)
            
            # Create maintenance swarm
            swarm_config = self._create_maintenance_swarm_config()
            
            # Execute maintenance session
            session_id = self.orchestrator.create_session(
                name=session_name,
                tasks=tasks,
                configuration=maintenance_config.get("sparc_config", {})
            )
            
            self.progress_tracker.start_session_tracking(session_id)
            launched_agents = self.launcher.launch_agent_swarm(session_id, swarm_config)
            
            self.orchestrator.start_session(session_id)
            self._monitor_workflow_execution(session_id, maintenance_config.get("timeout", 3600))
            
            results = self.result_aggregator.aggregate_session_results(session_id)
            self.progress_tracker.update_stage(session_id, SPARCProgressStage.COMPLETED)
            
            return session_id
            
        except Exception as e:
            self.logger.error(f"Maintenance workflow failed: {e}")
            raise
    
    def _create_maintenance_tasks(self, config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Create tasks for maintenance workflow"""
        tasks = []
        
        # Duplicate product cleanup
        if config.get("cleanup_duplicates", True):
            tasks.append({
                "type": "duplicate_cleanup",
                "parameters": {
                    "shop_url": config.get("shop_url", os.getenv("SHOPIFY_SHOP_URL")),
                    "access_token": config.get("access_token", os.getenv("SHOPIFY_ACCESS_TOKEN")),
                    "cleanup_type": "products"
                },
                "priority": 9,
                "required_capabilities": ["shopify_api", "cleanup", "duplicate_removal"]
            })
        
        # Image optimization
        if config.get("optimize_images", True):
            tasks.append({
                "type": "image_optimization",
                "parameters": {
                    "shop_url": config.get("shop_url", os.getenv("SHOPIFY_SHOP_URL")),
                    "access_token": config.get("access_token", os.getenv("SHOPIFY_ACCESS_TOKEN")),
                    "optimization_level": config.get("optimization_level", "standard")
                },
                "priority": 7,
                "required_capabilities": ["shopify_api", "image_processing"],
                "dependencies": ["task_0"] if config.get("cleanup_duplicates", True) else []
            })
        
        # Data synchronization check
        if config.get("sync_check", True):
            sync_task_index = len(tasks)
            tasks.append({
                "type": "data_sync_check",
                "parameters": {
                    "reference_data": config.get("reference_data", "data/reference.csv"),
                    "shop_url": config.get("shop_url", os.getenv("SHOPIFY_SHOP_URL")),
                    "access_token": config.get("access_token", os.getenv("SHOPIFY_ACCESS_TOKEN"))
                },
                "priority": 6,
                "required_capabilities": ["shopify_api", "data_processing"],
                "dependencies": [f"task_{i}" for i in range(sync_task_index)]
            })
        
        return tasks
    
    def _create_maintenance_swarm_config(self) -> Dict[str, Any]:
        """Create agent swarm configuration for maintenance workflow"""
        return {
            "agents": [
                {
                    "template": "cleanup_agent",
                    "customizations": {
                        "name": "Duplicate Cleanup Agent",
                        "capabilities": ["shopify_api", "cleanup", "duplicate_removal"],
                        "max_tasks": 1
                    }
                },
                {
                    "template": "shopify_uploader",
                    "customizations": {
                        "name": "Image Optimization Agent",
                        "capabilities": ["shopify_api", "image_processing"],
                        "max_tasks": 1
                    }
                },
                {
                    "template": "data_processor",
                    "customizations": {
                        "name": "Sync Check Agent",
                        "capabilities": ["shopify_api", "data_processing", "sync_validation"],
                        "max_tasks": 1
                    }
                }
            ],
            "required_capabilities": ["shopify_api", "cleanup", "data_processing"]
        }
    
    def get_workflow_status(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get comprehensive workflow status"""
        try:
            # Get session status from orchestrator
            session_status = self.orchestrator.get_session_status(session_id)
            
            # Get progress from tracker
            progress = self.progress_tracker.get_session_progress(session_id)
            
            # Get agent status
            agents = self.launcher.list_agents()
            
            return {
                "session": session_status,
                "progress": progress,
                "agents": agents,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get workflow status: {e}")
            return None
    
    def shutdown(self):
        """Shutdown all SPARC components"""
        self.logger.info("Shutting down SPARC Workflow Integration")
        
        self.progress_tracker.shutdown()
        self.launcher.shutdown()
        self.orchestrator.shutdown()
        self.memory.shutdown()
        
        self.logger.info("SPARC Workflow Integration shutdown complete")


def main():
    """Example usage of SPARC Workflow Integration"""
    
    # Initialize integration
    integration = SPARCWorkflowIntegration()
    
    print("SPARC Workflow Integration Example")
    print("=" * 50)
    
    try:
        # Example 1: Product Import Workflow
        print("\n1. Running Product Import Workflow...")
        
        import_config = {
            "session_name": "Example Product Import",
            "skip_download": True,  # Skip FTP download for demo
            "input_file": "data/sample_products.csv",
            "reference_file": "data/sample_reference.csv",
            "shop_url": "demo.myshopify.com",
            "access_token": "demo_token",
            "batch_size": 10,
            "timeout": 300
        }
        
        import_session_id = integration.run_full_product_import_workflow(import_config)
        print(f"Product import session completed: {import_session_id}")
        
        # Get final status
        final_status = integration.get_workflow_status(import_session_id)
        if final_status:
            print(f"Final progress: {final_status['progress'].overall_progress_percent:.1f}%")
        
        # Example 2: Parallel Analysis Workflow
        print("\n2. Running Parallel Analysis Workflow...")
        
        analysis_config = {
            "session_name": "Example Parallel Analysis",
            "data_chunks": ["products_1_1000.csv", "products_1001_2000.csv", "products_2001_3000.csv"],
            "analysis_type": "categorization",
            "max_workers": 3,
            "timeout": 300
        }
        
        analysis_session_id = integration.run_parallel_analysis_workflow(analysis_config)
        print(f"Parallel analysis session completed: {analysis_session_id}")
        
        # Example 3: Maintenance Workflow
        print("\n3. Running Maintenance Workflow...")
        
        maintenance_config = {
            "session_name": "Example Maintenance",
            "cleanup_duplicates": True,
            "optimize_images": True,
            "sync_check": True,
            "shop_url": "demo.myshopify.com",
            "access_token": "demo_token",
            "timeout": 300
        }
        
        maintenance_session_id = integration.run_shopify_maintenance_workflow(maintenance_config)
        print(f"Maintenance session completed: {maintenance_session_id}")
        
    except Exception as e:
        print(f"Workflow execution failed: {e}")
    
    finally:
        # Shutdown
        integration.shutdown()
        print("\nSPARC Integration example completed")


if __name__ == "__main__":
    main()