#!/usr/bin/env python3
"""
Error Handling and Edge Case Validator

Tests system resilience, error handling, recovery mechanisms, and edge cases.
Validates that the system gracefully handles failures and provides appropriate feedback.
"""

import asyncio
import json
import time
import threading
import queue
import logging
import sys
import os
import tempfile
import uuid
import psutil
import requests
import websocket
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple, Callable
from dataclasses import dataclass, asdict
from contextlib import contextmanager
import concurrent.futures
from unittest.mock import Mock, patch

# Add parent directories to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scripts.orchestration.sparc_orchestrator import SPARCOrchestrator, SPARCTaskStatus
from scripts.orchestration.sparc_memory import SPARCMemoryCoordinator
from api_integration_validator import APIIntegrationValidator


@dataclass
class ErrorTestCase:
    """Error test case definition"""
    name: str
    description: str
    test_type: str  # 'api_error', 'system_failure', 'resource_exhaustion', 'invalid_input', 'timeout'
    setup_actions: List[Dict[str, Any]]
    trigger_action: Dict[str, Any]
    expected_behavior: Dict[str, Any]
    recovery_actions: List[Dict[str, Any]]
    timeout: int = 60


@dataclass
class ErrorTestResult:
    """Error test result"""
    test_name: str
    test_type: str
    success: bool
    duration: float
    error_detected: bool
    error_handled_properly: bool
    recovery_successful: bool
    details: Dict[str, Any]
    error_message: Optional[str] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class ErrorHandlingValidator:
    """Comprehensive error handling and edge case validator"""
    
    def __init__(self, base_url: str = "http://localhost:3560"):
        self.base_url = base_url
        self.logger = self._setup_logging()
        
        # Test components
        self.api_validator = APIIntegrationValidator(base_url=base_url)
        self.orchestrator = None
        self.memory_coordinator = None
        
        # Results storage
        self.test_results: List[ErrorTestResult] = []
        
        # Error injection mechanisms
        self.error_injectors = {
            'network_failure': self._inject_network_failure,
            'memory_exhaustion': self._inject_memory_exhaustion,
            'disk_full': self._inject_disk_full,
            'invalid_response': self._inject_invalid_response,
            'timeout': self._inject_timeout,
            'authentication_failure': self._inject_auth_failure,
            'database_failure': self._inject_database_failure,
            'concurrent_access': self._inject_concurrent_access
        }
        
        # Define test cases
        self.test_cases = self._define_error_test_cases()
        
    def _setup_logging(self) -> logging.Logger:
        """Setup logging for error validator"""
        logger = logging.getLogger("error_validator")
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger
    
    def _define_error_test_cases(self) -> List[ErrorTestCase]:
        """Define comprehensive error test cases"""
        return [
            # API Error Cases
            ErrorTestCase(
                name="invalid_authentication",
                description="Test handling of invalid authentication credentials",
                test_type="api_error",
                setup_actions=[],
                trigger_action={
                    "type": "api_call",
                    "endpoint": "/api/auth/login",
                    "method": "POST",
                    "data": {"email": "invalid@test.com", "password": "wrong"}
                },
                expected_behavior={
                    "status_code": 401,
                    "error_message_present": True,
                    "no_token_issued": True
                },
                recovery_actions=[
                    {"type": "valid_login", "credentials": {"email": "test@example.com", "password": "test123"}}
                ]
            ),
            
            ErrorTestCase(
                name="unauthorized_api_access",
                description="Test handling of API access without authentication",
                test_type="api_error",
                setup_actions=[],
                trigger_action={
                    "type": "api_call",
                    "endpoint": "/api/scripts",
                    "method": "GET",
                    "authenticated": False
                },
                expected_behavior={
                    "status_code": 401,
                    "access_denied": True
                },
                recovery_actions=[
                    {"type": "authenticate_and_retry"}
                ]
            ),
            
            ErrorTestCase(
                name="invalid_script_parameters",
                description="Test handling of invalid script parameters",
                test_type="invalid_input",
                setup_actions=[
                    {"type": "authenticate"}
                ],
                trigger_action={
                    "type": "api_call",
                    "endpoint": "/api/scripts/execute",
                    "method": "POST",
                    "data": {
                        "script_name": "nonexistent_script",
                        "parameters": {"invalid_param": "invalid_value"}
                    }
                },
                expected_behavior={
                    "status_code": 400,
                    "validation_error": True,
                    "no_job_created": True
                },
                recovery_actions=[
                    {"type": "execute_valid_script"}
                ]
            ),
            
            ErrorTestCase(
                name="malformed_json_request",
                description="Test handling of malformed JSON in API requests",
                test_type="invalid_input",
                setup_actions=[
                    {"type": "authenticate"}
                ],
                trigger_action={
                    "type": "raw_request",
                    "endpoint": "/api/scripts/execute",
                    "method": "POST",
                    "data": "{'invalid': json, 'format'}"
                },
                expected_behavior={
                    "status_code": 400,
                    "json_error": True
                },
                recovery_actions=[
                    {"type": "send_valid_json"}
                ]
            ),
            
            # System Failure Cases
            ErrorTestCase(
                name="redis_connection_failure",
                description="Test system behavior when Redis is unavailable",
                test_type="system_failure",
                setup_actions=[
                    {"type": "simulate_redis_failure"}
                ],
                trigger_action={
                    "type": "api_call",
                    "endpoint": "/api/scripts/execute",
                    "method": "POST",
                    "data": {"script_name": "test_script", "parameters": {}}
                },
                expected_behavior={
                    "graceful_degradation": True,
                    "error_logged": True,
                    "fallback_behavior": True
                },
                recovery_actions=[
                    {"type": "restore_redis_connection"}
                ]
            ),
            
            ErrorTestCase(
                name="sparc_orchestrator_failure",
                description="Test handling of SPARC orchestrator failures",
                test_type="system_failure",
                setup_actions=[
                    {"type": "create_orchestrator_session"}
                ],
                trigger_action={
                    "type": "crash_orchestrator"
                },
                expected_behavior={
                    "session_cleanup": True,
                    "error_recovery": True,
                    "status_updated": True
                },
                recovery_actions=[
                    {"type": "restart_orchestrator"}
                ]
            ),
            
            # Resource Exhaustion Cases
            ErrorTestCase(
                name="memory_exhaustion",
                description="Test behavior under memory pressure",
                test_type="resource_exhaustion",
                setup_actions=[
                    {"type": "authenticate"}
                ],
                trigger_action={
                    "type": "exhaust_memory"
                },
                expected_behavior={
                    "graceful_handling": True,
                    "no_crash": True,
                    "error_logged": True
                },
                recovery_actions=[
                    {"type": "free_memory"}
                ]
            ),
            
            ErrorTestCase(
                name="concurrent_request_overload",
                description="Test handling of excessive concurrent requests",
                test_type="resource_exhaustion",
                setup_actions=[
                    {"type": "authenticate"}
                ],
                trigger_action={
                    "type": "flood_requests",
                    "request_count": 100,
                    "concurrent": True
                },
                expected_behavior={
                    "rate_limiting": True,
                    "system_stability": True,
                    "appropriate_errors": True
                },
                recovery_actions=[
                    {"type": "wait_for_system_recovery"}
                ]
            ),
            
            # Timeout Cases
            ErrorTestCase(
                name="script_execution_timeout",
                description="Test handling of script execution timeouts",
                test_type="timeout",
                setup_actions=[
                    {"type": "authenticate"}
                ],
                trigger_action={
                    "type": "execute_long_running_script",
                    "timeout": 5  # Very short timeout
                },
                expected_behavior={
                    "timeout_detected": True,
                    "job_cancelled": True,
                    "cleanup_performed": True
                },
                recovery_actions=[
                    {"type": "verify_cleanup"}
                ]
            ),
            
            ErrorTestCase(
                name="websocket_connection_loss",
                description="Test handling of WebSocket connection loss",
                test_type="network_failure",
                setup_actions=[
                    {"type": "establish_websocket"}
                ],
                trigger_action={
                    "type": "disconnect_websocket"
                },
                expected_behavior={
                    "reconnection_attempt": True,
                    "data_consistency": True,
                    "user_notification": True
                },
                recovery_actions=[
                    {"type": "reconnect_websocket"}
                ]
            ),
            
            # Edge Cases
            ErrorTestCase(
                name="extremely_large_payload",
                description="Test handling of extremely large request payloads",
                test_type="invalid_input",
                setup_actions=[
                    {"type": "authenticate"}
                ],
                trigger_action={
                    "type": "send_large_payload",
                    "size_mb": 100
                },
                expected_behavior={
                    "payload_rejected": True,
                    "error_message": True,
                    "no_memory_leak": True
                },
                recovery_actions=[
                    {"type": "send_normal_request"}
                ]
            ),
            
            ErrorTestCase(
                name="session_expiration",
                description="Test handling of expired authentication sessions",
                test_type="api_error",
                setup_actions=[
                    {"type": "authenticate"}
                ],
                trigger_action={
                    "type": "expire_session"
                },
                expected_behavior={
                    "session_expired_error": True,
                    "reauthentication_required": True
                },
                recovery_actions=[
                    {"type": "reauthenticate"}
                ]
            )
        ]
    
    def setup_test_environment(self) -> bool:
        """Setup test environment with error injection capabilities"""
        self.logger.info("Setting up error testing environment")
        
        try:
            # Setup API validator
            if not self.api_validator.authenticate():
                self.logger.warning("Initial authentication failed, will test this scenario")
            
            # Setup SPARC components with error injection
            self._setup_sparc_with_error_injection()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to setup error testing environment: {e}")
            return False
    
    def _setup_sparc_with_error_injection(self):
        """Setup SPARC components with error injection capabilities"""
        try:
            # Create mock Redis that can simulate failures
            self.mock_redis = Mock()
            self.redis_failure_mode = False
            
            def redis_ping():
                if self.redis_failure_mode:
                    raise Exception("Redis connection failed")
                return True
            
            def redis_setex(*args, **kwargs):
                if self.redis_failure_mode:
                    raise Exception("Redis write failed")
                return True
            
            self.mock_redis.ping = redis_ping
            self.mock_redis.setex = redis_setex
            self.mock_redis.get.return_value = None
            self.mock_redis.smembers.return_value = set()
            self.mock_redis.sadd.return_value = True
            self.mock_redis.hset.return_value = True
            self.mock_redis.hgetall.return_value = {}
            
            # Create orchestrator with error injection
            self.orchestrator = SPARCOrchestrator(redis_client=self.mock_redis)
            self.memory_coordinator = SPARCMemoryCoordinator(self.mock_redis, namespace="error_test")
            
        except Exception as e:
            self.logger.error(f"Failed to setup SPARC with error injection: {e}")
    
    # Error injection methods
    def _inject_network_failure(self):
        """Inject network failure"""
        self.logger.info("Injecting network failure")
        # Simulate network failure by patching requests
        original_request = requests.request
        
        def failing_request(*args, **kwargs):
            raise requests.ConnectionError("Network failure injected")
        
        return patch('requests.request', side_effect=failing_request)
    
    def _inject_memory_exhaustion(self):
        """Inject memory exhaustion"""
        self.logger.info("Injecting memory exhaustion")
        # Simulate memory pressure (be careful not to actually exhaust memory)
        self.memory_hog = []
        try:
            # Allocate significant memory but not enough to crash
            available_memory = psutil.virtual_memory().available
            # Use 10% of available memory
            chunk_size = min(available_memory // 10, 100 * 1024 * 1024)  # Max 100MB
            self.memory_hog = [b'x' * chunk_size]
        except Exception as e:
            self.logger.warning(f"Memory injection failed: {e}")
    
    def _inject_disk_full(self):
        """Inject disk full condition"""
        self.logger.info("Injecting disk full condition")
        # Create a large temporary file to simulate disk pressure
        try:
            self.temp_file = tempfile.NamedTemporaryFile(delete=False)
            # Write 100MB of data
            chunk = b'x' * (1024 * 1024)  # 1MB chunks
            for _ in range(100):
                self.temp_file.write(chunk)
            self.temp_file.flush()
        except Exception as e:
            self.logger.warning(f"Disk injection failed: {e}")
    
    def _inject_invalid_response(self):
        """Inject invalid response"""
        self.logger.info("Injecting invalid response")
        # Patch API to return invalid responses
        def invalid_response(*args, **kwargs):
            response = Mock()
            response.status_code = 200
            response.text = "Invalid JSON response: {broken json"
            response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
            return response
        
        return patch('requests.request', side_effect=invalid_response)
    
    def _inject_timeout(self):
        """Inject timeout"""
        self.logger.info("Injecting timeout")
        def timeout_request(*args, **kwargs):
            raise requests.Timeout("Request timeout injected")
        
        return patch('requests.request', side_effect=timeout_request)
    
    def _inject_auth_failure(self):
        """Inject authentication failure"""
        self.logger.info("Injecting authentication failure")
        self.api_validator.auth_token = None
        self.api_validator.auth_headers = {}
    
    def _inject_database_failure(self):
        """Inject database/Redis failure"""
        self.logger.info("Injecting database failure")
        self.redis_failure_mode = True
    
    def _inject_concurrent_access(self):
        """Inject concurrent access issues"""
        self.logger.info("Injecting concurrent access scenario")
        # This will be handled by the test execution logic
        pass
    
    def execute_error_test(self, test_case: ErrorTestCase) -> ErrorTestResult:
        """Execute a single error test case"""
        self.logger.info(f"Executing error test: {test_case.name}")
        start_time = time.time()
        
        result = ErrorTestResult(
            test_name=test_case.name,
            test_type=test_case.test_type,
            success=False,
            duration=0.0,
            error_detected=False,
            error_handled_properly=False,
            recovery_successful=False,
            details={}
        )
        
        error_context = None
        
        try:
            # Execute setup actions
            setup_success = self._execute_setup_actions(test_case.setup_actions)
            result.details["setup_success"] = setup_success
            
            if not setup_success:
                result.error_message = "Setup actions failed"
                return result
            
            # Apply error injection if needed
            if test_case.test_type in ["network_failure", "timeout", "invalid_response"]:
                injector_name = test_case.test_type
                if injector_name in self.error_injectors:
                    error_context = self.error_injectors[injector_name]()
            
            # Execute trigger action
            with error_context if error_context else self._null_context():
                trigger_result = self._execute_trigger_action(test_case.trigger_action)
                result.details["trigger_result"] = trigger_result
                
                # Check if error was detected
                result.error_detected = self._check_error_detected(trigger_result, test_case.expected_behavior)
                
                # Check if error was handled properly
                result.error_handled_properly = self._check_error_handling(trigger_result, test_case.expected_behavior)
            
            # Execute recovery actions
            recovery_success = self._execute_recovery_actions(test_case.recovery_actions)
            result.recovery_successful = recovery_success
            result.details["recovery_success"] = recovery_success
            
            # Overall success
            result.success = (
                result.error_detected and
                result.error_handled_properly and
                result.recovery_successful
            )
            
        except Exception as e:
            result.error_message = str(e)
            self.logger.error(f"Error test {test_case.name} failed with exception: {e}")
        
        finally:
            # Cleanup error injection
            self._cleanup_error_injection(test_case.test_type)
            
            result.duration = time.time() - start_time
            self.test_results.append(result)
        
        return result
    
    @contextmanager
    def _null_context(self):
        """Null context manager for when no error injection is needed"""
        yield
    
    def _execute_setup_actions(self, actions: List[Dict[str, Any]]) -> bool:
        """Execute setup actions"""
        for action in actions:
            action_type = action.get("type")
            
            try:
                if action_type == "authenticate":
                    success = self.api_validator.authenticate()
                    if not success:
                        return False
                        
                elif action_type == "simulate_redis_failure":
                    self.redis_failure_mode = True
                    
                elif action_type == "create_orchestrator_session":
                    if self.orchestrator:
                        session_id = self.orchestrator.create_session(
                            "Error Test Session",
                            [{"type": "data_processing", "parameters": {}}]
                        )
                        action["session_id"] = session_id
                        
                elif action_type == "establish_websocket":
                    # Would establish WebSocket connection
                    pass
                    
            except Exception as e:
                self.logger.error(f"Setup action {action_type} failed: {e}")
                return False
        
        return True
    
    def _execute_trigger_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Execute trigger action that should cause an error"""
        action_type = action.get("type")
        
        if action_type == "api_call":
            # Execute API call
            endpoint = action.get("endpoint")
            method = action.get("method", "GET")
            data = action.get("data")
            authenticated = action.get("authenticated", True)
            
            if authenticated:
                result = self.api_validator.test_api_endpoint(endpoint, method, data)
            else:
                # Call without authentication
                validator = APIIntegrationValidator(base_url=self.base_url)
                result = validator.test_api_endpoint(endpoint, method, data, auth_required=False)
            
            return {
                "type": "api_result",
                "success": result.success,
                "status_code": result.status_code,
                "response_time": result.response_time,
                "error_message": result.error_message,
                "response_data": result.response_data
            }
            
        elif action_type == "raw_request":
            # Send raw malformed request
            endpoint = action.get("endpoint")
            method = action.get("method", "POST")
            data = action.get("data")
            
            try:
                response = requests.request(
                    method,
                    f"{self.base_url}{endpoint}",
                    data=data,  # Raw data, not JSON
                    headers=self.api_validator.auth_headers,
                    timeout=30
                )
                
                return {
                    "type": "raw_result",
                    "status_code": response.status_code,
                    "response_text": response.text
                }
                
            except Exception as e:
                return {
                    "type": "raw_result",
                    "error": str(e)
                }
        
        elif action_type == "crash_orchestrator":
            # Simulate orchestrator crash
            if self.orchestrator:
                self.orchestrator._running = False
                return {"type": "orchestrator_crashed"}
        
        elif action_type == "exhaust_memory":
            # Trigger memory exhaustion
            self._inject_memory_exhaustion()
            return {"type": "memory_exhausted"}
        
        elif action_type == "flood_requests":
            # Send many concurrent requests
            request_count = action.get("request_count", 50)
            concurrent = action.get("concurrent", True)
            
            if concurrent:
                with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
                    futures = []
                    for _ in range(request_count):
                        future = executor.submit(
                            self.api_validator.test_api_endpoint,
                            "/api/scripts",
                            "GET"
                        )
                        futures.append(future)
                    
                    results = []
                    for future in concurrent.futures.as_completed(futures, timeout=30):
                        try:
                            result = future.result()
                            results.append(result)
                        except Exception as e:
                            results.append({"error": str(e)})
                
                return {
                    "type": "flood_result",
                    "request_count": request_count,
                    "response_count": len(results),
                    "results": results
                }
        
        elif action_type == "execute_long_running_script":
            # Execute a script that will timeout
            timeout = action.get("timeout", 5)
            
            result = self.api_validator.test_api_endpoint(
                "/api/scripts/execute",
                "POST",
                {"script_name": "long_running_script", "parameters": {"timeout": timeout}}
            )
            
            return {
                "type": "timeout_test",
                "result": result
            }
        
        elif action_type == "disconnect_websocket":
            # Simulate WebSocket disconnection
            return {"type": "websocket_disconnected"}
        
        elif action_type == "send_large_payload":
            # Send extremely large payload
            size_mb = action.get("size_mb", 10)
            large_data = {
                "script_name": "test_script",
                "parameters": {
                    "large_data": "x" * (size_mb * 1024 * 1024)
                }
            }
            
            try:
                result = self.api_validator.test_api_endpoint(
                    "/api/scripts/execute",
                    "POST",
                    large_data
                )
                return {
                    "type": "large_payload_result",
                    "result": result
                }
            except Exception as e:
                return {
                    "type": "large_payload_result",
                    "error": str(e)
                }
        
        elif action_type == "expire_session":
            # Expire authentication session
            self.api_validator.auth_token = "expired_token"
            self.api_validator.auth_headers = {'Authorization': 'Bearer expired_token'}
            
            result = self.api_validator.test_api_endpoint("/api/scripts")
            return {
                "type": "expired_session_result",
                "result": result
            }
        
        return {"type": "unknown_action", "action": action_type}
    
    def _check_error_detected(self, trigger_result: Dict[str, Any], expected: Dict[str, Any]) -> bool:
        """Check if error was properly detected"""
        # Check status code
        expected_status = expected.get("status_code")
        if expected_status:
            actual_status = trigger_result.get("status_code")
            if actual_status != expected_status:
                return False
        
        # Check for error conditions
        if expected.get("error_message_present"):
            error_msg = trigger_result.get("error_message") or trigger_result.get("error")
            if not error_msg:
                return False
        
        if expected.get("validation_error"):
            status_code = trigger_result.get("status_code")
            if status_code != 400:
                return False
        
        if expected.get("access_denied"):
            status_code = trigger_result.get("status_code")
            if status_code != 401:
                return False
        
        return True
    
    def _check_error_handling(self, trigger_result: Dict[str, Any], expected: Dict[str, Any]) -> bool:
        """Check if error was handled properly"""
        # Check for graceful degradation
        if expected.get("graceful_degradation"):
            # System should continue functioning
            health_result = self.api_validator.test_api_endpoint("/api/health", auth_required=False)
            if not health_result.success:
                return False
        
        # Check for proper error responses
        if expected.get("no_token_issued"):
            response_data = trigger_result.get("response_data", {})
            if "access_token" in response_data:
                return False
        
        if expected.get("no_job_created"):
            response_data = trigger_result.get("response_data", {})
            if "job_id" in response_data:
                return False
        
        # Check system stability after error
        if expected.get("system_stability"):
            # Verify system is still responsive
            for _ in range(3):
                health_result = self.api_validator.test_api_endpoint("/api/health", auth_required=False)
                if not health_result.success:
                    return False
                time.sleep(1)
        
        return True
    
    def _execute_recovery_actions(self, actions: List[Dict[str, Any]]) -> bool:
        """Execute recovery actions"""
        for action in actions:
            action_type = action.get("type")
            
            try:
                if action_type == "valid_login":
                    credentials = action.get("credentials", self.api_validator.test_credentials)
                    success = self.api_validator.authenticate()
                    if not success:
                        return False
                        
                elif action_type == "authenticate_and_retry":
                    if not self.api_validator.authenticate():
                        return False
                    # Retry the original request
                    result = self.api_validator.test_api_endpoint("/api/scripts")
                    if not result.success:
                        return False
                        
                elif action_type == "execute_valid_script":
                    result = self.api_validator.test_api_endpoint(
                        "/api/scripts/execute",
                        "POST",
                        {"script_name": "test_script", "parameters": {}}
                    )
                    if not result.success:
                        return False
                        
                elif action_type == "send_valid_json":
                    result = self.api_validator.test_api_endpoint(
                        "/api/scripts/execute",
                        "POST",
                        {"script_name": "test_script", "parameters": {}}
                    )
                    if not result.success:
                        return False
                        
                elif action_type == "restore_redis_connection":
                    self.redis_failure_mode = False
                    
                elif action_type == "restart_orchestrator":
                    if self.orchestrator:
                        self.orchestrator._running = True
                        self.orchestrator._start_coordination()
                        
                elif action_type == "free_memory":
                    if hasattr(self, 'memory_hog'):
                        del self.memory_hog
                        
                elif action_type == "wait_for_system_recovery":
                    time.sleep(5)  # Allow system to recover
                    
                elif action_type == "verify_cleanup":
                    # Verify system cleanup after timeout
                    pass
                    
                elif action_type == "reconnect_websocket":
                    # Would reconnect WebSocket
                    pass
                    
                elif action_type == "send_normal_request":
                    result = self.api_validator.test_api_endpoint("/api/scripts")
                    if not result.success:
                        return False
                        
                elif action_type == "reauthenticate":
                    success = self.api_validator.authenticate()
                    if not success:
                        return False
                    
            except Exception as e:
                self.logger.error(f"Recovery action {action_type} failed: {e}")
                return False
        
        return True
    
    def _cleanup_error_injection(self, test_type: str):
        """Clean up after error injection"""
        try:
            # Reset Redis failure mode
            self.redis_failure_mode = False
            
            # Clean up memory
            if hasattr(self, 'memory_hog'):
                del self.memory_hog
            
            # Clean up temp files
            if hasattr(self, 'temp_file'):
                try:
                    os.unlink(self.temp_file.name)
                except:
                    pass
                delattr(self, 'temp_file')
            
            # Reset API validator
            self.api_validator.auth_token = None
            self.api_validator.auth_headers = {}
            
        except Exception as e:
            self.logger.warning(f"Cleanup failed: {e}")
    
    def run_all_error_tests(self) -> Dict[str, ErrorTestResult]:
        """Run all error test cases"""
        self.logger.info("Running comprehensive error handling tests")
        
        if not self.setup_test_environment():
            self.logger.error("Failed to setup error testing environment")
            return {}
        
        results = {}
        
        for test_case in self.test_cases:
            self.logger.info(f"Running error test: {test_case.name}")
            try:
                result = self.execute_error_test(test_case)
                results[test_case.name] = result
                
                if result.success:
                    self.logger.info(f"Error test {test_case.name} passed")
                else:
                    self.logger.warning(f"Error test {test_case.name} failed: {result.error_message}")
                    
            except Exception as e:
                self.logger.error(f"Error test {test_case.name} crashed: {e}")
                results[test_case.name] = ErrorTestResult(
                    test_name=test_case.name,
                    test_type=test_case.test_type,
                    success=False,
                    duration=0.0,
                    error_detected=False,
                    error_handled_properly=False,
                    recovery_successful=False,
                    details={},
                    error_message=str(e)
                )
        
        return results
    
    def generate_error_test_report(self, results: Dict[str, ErrorTestResult], output_file: str = None) -> str:
        """Generate error test report"""
        if output_file is None:
            output_file = f"error_handling_report_{int(time.time())}.json"
        
        # Calculate summary statistics
        total_tests = len(results)
        successful_tests = sum(1 for r in results.values() if r.success)
        error_detection_rate = sum(1 for r in results.values() if r.error_detected) / total_tests * 100
        error_handling_rate = sum(1 for r in results.values() if r.error_handled_properly) / total_tests * 100
        recovery_rate = sum(1 for r in results.values() if r.recovery_successful) / total_tests * 100
        
        # Group by test type
        by_type = {}
        for result in results.values():
            test_type = result.test_type
            if test_type not in by_type:
                by_type[test_type] = []
            by_type[test_type].append(result)
        
        type_summary = {}
        for test_type, type_results in by_type.items():
            type_summary[test_type] = {
                "total": len(type_results),
                "successful": sum(1 for r in type_results if r.success),
                "error_detection_rate": sum(1 for r in type_results if r.error_detected) / len(type_results) * 100,
                "error_handling_rate": sum(1 for r in type_results if r.error_handled_properly) / len(type_results) * 100,
                "recovery_rate": sum(1 for r in type_results if r.recovery_successful) / len(type_results) * 100
            }
        
        report_data = {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_tests": total_tests,
                "successful_tests": successful_tests,
                "success_rate": successful_tests / total_tests * 100 if total_tests > 0 else 0,
                "error_detection_rate": error_detection_rate,
                "error_handling_rate": error_handling_rate,
                "recovery_rate": recovery_rate,
                "overall_resilience": (error_detection_rate + error_handling_rate + recovery_rate) / 3
            },
            "by_test_type": type_summary,
            "detailed_results": {name: asdict(result) for name, result in results.items()},
            "recommendations": self._generate_recommendations(results)
        }
        
        with open(output_file, 'w') as f:
            json.dump(report_data, f, indent=2, default=str)
        
        self.logger.info(f"Error handling report generated: {output_file}")
        return output_file
    
    def _generate_recommendations(self, results: Dict[str, ErrorTestResult]) -> List[str]:
        """Generate recommendations based on test results"""
        recommendations = []
        
        # Check for common failure patterns
        failed_tests = [r for r in results.values() if not r.success]
        
        if len(failed_tests) > 0:
            recommendations.append("Some error handling tests failed - review error handling mechanisms")
        
        # Check error detection
        poor_detection = [r for r in results.values() if not r.error_detected]
        if len(poor_detection) > len(results) * 0.2:  # More than 20% failed detection
            recommendations.append("Improve error detection mechanisms - many errors went undetected")
        
        # Check error handling
        poor_handling = [r for r in results.values() if not r.error_handled_properly]
        if len(poor_handling) > len(results) * 0.2:
            recommendations.append("Improve error handling - errors not handled gracefully")
        
        # Check recovery
        poor_recovery = [r for r in results.values() if not r.recovery_successful]
        if len(poor_recovery) > len(results) * 0.2:
            recommendations.append("Improve error recovery mechanisms")
        
        # Specific recommendations by test type
        api_errors = [r for r in results.values() if r.test_type == "api_error" and not r.success]
        if len(api_errors) > 0:
            recommendations.append("Review API error handling and validation")
        
        system_failures = [r for r in results.values() if r.test_type == "system_failure" and not r.success]
        if len(system_failures) > 0:
            recommendations.append("Improve system resilience and failover mechanisms")
        
        resource_issues = [r for r in results.values() if r.test_type == "resource_exhaustion" and not r.success]
        if len(resource_issues) > 0:
            recommendations.append("Implement better resource management and throttling")
        
        if not recommendations:
            recommendations.append("Error handling appears robust - continue monitoring")
        
        return recommendations


def main():
    """Main CLI entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Error Handling and Edge Case Validator")
    parser.add_argument('--base-url', default='http://localhost:3560',
                       help='Backend API base URL')
    parser.add_argument('--test-type', 
                       choices=['api_error', 'system_failure', 'resource_exhaustion', 'invalid_input', 'timeout', 'network_failure'],
                       help='Run only specific test type')
    parser.add_argument('--output', '-o', help='Output file for report')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Verbose logging')
    
    args = parser.parse_args()
    
    # Configure logging
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create validator
    validator = ErrorHandlingValidator(base_url=args.base_url)
    
    # Filter test cases if specific type requested
    if args.test_type:
        validator.test_cases = [tc for tc in validator.test_cases if tc.test_type == args.test_type]
    
    try:
        # Run error tests
        results = validator.run_all_error_tests()
        
        # Generate report
        report_file = validator.generate_error_test_report(results, args.output)
        
        # Print summary
        total = len(results)
        successful = sum(1 for r in results.values() if r.success)
        error_detection = sum(1 for r in results.values() if r.error_detected)
        error_handling = sum(1 for r in results.values() if r.error_handled_properly)
        recovery = sum(1 for r in results.values() if r.recovery_successful)
        
        print(f"""
Error Handling Validation Complete!
==================================
Total Tests: {total}
Successful: {successful}
Success Rate: {successful/total*100:.1f}%

Error Detection: {error_detection}/{total} ({error_detection/total*100:.1f}%)
Error Handling: {error_handling}/{total} ({error_handling/total*100:.1f}%)
Recovery: {recovery}/{total} ({recovery/total*100:.1f}%)

Overall Resilience: {(error_detection + error_handling + recovery)/(total*3)*100:.1f}%

Report: {report_file}
        """)
        
        # Exit with appropriate code
        sys.exit(0 if successful == total else 1)
        
    except KeyboardInterrupt:
        print("\nValidation interrupted by user")
        sys.exit(2)
    except Exception as e:
        print(f"Validation failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(3)


if __name__ == '__main__':
    main()