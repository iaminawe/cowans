#!/usr/bin/env python3
"""
Comprehensive Test Suite for Icon Generation and Sync Workflow

This script tests:
1. Test collection creation
2. Single icon generation
3. Bulk icon generation
4. Shopify sync verification
5. Error handling and edge cases
"""

import asyncio
import time
import json
import sys
import os
from typing import List, Dict, Any, Optional
from datetime import datetime
import aiohttp
import logging
from dataclasses import dataclass, asdict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class TestResult:
    """Result of a single test."""
    test_name: str
    passed: bool
    duration: float
    error: Optional[str] = None
    details: Optional[Dict[str, Any]] = None

@dataclass
class TestCollectionData:
    """Test collection data structure."""
    name: str
    slug: str
    description: str
    custom_elements: List[str]

class IconGenerationTestSuite:
    """Comprehensive test suite for icon generation workflow."""
    
    def __init__(self, base_url: str = "http://localhost:5001"):
        self.base_url = base_url
        self.api_base = f"{base_url}/api"
        self.test_results: List[TestResult] = []
        self.test_collections = [
            TestCollectionData(
                name="Test Electronics",
                slug="test-electronics",
                description="Test collection for electronics icons",
                custom_elements=["circuit board", "LED lights", "modern"]
            ),
            TestCollectionData(
                name="Test Office Supplies",
                slug="test-office-supplies", 
                description="Test collection for office supply icons",
                custom_elements=["desk", "paper", "professional"]
            ),
            TestCollectionData(
                name="Test Tools",
                slug="test-tools",
                description="Test collection for tool icons",
                custom_elements=["wrench", "hammer", "industrial"]
            ),
            TestCollectionData(
                name="Test Cleaning",
                slug="test-cleaning",
                description="Test collection for cleaning product icons",
                custom_elements=["bubbles", "spray bottle", "fresh"]
            ),
            TestCollectionData(
                name="Test Safety",
                slug="test-safety",
                description="Test collection for safety equipment icons",
                custom_elements=["shield", "helmet", "protective"]
            )
        ]
        self.created_collections: List[str] = []
        self.generated_icons: List[Dict[str, Any]] = []
        self.batch_jobs: List[str] = []
        
    async def run_all_tests(self):
        """Run all tests in sequence."""
        logger.info("Starting Icon Generation Test Suite")
        logger.info("=" * 80)
        
        # Check API health first
        if not await self.check_api_health():
            logger.error("API is not healthy. Aborting tests.")
            return
        
        # Run test groups
        await self.test_collection_creation()
        await self.test_single_icon_generation()
        await self.test_bulk_icon_generation()
        await self.test_error_handling()
        await self.test_shopify_sync()
        await self.test_ui_responsiveness()
        
        # Generate report
        self.generate_test_report()
        
    async def check_api_health(self) -> bool:
        """Check if API is healthy."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.api_base}/health") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        logger.info(f"API Health: {data}")
                        return True
                    else:
                        logger.error(f"API health check failed: {resp.status}")
                        return False
        except Exception as e:
            logger.error(f"Failed to connect to API: {e}")
            return False
    
    async def test_collection_creation(self):
        """Test 1: Create test collections for icon generation."""
        logger.info("\nTest 1: Creating Test Collections")
        logger.info("-" * 40)
        
        for collection in self.test_collections:
            start_time = time.time()
            try:
                # Create collection via API
                async with aiohttp.ClientSession() as session:
                    payload = {
                        "title": collection.name,
                        "handle": collection.slug,
                        "body_html": collection.description,
                        "published": True
                    }
                    
                    async with session.post(
                        f"{self.api_base}/shopify/collections",
                        json=payload
                    ) as resp:
                        duration = time.time() - start_time
                        
                        if resp.status in [200, 201]:
                            data = await resp.json()
                            self.created_collections.append(data.get('id'))
                            logger.info(f"✅ Created collection: {collection.name}")
                            
                            self.test_results.append(TestResult(
                                test_name=f"Create collection: {collection.name}",
                                passed=True,
                                duration=duration,
                                details={"collection_id": data.get('id')}
                            ))
                        else:
                            error_text = await resp.text()
                            logger.error(f"❌ Failed to create collection: {collection.name} - {error_text}")
                            
                            self.test_results.append(TestResult(
                                test_name=f"Create collection: {collection.name}",
                                passed=False,
                                duration=duration,
                                error=error_text
                            ))
                            
            except Exception as e:
                duration = time.time() - start_time
                logger.error(f"❌ Exception creating collection: {collection.name} - {e}")
                
                self.test_results.append(TestResult(
                    test_name=f"Create collection: {collection.name}",
                    passed=False,
                    duration=duration,
                    error=str(e)
                ))
    
    async def test_single_icon_generation(self):
        """Test 2: Test single icon generation."""
        logger.info("\nTest 2: Single Icon Generation")
        logger.info("-" * 40)
        
        # Test different styles and color schemes
        test_cases = [
            {"style": "modern", "color_scheme": "brand_colors"},
            {"style": "minimalist", "color_scheme": "monochrome"},
            {"style": "detailed", "color_scheme": "vibrant"},
            {"style": "abstract", "color_scheme": "pastel"},
            {"style": "flat", "color_scheme": "natural"}
        ]
        
        for i, test_case in enumerate(test_cases):
            if i >= len(self.test_collections):
                break
                
            collection = self.test_collections[i]
            start_time = time.time()
            
            try:
                async with aiohttp.ClientSession() as session:
                    payload = {
                        "category": collection.name,
                        "style": test_case["style"],
                        "color_scheme": test_case["color_scheme"],
                        "custom_elements": collection.custom_elements
                    }
                    
                    async with session.post(
                        f"{self.api_base}/icons/generate",
                        json=payload
                    ) as resp:
                        duration = time.time() - start_time
                        
                        if resp.status == 200:
                            data = await resp.json()
                            if data.get("success"):
                                self.generated_icons.append(data)
                                logger.info(f"✅ Generated icon for {collection.name} "
                                          f"(style: {test_case['style']}, "
                                          f"time: {data.get('generation_time', 0):.2f}s)")
                                
                                self.test_results.append(TestResult(
                                    test_name=f"Generate icon: {collection.name} ({test_case['style']})",
                                    passed=True,
                                    duration=duration,
                                    details={
                                        "image_url": data.get("image_url"),
                                        "generation_time": data.get("generation_time")
                                    }
                                ))
                            else:
                                logger.error(f"❌ Failed to generate icon: {data.get('error')}")
                                self.test_results.append(TestResult(
                                    test_name=f"Generate icon: {collection.name} ({test_case['style']})",
                                    passed=False,
                                    duration=duration,
                                    error=data.get("error")
                                ))
                        else:
                            error_text = await resp.text()
                            logger.error(f"❌ API error: {error_text}")
                            
                            self.test_results.append(TestResult(
                                test_name=f"Generate icon: {collection.name} ({test_case['style']})",
                                passed=False,
                                duration=duration,
                                error=error_text
                            ))
                            
            except Exception as e:
                duration = time.time() - start_time
                logger.error(f"❌ Exception generating icon: {e}")
                
                self.test_results.append(TestResult(
                    test_name=f"Generate icon: {collection.name} ({test_case['style']})",
                    passed=False,
                    duration=duration,
                    error=str(e)
                ))
            
            # Brief pause to avoid rate limiting
            await asyncio.sleep(2)
    
    async def test_bulk_icon_generation(self):
        """Test 3: Test bulk icon generation."""
        logger.info("\nTest 3: Bulk Icon Generation")
        logger.info("-" * 40)
        
        # Create bulk generation request
        categories = [c.name for c in self.test_collections]
        start_time = time.time()
        
        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "categories": categories,
                    "style": "modern",
                    "color_scheme": "brand_colors",
                    "variations_per_category": 2
                }
                
                async with session.post(
                    f"{self.api_base}/icons/generate/batch",
                    json=payload
                ) as resp:
                    duration = time.time() - start_time
                    
                    if resp.status == 200:
                        data = await resp.json()
                        batch_id = data.get("batch_id")
                        
                        if batch_id:
                            self.batch_jobs.append(batch_id)
                            logger.info(f"✅ Started batch job: {batch_id}")
                            
                            self.test_results.append(TestResult(
                                test_name="Start bulk generation",
                                passed=True,
                                duration=duration,
                                details={"batch_id": batch_id}
                            ))
                            
                            # Monitor batch progress
                            await self.monitor_batch_progress(batch_id)
                        else:
                            logger.error("❌ No batch ID returned")
                            self.test_results.append(TestResult(
                                test_name="Start bulk generation",
                                passed=False,
                                duration=duration,
                                error="No batch ID returned"
                            ))
                    else:
                        error_text = await resp.text()
                        logger.error(f"❌ Failed to start batch: {error_text}")
                        
                        self.test_results.append(TestResult(
                            test_name="Start bulk generation",
                            passed=False,
                            duration=duration,
                            error=error_text
                        ))
                        
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"❌ Exception in bulk generation: {e}")
            
            self.test_results.append(TestResult(
                test_name="Start bulk generation",
                passed=False,
                duration=duration,
                error=str(e)
            ))
    
    async def monitor_batch_progress(self, batch_id: str, timeout: int = 300):
        """Monitor batch generation progress."""
        start_time = time.time()
        last_progress = 0
        
        while time.time() - start_time < timeout:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        f"{self.api_base}/icons/batch/{batch_id}/status"
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            progress = data.get("progress", 0)
                            status = data.get("status", "unknown")
                            
                            if progress > last_progress:
                                logger.info(f"  Batch progress: {progress}% "
                                          f"({data.get('completed_categories', 0)}/"
                                          f"{data.get('total_categories', 0)} categories)")
                                last_progress = progress
                            
                            if status == "completed":
                                logger.info(f"✅ Batch completed successfully")
                                
                                self.test_results.append(TestResult(
                                    test_name=f"Monitor batch: {batch_id}",
                                    passed=True,
                                    duration=time.time() - start_time,
                                    details={
                                        "total_generated": data.get("successful", 0),
                                        "total_failed": data.get("failed", 0)
                                    }
                                ))
                                return
                                
                            elif status == "failed":
                                logger.error(f"❌ Batch failed")
                                
                                self.test_results.append(TestResult(
                                    test_name=f"Monitor batch: {batch_id}",
                                    passed=False,
                                    duration=time.time() - start_time,
                                    error="Batch processing failed"
                                ))
                                return
                                
            except Exception as e:
                logger.error(f"Error monitoring batch: {e}")
            
            await asyncio.sleep(5)
        
        # Timeout reached
        logger.error(f"❌ Batch monitoring timeout")
        self.test_results.append(TestResult(
            test_name=f"Monitor batch: {batch_id}",
            passed=False,
            duration=timeout,
            error="Monitoring timeout"
        ))
    
    async def test_error_handling(self):
        """Test 4: Test error handling scenarios."""
        logger.info("\nTest 4: Error Handling")
        logger.info("-" * 40)
        
        # Test invalid category
        start_time = time.time()
        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "category": "",  # Empty category
                    "style": "modern",
                    "color_scheme": "brand_colors"
                }
                
                async with session.post(
                    f"{self.api_base}/icons/generate",
                    json=payload
                ) as resp:
                    duration = time.time() - start_time
                    
                    if resp.status >= 400:
                        logger.info("✅ Correctly rejected empty category")
                        self.test_results.append(TestResult(
                            test_name="Error handling: Empty category",
                            passed=True,
                            duration=duration
                        ))
                    else:
                        logger.error("❌ Should have rejected empty category")
                        self.test_results.append(TestResult(
                            test_name="Error handling: Empty category",
                            passed=False,
                            duration=duration,
                            error="Accepted invalid input"
                        ))
                        
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"❌ Exception in error handling test: {e}")
            
            self.test_results.append(TestResult(
                test_name="Error handling: Empty category",
                passed=False,
                duration=duration,
                error=str(e)
            ))
        
        # Test invalid style
        start_time = time.time()
        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "category": "Test Category",
                    "style": "invalid_style",  # Invalid style
                    "color_scheme": "brand_colors"
                }
                
                async with session.post(
                    f"{self.api_base}/icons/generate",
                    json=payload
                ) as resp:
                    duration = time.time() - start_time
                    
                    if resp.status >= 400:
                        logger.info("✅ Correctly rejected invalid style")
                        self.test_results.append(TestResult(
                            test_name="Error handling: Invalid style",
                            passed=True,
                            duration=duration
                        ))
                    else:
                        logger.error("❌ Should have rejected invalid style")
                        self.test_results.append(TestResult(
                            test_name="Error handling: Invalid style",
                            passed=False,
                            duration=duration,
                            error="Accepted invalid style"
                        ))
                        
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"❌ Exception in error handling test: {e}")
            
            self.test_results.append(TestResult(
                test_name="Error handling: Invalid style",
                passed=False,
                duration=duration,
                error=str(e)
            ))
    
    async def test_shopify_sync(self):
        """Test 5: Verify Shopify sync functionality."""
        logger.info("\nTest 5: Shopify Sync Verification")
        logger.info("-" * 40)
        
        if not self.generated_icons:
            logger.warning("No generated icons to sync")
            return
        
        # Test syncing first generated icon
        icon_data = self.generated_icons[0]
        start_time = time.time()
        
        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "collection_id": self.created_collections[0] if self.created_collections else None,
                    "image_url": icon_data.get("image_url"),
                    "alt_text": f"Icon for {icon_data.get('category', 'Test')}"
                }
                
                async with session.post(
                    f"{self.api_base}/shopify/collections/image",
                    json=payload
                ) as resp:
                    duration = time.time() - start_time
                    
                    if resp.status == 200:
                        data = await resp.json()
                        logger.info("✅ Successfully synced icon to Shopify")
                        
                        self.test_results.append(TestResult(
                            test_name="Shopify sync: Upload collection image",
                            passed=True,
                            duration=duration,
                            details={"collection_id": payload["collection_id"]}
                        ))
                    else:
                        error_text = await resp.text()
                        logger.error(f"❌ Failed to sync to Shopify: {error_text}")
                        
                        self.test_results.append(TestResult(
                            test_name="Shopify sync: Upload collection image",
                            passed=False,
                            duration=duration,
                            error=error_text
                        ))
                        
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"❌ Exception syncing to Shopify: {e}")
            
            self.test_results.append(TestResult(
                test_name="Shopify sync: Upload collection image",
                passed=False,
                duration=duration,
                error=str(e)
            ))
    
    async def test_ui_responsiveness(self):
        """Test 6: Test UI responsiveness during operations."""
        logger.info("\nTest 6: UI Responsiveness")
        logger.info("-" * 40)
        
        # Test concurrent API calls
        start_time = time.time()
        
        async def make_api_call(endpoint: str):
            """Make a single API call."""
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"{self.api_base}{endpoint}") as resp:
                        return resp.status, time.time() - start_time
            except Exception as e:
                return None, time.time() - start_time
        
        # Make multiple concurrent calls
        endpoints = [
            "/icons/stats",
            "/icons/cached",
            "/icons/batches",
            "/health"
        ]
        
        tasks = [make_api_call(endpoint) for endpoint in endpoints]
        results = await asyncio.gather(*tasks)
        
        all_successful = all(r[0] == 200 for r in results if r[0] is not None)
        max_response_time = max(r[1] for r in results)
        
        if all_successful and max_response_time < 2.0:  # 2 second threshold
            logger.info(f"✅ UI responsive - max response time: {max_response_time:.2f}s")
            
            self.test_results.append(TestResult(
                test_name="UI responsiveness test",
                passed=True,
                duration=max_response_time,
                details={"endpoints_tested": len(endpoints)}
            ))
        else:
            logger.error(f"❌ UI responsiveness issues - max time: {max_response_time:.2f}s")
            
            self.test_results.append(TestResult(
                test_name="UI responsiveness test",
                passed=False,
                duration=max_response_time,
                error=f"Response time too high: {max_response_time:.2f}s"
            ))
    
    def generate_test_report(self):
        """Generate comprehensive test report."""
        logger.info("\n" + "=" * 80)
        logger.info("TEST REPORT")
        logger.info("=" * 80)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for r in self.test_results if r.passed)
        failed_tests = total_tests - passed_tests
        total_duration = sum(r.duration for r in self.test_results)
        
        logger.info(f"\nSummary:")
        logger.info(f"  Total Tests: {total_tests}")
        logger.info(f"  Passed: {passed_tests} ({passed_tests/total_tests*100:.1f}%)")
        logger.info(f"  Failed: {failed_tests} ({failed_tests/total_tests*100:.1f}%)")
        logger.info(f"  Total Duration: {total_duration:.2f}s")
        
        if failed_tests > 0:
            logger.info(f"\nFailed Tests:")
            for result in self.test_results:
                if not result.passed:
                    logger.info(f"  - {result.test_name}")
                    if result.error:
                        logger.info(f"    Error: {result.error}")
        
        # Save detailed report
        report_data = {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_tests": total_tests,
                "passed": passed_tests,
                "failed": failed_tests,
                "duration": total_duration
            },
            "test_results": [asdict(r) for r in self.test_results],
            "generated_icons": len(self.generated_icons),
            "created_collections": len(self.created_collections),
            "batch_jobs": len(self.batch_jobs)
        }
        
        report_path = f"icon_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_path, 'w') as f:
            json.dump(report_data, f, indent=2)
        
        logger.info(f"\nDetailed report saved to: {report_path}")
        
        # Cleanup test data
        if self.created_collections:
            logger.info(f"\nTest collections created: {len(self.created_collections)}")
            logger.info("Remember to clean up test collections from Shopify admin")

async def main():
    """Main test runner."""
    test_suite = IconGenerationTestSuite()
    await test_suite.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main())