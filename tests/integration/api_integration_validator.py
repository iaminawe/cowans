#!/usr/bin/env python3
"""
API Integration Validator

Validates API integrations between frontend, backend, and SPARC orchestrator.
Tests authentication, data flow, WebSocket communication, and error handling.
"""

import asyncio
import json
import time
import requests
import websocket
import threading
import queue
import logging
import sys
import os
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from contextlib import contextmanager
import concurrent.futures

# Add parent directories to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scripts.orchestration.sparc_orchestrator import SPARCOrchestrator
from scripts.orchestration.sparc_memory import SPARCMemoryCoordinator
from web_dashboard.backend.app import app


@dataclass
class APITestResult:
    """API test result structure"""
    endpoint: str
    method: str
    status_code: int
    response_time: float
    success: bool
    error_message: Optional[str] = None
    response_data: Optional[Dict] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


@dataclass
class WebSocketTestResult:
    """WebSocket test result structure"""
    event_type: str
    success: bool
    response_time: float
    message_count: int
    error_message: Optional[str] = None
    messages: List[Dict] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
        if self.messages is None:
            self.messages = []


class APIIntegrationValidator:
    """Comprehensive API integration validator"""
    
    def __init__(self, base_url: str = "http://localhost:3560", 
                 websocket_url: str = "ws://localhost:3560",
                 timeout: int = 30):
        self.base_url = base_url.rstrip('/')
        self.websocket_url = websocket_url
        self.timeout = timeout
        self.logger = self._setup_logging()
        
        # Authentication
        self.auth_token = None
        self.auth_headers = {}
        
        # Test data
        self.test_credentials = {
            "email": "test@example.com",
            "password": "test123"
        }
        
        # Results storage
        self.api_results: List[APITestResult] = []
        self.websocket_results: List[WebSocketTestResult] = []
        
        # WebSocket testing
        self.ws_message_queue = queue.Queue()
        self.ws_connection = None
        self.ws_connected = False
        
    def _setup_logging(self) -> logging.Logger:
        """Setup logging for validator"""
        logger = logging.getLogger("api_validator")
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger
    
    def authenticate(self) -> bool:
        """Authenticate with the API and get token"""
        self.logger.info("Authenticating with API")
        
        try:
            response = requests.post(
                f"{self.base_url}/api/auth/login",
                json=self.test_credentials,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                self.auth_token = data.get('access_token')
                self.auth_headers = {'Authorization': f'Bearer {self.auth_token}'}
                self.logger.info("Authentication successful")
                return True
            else:
                self.logger.error(f"Authentication failed: {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.error(f"Authentication error: {e}")
            return False
    
    def test_api_endpoint(self, endpoint: str, method: str = "GET", 
                         data: Optional[Dict] = None, 
                         headers: Optional[Dict] = None,
                         auth_required: bool = True) -> APITestResult:
        """Test a single API endpoint"""
        url = f"{self.base_url}{endpoint}"
        
        # Prepare headers
        request_headers = {}
        if auth_required:
            request_headers.update(self.auth_headers)
        if headers:
            request_headers.update(headers)
        
        start_time = time.time()
        
        try:
            if method.upper() == "GET":
                response = requests.get(url, headers=request_headers, timeout=self.timeout)
            elif method.upper() == "POST":
                response = requests.post(url, json=data, headers=request_headers, timeout=self.timeout)
            elif method.upper() == "PUT":
                response = requests.put(url, json=data, headers=request_headers, timeout=self.timeout)
            elif method.upper() == "DELETE":
                response = requests.delete(url, headers=request_headers, timeout=self.timeout)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            response_time = time.time() - start_time
            
            # Parse response
            try:
                response_data = response.json()
            except:
                response_data = {"raw_response": response.text}
            
            success = 200 <= response.status_code < 300
            
            result = APITestResult(
                endpoint=endpoint,
                method=method.upper(),
                status_code=response.status_code,
                response_time=response_time,
                success=success,
                response_data=response_data,
                error_message=None if success else f"HTTP {response.status_code}: {response.text}"
            )
            
        except Exception as e:
            response_time = time.time() - start_time
            result = APITestResult(
                endpoint=endpoint,
                method=method.upper(),
                status_code=0,
                response_time=response_time,
                success=False,
                error_message=str(e)
            )
        
        self.api_results.append(result)
        return result
    
    def test_authentication_endpoints(self) -> List[APITestResult]:
        """Test authentication-related endpoints"""
        self.logger.info("Testing authentication endpoints")
        results = []
        
        # Test login with valid credentials
        result = self.test_api_endpoint(
            "/api/auth/login",
            method="POST",
            data=self.test_credentials,
            auth_required=False
        )
        results.append(result)
        
        # Test login with invalid credentials
        result = self.test_api_endpoint(
            "/api/auth/login",
            method="POST",
            data={"email": "invalid@example.com", "password": "wrong"},
            auth_required=False
        )
        results.append(result)
        
        return results
    
    def test_script_endpoints(self) -> List[APITestResult]:
        """Test script management endpoints"""
        self.logger.info("Testing script management endpoints")
        results = []
        
        # Get all scripts
        result = self.test_api_endpoint("/api/scripts")
        results.append(result)
        
        # Get specific script details
        result = self.test_api_endpoint("/api/scripts/test_script")
        results.append(result)
        
        # Execute script
        result = self.test_api_endpoint(
            "/api/scripts/execute",
            method="POST",
            data={
                "script_name": "test_script",
                "parameters": {"input_file": "test.csv"}
            }
        )
        results.append(result)
        
        return results
    
    def test_job_endpoints(self) -> List[APITestResult]:
        """Test job management endpoints"""
        self.logger.info("Testing job management endpoints")
        results = []
        
        # Get user jobs
        result = self.test_api_endpoint("/api/jobs")
        results.append(result)
        
        # Get job status
        result = self.test_api_endpoint("/api/jobs/test_job_id")
        results.append(result)
        
        # Cancel job
        result = self.test_api_endpoint("/api/jobs/test_job_id/cancel", method="POST")
        results.append(result)
        
        # Get job logs
        result = self.test_api_endpoint("/api/jobs/test_job_id/logs")
        results.append(result)
        
        return results
    
    def test_sync_endpoints(self) -> List[APITestResult]:
        """Test synchronization endpoints"""
        self.logger.info("Testing sync endpoints")
        results = []
        
        # Trigger sync
        result = self.test_api_endpoint("/api/sync/trigger", method="POST")
        results.append(result)
        
        # Get sync history
        result = self.test_api_endpoint("/api/sync/history")
        results.append(result)
        
        return results
    
    def test_health_endpoint(self) -> APITestResult:
        """Test health check endpoint"""
        self.logger.info("Testing health endpoint")
        return self.test_api_endpoint("/api/health", auth_required=False)
    
    def on_websocket_message(self, ws, message):
        """WebSocket message handler"""
        try:
            data = json.loads(message)
            self.ws_message_queue.put(data)
        except json.JSONDecodeError:
            self.ws_message_queue.put({"raw": message})
    
    def on_websocket_error(self, ws, error):
        """WebSocket error handler"""
        self.logger.error(f"WebSocket error: {error}")
        self.ws_message_queue.put({"error": str(error)})
    
    def on_websocket_close(self, ws, close_status_code, close_msg):
        """WebSocket close handler"""
        self.logger.info("WebSocket connection closed")
        self.ws_connected = False
    
    def on_websocket_open(self, ws):
        """WebSocket open handler"""
        self.logger.info("WebSocket connection opened")
        self.ws_connected = True
    
    def test_websocket_connection(self) -> WebSocketTestResult:
        """Test WebSocket connection"""
        self.logger.info("Testing WebSocket connection")
        start_time = time.time()
        
        try:
            # Create WebSocket connection
            self.ws_connection = websocket.WebSocketApp(
                self.websocket_url,
                on_message=self.on_websocket_message,
                on_error=self.on_websocket_error,
                on_close=self.on_websocket_close,
                on_open=self.on_websocket_open
            )
            
            # Start WebSocket in thread
            ws_thread = threading.Thread(target=self.ws_connection.run_forever)
            ws_thread.daemon = True
            ws_thread.start()
            
            # Wait for connection
            connection_timeout = 5
            for _ in range(connection_timeout * 10):
                if self.ws_connected:
                    break
                time.sleep(0.1)
            
            response_time = time.time() - start_time
            
            if self.ws_connected:
                result = WebSocketTestResult(
                    event_type="connection",
                    success=True,
                    response_time=response_time,
                    message_count=0
                )
            else:
                result = WebSocketTestResult(
                    event_type="connection",
                    success=False,
                    response_time=response_time,
                    message_count=0,
                    error_message="Connection timeout"
                )
            
        except Exception as e:
            response_time = time.time() - start_time
            result = WebSocketTestResult(
                event_type="connection",
                success=False,
                response_time=response_time,
                message_count=0,
                error_message=str(e)
            )
        
        self.websocket_results.append(result)
        return result
    
    def test_websocket_script_execution(self) -> WebSocketTestResult:
        """Test script execution via WebSocket"""
        self.logger.info("Testing WebSocket script execution")
        
        if not self.ws_connected:
            return WebSocketTestResult(
                event_type="script_execution",
                success=False,
                response_time=0,
                message_count=0,
                error_message="WebSocket not connected"
            )
        
        start_time = time.time()
        
        try:
            # Clear message queue
            while not self.ws_message_queue.empty():
                self.ws_message_queue.get_nowait()
            
            # Send script execution command
            command = {
                "type": "execute",
                "scriptId": "test_script",
                "parameters": {"input": "test.csv"}
            }
            
            self.ws_connection.send(json.dumps(command))
            
            # Collect responses
            messages = []
            timeout = 10  # seconds
            end_time = start_time + timeout
            
            while time.time() < end_time:
                try:
                    message = self.ws_message_queue.get(timeout=1)
                    messages.append(message)
                    
                    # Check for completion
                    if message.get("type") == "complete":
                        break
                        
                except queue.Empty:
                    continue
            
            response_time = time.time() - start_time
            
            # Analyze results
            success = any(msg.get("type") == "complete" for msg in messages)
            
            result = WebSocketTestResult(
                event_type="script_execution",
                success=success,
                response_time=response_time,
                message_count=len(messages),
                messages=messages,
                error_message=None if success else "No completion message received"
            )
            
        except Exception as e:
            response_time = time.time() - start_time
            result = WebSocketTestResult(
                event_type="script_execution",
                success=False,
                response_time=response_time,
                message_count=0,
                error_message=str(e)
            )
        
        self.websocket_results.append(result)
        return result
    
    def test_sparc_orchestrator_integration(self) -> Dict[str, Any]:
        """Test integration with SPARC orchestrator"""
        self.logger.info("Testing SPARC orchestrator integration")
        
        try:
            # Create mock Redis client
            from unittest.mock import Mock
            mock_redis = Mock()
            mock_redis.ping.return_value = True
            
            # Create orchestrator
            orchestrator = SPARCOrchestrator(redis_client=mock_redis)
            
            # Test session creation
            session_id = orchestrator.create_session(
                "API Integration Test",
                [
                    {"type": "data_processing", "parameters": {"test": True}},
                    {"type": "shopify_upload", "parameters": {"test": True}}
                ]
            )
            
            # Test session management
            success = orchestrator.start_session(session_id)
            time.sleep(1)  # Allow brief execution
            status = orchestrator.get_session_status(session_id)
            orchestrator.stop_session(session_id)
            
            return {
                "success": True,
                "session_created": session_id is not None,
                "session_started": success,
                "status_retrieved": status is not None,
                "task_count": len(status.get("task_summary", {})) if status else 0
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def test_memory_coordinator_integration(self) -> Dict[str, Any]:
        """Test integration with memory coordinator"""
        self.logger.info("Testing memory coordinator integration")
        
        try:
            # Create mock Redis client
            from unittest.mock import Mock
            mock_redis = Mock()
            mock_redis.ping.return_value = True
            mock_redis.setex.return_value = True
            mock_redis.get.return_value = None
            mock_redis.smembers.return_value = set()
            mock_redis.sadd.return_value = True
            mock_redis.hset.return_value = True
            mock_redis.hgetall.return_value = {}
            
            # Create memory coordinator
            memory_coordinator = SPARCMemoryCoordinator(mock_redis, namespace="test_api")
            
            # Test session operations
            test_session_id = "api_test_session"
            session_data = {"id": test_session_id, "name": "API Test"}
            
            created = memory_coordinator.create_session(test_session_id, session_data)
            retrieved = memory_coordinator.get_session(test_session_id)
            updated = memory_coordinator.update_session(test_session_id, {"status": "active"})
            
            # Test context operations
            context_set = memory_coordinator.set_shared_context(test_session_id, "test_key", "test_value")
            context_retrieved = memory_coordinator.get_shared_context(test_session_id, "test_key")
            
            # Test agent operations
            agent_data = {"id": "test_agent", "name": "Test Agent", "capabilities": ["test"]}
            agent_registered = memory_coordinator.register_agent(test_session_id, "test_agent", agent_data)
            agents = memory_coordinator.get_session_agents(test_session_id)
            
            return {
                "success": True,
                "session_created": created,
                "session_retrieved": retrieved is not None,
                "session_updated": updated,
                "context_set": context_set,
                "context_retrieved": context_retrieved is not None,
                "agent_registered": agent_registered,
                "agents_count": len(agents)
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def run_comprehensive_validation(self) -> Dict[str, Any]:
        """Run comprehensive API validation"""
        self.logger.info("Starting comprehensive API validation")
        
        validation_results = {
            "timestamp": datetime.now().isoformat(),
            "authentication": {"success": False},
            "api_endpoints": [],
            "websocket": [],
            "sparc_integration": {},
            "memory_integration": {},
            "summary": {}
        }
        
        # Step 1: Authentication
        if self.authenticate():
            validation_results["authentication"]["success"] = True
            
            # Step 2: Test API endpoints
            validation_results["api_endpoints"].extend(self.test_authentication_endpoints())
            validation_results["api_endpoints"].extend(self.test_script_endpoints())
            validation_results["api_endpoints"].extend(self.test_job_endpoints())
            validation_results["api_endpoints"].extend(self.test_sync_endpoints())
            validation_results["api_endpoints"].append(self.test_health_endpoint())
            
        else:
            validation_results["authentication"]["error"] = "Failed to authenticate"
        
        # Step 3: Test WebSocket
        ws_connection_result = self.test_websocket_connection()
        validation_results["websocket"].append(ws_connection_result)
        
        if ws_connection_result.success:
            ws_execution_result = self.test_websocket_script_execution()
            validation_results["websocket"].append(ws_execution_result)
        
        # Step 4: Test SPARC integration
        validation_results["sparc_integration"] = self.test_sparc_orchestrator_integration()
        
        # Step 5: Test memory integration
        validation_results["memory_integration"] = self.test_memory_coordinator_integration()
        
        # Generate summary
        api_success_count = sum(1 for r in self.api_results if r.success)
        api_total = len(self.api_results)
        
        ws_success_count = sum(1 for r in self.websocket_results if r.success)
        ws_total = len(self.websocket_results)
        
        validation_results["summary"] = {
            "total_api_tests": api_total,
            "successful_api_tests": api_success_count,
            "api_success_rate": (api_success_count / api_total * 100) if api_total > 0 else 0,
            "total_websocket_tests": ws_total,
            "successful_websocket_tests": ws_success_count,
            "websocket_success_rate": (ws_success_count / ws_total * 100) if ws_total > 0 else 0,
            "sparc_integration_success": validation_results["sparc_integration"].get("success", False),
            "memory_integration_success": validation_results["memory_integration"].get("success", False),
            "overall_success": (
                validation_results["authentication"]["success"] and
                api_success_count == api_total and
                ws_success_count == ws_total and
                validation_results["sparc_integration"].get("success", False) and
                validation_results["memory_integration"].get("success", False)
            )
        }
        
        # Close WebSocket connection
        if self.ws_connection:
            self.ws_connection.close()
        
        return validation_results
    
    def generate_report(self, results: Dict[str, Any], output_file: str = None) -> str:
        """Generate validation report"""
        if output_file is None:
            output_file = f"api_validation_report_{int(time.time())}.json"
        
        # Add test results to report
        results["detailed_results"] = {
            "api_test_results": [
                {
                    "endpoint": r.endpoint,
                    "method": r.method,
                    "status_code": r.status_code,
                    "response_time": r.response_time,
                    "success": r.success,
                    "error_message": r.error_message,
                    "timestamp": r.timestamp.isoformat()
                }
                for r in self.api_results
            ],
            "websocket_test_results": [
                {
                    "event_type": r.event_type,
                    "success": r.success,
                    "response_time": r.response_time,
                    "message_count": r.message_count,
                    "error_message": r.error_message,
                    "timestamp": r.timestamp.isoformat()
                }
                for r in self.websocket_results
            ]
        }
        
        # Write report
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        self.logger.info(f"Validation report generated: {output_file}")
        return output_file


def main():
    """Main CLI entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="API Integration Validator")
    parser.add_argument('--base-url', default='http://localhost:3560',
                       help='Base URL for API testing')
    parser.add_argument('--websocket-url', default='ws://localhost:3560',
                       help='WebSocket URL for testing')
    parser.add_argument('--timeout', type=int, default=30,
                       help='Request timeout in seconds')
    parser.add_argument('--output', '-o', help='Output file for validation report')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Verbose logging')
    
    args = parser.parse_args()
    
    # Configure logging
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create validator
    validator = APIIntegrationValidator(
        base_url=args.base_url,
        websocket_url=args.websocket_url,
        timeout=args.timeout
    )
    
    try:
        # Run validation
        results = validator.run_comprehensive_validation()
        
        # Generate report
        report_file = validator.generate_report(results, args.output)
        
        # Print summary
        summary = results["summary"]
        print(f"""
API Integration Validation Complete!
===================================
Authentication: {'✅ Success' if results['authentication']['success'] else '❌ Failed'}
API Tests: {summary['successful_api_tests']}/{summary['total_api_tests']} passed ({summary['api_success_rate']:.1f}%)
WebSocket Tests: {summary['successful_websocket_tests']}/{summary['total_websocket_tests']} passed ({summary['websocket_success_rate']:.1f}%)
SPARC Integration: {'✅ Success' if summary['sparc_integration_success'] else '❌ Failed'}
Memory Integration: {'✅ Success' if summary['memory_integration_success'] else '❌ Failed'}
Overall Status: {'✅ All Passed' if summary['overall_success'] else '❌ Some Failed'}

Report: {report_file}
        """)
        
        # Exit with appropriate code
        sys.exit(0 if summary['overall_success'] else 1)
        
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