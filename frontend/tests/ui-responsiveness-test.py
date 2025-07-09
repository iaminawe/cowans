#!/usr/bin/env python3
"""
UI Responsiveness Test for Icon Generation

Tests the UI's ability to handle:
- Concurrent icon generation
- Progress updates via WebSocket
- Multiple simultaneous API calls
- Error recovery
"""

import asyncio
import aiohttp
import time
import json
import websockets
from datetime import datetime
from typing import Dict, List, Any
import statistics

# Configuration
BASE_URL = "http://localhost:5001"
API_URL = f"{BASE_URL}/api"
WS_URL = "ws://localhost:5001/ws"

class UIResponsivenessTest:
    """Test suite for UI responsiveness during icon operations."""
    
    def __init__(self):
        self.response_times: Dict[str, List[float]] = {
            "api_calls": [],
            "ws_messages": [],
            "generation_requests": []
        }
        self.ws_messages: List[Dict[str, Any]] = []
        self.test_results: Dict[str, Any] = {}
        
    async def run_all_tests(self):
        """Execute all responsiveness tests."""
        print("🚀 UI Responsiveness Test Suite")
        print("=" * 60)
        
        # Test 1: Concurrent API calls
        await self.test_concurrent_api_calls()
        
        # Test 2: WebSocket responsiveness
        await self.test_websocket_updates()
        
        # Test 3: Simultaneous generation requests
        await self.test_simultaneous_generations()
        
        # Test 4: Error recovery
        await self.test_error_recovery()
        
        # Test 5: Heavy load test
        await self.test_heavy_load()
        
        # Generate report
        self.generate_report()
    
    async def test_concurrent_api_calls(self):
        """Test API responsiveness under concurrent load."""
        print("\n📊 Test 1: Concurrent API Calls")
        print("-" * 40)
        
        endpoints = [
            "/icons/stats",
            "/icons/cached",
            "/icons/batches", 
            "/icons/categories/suggestions?q=test",
            "/health"
        ]
        
        # Make 5 rounds of concurrent calls
        for round in range(5):
            start_time = time.time()
            
            async def make_call(endpoint: str):
                call_start = time.time()
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(f"{API_URL}{endpoint}") as resp:
                            await resp.json()
                            call_time = time.time() - call_start
                            self.response_times["api_calls"].append(call_time)
                            return resp.status, call_time
                except Exception as e:
                    return None, time.time() - call_start
            
            # Execute all calls concurrently
            tasks = [make_call(endpoint) for endpoint in endpoints]
            results = await asyncio.gather(*tasks)
            
            round_time = time.time() - start_time
            successful = sum(1 for r in results if r[0] == 200)
            
            print(f"  Round {round + 1}: {successful}/{len(endpoints)} successful, "
                  f"Total time: {round_time:.3f}s")
        
        # Analyze results
        if self.response_times["api_calls"]:
            avg_response = statistics.mean(self.response_times["api_calls"])
            max_response = max(self.response_times["api_calls"])
            p95_response = statistics.quantiles(self.response_times["api_calls"], n=20)[18]
            
            print(f"\n  Average response time: {avg_response:.3f}s")
            print(f"  Max response time: {max_response:.3f}s")
            print(f"  95th percentile: {p95_response:.3f}s")
            
            self.test_results["concurrent_api"] = {
                "avg_response": avg_response,
                "max_response": max_response,
                "p95_response": p95_response,
                "passed": p95_response < 1.0  # 1 second threshold for 95th percentile
            }
    
    async def test_websocket_updates(self):
        """Test WebSocket message delivery and latency."""
        print("\n🔌 Test 2: WebSocket Responsiveness")
        print("-" * 40)
        
        messages_received = 0
        latencies = []
        
        try:
            async with websockets.connect(WS_URL) as websocket:
                # Start a batch generation to trigger updates
                batch_id = await self.start_test_batch()
                
                if not batch_id:
                    print("  ❌ Failed to start test batch")
                    self.test_results["websocket"] = {"passed": False, "error": "No batch started"}
                    return
                
                print(f"  Started batch: {batch_id}")
                print("  Monitoring WebSocket updates...")
                
                start_time = time.time()
                timeout = 30  # 30 second timeout
                
                while time.time() - start_time < timeout:
                    try:
                        message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                        received_time = time.time()
                        
                        data = json.loads(message)
                        messages_received += 1
                        
                        # Calculate latency if timestamp is included
                        if "timestamp" in data:
                            sent_time = data["timestamp"]
                            latency = received_time - sent_time
                            latencies.append(latency)
                        
                        self.ws_messages.append(data)
                        
                        if data.get("type") == "batch_progress":
                            print(f"  Progress update: {data.get('progress', 0)}%")
                            
                            if data.get("status") == "completed":
                                break
                                
                    except asyncio.TimeoutError:
                        continue
                    except Exception as e:
                        print(f"  WebSocket error: {e}")
                
                print(f"\n  Messages received: {messages_received}")
                
                if latencies:
                    avg_latency = statistics.mean(latencies)
                    print(f"  Average latency: {avg_latency * 1000:.1f}ms")
                    
                    self.test_results["websocket"] = {
                        "messages_received": messages_received,
                        "avg_latency_ms": avg_latency * 1000,
                        "passed": messages_received > 0 and avg_latency < 0.1  # 100ms threshold
                    }
                else:
                    self.test_results["websocket"] = {
                        "messages_received": messages_received,
                        "passed": messages_received > 0
                    }
                    
        except Exception as e:
            print(f"  ❌ WebSocket connection failed: {e}")
            self.test_results["websocket"] = {"passed": False, "error": str(e)}
    
    async def test_simultaneous_generations(self):
        """Test UI handling of multiple simultaneous generation requests."""
        print("\n🎨 Test 3: Simultaneous Generation Requests")
        print("-" * 40)
        
        num_requests = 5
        categories = [f"Test Category {i+1}" for i in range(num_requests)]
        
        async def generate_icon(category: str):
            start_time = time.time()
            try:
                async with aiohttp.ClientSession() as session:
                    payload = {
                        "category": category,
                        "style": "modern",
                        "color_scheme": "brand_colors"
                    }
                    
                    async with session.post(f"{API_URL}/icons/generate", json=payload) as resp:
                        response_time = time.time() - start_time
                        self.response_times["generation_requests"].append(response_time)
                        
                        if resp.status == 200:
                            data = await resp.json()
                            return data.get("success", False), response_time
                        else:
                            return False, response_time
                            
            except Exception as e:
                response_time = time.time() - start_time
                self.response_times["generation_requests"].append(response_time)
                return False, response_time
        
        print(f"  Starting {num_requests} simultaneous generations...")
        start_time = time.time()
        
        # Execute all generations concurrently
        tasks = [generate_icon(cat) for cat in categories]
        results = await asyncio.gather(*tasks)
        
        total_time = time.time() - start_time
        successful = sum(1 for r in results if r[0])
        
        print(f"  Completed: {successful}/{num_requests} successful")
        print(f"  Total time: {total_time:.2f}s")
        
        if self.response_times["generation_requests"]:
            avg_time = statistics.mean(self.response_times["generation_requests"])
            print(f"  Average generation time: {avg_time:.2f}s")
            
            self.test_results["simultaneous_generation"] = {
                "num_requests": num_requests,
                "successful": successful,
                "total_time": total_time,
                "avg_time": avg_time,
                "passed": successful >= num_requests * 0.8  # 80% success rate
            }
    
    async def test_error_recovery(self):
        """Test UI's ability to handle and recover from errors."""
        print("\n🔧 Test 4: Error Recovery")
        print("-" * 40)
        
        error_scenarios = [
            {
                "name": "Invalid category",
                "payload": {"category": "", "style": "modern", "color_scheme": "brand_colors"}
            },
            {
                "name": "Invalid style",
                "payload": {"category": "Test", "style": "invalid_style", "color_scheme": "brand_colors"}
            },
            {
                "name": "Missing parameters",
                "payload": {"category": "Test"}
            }
        ]
        
        recovery_times = []
        
        for scenario in error_scenarios:
            print(f"  Testing: {scenario['name']}")
            
            # Send invalid request
            start_time = time.time()
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(f"{API_URL}/icons/generate", json=scenario["payload"]) as resp:
                        error_time = time.time() - start_time
                        
                        # Immediately try a valid request to test recovery
                        valid_payload = {
                            "category": "Recovery Test",
                            "style": "modern",
                            "color_scheme": "brand_colors"
                        }
                        
                        recovery_start = time.time()
                        async with session.post(f"{API_URL}/icons/generate", json=valid_payload) as recovery_resp:
                            recovery_time = time.time() - recovery_start
                            recovery_times.append(recovery_time)
                            
                            if recovery_resp.status == 200:
                                print(f"    ✅ Recovered in {recovery_time:.3f}s")
                            else:
                                print(f"    ❌ Recovery failed")
                                
            except Exception as e:
                print(f"    ❌ Exception: {e}")
        
        if recovery_times:
            avg_recovery = statistics.mean(recovery_times)
            print(f"\n  Average recovery time: {avg_recovery:.3f}s")
            
            self.test_results["error_recovery"] = {
                "scenarios_tested": len(error_scenarios),
                "avg_recovery_time": avg_recovery,
                "passed": avg_recovery < 2.0  # 2 second recovery threshold
            }
    
    async def test_heavy_load(self):
        """Test UI under heavy load conditions."""
        print("\n⚡ Test 5: Heavy Load Test")
        print("-" * 40)
        
        # Start multiple batch jobs
        batch_ids = []
        num_batches = 3
        
        print(f"  Starting {num_batches} batch jobs...")
        
        for i in range(num_batches):
            batch_id = await self.start_test_batch(num_categories=10)
            if batch_id:
                batch_ids.append(batch_id)
                print(f"    Batch {i+1}: {batch_id}")
        
        if not batch_ids:
            print("  ❌ Failed to start any batch jobs")
            self.test_results["heavy_load"] = {"passed": False, "error": "No batches started"}
            return
        
        # While batches are running, make continuous API calls
        print("  Making continuous API calls during batch processing...")
        
        api_calls_made = 0
        api_errors = 0
        test_duration = 15  # 15 seconds of continuous calls
        start_time = time.time()
        
        while time.time() - start_time < test_duration:
            try:
                async with aiohttp.ClientSession() as session:
                    # Make multiple types of calls
                    calls = [
                        session.get(f"{API_URL}/icons/stats"),
                        session.get(f"{API_URL}/icons/cached"),
                        session.get(f"{API_URL}/icons/batches")
                    ]
                    
                    responses = await asyncio.gather(*[call for call in calls], return_exceptions=True)
                    
                    for resp in responses:
                        if isinstance(resp, Exception):
                            api_errors += 1
                        elif hasattr(resp, 'status') and resp.status == 200:
                            api_calls_made += 1
                        else:
                            api_errors += 1
                        
                        if hasattr(resp, 'close'):
                            await resp.close()
                            
            except Exception as e:
                api_errors += 1
            
            await asyncio.sleep(0.1)  # Small delay between rounds
        
        print(f"\n  API calls made: {api_calls_made}")
        print(f"  API errors: {api_errors}")
        
        error_rate = api_errors / (api_calls_made + api_errors) if (api_calls_made + api_errors) > 0 else 1.0
        
        self.test_results["heavy_load"] = {
            "batch_jobs": len(batch_ids),
            "api_calls_made": api_calls_made,
            "api_errors": api_errors,
            "error_rate": error_rate,
            "passed": error_rate < 0.1  # Less than 10% error rate
        }
    
    async def start_test_batch(self, num_categories: int = 5) -> str:
        """Helper to start a test batch generation."""
        categories = [f"Load Test Category {i+1}" for i in range(num_categories)]
        
        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "categories": categories,
                    "style": "modern",
                    "color_scheme": "brand_colors",
                    "variations_per_category": 1
                }
                
                async with session.post(f"{API_URL}/icons/generate/batch", json=payload) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("batch_id")
                    else:
                        return None
                        
        except Exception as e:
            print(f"  Error starting batch: {e}")
            return None
    
    def generate_report(self):
        """Generate comprehensive test report."""
        print("\n" + "=" * 60)
        print("📊 UI RESPONSIVENESS TEST REPORT")
        print("=" * 60)
        
        all_passed = all(result.get("passed", False) for result in self.test_results.values())
        
        print("\nTest Results:")
        for test_name, result in self.test_results.items():
            status = "✅ PASS" if result.get("passed", False) else "❌ FAIL"
            print(f"\n{test_name}: {status}")
            
            for key, value in result.items():
                if key != "passed":
                    if isinstance(value, float):
                        print(f"  {key}: {value:.3f}")
                    else:
                        print(f"  {key}: {value}")
        
        print("\nPerformance Metrics:")
        if self.response_times["api_calls"]:
            print(f"  API Call Response Times:")
            print(f"    Average: {statistics.mean(self.response_times['api_calls']):.3f}s")
            print(f"    Median: {statistics.median(self.response_times['api_calls']):.3f}s")
            print(f"    Min: {min(self.response_times['api_calls']):.3f}s")
            print(f"    Max: {max(self.response_times['api_calls']):.3f}s")
        
        if self.response_times["generation_requests"]:
            print(f"\n  Generation Request Times:")
            print(f"    Average: {statistics.mean(self.response_times['generation_requests']):.3f}s")
            print(f"    Median: {statistics.median(self.response_times['generation_requests']):.3f}s")
        
        print("\nOverall Result:")
        if all_passed:
            print("🎉 All UI responsiveness tests PASSED!")
            print("The UI maintains good performance under various load conditions.")
        else:
            print("⚠️ Some UI responsiveness tests FAILED.")
            print("Performance optimization may be needed for production use.")
        
        # Save detailed report
        report_data = {
            "timestamp": datetime.now().isoformat(),
            "test_results": self.test_results,
            "response_times": {
                k: {
                    "count": len(v),
                    "mean": statistics.mean(v) if v else 0,
                    "median": statistics.median(v) if v else 0,
                    "min": min(v) if v else 0,
                    "max": max(v) if v else 0
                }
                for k, v in self.response_times.items()
            },
            "websocket_messages": len(self.ws_messages),
            "overall_passed": all_passed
        }
        
        report_path = f"ui_responsiveness_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_path, 'w') as f:
            json.dump(report_data, f, indent=2)
        
        print(f"\nDetailed report saved to: {report_path}")

async def main():
    """Run UI responsiveness tests."""
    tester = UIResponsivenessTest()
    await tester.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main())