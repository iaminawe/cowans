#!/usr/bin/env python3
"""
End-to-End Workflow Tester

Tests complete workflows from UI interaction to script execution to result logging.
Simulates real user interactions and validates the entire system pipeline.
"""

import asyncio
import json
import time
import threading
import queue
import logging
import sys
import os
import subprocess
import tempfile
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from contextlib import contextmanager
import concurrent.futures
import websocket
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

# Add parent directories to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scripts.orchestration.sparc_orchestrator import SPARCOrchestrator
from scripts.orchestration.sparc_memory import SPARCMemoryCoordinator
from api_integration_validator import APIIntegrationValidator


@dataclass
class WorkflowStep:
    """Workflow step definition"""
    name: str
    action: str  # 'ui_interaction', 'api_call', 'wait', 'validate'
    parameters: Dict[str, Any]
    expected_result: Optional[Dict[str, Any]] = None
    timeout: int = 30
    optional: bool = False


@dataclass
class WorkflowResult:
    """Workflow execution result"""
    workflow_name: str
    total_steps: int
    completed_steps: int
    success: bool
    duration: float
    step_results: List[Dict[str, Any]]
    error_message: Optional[str] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class E2EWorkflowTester:
    """End-to-end workflow testing system"""
    
    def __init__(self, base_url: str = "http://localhost:3560",
                 frontend_url: str = "http://localhost:3055",
                 headless: bool = True):
        self.base_url = base_url
        self.frontend_url = frontend_url
        self.headless = headless
        self.logger = self._setup_logging()
        
        # Test components
        self.api_validator = None
        self.driver = None
        self.orchestrator = None
        self.memory_coordinator = None
        
        # Results storage
        self.workflow_results: List[WorkflowResult] = []
        
        # Test data
        self.test_credentials = {
            "email": "test@example.com",
            "password": "test123"
        }
        
        # Define workflows
        self.workflows = self._define_workflows()
        
    def _setup_logging(self) -> logging.Logger:
        """Setup logging for E2E tester"""
        logger = logging.getLogger("e2e_tester")
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger
    
    def _define_workflows(self) -> Dict[str, List[WorkflowStep]]:
        """Define test workflows"""
        return {
            "full_sync_workflow": [
                WorkflowStep(
                    name="login_ui",
                    action="ui_interaction",
                    parameters={"action": "login", "credentials": self.test_credentials}
                ),
                WorkflowStep(
                    name="navigate_to_sync",
                    action="ui_interaction", 
                    parameters={"action": "navigate", "tab": "sync"}
                ),
                WorkflowStep(
                    name="trigger_sync",
                    action="ui_interaction",
                    parameters={"action": "click", "element": "sync_button"}
                ),
                WorkflowStep(
                    name="wait_for_sync_start",
                    action="wait",
                    parameters={"condition": "sync_in_progress", "timeout": 10}
                ),
                WorkflowStep(
                    name="monitor_progress",
                    action="validate",
                    parameters={"check": "progress_updates", "duration": 30}
                ),
                WorkflowStep(
                    name="verify_completion",
                    action="validate",
                    parameters={"check": "sync_completion"}
                ),
                WorkflowStep(
                    name="check_history",
                    action="ui_interaction",
                    parameters={"action": "verify", "element": "sync_history"}
                )
            ],
            
            "script_execution_workflow": [
                WorkflowStep(
                    name="login_ui",
                    action="ui_interaction",
                    parameters={"action": "login", "credentials": self.test_credentials}
                ),
                WorkflowStep(
                    name="navigate_to_scripts",
                    action="ui_interaction",
                    parameters={"action": "navigate", "tab": "scripts"}
                ),
                WorkflowStep(
                    name="select_script",
                    action="ui_interaction",
                    parameters={"action": "select", "script": "data_processing"}
                ),
                WorkflowStep(
                    name="configure_parameters",
                    action="ui_interaction",
                    parameters={"action": "configure", "parameters": {"input_file": "test.csv"}}
                ),
                WorkflowStep(
                    name="execute_script",
                    action="ui_interaction",
                    parameters={"action": "execute"}
                ),
                WorkflowStep(
                    name="monitor_execution",
                    action="validate",
                    parameters={"check": "execution_progress", "duration": 60}
                ),
                WorkflowStep(
                    name="verify_logs",
                    action="validate",
                    parameters={"check": "execution_logs"}
                )
            ],
            
            "error_handling_workflow": [
                WorkflowStep(
                    name="login_ui",
                    action="ui_interaction",
                    parameters={"action": "login", "credentials": self.test_credentials}
                ),
                WorkflowStep(
                    name="navigate_to_scripts",
                    action="ui_interaction",
                    parameters={"action": "navigate", "tab": "scripts"}
                ),
                WorkflowStep(
                    name="execute_invalid_script",
                    action="ui_interaction",
                    parameters={"action": "execute", "script": "invalid_script"}
                ),
                WorkflowStep(
                    name="verify_error_handling",
                    action="validate",
                    parameters={"check": "error_display"}
                ),
                WorkflowStep(
                    name="check_error_logs",
                    action="ui_interaction",
                    parameters={"action": "navigate", "tab": "logs"}
                ),
                WorkflowStep(
                    name="verify_error_logged",
                    action="validate",
                    parameters={"check": "error_in_logs"}
                )
            ],
            
            "concurrent_operations_workflow": [
                WorkflowStep(
                    name="login_ui",
                    action="ui_interaction",
                    parameters={"action": "login", "credentials": self.test_credentials}
                ),
                WorkflowStep(
                    name="start_sync",
                    action="api_call",
                    parameters={"endpoint": "/api/sync/trigger", "method": "POST"}
                ),
                WorkflowStep(
                    name="start_script_execution",
                    action="api_call",
                    parameters={
                        "endpoint": "/api/scripts/execute",
                        "method": "POST",
                        "data": {"script_name": "test_script", "parameters": {}}
                    }
                ),
                WorkflowStep(
                    name="monitor_concurrent_execution",
                    action="validate",
                    parameters={"check": "concurrent_operations", "duration": 45}
                ),
                WorkflowStep(
                    name="verify_both_completed",
                    action="validate",
                    parameters={"check": "all_operations_complete"}
                )
            ]
        }
    
    def setup_test_environment(self) -> bool:
        """Setup the test environment"""
        self.logger.info("Setting up test environment")
        
        try:
            # Setup API validator
            self.api_validator = APIIntegrationValidator(base_url=self.base_url)
            
            # Setup browser driver
            if self._setup_browser():
                self.logger.info("Browser setup successful")
            else:
                self.logger.warning("Browser setup failed, UI tests will be skipped")
            
            # Setup SPARC components
            self._setup_sparc_components()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to setup test environment: {e}")
            return False
    
    def _setup_browser(self) -> bool:
        """Setup browser for UI testing"""
        try:
            chrome_options = Options()
            if self.headless:
                chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
            
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.implicitly_wait(10)
            
            return True
            
        except Exception as e:
            self.logger.warning(f"Browser setup failed: {e}")
            return False
    
    def _setup_sparc_components(self):
        """Setup SPARC orchestrator and memory coordinator"""
        try:
            from unittest.mock import Mock
            
            # Mock Redis for testing
            mock_redis = Mock()
            mock_redis.ping.return_value = True
            mock_redis.setex.return_value = True
            mock_redis.get.return_value = None
            mock_redis.smembers.return_value = set()
            mock_redis.sadd.return_value = True
            mock_redis.hset.return_value = True
            mock_redis.hgetall.return_value = {}
            
            self.orchestrator = SPARCOrchestrator(redis_client=mock_redis)
            self.memory_coordinator = SPARCMemoryCoordinator(mock_redis, namespace="e2e_test")
            
            self.logger.info("SPARC components setup successful")
            
        except Exception as e:
            self.logger.error(f"Failed to setup SPARC components: {e}")
    
    def execute_ui_interaction(self, step: WorkflowStep) -> Dict[str, Any]:
        """Execute UI interaction step"""
        if not self.driver:
            return {
                "success": False,
                "error": "Browser driver not available",
                "skipped": True
            }
        
        action = step.parameters.get("action")
        
        try:
            if action == "login":
                return self._ui_login(step.parameters.get("credentials", {}))
            elif action == "navigate":
                return self._ui_navigate(step.parameters.get("tab"))
            elif action == "click":
                return self._ui_click(step.parameters.get("element"))
            elif action == "select":
                return self._ui_select(step.parameters.get("script"))
            elif action == "configure":
                return self._ui_configure(step.parameters.get("parameters", {}))
            elif action == "execute":
                return self._ui_execute()
            elif action == "verify":
                return self._ui_verify(step.parameters.get("element"))
            else:
                return {"success": False, "error": f"Unknown UI action: {action}"}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _ui_login(self, credentials: Dict[str, str]) -> Dict[str, Any]:
        """Perform UI login"""
        try:
            self.driver.get(self.frontend_url)
            
            # Wait for login form
            email_field = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='email']"))
            )
            
            password_field = self.driver.find_element(By.CSS_SELECTOR, "input[type='password']")
            login_button = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            
            # Fill form
            email_field.send_keys(credentials.get("email", ""))
            password_field.send_keys(credentials.get("password", ""))
            
            # Submit
            login_button.click()
            
            # Wait for dashboard
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='dashboard']"))
            )
            
            return {"success": True, "message": "Login successful"}
            
        except Exception as e:
            return {"success": False, "error": f"Login failed: {e}"}
    
    def _ui_navigate(self, tab: str) -> Dict[str, Any]:
        """Navigate to a specific tab"""
        try:
            tab_selector = f"[data-testid='tab-{tab}']"
            tab_element = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, tab_selector))
            )
            
            tab_element.click()
            
            # Wait for tab content to load
            content_selector = f"[data-testid='{tab}-content']"
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, content_selector))
            )
            
            return {"success": True, "message": f"Navigated to {tab} tab"}
            
        except Exception as e:
            return {"success": False, "error": f"Navigation failed: {e}"}
    
    def _ui_click(self, element: str) -> Dict[str, Any]:
        """Click a UI element"""
        try:
            element_selector = f"[data-testid='{element}']"
            button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, element_selector))
            )
            
            button.click()
            
            return {"success": True, "message": f"Clicked {element}"}
            
        except Exception as e:
            return {"success": False, "error": f"Click failed: {e}"}
    
    def _ui_select(self, script: str) -> Dict[str, Any]:
        """Select a script from dropdown"""
        try:
            select_selector = "[data-testid='script-selector']"
            select_element = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, select_selector))
            )
            
            select_element.click()
            
            # Select option
            option_selector = f"[data-testid='script-option-{script}']"
            option = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, option_selector))
            )
            
            option.click()
            
            return {"success": True, "message": f"Selected script {script}"}
            
        except Exception as e:
            return {"success": False, "error": f"Script selection failed: {e}"}
    
    def _ui_configure(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Configure script parameters"""
        try:
            for param, value in parameters.items():
                input_selector = f"[data-testid='param-{param}']"
                input_field = WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, input_selector))
                )
                
                input_field.clear()
                input_field.send_keys(str(value))
            
            return {"success": True, "message": "Parameters configured"}
            
        except Exception as e:
            return {"success": False, "error": f"Parameter configuration failed: {e}"}
    
    def _ui_execute(self) -> Dict[str, Any]:
        """Execute the configured script"""
        try:
            execute_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='execute-button']"))
            )
            
            execute_button.click()
            
            # Wait for execution to start
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='execution-status']"))
            )
            
            return {"success": True, "message": "Script execution started"}
            
        except Exception as e:
            return {"success": False, "error": f"Script execution failed: {e}"}
    
    def _ui_verify(self, element: str) -> Dict[str, Any]:
        """Verify presence of UI element"""
        try:
            element_selector = f"[data-testid='{element}']"
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, element_selector))
            )
            
            return {"success": True, "message": f"Element {element} verified"}
            
        except Exception as e:
            return {"success": False, "error": f"Element verification failed: {e}"}
    
    def execute_api_call(self, step: WorkflowStep) -> Dict[str, Any]:
        """Execute API call step"""
        if not self.api_validator:
            return {"success": False, "error": "API validator not available"}
        
        try:
            # Ensure authentication
            if not self.api_validator.auth_token:
                if not self.api_validator.authenticate():
                    return {"success": False, "error": "API authentication failed"}
            
            endpoint = step.parameters.get("endpoint")
            method = step.parameters.get("method", "GET")
            data = step.parameters.get("data")
            
            result = self.api_validator.test_api_endpoint(endpoint, method, data)
            
            return {
                "success": result.success,
                "status_code": result.status_code,
                "response_time": result.response_time,
                "error": result.error_message,
                "data": result.response_data
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def execute_wait(self, step: WorkflowStep) -> Dict[str, Any]:
        """Execute wait step"""
        try:
            condition = step.parameters.get("condition")
            timeout = step.parameters.get("timeout", step.timeout)
            
            if condition == "sync_in_progress":
                return self._wait_for_sync_status("running", timeout)
            elif condition == "execution_complete":
                return self._wait_for_execution_complete(timeout)
            else:
                # Simple time-based wait
                time.sleep(timeout)
                return {"success": True, "message": f"Waited {timeout} seconds"}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _wait_for_sync_status(self, status: str, timeout: int) -> Dict[str, Any]:
        """Wait for sync to reach specific status"""
        try:
            start_time = time.time()
            
            while time.time() - start_time < timeout:
                # Check sync status via API
                if self.api_validator:
                    result = self.api_validator.test_api_endpoint("/api/sync/history")
                    if result.success and result.response_data:
                        history = result.response_data
                        if history and len(history) > 0:
                            latest_sync = history[0]
                            if latest_sync.get("status") == status:
                                return {"success": True, "message": f"Sync status {status} reached"}
                
                time.sleep(1)
            
            return {"success": False, "error": f"Sync status {status} not reached within {timeout}s"}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _wait_for_execution_complete(self, timeout: int) -> Dict[str, Any]:
        """Wait for script execution to complete"""
        try:
            start_time = time.time()
            
            while time.time() - start_time < timeout:
                # Check if execution indicator is gone (execution complete)
                if self.driver:
                    try:
                        execution_elements = self.driver.find_elements(
                            By.CSS_SELECTOR, "[data-testid='execution-in-progress']"
                        )
                        if not execution_elements:
                            return {"success": True, "message": "Execution completed"}
                    except:
                        pass
                
                time.sleep(1)
            
            return {"success": False, "error": f"Execution not completed within {timeout}s"}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def execute_validation(self, step: WorkflowStep) -> Dict[str, Any]:
        """Execute validation step"""
        try:
            check = step.parameters.get("check")
            duration = step.parameters.get("duration", 10)
            
            if check == "progress_updates":
                return self._validate_progress_updates(duration)
            elif check == "sync_completion":
                return self._validate_sync_completion()
            elif check == "execution_progress":
                return self._validate_execution_progress(duration)
            elif check == "execution_logs":
                return self._validate_execution_logs()
            elif check == "error_display":
                return self._validate_error_display()
            elif check == "error_in_logs":
                return self._validate_error_in_logs()
            elif check == "concurrent_operations":
                return self._validate_concurrent_operations(duration)
            elif check == "all_operations_complete":
                return self._validate_all_operations_complete()
            else:
                return {"success": False, "error": f"Unknown validation check: {check}"}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _validate_progress_updates(self, duration: int) -> Dict[str, Any]:
        """Validate that progress updates are received"""
        try:
            updates_received = 0
            start_time = time.time()
            
            while time.time() - start_time < duration:
                # Check for progress indicators in UI
                if self.driver:
                    try:
                        progress_elements = self.driver.find_elements(
                            By.CSS_SELECTOR, "[data-testid='progress-indicator']"
                        )
                        if progress_elements:
                            updates_received += 1
                    except:
                        pass
                
                time.sleep(1)
            
            success = updates_received > 0
            return {
                "success": success,
                "message": f"Received {updates_received} progress updates",
                "updates_count": updates_received
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _validate_sync_completion(self) -> Dict[str, Any]:
        """Validate sync completion"""
        try:
            # Check via API
            if self.api_validator:
                result = self.api_validator.test_api_endpoint("/api/sync/history")
                if result.success and result.response_data:
                    history = result.response_data
                    if history and len(history) > 0:
                        latest_sync = history[0]
                        status = latest_sync.get("status")
                        if status in ["success", "completed"]:
                            return {"success": True, "message": "Sync completed successfully"}
                        elif status == "failed":
                            return {"success": False, "error": "Sync failed"}
            
            return {"success": False, "error": "Sync completion status unclear"}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _validate_execution_progress(self, duration: int) -> Dict[str, Any]:
        """Validate script execution progress"""
        try:
            progress_observed = False
            start_time = time.time()
            
            while time.time() - start_time < duration:
                if self.driver:
                    try:
                        # Check for execution progress indicators
                        progress_elements = self.driver.find_elements(
                            By.CSS_SELECTOR, "[data-testid='execution-progress']"
                        )
                        if progress_elements:
                            progress_observed = True
                            break
                    except:
                        pass
                
                time.sleep(1)
            
            return {
                "success": progress_observed,
                "message": "Execution progress observed" if progress_observed else "No execution progress observed"
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _validate_execution_logs(self) -> Dict[str, Any]:
        """Validate execution logs are generated"""
        try:
            if self.driver:
                # Navigate to logs tab
                logs_tab = self.driver.find_element(By.CSS_SELECTOR, "[data-testid='tab-logs']")
                logs_tab.click()
                
                # Check for log entries
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='log-entry']"))
                )
                
                log_entries = self.driver.find_elements(By.CSS_SELECTOR, "[data-testid='log-entry']")
                return {
                    "success": len(log_entries) > 0,
                    "message": f"Found {len(log_entries)} log entries",
                    "log_count": len(log_entries)
                }
            
            return {"success": False, "error": "Browser driver not available"}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _validate_error_display(self) -> Dict[str, Any]:
        """Validate error is displayed in UI"""
        try:
            if self.driver:
                # Look for error indicators
                error_elements = self.driver.find_elements(
                    By.CSS_SELECTOR, "[data-testid='error-message'], .error, .alert-error"
                )
                
                return {
                    "success": len(error_elements) > 0,
                    "message": f"Found {len(error_elements)} error displays",
                    "error_count": len(error_elements)
                }
            
            return {"success": False, "error": "Browser driver not available"}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _validate_error_in_logs(self) -> Dict[str, Any]:
        """Validate error appears in logs"""
        try:
            if self.driver:
                # Check log entries for error-level logs
                log_entries = self.driver.find_elements(
                    By.CSS_SELECTOR, "[data-testid='log-entry']"
                )
                
                error_logs = 0
                for entry in log_entries:
                    if "error" in entry.get_attribute("class").lower():
                        error_logs += 1
                
                return {
                    "success": error_logs > 0,
                    "message": f"Found {error_logs} error log entries",
                    "error_log_count": error_logs
                }
            
            return {"success": False, "error": "Browser driver not available"}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _validate_concurrent_operations(self, duration: int) -> Dict[str, Any]:
        """Validate concurrent operations are handled properly"""
        try:
            # Monitor for concurrent operation indicators
            concurrent_observed = False
            start_time = time.time()
            
            while time.time() - start_time < duration:
                # Check API for active jobs
                if self.api_validator:
                    result = self.api_validator.test_api_endpoint("/api/jobs")
                    if result.success and result.response_data:
                        active_jobs = result.response_data
                        if len(active_jobs) >= 2:
                            concurrent_observed = True
                            break
                
                time.sleep(2)
            
            return {
                "success": concurrent_observed,
                "message": "Concurrent operations observed" if concurrent_observed else "No concurrent operations detected"
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _validate_all_operations_complete(self) -> Dict[str, Any]:
        """Validate all operations have completed"""
        try:
            # Check that no operations are in progress
            if self.api_validator:
                result = self.api_validator.test_api_endpoint("/api/jobs")
                if result.success and result.response_data:
                    active_jobs = result.response_data
                    in_progress_jobs = [job for job in active_jobs if job.get("status") == "running"]
                    
                    return {
                        "success": len(in_progress_jobs) == 0,
                        "message": f"{len(in_progress_jobs)} operations still in progress",
                        "in_progress_count": len(in_progress_jobs)
                    }
            
            return {"success": False, "error": "Could not verify operation status"}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def execute_workflow(self, workflow_name: str) -> WorkflowResult:
        """Execute a complete workflow"""
        self.logger.info(f"Executing workflow: {workflow_name}")
        
        if workflow_name not in self.workflows:
            return WorkflowResult(
                workflow_name=workflow_name,
                total_steps=0,
                completed_steps=0,
                success=False,
                duration=0.0,
                step_results=[],
                error_message=f"Unknown workflow: {workflow_name}"
            )
        
        workflow_steps = self.workflows[workflow_name]
        start_time = time.time()
        step_results = []
        completed_steps = 0
        
        for i, step in enumerate(workflow_steps):
            self.logger.info(f"Executing step {i+1}/{len(workflow_steps)}: {step.name}")
            step_start_time = time.time()
            
            try:
                if step.action == "ui_interaction":
                    result = self.execute_ui_interaction(step)
                elif step.action == "api_call":
                    result = self.execute_api_call(step)
                elif step.action == "wait":
                    result = self.execute_wait(step)
                elif step.action == "validate":
                    result = self.execute_validation(step)
                else:
                    result = {"success": False, "error": f"Unknown action: {step.action}"}
                
                step_duration = time.time() - step_start_time
                
                step_result = {
                    "step_name": step.name,
                    "action": step.action,
                    "success": result.get("success", False),
                    "duration": step_duration,
                    "result": result,
                    "timestamp": datetime.now().isoformat()
                }
                
                step_results.append(step_result)
                
                if result.get("success", False):
                    completed_steps += 1
                    self.logger.info(f"Step {step.name} completed successfully")
                else:
                    if not step.optional:
                        self.logger.error(f"Step {step.name} failed: {result.get('error', 'Unknown error')}")
                        break
                    else:
                        self.logger.warning(f"Optional step {step.name} failed: {result.get('error', 'Unknown error')}")
                        completed_steps += 1
                
            except Exception as e:
                step_result = {
                    "step_name": step.name,
                    "action": step.action,
                    "success": False,
                    "duration": time.time() - step_start_time,
                    "result": {"error": str(e)},
                    "timestamp": datetime.now().isoformat()
                }
                step_results.append(step_result)
                
                if not step.optional:
                    self.logger.error(f"Step {step.name} failed with exception: {e}")
                    break
                else:
                    self.logger.warning(f"Optional step {step.name} failed with exception: {e}")
                    completed_steps += 1
        
        total_duration = time.time() - start_time
        success = completed_steps == len(workflow_steps)
        
        result = WorkflowResult(
            workflow_name=workflow_name,
            total_steps=len(workflow_steps),
            completed_steps=completed_steps,
            success=success,
            duration=total_duration,
            step_results=step_results,
            error_message=None if success else "Workflow failed"
        )
        
        self.workflow_results.append(result)
        
        self.logger.info(f"Workflow {workflow_name} completed: {completed_steps}/{len(workflow_steps)} steps successful")
        
        return result
    
    def run_all_workflows(self) -> Dict[str, WorkflowResult]:
        """Run all defined workflows"""
        self.logger.info("Running all E2E workflows")
        
        if not self.setup_test_environment():
            self.logger.error("Failed to setup test environment")
            return {}
        
        results = {}
        
        for workflow_name in self.workflows:
            self.logger.info(f"Starting workflow: {workflow_name}")
            try:
                result = self.execute_workflow(workflow_name)
                results[workflow_name] = result
            except Exception as e:
                self.logger.error(f"Workflow {workflow_name} failed with exception: {e}")
                results[workflow_name] = WorkflowResult(
                    workflow_name=workflow_name,
                    total_steps=0,
                    completed_steps=0,
                    success=False,
                    duration=0.0,
                    step_results=[],
                    error_message=str(e)
                )
        
        return results
    
    def generate_report(self, results: Dict[str, WorkflowResult], output_file: str = None) -> str:
        """Generate workflow test report"""
        if output_file is None:
            output_file = f"e2e_workflow_report_{int(time.time())}.json"
        
        report_data = {
            "timestamp": datetime.now().isoformat(),
            "total_workflows": len(results),
            "successful_workflows": sum(1 for r in results.values() if r.success),
            "workflows": {name: asdict(result) for name, result in results.items()},
            "summary": {
                "overall_success": all(r.success for r in results.values()),
                "total_steps": sum(r.total_steps for r in results.values()),
                "completed_steps": sum(r.completed_steps for r in results.values()),
                "total_duration": sum(r.duration for r in results.values())
            }
        }
        
        with open(output_file, 'w') as f:
            json.dump(report_data, f, indent=2, default=str)
        
        self.logger.info(f"E2E workflow report generated: {output_file}")
        return output_file
    
    def cleanup(self):
        """Cleanup test resources"""
        if self.driver:
            self.driver.quit()
        
        if self.orchestrator:
            self.orchestrator.shutdown()
        
        if self.memory_coordinator:
            self.memory_coordinator.shutdown()


def main():
    """Main CLI entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="End-to-End Workflow Tester")
    parser.add_argument('--base-url', default='http://localhost:3560',
                       help='Backend API base URL')
    parser.add_argument('--frontend-url', default='http://localhost:3055',
                       help='Frontend URL')
    parser.add_argument('--headless', action='store_true', default=True,
                       help='Run browser in headless mode')
    parser.add_argument('--workflow', help='Run specific workflow')
    parser.add_argument('--output', '-o', help='Output file for report')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Verbose logging')
    
    args = parser.parse_args()
    
    # Configure logging
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create tester
    tester = E2EWorkflowTester(
        base_url=args.base_url,
        frontend_url=args.frontend_url,
        headless=args.headless
    )
    
    try:
        if args.workflow:
            # Run specific workflow
            if not tester.setup_test_environment():
                print("Failed to setup test environment")
                sys.exit(1)
            
            result = tester.execute_workflow(args.workflow)
            results = {args.workflow: result}
        else:
            # Run all workflows
            results = tester.run_all_workflows()
        
        # Generate report
        report_file = tester.generate_report(results, args.output)
        
        # Print summary
        successful = sum(1 for r in results.values() if r.success)
        total = len(results)
        
        print(f"""
End-to-End Workflow Testing Complete!
====================================
Workflows: {successful}/{total} successful
Total Steps: {sum(r.total_steps for r in results.values())}
Completed Steps: {sum(r.completed_steps for r in results.values())}
Total Duration: {sum(r.duration for r in results.values()):.2f}s

Report: {report_file}
        """)
        
        # Exit with appropriate code
        sys.exit(0 if successful == total else 1)
        
    except KeyboardInterrupt:
        print("\nTesting interrupted by user")
        sys.exit(2)
    except Exception as e:
        print(f"Testing failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(3)
    finally:
        tester.cleanup()


if __name__ == '__main__':
    main()