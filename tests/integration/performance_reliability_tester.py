#!/usr/bin/env python3
"""
Performance and Reliability Testing Framework

Comprehensive testing of system performance, load handling, reliability metrics,
and scalability characteristics under various conditions.
"""

import asyncio
import json
import time
import threading
import queue
import logging
import sys
import os
import psutil
import statistics
import requests
import websocket
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple, Callable
from dataclasses import dataclass, asdict, field
from contextlib import contextmanager
import concurrent.futures
import multiprocessing
import resource
import gc

# Add parent directories to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scripts.orchestration.sparc_orchestrator import SPARCOrchestrator
from scripts.orchestration.sparc_memory import SPARCMemoryCoordinator
from api_integration_validator import APIIntegrationValidator


@dataclass
class PerformanceMetrics:
    """Performance metrics data structure"""
    response_times: List[float] = field(default_factory=list)
    throughput: float = 0.0
    error_rate: float = 0.0
    cpu_usage: List[float] = field(default_factory=list)
    memory_usage: List[float] = field(default_factory=list)
    disk_io: Dict[str, float] = field(default_factory=dict)
    network_io: Dict[str, float] = field(default_factory=dict)
    concurrent_connections: int = 0
    success_count: int = 0
    error_count: int = 0
    total_requests: int = 0
    
    def calculate_statistics(self) -> Dict[str, Any]:
        """Calculate statistical metrics"""
        stats = {}
        
        if self.response_times:
            stats["response_time_stats"] = {
                "min": min(self.response_times),
                "max": max(self.response_times),
                "mean": statistics.mean(self.response_times),
                "median": statistics.median(self.response_times),
                "p95": self._percentile(self.response_times, 95),
                "p99": self._percentile(self.response_times, 99),
                "std_dev": statistics.stdev(self.response_times) if len(self.response_times) > 1 else 0
            }
        
        if self.cpu_usage:
            stats["cpu_stats"] = {
                "min": min(self.cpu_usage),
                "max": max(self.cpu_usage),
                "mean": statistics.mean(self.cpu_usage)
            }
        
        if self.memory_usage:
            stats["memory_stats"] = {
                "min": min(self.memory_usage),
                "max": max(self.memory_usage),
                "mean": statistics.mean(self.memory_usage)
            }
        
        stats["reliability_stats"] = {
            "success_rate": (self.success_count / self.total_requests * 100) if self.total_requests > 0 else 0,
            "error_rate": self.error_rate,
            "throughput_rps": self.throughput
        }
        
        return stats
    
    def _percentile(self, data: List[float], percentile: float) -> float:
        """Calculate percentile"""
        if not data:
            return 0.0
        sorted_data = sorted(data)
        index = (percentile / 100) * (len(sorted_data) - 1)
        if index.is_integer():
            return sorted_data[int(index)]
        else:
            lower = sorted_data[int(index)]
            upper = sorted_data[int(index) + 1]
            return lower + (upper - lower) * (index - int(index))


@dataclass
class LoadTestConfig:
    """Load test configuration"""
    name: str
    description: str
    endpoint: str
    method: str = "GET"
    payload: Optional[Dict[str, Any]] = None
    concurrent_users: int = 10
    requests_per_user: int = 10
    ramp_up_time: int = 10  # seconds
    test_duration: int = 60  # seconds
    think_time: float = 1.0  # seconds between requests
    timeout: int = 30  # request timeout
    expected_response_time: float = 1.0  # seconds
    expected_throughput: float = 100.0  # requests per second
    expected_success_rate: float = 95.0  # percentage


@dataclass
class ReliabilityTestResult:
    """Reliability test result"""
    test_name: str
    test_type: str
    duration: float
    metrics: PerformanceMetrics
    statistics: Dict[str, Any]
    sla_compliance: Dict[str, bool]
    issues_detected: List[str]
    recommendations: List[str]
    success: bool
    timestamp: datetime = field(default_factory=datetime.now)


class SystemMonitor:
    """System resource monitoring"""
    
    def __init__(self, monitoring_interval: float = 1.0):
        self.monitoring_interval = monitoring_interval
        self.monitoring = False
        self.monitor_thread = None
        self.metrics_queue = queue.Queue()
        
    def start_monitoring(self):
        """Start system monitoring"""
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.monitor_thread.start()
        
    def stop_monitoring(self):
        """Stop system monitoring"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
    
    def _monitoring_loop(self):
        """System monitoring loop"""
        while self.monitoring:
            try:
                # CPU usage
                cpu_percent = psutil.cpu_percent(interval=None)
                
                # Memory usage
                memory = psutil.virtual_memory()
                memory_percent = memory.percent
                
                # Disk I/O
                disk_io = psutil.disk_io_counters()
                
                # Network I/O
                network_io = psutil.net_io_counters()
                
                metrics = {
                    "timestamp": time.time(),
                    "cpu_percent": cpu_percent,
                    "memory_percent": memory_percent,
                    "memory_used_gb": memory.used / (1024**3),
                    "disk_read_mb": disk_io.read_bytes / (1024**2) if disk_io else 0,
                    "disk_write_mb": disk_io.write_bytes / (1024**2) if disk_io else 0,
                    "network_sent_mb": network_io.bytes_sent / (1024**2) if network_io else 0,
                    "network_recv_mb": network_io.bytes_recv / (1024**2) if network_io else 0
                }
                
                self.metrics_queue.put(metrics)
                
            except Exception as e:
                logging.error(f"Error in system monitoring: {e}")
            
            time.sleep(self.monitoring_interval)
    
    def get_metrics(self) -> List[Dict[str, Any]]:
        """Get collected metrics"""
        metrics = []
        while not self.metrics_queue.empty():
            try:
                metric = self.metrics_queue.get_nowait()
                metrics.append(metric)
            except queue.Empty:
                break
        return metrics


class PerformanceReliabilityTester:
    """Comprehensive performance and reliability testing framework"""
    
    def __init__(self, base_url: str = "http://localhost:3560"):
        self.base_url = base_url
        self.logger = self._setup_logging()
        
        # Test components
        self.api_validator = APIIntegrationValidator(base_url=base_url)
        self.system_monitor = SystemMonitor()
        
        # Results storage
        self.test_results: List[ReliabilityTestResult] = []
        
        # Load test configurations
        self.load_test_configs = self._define_load_test_configs()
        
        # Performance thresholds
        self.performance_thresholds = {
            "max_response_time": 5.0,  # seconds
            "min_throughput": 10.0,    # requests per second
            "max_error_rate": 5.0,     # percentage
            "max_cpu_usage": 80.0,     # percentage
            "max_memory_usage": 80.0,  # percentage
        }
        
    def _setup_logging(self) -> logging.Logger:
        """Setup logging for performance tester"""
        logger = logging.getLogger("perf_tester")
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger
    
    def _define_load_test_configs(self) -> List[LoadTestConfig]:
        """Define load test configurations"""
        return [
            LoadTestConfig(
                name="api_health_check_load",
                description="Load test for health check endpoint",
                endpoint="/api/health",
                method="GET",
                concurrent_users=50,
                requests_per_user=20,
                test_duration=30,
                expected_response_time=0.5,
                expected_throughput=200.0,
                expected_success_rate=99.0
            ),
            
            LoadTestConfig(
                name="authentication_load",
                description="Load test for authentication endpoint",
                endpoint="/api/auth/login",
                method="POST",
                payload={"email": "test@example.com", "password": "test123"},
                concurrent_users=25,
                requests_per_user=10,
                test_duration=30,
                expected_response_time=1.0,
                expected_throughput=50.0,
                expected_success_rate=95.0
            ),
            
            LoadTestConfig(
                name="script_listing_load",
                description="Load test for script listing endpoint",
                endpoint="/api/scripts",
                method="GET",
                concurrent_users=30,
                requests_per_user=15,
                test_duration=45,
                expected_response_time=1.5,
                expected_throughput=75.0,
                expected_success_rate=98.0
            ),
            
            LoadTestConfig(
                name="script_execution_load",
                description="Load test for script execution endpoint",
                endpoint="/api/scripts/execute",
                method="POST",
                payload={"script_name": "test_script", "parameters": {}},
                concurrent_users=10,
                requests_per_user=5,
                test_duration=60,
                expected_response_time=3.0,
                expected_throughput=15.0,
                expected_success_rate=90.0
            ),
            
            LoadTestConfig(
                name="concurrent_mixed_load",
                description="Mixed load test with multiple endpoints",
                endpoint="/api/scripts",  # Will be varied during test
                method="GET",
                concurrent_users=50,
                requests_per_user=20,
                test_duration=120,
                expected_response_time=2.0,
                expected_throughput=100.0,
                expected_success_rate=95.0
            ),
            
            LoadTestConfig(
                name="stress_test",
                description="Stress test with high load",
                endpoint="/api/health",
                method="GET",
                concurrent_users=100,
                requests_per_user=50,
                test_duration=180,
                expected_response_time=5.0,
                expected_throughput=300.0,
                expected_success_rate=90.0
            )
        ]
    
    def setup_performance_environment(self) -> bool:
        """Setup performance testing environment"""
        self.logger.info("Setting up performance testing environment")
        
        try:
            # Authenticate API validator
            if not self.api_validator.authenticate():
                self.logger.warning("Authentication failed, some tests may fail")
            
            # Start system monitoring
            self.system_monitor.start_monitoring()
            
            # Warm up the system
            self._warmup_system()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to setup performance environment: {e}")
            return False
    
    def _warmup_system(self):
        """Warm up the system before testing"""
        self.logger.info("Warming up system")
        
        # Make some initial requests to warm up connections
        for _ in range(5):
            try:
                self.api_validator.test_api_endpoint("/api/health", auth_required=False)
                time.sleep(0.1)
            except:
                pass
    
    def execute_load_test(self, config: LoadTestConfig) -> ReliabilityTestResult:
        """Execute a single load test"""
        self.logger.info(f"Executing load test: {config.name}")
        
        start_time = time.time()
        metrics = PerformanceMetrics()
        issues = []
        
        # Clear system metrics
        self.system_monitor.get_metrics()  # Clear any existing metrics
        
        try:
            if config.name == "concurrent_mixed_load":
                result = self._execute_mixed_load_test(config, metrics)
            else:
                result = self._execute_single_endpoint_load_test(config, metrics)
            
        except Exception as e:
            self.logger.error(f"Load test {config.name} failed: {e}")
            issues.append(f"Test execution failed: {e}")
            result = False
        
        duration = time.time() - start_time
        
        # Collect system metrics
        system_metrics = self.system_monitor.get_metrics()
        if system_metrics:
            metrics.cpu_usage = [m["cpu_percent"] for m in system_metrics]
            metrics.memory_usage = [m["memory_percent"] for m in system_metrics]
            
            # Check for resource issues
            if max(metrics.cpu_usage) > self.performance_thresholds["max_cpu_usage"]:
                issues.append(f"High CPU usage detected: {max(metrics.cpu_usage):.1f}%")
            
            if max(metrics.memory_usage) > self.performance_thresholds["max_memory_usage"]:
                issues.append(f"High memory usage detected: {max(metrics.memory_usage):.1f}%")
        
        # Calculate statistics
        statistics = metrics.calculate_statistics()
        
        # Check SLA compliance
        sla_compliance = self._check_sla_compliance(config, statistics)
        
        # Generate recommendations
        recommendations = self._generate_performance_recommendations(config, statistics, issues)
        
        # Determine overall success
        success = (
            result and
            len(issues) == 0 and
            all(sla_compliance.values())
        )
        
        test_result = ReliabilityTestResult(
            test_name=config.name,
            test_type="load_test",
            duration=duration,
            metrics=metrics,
            statistics=statistics,
            sla_compliance=sla_compliance,
            issues_detected=issues,
            recommendations=recommendations,
            success=success
        )
        
        self.test_results.append(test_result)
        
        return test_result
    
    def _execute_single_endpoint_load_test(self, config: LoadTestConfig, metrics: PerformanceMetrics) -> bool:
        """Execute load test for single endpoint"""
        
        def user_simulation(user_id: int, results_queue: queue.Queue):
            """Simulate a single user's requests"""
            user_results = []
            
            for request_num in range(config.requests_per_user):
                start_time = time.time()
                
                try:
                    if config.method == "GET":
                        result = self.api_validator.test_api_endpoint(
                            config.endpoint,
                            config.method,
                            auth_required=(config.endpoint != "/api/health")
                        )
                    else:
                        result = self.api_validator.test_api_endpoint(
                            config.endpoint,
                            config.method,
                            config.payload,
                            auth_required=(config.endpoint != "/api/auth/login")
                        )
                    
                    response_time = time.time() - start_time
                    
                    user_results.append({
                        "user_id": user_id,
                        "request_num": request_num,
                        "response_time": response_time,
                        "success": result.success,
                        "status_code": result.status_code,
                        "error": result.error_message
                    })
                    
                except Exception as e:
                    response_time = time.time() - start_time
                    user_results.append({
                        "user_id": user_id,
                        "request_num": request_num,
                        "response_time": response_time,
                        "success": False,
                        "status_code": 0,
                        "error": str(e)
                    })
                
                # Think time between requests
                if request_num < config.requests_per_user - 1:
                    time.sleep(config.think_time)
            
            results_queue.put(user_results)
        
        # Execute concurrent users
        results_queue = queue.Queue()
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=config.concurrent_users) as executor:
            # Ramp up users gradually
            futures = []
            for user_id in range(config.concurrent_users):
                future = executor.submit(user_simulation, user_id, results_queue)
                futures.append(future)
                
                # Ramp up delay
                if config.ramp_up_time > 0:
                    time.sleep(config.ramp_up_time / config.concurrent_users)
            
            # Wait for all users to complete
            test_start_time = time.time()
            completed_futures = 0
            
            for future in concurrent.futures.as_completed(futures, timeout=config.test_duration + 60):
                try:
                    future.result()
                    completed_futures += 1
                except Exception as e:
                    self.logger.error(f"User simulation failed: {e}")
        
        # Collect results
        all_results = []
        while not results_queue.empty():
            try:
                user_results = results_queue.get_nowait()
                all_results.extend(user_results)
            except queue.Empty:
                break
        
        # Process results into metrics
        metrics.total_requests = len(all_results)
        metrics.success_count = sum(1 for r in all_results if r["success"])
        metrics.error_count = metrics.total_requests - metrics.success_count
        metrics.error_rate = (metrics.error_count / metrics.total_requests * 100) if metrics.total_requests > 0 else 0
        metrics.response_times = [r["response_time"] for r in all_results]
        
        # Calculate throughput
        if all_results:
            test_duration = max(time.time() - test_start_time, 1.0)
            metrics.throughput = metrics.total_requests / test_duration
        
        return True
    
    def _execute_mixed_load_test(self, config: LoadTestConfig, metrics: PerformanceMetrics) -> bool:
        """Execute mixed load test with multiple endpoints"""
        
        endpoints = [
            ("/api/health", "GET", None, False),
            ("/api/scripts", "GET", None, True),
            ("/api/sync/history", "GET", None, True),
            ("/api/jobs", "GET", None, True),
        ]
        
        def mixed_user_simulation(user_id: int, results_queue: queue.Queue):
            """Simulate user making requests to different endpoints"""
            user_results = []
            
            for request_num in range(config.requests_per_user):
                # Select random endpoint
                endpoint, method, payload, auth_required = endpoints[request_num % len(endpoints)]
                
                start_time = time.time()
                
                try:
                    result = self.api_validator.test_api_endpoint(
                        endpoint,
                        method,
                        payload,
                        auth_required=auth_required
                    )
                    
                    response_time = time.time() - start_time
                    
                    user_results.append({
                        "user_id": user_id,
                        "request_num": request_num,
                        "endpoint": endpoint,
                        "response_time": response_time,
                        "success": result.success,
                        "status_code": result.status_code,
                        "error": result.error_message
                    })
                    
                except Exception as e:
                    response_time = time.time() - start_time
                    user_results.append({
                        "user_id": user_id,
                        "request_num": request_num,
                        "endpoint": endpoint,
                        "response_time": response_time,
                        "success": False,
                        "status_code": 0,
                        "error": str(e)
                    })
                
                time.sleep(config.think_time)
            
            results_queue.put(user_results)
        
        # Execute mixed load test
        results_queue = queue.Queue()
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=config.concurrent_users) as executor:
            futures = []
            test_start_time = time.time()
            
            for user_id in range(config.concurrent_users):
                future = executor.submit(mixed_user_simulation, user_id, results_queue)
                futures.append(future)
                
                # Ramp up delay
                if config.ramp_up_time > 0:
                    time.sleep(config.ramp_up_time / config.concurrent_users)
            
            # Wait for completion
            for future in concurrent.futures.as_completed(futures, timeout=config.test_duration + 60):
                try:
                    future.result()
                except Exception as e:
                    self.logger.error(f"Mixed user simulation failed: {e}")
        
        # Process results
        all_results = []
        while not results_queue.empty():
            try:
                user_results = results_queue.get_nowait()
                all_results.extend(user_results)
            except queue.Empty:
                break
        
        # Update metrics
        metrics.total_requests = len(all_results)
        metrics.success_count = sum(1 for r in all_results if r["success"])
        metrics.error_count = metrics.total_requests - metrics.success_count
        metrics.error_rate = (metrics.error_count / metrics.total_requests * 100) if metrics.total_requests > 0 else 0
        metrics.response_times = [r["response_time"] for r in all_results]
        
        if all_results:
            test_duration = max(time.time() - test_start_time, 1.0)
            metrics.throughput = metrics.total_requests / test_duration
        
        return True
    
    def _check_sla_compliance(self, config: LoadTestConfig, statistics: Dict[str, Any]) -> Dict[str, bool]:
        """Check SLA compliance against expectations"""
        compliance = {}
        
        response_stats = statistics.get("response_time_stats", {})
        reliability_stats = statistics.get("reliability_stats", {})
        
        # Response time compliance
        if response_stats:
            mean_response_time = response_stats.get("mean", float('inf'))
            compliance["response_time"] = mean_response_time <= config.expected_response_time
            
            p95_response_time = response_stats.get("p95", float('inf'))
            compliance["p95_response_time"] = p95_response_time <= (config.expected_response_time * 2)
        else:
            compliance["response_time"] = False
            compliance["p95_response_time"] = False
        
        # Throughput compliance
        actual_throughput = reliability_stats.get("throughput_rps", 0)
        compliance["throughput"] = actual_throughput >= config.expected_throughput
        
        # Success rate compliance
        actual_success_rate = reliability_stats.get("success_rate", 0)
        compliance["success_rate"] = actual_success_rate >= config.expected_success_rate
        
        # Error rate compliance
        actual_error_rate = reliability_stats.get("error_rate", 100)
        compliance["error_rate"] = actual_error_rate <= (100 - config.expected_success_rate)
        
        return compliance
    
    def _generate_performance_recommendations(self, config: LoadTestConfig, statistics: Dict[str, Any], issues: List[str]) -> List[str]:
        """Generate performance recommendations"""
        recommendations = []
        
        response_stats = statistics.get("response_time_stats", {})
        reliability_stats = statistics.get("reliability_stats", {})
        cpu_stats = statistics.get("cpu_stats", {})
        memory_stats = statistics.get("memory_stats", {})
        
        # Response time recommendations
        if response_stats:
            mean_response_time = response_stats.get("mean", 0)
            if mean_response_time > config.expected_response_time:
                recommendations.append(f"Response time ({mean_response_time:.2f}s) exceeds target ({config.expected_response_time}s) - optimize endpoint performance")
            
            p95_response_time = response_stats.get("p95", 0)
            if p95_response_time > config.expected_response_time * 3:
                recommendations.append(f"High P95 response time ({p95_response_time:.2f}s) indicates performance inconsistency")
        
        # Throughput recommendations
        actual_throughput = reliability_stats.get("throughput_rps", 0)
        if actual_throughput < config.expected_throughput:
            recommendations.append(f"Throughput ({actual_throughput:.1f} RPS) below target ({config.expected_throughput} RPS) - consider scaling or optimization")
        
        # Error rate recommendations
        actual_error_rate = reliability_stats.get("error_rate", 0)
        if actual_error_rate > 5.0:
            recommendations.append(f"High error rate ({actual_error_rate:.1f}%) indicates system stress or bugs")
        
        # Resource recommendations
        if cpu_stats:
            max_cpu = cpu_stats.get("max", 0)
            if max_cpu > 90:
                recommendations.append(f"Very high CPU usage ({max_cpu:.1f}%) - consider CPU optimization or scaling")
            elif max_cpu > 70:
                recommendations.append(f"High CPU usage ({max_cpu:.1f}%) - monitor for potential bottlenecks")
        
        if memory_stats:
            max_memory = memory_stats.get("max", 0)
            if max_memory > 85:
                recommendations.append(f"High memory usage ({max_memory:.1f}%) - check for memory leaks or optimize memory usage")
        
        # Specific test recommendations
        if config.name == "stress_test" and len(issues) == 0:
            recommendations.append("System handled stress test well - good resilience characteristics")
        
        if not recommendations:
            recommendations.append("Performance metrics within acceptable ranges")
        
        return recommendations
    
    def execute_reliability_tests(self) -> List[ReliabilityTestResult]:
        """Execute reliability-specific tests"""
        self.logger.info("Executing reliability tests")
        
        reliability_tests = [
            self._test_system_stability,
            self._test_memory_leak_detection,
            self._test_connection_handling,
            self._test_graceful_degradation,
            self._test_recovery_time
        ]
        
        results = []
        
        for test_func in reliability_tests:
            try:
                result = test_func()
                results.append(result)
                self.test_results.append(result)
            except Exception as e:
                self.logger.error(f"Reliability test {test_func.__name__} failed: {e}")
                # Create error result
                error_result = ReliabilityTestResult(
                    test_name=test_func.__name__,
                    test_type="reliability",
                    duration=0.0,
                    metrics=PerformanceMetrics(),
                    statistics={},
                    sla_compliance={},
                    issues_detected=[str(e)],
                    recommendations=["Test execution failed - investigate test framework"],
                    success=False
                )
                results.append(error_result)
                self.test_results.append(error_result)
        
        return results
    
    def _test_system_stability(self) -> ReliabilityTestResult:
        """Test system stability over extended period"""
        self.logger.info("Testing system stability")
        
        start_time = time.time()
        metrics = PerformanceMetrics()
        issues = []
        
        # Run steady load for extended period
        test_duration = 300  # 5 minutes
        request_interval = 2   # seconds
        
        end_time = start_time + test_duration
        
        while time.time() < end_time:
            try:
                request_start = time.time()
                result = self.api_validator.test_api_endpoint("/api/health", auth_required=False)
                response_time = time.time() - request_start
                
                metrics.response_times.append(response_time)
                metrics.total_requests += 1
                
                if result.success:
                    metrics.success_count += 1
                else:
                    metrics.error_count += 1
                    issues.append(f"Request failed at {time.time() - start_time:.1f}s: {result.error_message}")
                
                time.sleep(request_interval)
                
            except Exception as e:
                issues.append(f"Exception at {time.time() - start_time:.1f}s: {e}")
                metrics.error_count += 1
                metrics.total_requests += 1
        
        duration = time.time() - start_time
        
        # Calculate metrics
        if metrics.total_requests > 0:
            metrics.error_rate = metrics.error_count / metrics.total_requests * 100
            metrics.throughput = metrics.total_requests / duration
        
        statistics = metrics.calculate_statistics()
        
        # Check stability criteria
        sla_compliance = {
            "stability": len(issues) < 5,  # Less than 5 issues over test period
            "consistent_performance": (
                statistics.get("response_time_stats", {}).get("std_dev", float('inf')) < 1.0
            ),
            "error_rate": metrics.error_rate < 5.0
        }
        
        recommendations = []
        if not sla_compliance["stability"]:
            recommendations.append("System stability issues detected - investigate error patterns")
        if not sla_compliance["consistent_performance"]:
            recommendations.append("Inconsistent performance detected - check for resource contention")
        if not sla_compliance["error_rate"]:
            recommendations.append("High error rate indicates reliability issues")
        
        if not recommendations:
            recommendations.append("System demonstrates good stability characteristics")
        
        return ReliabilityTestResult(
            test_name="system_stability",
            test_type="reliability",
            duration=duration,
            metrics=metrics,
            statistics=statistics,
            sla_compliance=sla_compliance,
            issues_detected=issues,
            recommendations=recommendations,
            success=all(sla_compliance.values())
        )
    
    def _test_memory_leak_detection(self) -> ReliabilityTestResult:
        """Test for memory leaks during operation"""
        self.logger.info("Testing memory leak detection")
        
        start_time = time.time()
        metrics = PerformanceMetrics()
        issues = []
        
        # Monitor memory usage during sustained operation
        initial_memory = psutil.virtual_memory().used
        memory_samples = [initial_memory]
        
        # Run requests while monitoring memory
        for i in range(100):
            try:
                result = self.api_validator.test_api_endpoint("/api/scripts", "GET")
                metrics.total_requests += 1
                
                if result.success:
                    metrics.success_count += 1
                else:
                    metrics.error_count += 1
                
                # Sample memory every 10 requests
                if i % 10 == 0:
                    current_memory = psutil.virtual_memory().used
                    memory_samples.append(current_memory)
                    metrics.memory_usage.append(current_memory / (1024**3))  # GB
                
                time.sleep(0.1)
                
            except Exception as e:
                issues.append(f"Request {i} failed: {e}")
                metrics.error_count += 1
                metrics.total_requests += 1
        
        # Force garbage collection
        gc.collect()
        final_memory = psutil.virtual_memory().used
        memory_samples.append(final_memory)
        
        duration = time.time() - start_time
        
        # Analyze memory growth
        memory_growth = final_memory - initial_memory
        memory_growth_mb = memory_growth / (1024**2)
        
        # Check for significant memory growth (more than 100MB)
        memory_leak_detected = memory_growth_mb > 100
        
        if memory_leak_detected:
            issues.append(f"Potential memory leak detected: {memory_growth_mb:.1f}MB growth")
        
        statistics = {
            "memory_growth_mb": memory_growth_mb,
            "initial_memory_gb": initial_memory / (1024**3),
            "final_memory_gb": final_memory / (1024**3),
            "memory_samples": len(memory_samples)
        }
        
        sla_compliance = {
            "no_memory_leak": not memory_leak_detected,
            "reasonable_growth": memory_growth_mb < 50
        }
        
        recommendations = []
        if memory_leak_detected:
            recommendations.append("Potential memory leak detected - investigate resource cleanup")
        elif memory_growth_mb > 10:
            recommendations.append("Moderate memory growth observed - monitor for trends")
        else:
            recommendations.append("Memory usage appears stable")
        
        return ReliabilityTestResult(
            test_name="memory_leak_detection",
            test_type="reliability",
            duration=duration,
            metrics=metrics,
            statistics=statistics,
            sla_compliance=sla_compliance,
            issues_detected=issues,
            recommendations=recommendations,
            success=all(sla_compliance.values())
        )
    
    def _test_connection_handling(self) -> ReliabilityTestResult:
        """Test connection handling and cleanup"""
        self.logger.info("Testing connection handling")
        
        start_time = time.time()
        metrics = PerformanceMetrics()
        issues = []
        
        # Test rapid connection creation and closure
        for i in range(50):
            try:
                # Create new API validator (new connection)
                temp_validator = APIIntegrationValidator(base_url=self.base_url)
                
                request_start = time.time()
                result = temp_validator.test_api_endpoint("/api/health", auth_required=False)
                response_time = time.time() - request_start
                
                metrics.response_times.append(response_time)
                metrics.total_requests += 1
                
                if result.success:
                    metrics.success_count += 1
                else:
                    metrics.error_count += 1
                    issues.append(f"Connection test {i} failed: {result.error_message}")
                
                # Clean up connection explicitly
                del temp_validator
                
            except Exception as e:
                issues.append(f"Connection test {i} exception: {e}")
                metrics.error_count += 1
                metrics.total_requests += 1
        
        duration = time.time() - start_time
        
        statistics = metrics.calculate_statistics()
        
        # Check connection handling
        connection_success_rate = metrics.success_count / metrics.total_requests * 100 if metrics.total_requests > 0 else 0
        
        sla_compliance = {
            "connection_success": connection_success_rate >= 95.0,
            "no_connection_leaks": len(issues) < 5,
            "response_time": statistics.get("response_time_stats", {}).get("mean", float('inf')) < 2.0
        }
        
        recommendations = []
        if not sla_compliance["connection_success"]:
            recommendations.append("Connection handling issues detected - check connection pooling")
        if not sla_compliance["no_connection_leaks"]:
            recommendations.append("Potential connection leaks detected")
        if not sla_compliance["response_time"]:
            recommendations.append("Slow connection handling - optimize connection setup")
        
        if not recommendations:
            recommendations.append("Connection handling appears robust")
        
        return ReliabilityTestResult(
            test_name="connection_handling",
            test_type="reliability",
            duration=duration,
            metrics=metrics,
            statistics=statistics,
            sla_compliance=sla_compliance,
            issues_detected=issues,
            recommendations=recommendations,
            success=all(sla_compliance.values())
        )
    
    def _test_graceful_degradation(self) -> ReliabilityTestResult:
        """Test graceful degradation under stress"""
        self.logger.info("Testing graceful degradation")
        
        start_time = time.time()
        metrics = PerformanceMetrics()
        issues = []
        
        # Gradually increase load to test degradation
        max_concurrent = 50
        step_size = 5
        step_duration = 10  # seconds per step
        
        for concurrent_level in range(step_size, max_concurrent + 1, step_size):
            self.logger.info(f"Testing with {concurrent_level} concurrent requests")
            
            step_start = time.time()
            step_results = []
            
            def make_request():
                try:
                    request_start = time.time()
                    result = self.api_validator.test_api_endpoint("/api/health", auth_required=False)
                    response_time = time.time() - request_start
                    return {
                        "success": result.success,
                        "response_time": response_time,
                        "error": result.error_message
                    }
                except Exception as e:
                    return {
                        "success": False,
                        "response_time": 0.0,
                        "error": str(e)
                    }
            
            # Run concurrent requests for this step
            while time.time() - step_start < step_duration:
                with concurrent.futures.ThreadPoolExecutor(max_workers=concurrent_level) as executor:
                    futures = [executor.submit(make_request) for _ in range(concurrent_level)]
                    
                    for future in concurrent.futures.as_completed(futures, timeout=5):
                        try:
                            result = future.result()
                            step_results.append(result)
                        except Exception as e:
                            step_results.append({
                                "success": False,
                                "response_time": 0.0,
                                "error": str(e)
                            })
                
                time.sleep(1)
            
            # Analyze step results
            step_success_rate = sum(1 for r in step_results if r["success"]) / len(step_results) * 100
            step_avg_response_time = sum(r["response_time"] for r in step_results) / len(step_results)
            
            self.logger.info(f"Level {concurrent_level}: {step_success_rate:.1f}% success, {step_avg_response_time:.2f}s avg response")
            
            # Update overall metrics
            metrics.total_requests += len(step_results)
            metrics.success_count += sum(1 for r in step_results if r["success"])
            metrics.error_count += sum(1 for r in step_results if not r["success"])
            metrics.response_times.extend([r["response_time"] for r in step_results])
            
            # Check for degradation issues
            if step_success_rate < 80:
                issues.append(f"Poor success rate ({step_success_rate:.1f}%) at concurrency level {concurrent_level}")
            
            if step_avg_response_time > 5.0:
                issues.append(f"High response time ({step_avg_response_time:.2f}s) at concurrency level {concurrent_level}")
        
        duration = time.time() - start_time
        
        statistics = metrics.calculate_statistics()
        
        # Check degradation characteristics
        overall_success_rate = metrics.success_count / metrics.total_requests * 100 if metrics.total_requests > 0 else 0
        
        sla_compliance = {
            "graceful_degradation": overall_success_rate >= 70.0,  # Should maintain reasonable success rate
            "manageable_response_times": statistics.get("response_time_stats", {}).get("p95", float('inf')) < 10.0,
            "system_stability": len(issues) < 5
        }
        
        recommendations = []
        if not sla_compliance["graceful_degradation"]:
            recommendations.append("System does not degrade gracefully under load - implement throttling")
        if not sla_compliance["manageable_response_times"]:
            recommendations.append("Response times become unacceptable under load - optimize performance")
        if not sla_compliance["system_stability"]:
            recommendations.append("System becomes unstable under load - improve error handling")
        
        if not recommendations:
            recommendations.append("System demonstrates good graceful degradation characteristics")
        
        return ReliabilityTestResult(
            test_name="graceful_degradation",
            test_type="reliability",
            duration=duration,
            metrics=metrics,
            statistics=statistics,
            sla_compliance=sla_compliance,
            issues_detected=issues,
            recommendations=recommendations,
            success=all(sla_compliance.values())
        )
    
    def _test_recovery_time(self) -> ReliabilityTestResult:
        """Test system recovery time after stress"""
        self.logger.info("Testing recovery time")
        
        start_time = time.time()
        metrics = PerformanceMetrics()
        issues = []
        
        # Step 1: Create stress condition
        stress_duration = 30  # seconds
        stress_concurrent = 50
        
        self.logger.info("Creating stress condition")
        stress_start = time.time()
        stress_results = []
        
        def stress_request():
            try:
                result = self.api_validator.test_api_endpoint("/api/health", auth_required=False)
                return result.success
            except:
                return False
        
        # Apply stress
        while time.time() - stress_start < stress_duration:
            with concurrent.futures.ThreadPoolExecutor(max_workers=stress_concurrent) as executor:
                futures = [executor.submit(stress_request) for _ in range(stress_concurrent)]
                for future in concurrent.futures.as_completed(futures, timeout=2):
                    try:
                        stress_results.append(future.result())
                    except:
                        stress_results.append(False)
            time.sleep(0.5)
        
        # Step 2: Measure recovery time
        self.logger.info("Measuring recovery time")
        recovery_start = time.time()
        recovery_achieved = False
        recovery_time = None
        
        # Test recovery with lighter load
        while time.time() - recovery_start < 60:  # Max 1 minute recovery time
            try:
                request_start = time.time()
                result = self.api_validator.test_api_endpoint("/api/health", auth_required=False)
                response_time = time.time() - request_start
                
                metrics.response_times.append(response_time)
                metrics.total_requests += 1
                
                if result.success:
                    metrics.success_count += 1
                    
                    # Check if recovery achieved (good response time)
                    if response_time < 1.0 and not recovery_achieved:
                        recovery_time = time.time() - recovery_start
                        recovery_achieved = True
                        self.logger.info(f"Recovery achieved in {recovery_time:.2f} seconds")
                        break
                else:
                    metrics.error_count += 1
                
                time.sleep(1)
                
            except Exception as e:
                issues.append(f"Recovery test error: {e}")
                metrics.error_count += 1
                metrics.total_requests += 1
        
        if not recovery_achieved:
            recovery_time = 60.0  # Max time
            issues.append("System did not recover within 60 seconds")
        
        duration = time.time() - start_time
        
        statistics = metrics.calculate_statistics()
        statistics["recovery_time_seconds"] = recovery_time
        
        # Check recovery criteria
        sla_compliance = {
            "fast_recovery": recovery_time and recovery_time < 30.0,  # Should recover within 30 seconds
            "complete_recovery": recovery_achieved,
            "stable_after_recovery": len(issues) < 3
        }
        
        recommendations = []
        if not sla_compliance["fast_recovery"]:
            recommendations.append(f"Slow recovery time ({recovery_time:.1f}s) - optimize recovery mechanisms")
        if not sla_compliance["complete_recovery"]:
            recommendations.append("System did not fully recover - investigate persistent issues")
        if not sla_compliance["stable_after_recovery"]:
            recommendations.append("System instability after stress - improve resilience")
        
        if not recommendations:
            recommendations.append("System demonstrates good recovery characteristics")
        
        return ReliabilityTestResult(
            test_name="recovery_time",
            test_type="reliability",
            duration=duration,
            metrics=metrics,
            statistics=statistics,
            sla_compliance=sla_compliance,
            issues_detected=issues,
            recommendations=recommendations,
            success=all(sla_compliance.values())
        )
    
    def run_comprehensive_performance_tests(self) -> Dict[str, Any]:
        """Run comprehensive performance and reliability tests"""
        self.logger.info("Starting comprehensive performance and reliability testing")
        
        if not self.setup_performance_environment():
            return {"error": "Failed to setup performance environment"}
        
        try:
            # Run load tests
            load_test_results = {}
            for config in self.load_test_configs:
                self.logger.info(f"Running load test: {config.name}")
                result = self.execute_load_test(config)
                load_test_results[config.name] = result
                
                # Short break between tests
                time.sleep(5)
            
            # Run reliability tests
            self.logger.info("Running reliability tests")
            reliability_results = self.execute_reliability_tests()
            
            # Generate comprehensive report
            return self._generate_comprehensive_report(load_test_results, reliability_results)
            
        finally:
            # Stop monitoring
            self.system_monitor.stop_monitoring()
    
    def _generate_comprehensive_report(self, load_results: Dict[str, ReliabilityTestResult], 
                                     reliability_results: List[ReliabilityTestResult]) -> Dict[str, Any]:
        """Generate comprehensive performance report"""
        
        # Calculate overall statistics
        all_tests = list(load_results.values()) + reliability_results
        total_tests = len(all_tests)
        successful_tests = sum(1 for test in all_tests if test.success)
        
        # Performance metrics summary
        all_response_times = []
        all_throughputs = []
        all_error_rates = []
        
        for test in all_tests:
            if test.metrics.response_times:
                all_response_times.extend(test.metrics.response_times)
            if test.metrics.throughput > 0:
                all_throughputs.append(test.metrics.throughput)
            if test.metrics.total_requests > 0:
                error_rate = test.metrics.error_count / test.metrics.total_requests * 100
                all_error_rates.append(error_rate)
        
        # Calculate overall performance statistics
        performance_summary = {
            "overall_success_rate": successful_tests / total_tests * 100 if total_tests > 0 else 0,
            "average_response_time": statistics.mean(all_response_times) if all_response_times else 0,
            "p95_response_time": self._percentile(all_response_times, 95) if all_response_times else 0,
            "average_throughput": statistics.mean(all_throughputs) if all_throughputs else 0,
            "average_error_rate": statistics.mean(all_error_rates) if all_error_rates else 0
        }
        
        # Categorize results
        load_test_summary = {
            "total_load_tests": len(load_results),
            "successful_load_tests": sum(1 for test in load_results.values() if test.success),
            "load_test_results": {name: asdict(result) for name, result in load_results.items()}
        }
        
        reliability_test_summary = {
            "total_reliability_tests": len(reliability_results),
            "successful_reliability_tests": sum(1 for test in reliability_results if test.success),
            "reliability_test_results": [asdict(result) for result in reliability_results]
        }
        
        # Generate overall recommendations
        overall_recommendations = self._generate_overall_recommendations(all_tests, performance_summary)
        
        # System assessment
        system_assessment = self._assess_system_performance(performance_summary, all_tests)
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "test_execution_summary": {
                "total_tests": total_tests,
                "successful_tests": successful_tests,
                "overall_success_rate": performance_summary["overall_success_rate"]
            },
            "performance_summary": performance_summary,
            "load_testing": load_test_summary,
            "reliability_testing": reliability_test_summary,
            "system_assessment": system_assessment,
            "recommendations": overall_recommendations,
            "performance_thresholds": self.performance_thresholds
        }
        
        return report
    
    def _percentile(self, data: List[float], percentile: float) -> float:
        """Calculate percentile"""
        if not data:
            return 0.0
        sorted_data = sorted(data)
        index = (percentile / 100) * (len(sorted_data) - 1)
        if index.is_integer():
            return sorted_data[int(index)]
        else:
            lower = sorted_data[int(index)]
            upper = sorted_data[int(index) + 1]
            return lower + (upper - lower) * (index - int(index))
    
    def _generate_overall_recommendations(self, all_tests: List[ReliabilityTestResult], 
                                        performance_summary: Dict[str, Any]) -> List[str]:
        """Generate overall system recommendations"""
        recommendations = []
        
        # Performance recommendations
        if performance_summary["average_response_time"] > 2.0:
            recommendations.append("Average response time is high - optimize critical endpoints")
        
        if performance_summary["p95_response_time"] > 5.0:
            recommendations.append("P95 response time indicates performance inconsistency - investigate outliers")
        
        if performance_summary["average_throughput"] < 50.0:
            recommendations.append("Low average throughput - consider scaling or performance optimization")
        
        if performance_summary["average_error_rate"] > 5.0:
            recommendations.append("High error rate indicates reliability issues - improve error handling")
        
        # Reliability recommendations
        failed_tests = [test for test in all_tests if not test.success]
        if len(failed_tests) > 0:
            recommendations.append(f"{len(failed_tests)} tests failed - review specific failure causes")
        
        # Pattern analysis
        load_failures = [test for test in all_tests if test.test_type == "load_test" and not test.success]
        if len(load_failures) > 0:
            recommendations.append("Load test failures indicate scalability issues")
        
        reliability_failures = [test for test in all_tests if test.test_type == "reliability" and not test.success]
        if len(reliability_failures) > 0:
            recommendations.append("Reliability test failures indicate system robustness issues")
        
        # Success case recommendations
        if performance_summary["overall_success_rate"] > 90:
            recommendations.append("System demonstrates good overall performance and reliability")
        
        if not recommendations:
            recommendations.append("No significant performance or reliability issues detected")
        
        return recommendations
    
    def _assess_system_performance(self, performance_summary: Dict[str, Any], 
                                 all_tests: List[ReliabilityTestResult]) -> Dict[str, Any]:
        """Assess overall system performance"""
        
        # Performance grade
        performance_score = 0
        
        # Response time scoring (30%)
        avg_response_time = performance_summary["average_response_time"]
        if avg_response_time < 0.5:
            performance_score += 30
        elif avg_response_time < 1.0:
            performance_score += 25
        elif avg_response_time < 2.0:
            performance_score += 20
        elif avg_response_time < 5.0:
            performance_score += 10
        
        # Throughput scoring (25%)
        avg_throughput = performance_summary["average_throughput"]
        if avg_throughput > 200:
            performance_score += 25
        elif avg_throughput > 100:
            performance_score += 20
        elif avg_throughput > 50:
            performance_score += 15
        elif avg_throughput > 20:
            performance_score += 10
        
        # Error rate scoring (25%)
        avg_error_rate = performance_summary["average_error_rate"]
        if avg_error_rate < 1.0:
            performance_score += 25
        elif avg_error_rate < 3.0:
            performance_score += 20
        elif avg_error_rate < 5.0:
            performance_score += 15
        elif avg_error_rate < 10.0:
            performance_score += 10
        
        # Reliability scoring (20%)
        reliability_score = performance_summary["overall_success_rate"] / 100 * 20
        performance_score += reliability_score
        
        # Grade assignment
        if performance_score >= 90:
            grade = "A"
            assessment = "Excellent"
        elif performance_score >= 80:
            grade = "B"
            assessment = "Good"
        elif performance_score >= 70:
            grade = "C"
            assessment = "Acceptable"
        elif performance_score >= 60:
            grade = "D"
            assessment = "Poor"
        else:
            grade = "F"
            assessment = "Unacceptable"
        
        return {
            "performance_score": performance_score,
            "performance_grade": grade,
            "assessment": assessment,
            "breakdown": {
                "response_time_component": min(30, max(0, 30 - (avg_response_time - 0.5) * 6)),
                "throughput_component": min(25, max(0, avg_throughput / 8)),
                "error_rate_component": min(25, max(0, 25 - avg_error_rate * 2.5)),
                "reliability_component": reliability_score
            },
            "ready_for_production": performance_score >= 70 and avg_error_rate < 5.0
        }
    
    def generate_performance_report(self, results: Dict[str, Any], output_file: str = None) -> str:
        """Generate performance test report file"""
        if output_file is None:
            output_file = f"performance_report_{int(time.time())}.json"
        
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        self.logger.info(f"Performance report generated: {output_file}")
        return output_file


def main():
    """Main CLI entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Performance and Reliability Tester")
    parser.add_argument('--base-url', default='http://localhost:3560',
                       help='Backend API base URL')
    parser.add_argument('--test-type', 
                       choices=['load', 'reliability', 'all'],
                       default='all',
                       help='Type of tests to run')
    parser.add_argument('--output', '-o', help='Output file for report')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Verbose logging')
    
    args = parser.parse_args()
    
    # Configure logging
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create tester
    tester = PerformanceReliabilityTester(base_url=args.base_url)
    
    try:
        if args.test_type == 'all':
            # Run comprehensive tests
            results = tester.run_comprehensive_performance_tests()
        else:
            # Run specific test type
            if not tester.setup_performance_environment():
                print("Failed to setup performance environment")
                sys.exit(1)
            
            if args.test_type == 'load':
                load_results = {}
                for config in tester.load_test_configs:
                    result = tester.execute_load_test(config)
                    load_results[config.name] = result
                
                results = {
                    "load_testing": {
                        "results": {name: asdict(result) for name, result in load_results.items()}
                    }
                }
            
            elif args.test_type == 'reliability':
                reliability_results = tester.execute_reliability_tests()
                results = {
                    "reliability_testing": {
                        "results": [asdict(result) for result in reliability_results]
                    }
                }
        
        # Generate report
        report_file = tester.generate_performance_report(results, args.output)
        
        # Print summary
        if 'performance_summary' in results:
            summary = results['performance_summary']
            assessment = results.get('system_assessment', {})
            
            print(f"""
Performance and Reliability Testing Complete!
=============================================
Overall Success Rate: {summary.get('overall_success_rate', 0):.1f}%
Average Response Time: {summary.get('average_response_time', 0):.2f}s
P95 Response Time: {summary.get('p95_response_time', 0):.2f}s
Average Throughput: {summary.get('average_throughput', 0):.1f} RPS
Average Error Rate: {summary.get('average_error_rate', 0):.1f}%

System Assessment: {assessment.get('assessment', 'Unknown')} (Grade: {assessment.get('performance_grade', 'N/A')})
Performance Score: {assessment.get('performance_score', 0):.1f}/100
Production Ready: {'Yes' if assessment.get('ready_for_production', False) else 'No'}

Report: {report_file}
            """)
        else:
            print(f"Testing completed. Report: {report_file}")
        
        # Exit with appropriate code based on results
        if 'system_assessment' in results:
            ready_for_production = results['system_assessment'].get('ready_for_production', False)
            sys.exit(0 if ready_for_production else 1)
        else:
            sys.exit(0)
        
    except KeyboardInterrupt:
        print("\nTesting interrupted by user")
        sys.exit(2)
    except Exception as e:
        print(f"Testing failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(3)
    finally:
        # Cleanup
        tester.system_monitor.stop_monitoring()


if __name__ == '__main__':
    main()