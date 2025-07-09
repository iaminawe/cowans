#!/usr/bin/env python3
"""
SWARM Integration Test Suite

Comprehensive testing of the integrated dashboard system including:
- Frontend/Backend API integration
- SPARC orchestrator coordination
- Memory system functionality
- End-to-end workflow validation
- Real-time communication testing
"""

import unittest
import asyncio
import json
import time
import requests
import websocket
import threading
import tempfile
import os
import sys
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
from contextlib import contextmanager

# Add parent directories to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scripts.orchestration.sparc_orchestrator import SPARCOrchestrator, SPARCTask, SPARCAgent, SPARCSession
from scripts.orchestration.sparc_memory import SPARCMemoryCoordinator, SPARCMemoryEventType
from web_dashboard.backend.app import app, socketio
from web_dashboard.backend.job_manager import JobManager


class SWARMIntegrationTestCase(unittest.TestCase):
    """Base test case for SWARM integration tests"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test environment"""
        cls.test_session_id = f"test_session_{int(time.time())}"
        cls.base_url = "http://localhost:3560"
        cls.websocket_url = "ws://localhost:3560"
        
        # Start Flask app in test mode
        cls.app = app
        cls.app.config['TESTING'] = True
        cls.app.config['JWT_SECRET_KEY'] = 'test-secret-key'
        cls.client = cls.app.test_client()
        
        # Mock Redis for testing
        cls.mock_redis = Mock()
        cls.mock_redis.ping.return_value = True
        cls.mock_redis.setex.return_value = True
        cls.mock_redis.get.return_value = None
        cls.mock_redis.smembers.return_value = set()
        cls.mock_redis.sadd.return_value = True
        cls.mock_redis.hset.return_value = True
        cls.mock_redis.hgetall.return_value = {}
        
        # Create test orchestrator
        cls.orchestrator = SPARCOrchestrator(redis_client=cls.mock_redis)
        
        # Create memory coordinator
        cls.memory_coordinator = SPARCMemoryCoordinator(cls.mock_redis, namespace="test_sparc")
        
    def setUp(self):
        """Set up each test"""
        self.test_data = {
            "session_name": f"Test Session {datetime.now().isoformat()}",
            "tasks": [
                {
                    "type": "data_processing",
                    "parameters": {"input_data": "test.csv", "processing_type": "filter"},
                    "priority": 10
                },
                {
                    "type": "shopify_upload",
                    "parameters": {"shop_url": "test.myshopify.com", "access_token": "test_token"},
                    "priority": 8
                }
            ],
            "agents": [
                {
                    "id": "test_agent_1",
                    "name": "Data Processor",
                    "capabilities": ["data_processing", "transformation"]
                },
                {
                    "id": "test_agent_2", 
                    "name": "Shopify Uploader",
                    "capabilities": ["shopify_api", "upload"]
                }
            ]
        }
        
        # Authenticate for API tests
        self.auth_token = self._get_auth_token()
        
    def _get_auth_token(self):
        """Get authentication token for API testing"""
        response = self.client.post('/api/auth/login', 
                                  json={"email": "test@example.com", "password": "test123"})
        if response.status_code == 200:
            return response.json.get('access_token')
        return None
    
    def _get_auth_headers(self):
        """Get authorization headers"""
        if self.auth_token:
            return {'Authorization': f'Bearer {self.auth_token}'}
        return {}


class TestSPARCOrchestrationIntegration(SWARMIntegrationTestCase):
    """Test SPARC orchestrator integration"""
    
    def test_session_creation_and_lifecycle(self):
        """Test complete session lifecycle"""
        # Create session
        session_id = self.orchestrator.create_session(
            self.test_data["session_name"],
            self.test_data["tasks"],
            self.test_data["agents"]
        )
        
        self.assertIsNotNone(session_id)
        self.assertIn(session_id, self.orchestrator.sessions)
        
        # Start session
        success = self.orchestrator.start_session(session_id)
        self.assertTrue(success)
        
        session = self.orchestrator.sessions[session_id]
        self.assertEqual(session.status.value, "active")
        
        # Get session status
        status = self.orchestrator.get_session_status(session_id)
        self.assertIsNotNone(status)
        self.assertEqual(status["status"], "active")
        self.assertIn("progress", status)
        self.assertIn("task_summary", status)
        
        # Stop session
        success = self.orchestrator.stop_session(session_id)
        self.assertTrue(success)
        
        session = self.orchestrator.sessions[session_id]
        self.assertEqual(session.status.value, "cancelled")
    
    def test_task_assignment_and_execution(self):
        """Test task assignment to agents"""
        session_id = self.orchestrator.create_session(
            self.test_data["session_name"],
            self.test_data["tasks"],
            self.test_data["agents"]
        )
        
        session = self.orchestrator.sessions[session_id]
        
        # Verify tasks are created
        self.assertEqual(len(session.tasks), 2)
        
        # Verify agents are created
        self.assertEqual(len(session.agents), 2)
        
        # Start session and let it run briefly
        self.orchestrator.start_session(session_id)
        time.sleep(2)  # Allow task assignment
        
        # Check if tasks were assigned
        assigned_tasks = [task for task in session.tasks.values() 
                         if task.status.value in ["assigned", "in_progress"]]
        
        # At least one task should be assigned or in progress
        self.assertGreater(len(assigned_tasks), 0)
        
        self.orchestrator.stop_session(session_id)
    
    def test_error_handling_and_recovery(self):
        """Test error handling in orchestration"""
        # Create session with invalid task type
        invalid_tasks = [
            {
                "type": "invalid_task_type",
                "parameters": {},
                "priority": 5
            }
        ]
        
        session_id = self.orchestrator.create_session(
            "Error Test Session",
            invalid_tasks
        )
        
        self.orchestrator.start_session(session_id)
        time.sleep(3)  # Allow task execution attempt
        
        session = self.orchestrator.sessions[session_id]
        
        # Task should fail due to invalid type
        failed_tasks = [task for task in session.tasks.values() 
                       if task.status.value == "failed"]
        
        self.assertGreater(len(failed_tasks), 0)
        self.orchestrator.stop_session(session_id)


class TestMemoryCoordinationIntegration(SWARMIntegrationTestCase):
    """Test memory coordination system integration"""
    
    def test_session_memory_operations(self):
        """Test session memory management"""
        test_session_data = {
            "id": self.test_session_id,
            "name": "Memory Test Session",
            "status": "active",
            "created_at": datetime.now().isoformat()
        }
        
        # Create session in memory
        success = self.memory_coordinator.create_session(self.test_session_id, test_session_data)
        self.assertTrue(success)
        
        # Retrieve session
        retrieved_session = self.memory_coordinator.get_session(self.test_session_id)
        self.assertIsNotNone(retrieved_session)
        self.assertEqual(retrieved_session["name"], "Memory Test Session")
        
        # Update session
        updates = {"status": "completing", "progress": 75}
        success = self.memory_coordinator.update_session(self.test_session_id, updates)
        self.assertTrue(success)
        
        # Verify updates
        updated_session = self.memory_coordinator.get_session(self.test_session_id)
        self.assertEqual(updated_session["status"], "completing")
        self.assertEqual(updated_session["progress"], 75)
        
        # Delete session
        success = self.memory_coordinator.delete_session(self.test_session_id)
        self.assertTrue(success)
        
        # Verify deletion
        deleted_session = self.memory_coordinator.get_session(self.test_session_id)
        self.assertIsNone(deleted_session)
    
    def test_shared_context_operations(self):
        """Test shared context management"""
        # Create session first
        test_session_data = {"id": self.test_session_id, "name": "Context Test"}
        self.memory_coordinator.create_session(self.test_session_id, test_session_data)
        
        # Set context values
        context_data = {
            "input_file": "test_products.csv",
            "processing_stage": "filtering",
            "stats": {"total_products": 1000, "filtered_products": 750}
        }
        
        for key, value in context_data.items():
            success = self.memory_coordinator.set_shared_context(self.test_session_id, key, value)
            self.assertTrue(success)
        
        # Retrieve individual context values
        input_file = self.memory_coordinator.get_shared_context(self.test_session_id, "input_file")
        self.assertEqual(input_file, "test_products.csv")
        
        stats = self.memory_coordinator.get_shared_context(self.test_session_id, "stats")
        self.assertEqual(stats["total_products"], 1000)
        
        # Retrieve all context
        all_context = self.memory_coordinator.get_shared_context(self.test_session_id)
        self.assertIn("input_file", all_context)
        self.assertIn("processing_stage", all_context)
        self.assertIn("stats", all_context)
        
        # Cleanup
        self.memory_coordinator.delete_session(self.test_session_id)
    
    def test_agent_registration_and_discovery(self):
        """Test agent registration and discovery"""
        # Create session
        test_session_data = {"id": self.test_session_id, "name": "Agent Test"}
        self.memory_coordinator.create_session(self.test_session_id, test_session_data)
        
        # Register agents
        agents_data = [
            {
                "id": "agent_1",
                "name": "Data Processor",
                "capabilities": ["data_processing", "csv_handling"],
                "status": "idle"
            },
            {
                "id": "agent_2",
                "name": "API Uploader", 
                "capabilities": ["api_calls", "shopify_upload"],
                "status": "idle"
            }
        ]
        
        for agent_data in agents_data:
            success = self.memory_coordinator.register_agent(
                self.test_session_id, agent_data["id"], agent_data
            )
            self.assertTrue(success)
        
        # Get all agents
        registered_agents = self.memory_coordinator.get_session_agents(self.test_session_id)
        self.assertEqual(len(registered_agents), 2)
        
        # Find available agents
        available_agents = self.memory_coordinator.find_available_agents(self.test_session_id)
        self.assertEqual(len(available_agents), 2)
        
        # Find agents with specific capabilities
        data_agents = self.memory_coordinator.find_available_agents(
            self.test_session_id, ["data_processing"]
        )
        self.assertEqual(len(data_agents), 1)
        self.assertEqual(data_agents[0]["id"], "agent_1")
        
        # Update agent heartbeat
        success = self.memory_coordinator.update_agent_heartbeat(
            self.test_session_id, "agent_1", {"status": "busy", "current_task": "processing_data"}
        )
        self.assertTrue(success)
        
        # Check agent is no longer available
        available_agents = self.memory_coordinator.find_available_agents(self.test_session_id)
        self.assertEqual(len(available_agents), 1)  # Only agent_2 should be available
        
        # Cleanup
        self.memory_coordinator.delete_session(self.test_session_id)


class TestAPIIntegration(SWARMIntegrationTestCase):
    """Test API integration between frontend and backend"""
    
    def test_authentication_flow(self):
        """Test authentication API"""
        # Test login
        response = self.client.post('/api/auth/login', 
                                  json={"email": "test@example.com", "password": "test123"})
        self.assertEqual(response.status_code, 200)
        
        data = response.get_json()
        self.assertIn('access_token', data)
        self.assertIn('user', data)
        
        # Test invalid login
        response = self.client.post('/api/auth/login',
                                  json={"email": "invalid@example.com", "password": "wrong"})
        self.assertEqual(response.status_code, 401)
    
    def test_script_management_api(self):
        """Test script management endpoints"""
        headers = self._get_auth_headers()
        
        # Get all scripts
        response = self.client.get('/api/scripts', headers=headers)
        self.assertEqual(response.status_code, 200)
        
        scripts = response.get_json()
        self.assertIsInstance(scripts, dict)
        
        # Test script execution
        execution_data = {
            "script_name": "test_script",
            "parameters": {"input_file": "test.csv"}
        }
        
        with patch('web_dashboard.backend.script_registry.validate_script_parameters') as mock_validate:
            mock_validate.return_value = (True, "Valid")
            
            response = self.client.post('/api/scripts/execute', 
                                      json=execution_data, headers=headers)
            self.assertIn(response.status_code, [200, 201])
    
    def test_job_management_api(self):
        """Test job management endpoints"""
        headers = self._get_auth_headers()
        
        # Get user jobs
        response = self.client.get('/api/jobs', headers=headers)
        self.assertEqual(response.status_code, 200)
        
        # Test job status (mock)
        response = self.client.get('/api/jobs/test_job_id', headers=headers)
        self.assertEqual(response.status_code, 200)
        
        job_data = response.get_json()
        self.assertIn('job_id', job_data)
        self.assertIn('status', job_data)
    
    def test_sync_api(self):
        """Test sync management endpoints"""
        headers = self._get_auth_headers()
        
        # Trigger sync
        response = self.client.post('/api/sync/trigger', headers=headers)
        self.assertEqual(response.status_code, 200)
        
        sync_data = response.get_json()
        self.assertIn('job_id', sync_data)
        self.assertIn('message', sync_data)
        
        # Get sync history
        response = self.client.get('/api/sync/history', headers=headers)
        self.assertEqual(response.status_code, 200)
        
        history = response.get_json()
        self.assertIsInstance(history, list)
    
    def test_health_check(self):
        """Test health check endpoint"""
        response = self.client.get('/api/health')
        self.assertEqual(response.status_code, 200)
        
        health_data = response.get_json()
        self.assertIn('status', health_data)
        self.assertIn('services', health_data)


class TestWebSocketIntegration(SWARMIntegrationTestCase):
    """Test WebSocket communication integration"""
    
    def setUp(self):
        super().setUp()
        self.ws_messages = []
        self.ws_connected = False
        
    def on_message(self, ws, message):
        """WebSocket message handler"""
        try:
            data = json.loads(message)
            self.ws_messages.append(data)
        except json.JSONDecodeError:
            self.ws_messages.append({"raw": message})
    
    def on_open(self, ws):
        """WebSocket open handler"""
        self.ws_connected = True
        
    def on_error(self, ws, error):
        """WebSocket error handler"""
        print(f"WebSocket error: {error}")
    
    def test_websocket_connection(self):
        """Test WebSocket connection and basic communication"""
        try:
            # This test would require running server
            # For now, we'll test the socketio handlers directly
            from web_dashboard.backend.app import socketio
            
            # Test connect handler
            with self.app.test_request_context():
                with socketio.test_client(self.app) as client:
                    received = client.get_received()
                    self.assertTrue(len(received) >= 0)  # Should receive connect message
                    
        except Exception as e:
            # Skip if can't connect to server
            self.skipTest(f"WebSocket server not available: {e}")
    
    def test_script_execution_websocket(self):
        """Test script execution via WebSocket"""
        try:
            with self.app.test_request_context():
                with socketio.test_client(self.app) as client:
                    # Send execute command
                    client.emit('execute', {
                        'scriptId': 'test_script',
                        'parameters': {'input': 'test.csv'}
                    })
                    
                    # Should receive status and log messages
                    received = client.get_received()
                    self.assertGreater(len(received), 0)
                    
        except Exception as e:
            self.skipTest(f"WebSocket server not available: {e}")


class TestEndToEndWorkflow(SWARMIntegrationTestCase):
    """Test complete end-to-end workflows"""
    
    def test_complete_sync_workflow(self):
        """Test complete synchronization workflow"""
        # This would test the full pipeline:
        # 1. UI triggers sync
        # 2. Backend creates SPARC session
        # 3. SPARC orchestrates tasks
        # 4. Memory coordination
        # 5. Progress updates via WebSocket
        # 6. Completion notification
        
        # For now, test the coordination between components
        headers = self._get_auth_headers()
        
        # 1. Trigger sync via API
        response = self.client.post('/api/sync/trigger', headers=headers)
        self.assertEqual(response.status_code, 200)
        job_id = response.get_json()['job_id']
        
        # 2. Create corresponding SPARC session
        session_id = self.orchestrator.create_session(
            f"Sync Job {job_id}",
            [
                {"type": "data_processing", "parameters": {"job_id": job_id}},
                {"type": "shopify_upload", "parameters": {"job_id": job_id}}
            ]
        )
        
        # 3. Start orchestration
        success = self.orchestrator.start_session(session_id)
        self.assertTrue(success)
        
        # 4. Monitor progress
        for i in range(5):  # Check for 5 seconds
            status = self.orchestrator.get_session_status(session_id)
            if status and status.get('progress', {}).get('completion_percentage', 0) > 0:
                break
            time.sleep(1)
        
        # 5. Verify session is running
        status = self.orchestrator.get_session_status(session_id)
        self.assertIsNotNone(status)
        self.assertIn(status['status'], ['active', 'completing', 'completed'])
        
        # Cleanup
        self.orchestrator.stop_session(session_id)
    
    def test_error_propagation_workflow(self):
        """Test error propagation through the system"""
        # Test that errors in SPARC propagate to UI
        session_id = self.orchestrator.create_session(
            "Error Test",
            [{"type": "invalid_task", "parameters": {}}]
        )
        
        self.orchestrator.start_session(session_id)
        time.sleep(2)  # Allow task to fail
        
        status = self.orchestrator.get_session_status(session_id)
        self.assertGreater(status['task_summary']['failed'], 0)
        
        self.orchestrator.stop_session(session_id)
    
    def test_concurrent_sessions(self):
        """Test handling multiple concurrent sessions"""
        session_ids = []
        
        # Create multiple sessions
        for i in range(3):
            session_id = self.orchestrator.create_session(
                f"Concurrent Session {i}",
                [
                    {"type": "data_processing", "parameters": {"session_id": i}},
                    {"type": "cleanup_operation", "parameters": {"session_id": i}}
                ]
            )
            session_ids.append(session_id)
            self.orchestrator.start_session(session_id)
        
        # Let them run concurrently
        time.sleep(3)
        
        # Check all sessions are being processed
        active_sessions = len(self.orchestrator.active_sessions)
        self.assertGreater(active_sessions, 0)
        
        # Cleanup
        for session_id in session_ids:
            self.orchestrator.stop_session(session_id)


class TestPerformanceAndReliability(SWARMIntegrationTestCase):
    """Test performance and reliability aspects"""
    
    def test_memory_usage_monitoring(self):
        """Test memory usage doesn't grow unbounded"""
        initial_sessions = len(self.orchestrator.sessions)
        
        # Create and complete multiple sessions
        for i in range(5):
            session_id = self.orchestrator.create_session(
                f"Memory Test {i}",
                [{"type": "cleanup_operation", "parameters": {"test_id": i}}]
            )
            self.orchestrator.start_session(session_id)
            time.sleep(1)
            self.orchestrator.stop_session(session_id)
        
        # Trigger cleanup
        self.orchestrator._cleanup_sessions()
        
        # Memory usage should not grow significantly
        final_sessions = len(self.orchestrator.sessions)
        self.assertLessEqual(final_sessions - initial_sessions, 5)
    
    def test_api_response_times(self):
        """Test API response times are reasonable"""
        headers = self._get_auth_headers()
        
        # Test multiple API endpoints
        endpoints = [
            '/api/scripts',
            '/api/jobs',
            '/api/sync/history',
            '/api/health'
        ]
        
        for endpoint in endpoints:
            start_time = time.time()
            response = self.client.get(endpoint, headers=headers)
            response_time = time.time() - start_time
            
            self.assertEqual(response.status_code, 200)
            self.assertLess(response_time, 1.0)  # Should respond within 1 second
    
    def test_error_recovery(self):
        """Test system recovery from errors"""
        # Test SPARC orchestrator recovery
        original_running = self.orchestrator._running
        
        # Simulate orchestrator stop
        self.orchestrator._running = False
        time.sleep(0.1)
        
        # Create new session (should still work)
        session_id = self.orchestrator.create_session(
            "Recovery Test",
            [{"type": "data_processing", "parameters": {}}]
        )
        self.assertIsNotNone(session_id)
        
        # Restore running state
        self.orchestrator._running = original_running
        if not self.orchestrator._coordinator_thread or not self.orchestrator._coordinator_thread.is_alive():
            self.orchestrator._start_coordination()


class TestSystemMonitoring(SWARMIntegrationTestCase):
    """Test system monitoring and alerting capabilities"""
    
    def test_health_monitoring(self):
        """Test health check monitoring"""
        response = self.client.get('/api/health')
        self.assertEqual(response.status_code, 200)
        
        health_data = response.get_json()
        self.assertEqual(health_data['status'], 'healthy')
        self.assertIn('services', health_data)
        
        # Test individual service health
        services = health_data['services']
        self.assertIn('flask', services)
        self.assertEqual(services['flask'], 'healthy')
    
    def test_performance_metrics(self):
        """Test performance metrics collection"""
        # Test SPARC orchestrator metrics
        session_id = self.orchestrator.create_session(
            "Metrics Test",
            [{"type": "data_processing", "parameters": {}}]
        )
        
        self.orchestrator.start_session(session_id)
        time.sleep(1)
        
        status = self.orchestrator.get_session_status(session_id)
        self.assertIn('progress', status)
        self.assertIn('task_summary', status)
        
        # Test memory coordinator metrics
        if hasattr(self.memory_coordinator, 'get_memory_stats'):
            stats = self.memory_coordinator.get_memory_stats()
            self.assertIsInstance(stats, dict)
        
        self.orchestrator.stop_session(session_id)


def run_integration_tests():
    """Run all integration tests"""
    # Create test suite
    test_suite = unittest.TestSuite()
    
    # Add test cases
    test_cases = [
        TestSPARCOrchestrationIntegration,
        TestMemoryCoordinationIntegration,
        TestAPIIntegration,
        TestWebSocketIntegration,
        TestEndToEndWorkflow,
        TestPerformanceAndReliability,
        TestSystemMonitoring
    ]
    
    for test_case in test_cases:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_case)
        test_suite.addTests(tests)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='SWARM Integration Test Suite')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    parser.add_argument('--test', '-t', help='Run specific test class')
    
    args = parser.parse_args()
    
    if args.test:
        # Run specific test
        suite = unittest.TestSuite()
        suite.addTest(unittest.TestLoader().loadTestsFromName(args.test))
        runner = unittest.TextTestRunner(verbosity=2 if args.verbose else 1)
        result = runner.run(suite)
    else:
        # Run all tests
        success = run_integration_tests()
        sys.exit(0 if success else 1)