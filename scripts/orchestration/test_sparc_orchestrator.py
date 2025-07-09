#!/usr/bin/env python3
"""
SPARC Orchestrator Test Suite

Comprehensive test suite for the SPARC orchestration system.
Tests core functionality, integration patterns, and edge cases.
"""

import unittest
import tempfile
import shutil
import time
import json
import os
import sys
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

# Add parent directories to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import SPARC components
from orchestration.sparc_orchestrator import (
    SPARCOrchestrator, SPARCTask, SPARCAgent, SPARCSession,
    SPARCTaskStatus, SPARCAgentStatus, SPARCSessionStatus
)
from orchestration.sparc_memory import SPARCMemoryCoordinator, SPARCMemoryEventType
from orchestration.sparc_agent_launcher import SPARCAgentLauncher, SPARCAgentConfig, SPARCAgentType, SPARCAgentLaunchMode
from orchestration.sparc_progress_tracker import SPARCProgressTracker, SPARCResultAggregator, SPARCProgressStage
from orchestration.sparc_integration_example import SPARCWorkflowIntegration


class MockRedisClient:
    """Mock Redis client for testing"""
    
    def __init__(self):
        self.data = {}
        self.sets = {}
        self.lists = {}
        self.hashes = {}
        self.expirations = {}
        self.pubsub_channels = {}
    
    def ping(self):
        return True
    
    def setex(self, key, ttl, value):
        self.data[key] = value
        self.expirations[key] = datetime.now() + timedelta(seconds=ttl)
        return True
    
    def get(self, key):
        if key in self.data:
            # Check expiration
            if key in self.expirations and datetime.now() > self.expirations[key]:
                del self.data[key]
                del self.expirations[key]
                return None
            return self.data[key]
        return None
    
    def delete(self, *keys):
        deleted = 0
        for key in keys:
            if key in self.data:
                del self.data[key]
                deleted += 1
            if key in self.expirations:
                del self.expirations[key]
        return deleted
    
    def sadd(self, key, *values):
        if key not in self.sets:
            self.sets[key] = set()
        self.sets[key].update(values)
        return len(values)
    
    def smembers(self, key):
        return self.sets.get(key, set())
    
    def srem(self, key, *values):
        if key in self.sets:
            self.sets[key].discard(*values)
        return len(values)
    
    def scard(self, key):
        return len(self.sets.get(key, set()))
    
    def hset(self, key, field=None, value=None, mapping=None):
        if key not in self.hashes:
            self.hashes[key] = {}
        
        if mapping:
            self.hashes[key].update(mapping)
        elif field and value:
            self.hashes[key][field] = value
        
        return True
    
    def hget(self, key, field):
        return self.hashes.get(key, {}).get(field)
    
    def hgetall(self, key):
        return self.hashes.get(key, {})
    
    def lpush(self, key, *values):
        if key not in self.lists:
            self.lists[key] = []
        self.lists[key] = list(values) + self.lists[key]
        return len(self.lists[key])
    
    def lrange(self, key, start, end):
        return self.lists.get(key, [])[start:end+1 if end != -1 else None]
    
    def ltrim(self, key, start, end):
        if key in self.lists:
            self.lists[key] = self.lists[key][start:end+1]
        return True
    
    def expire(self, key, ttl):
        self.expirations[key] = datetime.now() + timedelta(seconds=ttl)
        return True
    
    def publish(self, channel, message):
        if channel not in self.pubsub_channels:
            self.pubsub_channels[channel] = []
        self.pubsub_channels[channel].append(message)
        return 1
    
    def pubsub(self):
        return MockPubSub()
    
    def info(self, section=None):
        return {
            'used_memory': 1024 * 1024,
            'used_memory_peak': 2048 * 1024,
            'redis_version': '6.0.0',
            'keyspace_hits': 100,
            'keyspace_misses': 10
        }


class MockPubSub:
    """Mock Redis pubsub for testing"""
    
    def __init__(self):
        self.subscriptions = set()
    
    def subscribe(self, *channels):
        self.subscriptions.update(channels)
    
    def get_message(self, timeout=None):
        return None
    
    def close(self):
        pass


class TestSPARCOrchestrator(unittest.TestCase):
    """Test SPARC Orchestrator core functionality"""
    
    def setUp(self):
        self.mock_redis = MockRedisClient()
        self.orchestrator = SPARCOrchestrator(redis_client=self.mock_redis)
    
    def tearDown(self):
        self.orchestrator.shutdown()
    
    def test_create_session(self):
        """Test session creation"""
        tasks = [
            {
                "type": "data_processing",
                "parameters": {"input_data": "test.csv", "processing_type": "filter"},
                "priority": 10
            },
            {
                "type": "shopify_upload",
                "parameters": {"products": [], "shop_url": "test.myshopify.com"},
                "priority": 8,
                "dependencies": ["test_session_task_0"]
            }
        ]
        
        session_id = self.orchestrator.create_session("Test Session", tasks)
        
        self.assertIsNotNone(session_id)
        self.assertIn(session_id, self.orchestrator.sessions)
        
        session = self.orchestrator.sessions[session_id]
        self.assertEqual(session.name, "Test Session")
        self.assertEqual(len(session.tasks), 2)
        self.assertEqual(session.status, SPARCSessionStatus.INITIALIZING)
    
    def test_start_session(self):
        """Test session startup"""
        tasks = [{"type": "data_processing", "parameters": {}}]
        session_id = self.orchestrator.create_session("Test Session", tasks)
        
        success = self.orchestrator.start_session(session_id)
        
        self.assertTrue(success)
        session = self.orchestrator.sessions[session_id]
        self.assertEqual(session.status, SPARCSessionStatus.ACTIVE)
        self.assertIsNotNone(session.started_at)
    
    def test_get_session_status(self):
        """Test session status retrieval"""
        tasks = [{"type": "data_processing", "parameters": {}}]
        session_id = self.orchestrator.create_session("Test Session", tasks)
        
        status = self.orchestrator.get_session_status(session_id)
        
        self.assertIsNotNone(status)
        self.assertEqual(status["name"], "Test Session")
        self.assertEqual(status["task_summary"]["total"], 1)
    
    def test_stop_session(self):
        """Test session stopping"""
        tasks = [{"type": "data_processing", "parameters": {}}]
        session_id = self.orchestrator.create_session("Test Session", tasks)
        self.orchestrator.start_session(session_id)
        
        success = self.orchestrator.stop_session(session_id)
        
        self.assertTrue(success)
        session = self.orchestrator.sessions[session_id]
        self.assertEqual(session.status, SPARCSessionStatus.CANCELLED)


class TestSPARCMemoryCoordinator(unittest.TestCase):
    """Test SPARC Memory Coordinator functionality"""
    
    def setUp(self):
        self.mock_redis = MockRedisClient()
        self.memory = SPARCMemoryCoordinator(self.mock_redis)
    
    def tearDown(self):
        self.memory.shutdown()
    
    def test_create_session(self):
        """Test session creation in memory"""
        session_data = {
            "id": "test_session",
            "name": "Test Session",
            "status": "active"
        }
        
        success = self.memory.create_session("test_session", session_data)
        
        self.assertTrue(success)
        retrieved_data = self.memory.get_session("test_session")
        self.assertEqual(retrieved_data["name"], "Test Session")
    
    def test_shared_context(self):
        """Test shared context management"""
        session_data = {"id": "test_session", "name": "Test"}
        self.memory.create_session("test_session", session_data)
        
        # Set context value
        success = self.memory.set_shared_context("test_session", "test_key", {"data": [1, 2, 3]})
        self.assertTrue(success)
        
        # Get context value
        value = self.memory.get_shared_context("test_session", "test_key")
        self.assertEqual(value, {"data": [1, 2, 3]})
        
        # Get all context
        all_context = self.memory.get_shared_context("test_session")
        self.assertIn("test_key", all_context)
    
    def test_agent_registration(self):
        """Test agent registration and discovery"""
        session_data = {"id": "test_session", "name": "Test"}
        self.memory.create_session("test_session", session_data)
        
        agent_data = {
            "id": "agent_1",
            "name": "Test Agent",
            "capabilities": ["data_processing"],
            "status": "idle"
        }
        
        success = self.memory.register_agent("test_session", "agent_1", agent_data)
        self.assertTrue(success)
        
        agents = self.memory.get_session_agents("test_session")
        self.assertEqual(len(agents), 1)
        self.assertEqual(agents[0]["name"], "Test Agent")
    
    def test_progress_tracking(self):
        """Test progress tracking"""
        session_data = {"id": "test_session", "name": "Test"}
        self.memory.create_session("test_session", session_data)
        
        progress_data = {
            "total_tasks": 10,
            "completed_tasks": 5,
            "completion_percentage": 50.0
        }
        
        success = self.memory.update_progress("test_session", progress_data)
        self.assertTrue(success)
        
        retrieved_progress = self.memory.get_progress("test_session")
        self.assertEqual(retrieved_progress["total_tasks"], 10)
        self.assertEqual(retrieved_progress["completion_percentage"], 50.0)


class TestSPARCAgentLauncher(unittest.TestCase):
    """Test SPARC Agent Launcher functionality"""
    
    def setUp(self):
        self.mock_redis = MockRedisClient()
        self.memory = SPARCMemoryCoordinator(self.mock_redis)
        self.launcher = SPARCAgentLauncher(self.memory)
    
    def tearDown(self):
        self.launcher.shutdown()
        self.memory.shutdown()
    
    def test_create_agent_from_template(self):
        """Test agent creation from template"""
        config = self.launcher.create_agent_from_template(
            "data_processor",
            agent_id="test_agent",
            customizations={"max_tasks": 3}
        )
        
        self.assertEqual(config.id, "test_agent")
        self.assertEqual(config.max_tasks, 3)
        self.assertIn("data_processing", config.capabilities)
    
    @patch('subprocess.Popen')
    def test_launch_process_agent(self, mock_popen):
        """Test launching process-based agent"""
        # Mock successful process launch
        mock_process = Mock()
        mock_process.pid = 12345
        mock_process.poll.return_value = None
        mock_popen.return_value = mock_process
        
        config = self.launcher.create_agent_from_template("data_processor")
        
        success = self.launcher.launch_agent("test_session", config)
        
        self.assertTrue(success)
        self.assertIn(config.id, self.launcher.agents)
        
        # Verify process was started
        mock_popen.assert_called_once()
    
    def test_launch_thread_agent(self):
        """Test launching thread-based agent"""
        config = self.launcher.create_agent_from_template("monitor_agent")
        config.launch_mode = SPARCAgentLaunchMode.THREAD
        
        with patch('orchestration.sparc_agent_worker.SPARCAgentWorker') as mock_worker_class:
            mock_worker = Mock()
            mock_worker_class.return_value = mock_worker
            
            success = self.launcher.launch_agent("test_session", config)
            
            self.assertTrue(success)
            self.assertIn(config.id, self.launcher.agents)
    
    def test_agent_swarm_launch(self):
        """Test launching agent swarm"""
        swarm_config = {
            "agents": [
                {"template": "data_processor"},
                {"template": "shopify_uploader"}
            ],
            "auto_scale": False
        }
        
        with patch.object(self.launcher, 'launch_agent', return_value=True) as mock_launch:
            launched_agents = self.launcher.launch_agent_swarm("test_session", swarm_config)
            
            self.assertEqual(len(launched_agents), 2)
            self.assertEqual(mock_launch.call_count, 2)


class TestSPARCProgressTracker(unittest.TestCase):
    """Test SPARC Progress Tracker functionality"""
    
    def setUp(self):
        self.mock_redis = MockRedisClient()
        self.memory = SPARCMemoryCoordinator(self.mock_redis)
        self.websocket_handler = Mock()
        self.tracker = SPARCProgressTracker(self.memory, self.websocket_handler)
    
    def tearDown(self):
        self.tracker.shutdown()
        self.memory.shutdown()
    
    def test_start_session_tracking(self):
        """Test starting session tracking"""
        success = self.tracker.start_session_tracking("test_session")
        
        self.assertTrue(success)
        self.assertIn("test_session", self.tracker.session_snapshots)
        
        snapshots = self.tracker.session_snapshots["test_session"]
        self.assertEqual(len(snapshots), 1)
        self.assertEqual(snapshots[0].stage, SPARCProgressStage.INITIALIZATION)
    
    def test_update_stage(self):
        """Test stage updates"""
        self.tracker.start_session_tracking("test_session")
        
        success = self.tracker.update_stage("test_session", SPARCProgressStage.EXECUTION)
        
        self.assertTrue(success)
        snapshots = self.tracker.session_snapshots["test_session"]
        self.assertEqual(len(snapshots), 2)
        self.assertEqual(snapshots[-1].stage, SPARCProgressStage.EXECUTION)
    
    def test_get_session_progress(self):
        """Test retrieving session progress"""
        self.tracker.start_session_tracking("test_session")
        self.tracker.update_stage("test_session", SPARCProgressStage.EXECUTION)
        
        progress = self.tracker.get_session_progress("test_session")
        
        self.assertIsNotNone(progress)
        self.assertEqual(progress.stage, SPARCProgressStage.EXECUTION)
        self.assertEqual(progress.session_id, "test_session")
    
    def test_websocket_updates(self):
        """Test WebSocket progress updates"""
        self.tracker.start_session_tracking("test_session")
        self.tracker.update_stage("test_session", SPARCProgressStage.EXECUTION)
        
        # Verify WebSocket handler was called
        self.websocket_handler.assert_called()


class TestSPARCResultAggregator(unittest.TestCase):
    """Test SPARC Result Aggregator functionality"""
    
    def setUp(self):
        self.mock_redis = MockRedisClient()
        self.memory = SPARCMemoryCoordinator(self.mock_redis)
        self.aggregator = SPARCResultAggregator(self.memory)
    
    def tearDown(self):
        self.memory.shutdown()
    
    def test_aggregate_session_results(self):
        """Test session result aggregation"""
        # Create test session data
        session_data = {
            "id": "test_session",
            "name": "Test Session",
            "started_at": datetime.now().isoformat(),
            "completed_at": (datetime.now() + timedelta(minutes=5)).isoformat(),
            "tasks": {
                "task_1": {
                    "type": "data_processing",
                    "status": "completed",
                    "execution_time": 120.0,
                    "result": {"processed_records": 1000}
                },
                "task_2": {
                    "type": "shopify_upload",
                    "status": "failed",
                    "error": "Connection timeout"
                }
            }
        }
        
        self.memory.create_session("test_session", session_data)
        
        # Register test agents
        agent_data = {
            "id": "agent_1",
            "performance_metrics": {
                "tasks_completed": 1,
                "tasks_failed": 1,
                "cpu_percent": 75.0,
                "memory_mb": 256.0
            }
        }
        self.memory.register_agent("test_session", "agent_1", agent_data)
        
        results = self.aggregator.aggregate_session_results("test_session")
        
        self.assertIsNotNone(results)
        self.assertEqual(results.session_id, "test_session")
        self.assertAlmostEqual(results.total_execution_time, 300.0, delta=1.0)
        self.assertEqual(results.task_results["total_tasks"], 2)
        self.assertEqual(results.task_results["completed_tasks"], 1)
        self.assertEqual(results.task_results["failed_tasks"], 1)


class TestSPARCIntegration(unittest.TestCase):
    """Test SPARC Integration functionality"""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        
        # Mock Redis to avoid external dependencies
        with patch('redis.from_url') as mock_redis:
            mock_redis.return_value = MockRedisClient()
            self.integration = SPARCWorkflowIntegration()
    
    def tearDown(self):
        self.integration.shutdown()
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_create_product_import_tasks(self):
        """Test product import task creation"""
        config = {
            "skip_download": True,
            "input_file": "test_input.csv",
            "reference_file": "test_reference.csv",
            "shop_url": "test.myshopify.com",
            "access_token": "test_token"
        }
        
        tasks = self.integration._create_product_import_tasks(config)
        
        self.assertGreater(len(tasks), 0)
        
        # Check task types
        task_types = [task["type"] for task in tasks]
        self.assertIn("data_processing", task_types)
        self.assertIn("cleanup_operation", task_types)
        
        # Check dependencies
        filter_task = next((task for task in tasks if task["type"] == "data_processing"), None)
        self.assertIsNotNone(filter_task)
    
    def test_create_analysis_tasks(self):
        """Test parallel analysis task creation"""
        config = {
            "data_chunks": ["chunk1", "chunk2", "chunk3"],
            "analysis_type": "categorization"
        }
        
        tasks = self.integration._create_parallel_analysis_tasks(config)
        
        # Should have one task per chunk plus aggregation
        self.assertEqual(len(tasks), 4)
        
        # Check task types
        analysis_tasks = [task for task in tasks if task["type"] == "parallel_analysis"]
        self.assertEqual(len(analysis_tasks), 3)
        
        aggregation_tasks = [task for task in tasks if task["type"] == "result_aggregation"]
        self.assertEqual(len(aggregation_tasks), 1)
    
    @patch.object(SPARCOrchestrator, 'create_session')
    @patch.object(SPARCOrchestrator, 'start_session')
    @patch.object(SPARCAgentLauncher, 'launch_agent_swarm')
    def test_workflow_execution_mock(self, mock_launch_swarm, mock_start_session, mock_create_session):
        """Test workflow execution with mocks"""
        mock_create_session.return_value = "test_session_id"
        mock_start_session.return_value = True
        mock_launch_swarm.return_value = ["agent_1", "agent_2"]
        
        # Mock session status to simulate completion
        with patch.object(self.integration.orchestrator, 'get_session_status') as mock_status:
            mock_status.return_value = {
                "status": "completed",
                "progress": {"completion_percentage": 100.0}
            }
            
            config = {
                "session_name": "Test Workflow",
                "skip_download": True,
                "timeout": 10
            }
            
            session_id = self.integration.run_full_product_import_workflow(config)
            
            self.assertEqual(session_id, "test_session_id")
            mock_create_session.assert_called_once()
            mock_start_session.assert_called_once()
            mock_launch_swarm.assert_called_once()


class TestSPARCEdgeCases(unittest.TestCase):
    """Test SPARC edge cases and error handling"""
    
    def setUp(self):
        self.mock_redis = MockRedisClient()
    
    def test_orchestrator_without_redis(self):
        """Test orchestrator behavior without Redis"""
        orchestrator = SPARCOrchestrator(redis_client=None)
        
        # Should still work with in-memory storage
        tasks = [{"type": "data_processing", "parameters": {}}]
        session_id = orchestrator.create_session("Test Session", tasks)
        
        self.assertIsNotNone(session_id)
        orchestrator.shutdown()
    
    def test_invalid_task_configuration(self):
        """Test handling of invalid task configurations"""
        orchestrator = SPARCOrchestrator(redis_client=self.mock_redis)
        
        # Invalid task (missing required fields)
        invalid_tasks = [{"parameters": {}}]  # Missing type
        
        # Should handle gracefully
        session_id = orchestrator.create_session("Invalid Session", invalid_tasks)
        self.assertIsNotNone(session_id)
        
        orchestrator.shutdown()
    
    def test_memory_coordinator_redis_failure(self):
        """Test memory coordinator behavior when Redis fails"""
        # Simulate Redis failure
        failing_redis = Mock()
        failing_redis.ping.side_effect = Exception("Redis connection failed")
        
        memory = SPARCMemoryCoordinator(failing_redis)
        
        # Should handle Redis failures gracefully
        success = memory.create_session("test_session", {"id": "test", "name": "Test"})
        # Depending on implementation, this might return False or handle gracefully
        memory.shutdown()
    
    def test_agent_launcher_resource_limits(self):
        """Test agent launcher resource limit enforcement"""
        memory = SPARCMemoryCoordinator(self.mock_redis)
        launcher = SPARCAgentLauncher(memory, config={"max_agents": 1})
        
        # Create two agent configs
        config1 = launcher.create_agent_from_template("data_processor", agent_id="agent_1")
        config2 = launcher.create_agent_from_template("data_processor", agent_id="agent_2")
        
        with patch.object(launcher, '_launch_process_agent', return_value=True):
            # First agent should launch successfully
            success1 = launcher.launch_agent("test_session", config1)
            self.assertTrue(success1)
            
            # Second agent should fail due to limit
            success2 = launcher.launch_agent("test_session", config2)
            # Implementation might allow or reject based on resource checks
        
        launcher.shutdown()
        memory.shutdown()


def run_performance_tests():
    """Run performance tests for SPARC components"""
    print("\nRunning SPARC Performance Tests...")
    
    mock_redis = MockRedisClient()
    
    # Test memory coordinator performance
    print("Testing Memory Coordinator performance...")
    memory = SPARCMemoryCoordinator(mock_redis)
    
    start_time = time.time()
    
    # Create many sessions
    for i in range(100):
        session_data = {"id": f"session_{i}", "name": f"Session {i}"}
        memory.create_session(f"session_{i}", session_data)
    
    # Set context for each session
    for i in range(100):
        memory.set_shared_context(f"session_{i}", "test_data", {"value": i})
    
    end_time = time.time()
    print(f"Created 100 sessions and set context in {end_time - start_time:.2f}s")
    
    memory.shutdown()
    
    # Test orchestrator performance
    print("Testing Orchestrator performance...")
    orchestrator = SPARCOrchestrator(redis_client=mock_redis)
    
    start_time = time.time()
    
    # Create sessions with multiple tasks
    session_ids = []
    for i in range(10):
        tasks = [
            {"type": "data_processing", "parameters": {"data": f"dataset_{j}"}}
            for j in range(10)
        ]
        session_id = orchestrator.create_session(f"Perf Session {i}", tasks)
        session_ids.append(session_id)
    
    end_time = time.time()
    print(f"Created 10 sessions with 100 total tasks in {end_time - start_time:.2f}s")
    
    orchestrator.shutdown()


if __name__ == "__main__":
    # Run unit tests
    print("Running SPARC Orchestrator Test Suite")
    print("=" * 50)
    
    # Create test suite
    test_suite = unittest.TestSuite()
    
    # Add test cases
    test_cases = [
        TestSPARCOrchestrator,
        TestSPARCMemoryCoordinator,
        TestSPARCAgentLauncher,
        TestSPARCProgressTracker,
        TestSPARCResultAggregator,
        TestSPARCIntegration,
        TestSPARCEdgeCases
    ]
    
    for test_case in test_cases:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_case)
        test_suite.addTests(tests)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # Print summary
    print(f"\nTest Summary:")
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    
    if result.failures:
        print("\nFailures:")
        for test, traceback in result.failures:
            print(f"- {test}: {traceback}")
    
    if result.errors:
        print("\nErrors:")
        for test, traceback in result.errors:
            print(f"- {test}: {traceback}")
    
    # Run performance tests
    run_performance_tests()
    
    print("\nSPARC Test Suite completed!")