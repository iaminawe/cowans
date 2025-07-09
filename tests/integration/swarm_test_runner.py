#!/usr/bin/env python3
"""
SWARM Integration Test Runner

Comprehensive test execution and reporting system for SWARM integration testing.
Provides batch testing, detailed reporting, and system validation.
"""

import os
import sys
import time
import json
import argparse
import subprocess
import threading
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
import concurrent.futures
import logging
import unittest
import traceback

# Add parent directories to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from test_swarm_integration import (
    TestSPARCOrchestrationIntegration,
    TestMemoryCoordinationIntegration, 
    TestAPIIntegration,
    TestWebSocketIntegration,
    TestEndToEndWorkflow,
    TestPerformanceAndReliability,
    TestSystemMonitoring
)


@dataclass
class TestResult:
    """Test result data structure"""
    test_name: str
    test_class: str
    status: str  # 'passed', 'failed', 'error', 'skipped'
    duration: float
    error_message: Optional[str] = None
    traceback: Optional[str] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


@dataclass
class TestSuiteResult:
    """Test suite result data structure"""
    suite_name: str
    total_tests: int
    passed: int
    failed: int
    errors: int
    skipped: int
    duration: float
    timestamp: datetime
    test_results: List[TestResult]
    system_info: Dict[str, Any]
    coverage_report: Optional[Dict[str, Any]] = None


class SWARMTestRunner:
    """Advanced test runner for SWARM integration tests"""
    
    def __init__(self, output_dir: str = "./test_reports", parallel: bool = True, 
                 max_workers: int = 4, timeout: int = 300):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.parallel = parallel
        self.max_workers = max_workers
        self.timeout = timeout
        self.logger = self._setup_logging()
        
        # Test configuration
        self.test_suites = {
            "orchestration": TestSPARCOrchestrationIntegration,
            "memory": TestMemoryCoordinationIntegration,
            "api": TestAPIIntegration,
            "websocket": TestWebSocketIntegration,
            "e2e": TestEndToEndWorkflow,
            "performance": TestPerformanceAndReliability,
            "monitoring": TestSystemMonitoring
        }
        
        # System dependencies
        self.required_services = [
            "redis",
            "flask_app",
            "websocket_server"
        ]
        
    def _setup_logging(self) -> logging.Logger:
        """Setup logging for test runner"""
        logger = logging.getLogger("swarm_test_runner")
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            # Console handler
            console_handler = logging.StreamHandler()
            console_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            console_handler.setFormatter(console_formatter)
            logger.addHandler(console_handler)
            
            # File handler
            log_file = self.output_dir / "test_runner.log"
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(console_formatter)
            logger.addHandler(file_handler)
        
        return logger
    
    def check_system_requirements(self) -> Dict[str, bool]:
        """Check if required system components are available"""
        requirements = {}
        
        # Check Redis
        try:
            import redis
            client = redis.from_url("redis://localhost:6379/0")
            client.ping()
            requirements["redis"] = True
        except Exception as e:
            self.logger.warning(f"Redis not available: {e}")
            requirements["redis"] = False
        
        # Check Flask app components
        try:
            from web_dashboard.backend.app import app
            requirements["flask_app"] = True
        except Exception as e:
            self.logger.warning(f"Flask app not available: {e}")
            requirements["flask_app"] = False
        
        # Check SPARC orchestrator
        try:
            from scripts.orchestration.sparc_orchestrator import SPARCOrchestrator
            requirements["sparc_orchestrator"] = True
        except Exception as e:
            self.logger.warning(f"SPARC orchestrator not available: {e}")
            requirements["sparc_orchestrator"] = False
        
        # Check WebSocket server (optional)
        requirements["websocket_server"] = True  # Will be tested during execution
        
        return requirements
    
    def get_system_info(self) -> Dict[str, Any]:
        """Get system information for test report"""
        import platform
        import psutil
        
        return {
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "cpu_count": psutil.cpu_count(),
            "memory_gb": round(psutil.virtual_memory().total / (1024**3), 2),
            "disk_free_gb": round(psutil.disk_usage('.').free / (1024**3), 2),
            "timestamp": datetime.now().isoformat(),
            "requirements": self.check_system_requirements()
        }
    
    def run_single_test_class(self, test_class, test_name: str) -> List[TestResult]:
        """Run a single test class and return results"""
        results = []
        suite = unittest.TestLoader().loadTestsFromTestCase(test_class)
        
        for test in suite:
            test_method = test._testMethodName
            full_test_name = f"{test_name}.{test_method}"
            
            self.logger.info(f"Running test: {full_test_name}")
            start_time = time.time()
            
            # Create a test result to capture output
            result = unittest.TestResult()
            test(result)
            
            duration = time.time() - start_time
            
            # Determine test status
            if result.wasSuccessful():
                status = "passed"
                error_message = None
                tb = None
            elif result.failures:
                status = "failed"
                error_message = result.failures[0][1] if result.failures else "Unknown failure"
                tb = error_message  # Traceback is included in failure message
            elif result.errors:
                status = "error"
                error_message = result.errors[0][1] if result.errors else "Unknown error"
                tb = error_message
            elif result.skipped:
                status = "skipped"
                error_message = result.skipped[0][1] if result.skipped else "Test skipped"
                tb = None
            else:
                status = "unknown"
                error_message = "Unknown test state"
                tb = None
            
            test_result = TestResult(
                test_name=full_test_name,
                test_class=test_name,
                status=status,
                duration=duration,
                error_message=error_message,
                traceback=tb
            )
            
            results.append(test_result)
            
            self.logger.info(f"Test {full_test_name}: {status} ({duration:.2f}s)")
        
        return results
    
    def run_test_suite_parallel(self, suites: Dict[str, Any]) -> TestSuiteResult:
        """Run test suites in parallel"""
        all_results = []
        start_time = time.time()
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all test suites
            future_to_suite = {
                executor.submit(self.run_single_test_class, test_class, suite_name): suite_name
                for suite_name, test_class in suites.items()
            }
            
            # Collect results
            for future in concurrent.futures.as_completed(future_to_suite, timeout=self.timeout):
                suite_name = future_to_suite[future]
                try:
                    results = future.result()
                    all_results.extend(results)
                    self.logger.info(f"Completed test suite: {suite_name}")
                except Exception as e:
                    self.logger.error(f"Test suite {suite_name} failed: {e}")
                    # Create error result
                    error_result = TestResult(
                        test_name=f"{suite_name}.execution_error",
                        test_class=suite_name,
                        status="error",
                        duration=0.0,
                        error_message=str(e),
                        traceback=traceback.format_exc()
                    )
                    all_results.append(error_result)
        
        total_duration = time.time() - start_time
        
        # Calculate statistics
        passed = sum(1 for r in all_results if r.status == "passed")
        failed = sum(1 for r in all_results if r.status == "failed")
        errors = sum(1 for r in all_results if r.status == "error")
        skipped = sum(1 for r in all_results if r.status == "skipped")
        
        return TestSuiteResult(
            suite_name="SWARM Integration Tests",
            total_tests=len(all_results),
            passed=passed,
            failed=failed,
            errors=errors,
            skipped=skipped,
            duration=total_duration,
            timestamp=datetime.now(),
            test_results=all_results,
            system_info=self.get_system_info()
        )
    
    def run_test_suite_sequential(self, suites: Dict[str, Any]) -> TestSuiteResult:
        """Run test suites sequentially"""
        all_results = []
        start_time = time.time()
        
        for suite_name, test_class in suites.items():
            self.logger.info(f"Running test suite: {suite_name}")
            try:
                results = self.run_single_test_class(test_class, suite_name)
                all_results.extend(results)
            except Exception as e:
                self.logger.error(f"Test suite {suite_name} failed: {e}")
                error_result = TestResult(
                    test_name=f"{suite_name}.execution_error",
                    test_class=suite_name,
                    status="error",
                    duration=0.0,
                    error_message=str(e),
                    traceback=traceback.format_exc()
                )
                all_results.append(error_result)
        
        total_duration = time.time() - start_time
        
        # Calculate statistics
        passed = sum(1 for r in all_results if r.status == "passed")
        failed = sum(1 for r in all_results if r.status == "failed")
        errors = sum(1 for r in all_results if r.status == "error")
        skipped = sum(1 for r in all_results if r.status == "skipped")
        
        return TestSuiteResult(
            suite_name="SWARM Integration Tests",
            total_tests=len(all_results),
            passed=passed,
            failed=failed,
            errors=errors,
            skipped=skipped,
            duration=total_duration,
            timestamp=datetime.now(),
            test_results=all_results,
            system_info=self.get_system_info()
        )
    
    def generate_html_report(self, results: TestSuiteResult) -> Path:
        """Generate HTML test report"""
        html_template = """
<!DOCTYPE html>
<html>
<head>
    <title>SWARM Integration Test Report</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; }
        .header { background: #f5f5f5; padding: 20px; border-radius: 5px; margin-bottom: 20px; }
        .summary { display: flex; gap: 20px; margin-bottom: 20px; }
        .metric { background: white; padding: 15px; border-radius: 5px; border-left: 4px solid #007cba; }
        .passed { border-left-color: #28a745; }
        .failed { border-left-color: #dc3545; }
        .error { border-left-color: #ffc107; }
        .skipped { border-left-color: #6c757d; }
        .test-results { margin-top: 20px; }
        .test-item { padding: 10px; margin: 5px 0; border-radius: 3px; }
        .test-passed { background: #d4edda; }
        .test-failed { background: #f8d7da; }
        .test-error { background: #fff3cd; }
        .test-skipped { background: #e2e3e5; }
        .error-details { margin-top: 10px; padding: 10px; background: #f8f9fa; border-radius: 3px; font-family: monospace; font-size: 12px; }
        .system-info { margin-top: 30px; padding: 15px; background: #f8f9fa; border-radius: 5px; }
        .duration { color: #666; font-size: 12px; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        th, td { padding: 8px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background-color: #f2f2f2; }
    </style>
</head>
<body>
    <div class="header">
        <h1>SWARM Integration Test Report</h1>
        <p>Generated: {timestamp}</p>
        <p>Duration: {duration:.2f} seconds</p>
    </div>
    
    <div class="summary">
        <div class="metric">
            <h3>Total Tests</h3>
            <h2>{total_tests}</h2>
        </div>
        <div class="metric passed">
            <h3>Passed</h3>
            <h2>{passed}</h2>
        </div>
        <div class="metric failed">
            <h3>Failed</h3>
            <h2>{failed}</h2>
        </div>
        <div class="metric error">
            <h3>Errors</h3>
            <h2>{errors}</h2>
        </div>
        <div class="metric skipped">
            <h3>Skipped</h3>
            <h2>{skipped}</h2>
        </div>
    </div>
    
    <div class="test-results">
        <h2>Test Results</h2>
        {test_results_html}
    </div>
    
    <div class="system-info">
        <h2>System Information</h2>
        <table>
            <tr><th>Property</th><th>Value</th></tr>
            <tr><td>Platform</td><td>{platform}</td></tr>
            <tr><td>Python Version</td><td>{python_version}</td></tr>
            <tr><td>CPU Cores</td><td>{cpu_count}</td></tr>
            <tr><td>Memory (GB)</td><td>{memory_gb}</td></tr>
            <tr><td>Disk Free (GB)</td><td>{disk_free_gb}</td></tr>
        </table>
        
        <h3>Service Requirements</h3>
        <table>
            <tr><th>Service</th><th>Status</th></tr>
            {requirements_html}
        </table>
    </div>
</body>
</html>
        """
        
        # Generate test results HTML
        test_results_html = ""
        for test in results.test_results:
            status_class = f"test-{test.status}"
            error_html = ""
            if test.error_message:
                error_html = f'<div class="error-details"><strong>Error:</strong><br>{test.error_message}</div>'
            
            test_results_html += f"""
            <div class="test-item {status_class}">
                <strong>{test.test_name}</strong> 
                <span class="duration">({test.duration:.2f}s)</span>
                <span style="float: right; text-transform: uppercase; font-weight: bold;">{test.status}</span>
                {error_html}
            </div>
            """
        
        # Generate requirements HTML
        requirements_html = ""
        for service, status in results.system_info.get("requirements", {}).items():
            status_text = "✅ Available" if status else "❌ Not Available"
            requirements_html += f"<tr><td>{service}</td><td>{status_text}</td></tr>"
        
        # Fill template
        html_content = html_template.format(
            timestamp=results.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            duration=results.duration,
            total_tests=results.total_tests,
            passed=results.passed,
            failed=results.failed,
            errors=results.errors,
            skipped=results.skipped,
            test_results_html=test_results_html,
            platform=results.system_info.get("platform", "Unknown"),
            python_version=results.system_info.get("python_version", "Unknown"),
            cpu_count=results.system_info.get("cpu_count", "Unknown"),
            memory_gb=results.system_info.get("memory_gb", "Unknown"),
            disk_free_gb=results.system_info.get("disk_free_gb", "Unknown"),
            requirements_html=requirements_html
        )
        
        # Write HTML file
        html_file = self.output_dir / f"test_report_{int(time.time())}.html"
        html_file.write_text(html_content)
        
        self.logger.info(f"HTML report generated: {html_file}")
        return html_file
    
    def generate_json_report(self, results: TestSuiteResult) -> Path:
        """Generate JSON test report"""
        json_data = asdict(results)
        
        # Convert datetime objects to strings
        json_data["timestamp"] = json_data["timestamp"].isoformat()
        for test_result in json_data["test_results"]:
            test_result["timestamp"] = test_result["timestamp"].isoformat()
        
        json_file = self.output_dir / f"test_report_{int(time.time())}.json"
        with open(json_file, 'w') as f:
            json.dump(json_data, f, indent=2, default=str)
        
        self.logger.info(f"JSON report generated: {json_file}")
        return json_file
    
    def generate_junit_xml(self, results: TestSuiteResult) -> Path:
        """Generate JUnit XML report for CI/CD integration"""
        xml_template = """<?xml version="1.0" encoding="UTF-8"?>
<testsuites name="SWARM Integration Tests" tests="{total_tests}" failures="{failed}" errors="{errors}" time="{duration:.2f}">
    <testsuite name="{suite_name}" tests="{total_tests}" failures="{failed}" errors="{errors}" skipped="{skipped}" time="{duration:.2f}">
        {test_cases}
    </testsuite>
</testsuites>"""
        
        test_cases_xml = ""
        for test in results.test_results:
            failure_xml = ""
            if test.status == "failed" and test.error_message:
                failure_xml = f'<failure message="Test failed">{test.error_message}</failure>'
            elif test.status == "error" and test.error_message:
                failure_xml = f'<error message="Test error">{test.error_message}</error>'
            elif test.status == "skipped":
                failure_xml = '<skipped/>'
            
            test_cases_xml += f"""
        <testcase classname="{test.test_class}" name="{test.test_name}" time="{test.duration:.2f}">
            {failure_xml}
        </testcase>"""
        
        xml_content = xml_template.format(
            total_tests=results.total_tests,
            failed=results.failed,
            errors=results.errors,
            skipped=results.skipped,
            duration=results.duration,
            suite_name=results.suite_name,
            test_cases=test_cases_xml
        )
        
        xml_file = self.output_dir / f"junit_report_{int(time.time())}.xml"
        xml_file.write_text(xml_content)
        
        self.logger.info(f"JUnit XML report generated: {xml_file}")
        return xml_file
    
    def run_all_tests(self, suites: Optional[List[str]] = None) -> TestSuiteResult:
        """Run all or specified test suites"""
        self.logger.info("Starting SWARM integration test execution")
        
        # Check system requirements
        requirements = self.check_system_requirements()
        missing_requirements = [k for k, v in requirements.items() if not v]
        if missing_requirements:
            self.logger.warning(f"Missing requirements: {missing_requirements}")
        
        # Filter test suites if specified
        if suites:
            filtered_suites = {k: v for k, v in self.test_suites.items() if k in suites}
        else:
            filtered_suites = self.test_suites
        
        self.logger.info(f"Running {len(filtered_suites)} test suites")
        
        # Run tests
        if self.parallel and len(filtered_suites) > 1:
            self.logger.info("Running tests in parallel")
            results = self.run_test_suite_parallel(filtered_suites)
        else:
            self.logger.info("Running tests sequentially")
            results = self.run_test_suite_sequential(filtered_suites)
        
        # Generate reports
        self.logger.info("Generating test reports")
        html_file = self.generate_html_report(results)
        json_file = self.generate_json_report(results)
        junit_file = self.generate_junit_xml(results)
        
        # Print summary
        success_rate = (results.passed / results.total_tests * 100) if results.total_tests > 0 else 0
        self.logger.info(f"""
Test Execution Complete!
========================
Total Tests: {results.total_tests}
Passed: {results.passed}
Failed: {results.failed}
Errors: {results.errors}
Skipped: {results.skipped}
Success Rate: {success_rate:.1f}%
Duration: {results.duration:.2f} seconds

Reports generated:
- HTML: {html_file}
- JSON: {json_file}
- JUnit: {junit_file}
        """)
        
        return results


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(description="SWARM Integration Test Runner")
    parser.add_argument('--output-dir', '-o', default='./test_reports', 
                       help='Output directory for test reports')
    parser.add_argument('--parallel', '-p', action='store_true', default=True,
                       help='Run tests in parallel (default: True)')
    parser.add_argument('--sequential', '-s', action='store_true',
                       help='Run tests sequentially')
    parser.add_argument('--max-workers', '-w', type=int, default=4,
                       help='Maximum parallel workers (default: 4)')
    parser.add_argument('--timeout', '-t', type=int, default=300,
                       help='Test timeout in seconds (default: 300)')
    parser.add_argument('--suites', nargs='+', 
                       choices=['orchestration', 'memory', 'api', 'websocket', 'e2e', 'performance', 'monitoring'],
                       help='Specific test suites to run')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Verbose logging')
    
    args = parser.parse_args()
    
    # Configure logging
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create test runner
    runner = SWARMTestRunner(
        output_dir=args.output_dir,
        parallel=args.parallel and not args.sequential,
        max_workers=args.max_workers,
        timeout=args.timeout
    )
    
    try:
        # Run tests
        results = runner.run_all_tests(args.suites)
        
        # Exit with appropriate code
        if results.failed > 0 or results.errors > 0:
            sys.exit(1)
        else:
            sys.exit(0)
            
    except KeyboardInterrupt:
        print("\nTest execution interrupted by user")
        sys.exit(2)
    except Exception as e:
        print(f"Test execution failed: {e}")
        traceback.print_exc()
        sys.exit(3)


if __name__ == '__main__':
    main()