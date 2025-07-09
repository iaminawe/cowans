#!/usr/bin/env python3
"""
Quick Icon Generation Test Script

Simple script to quickly test icon generation functionality.
"""

import asyncio
import aiohttp
import json
import sys
from datetime import datetime

# Configuration
BASE_URL = "http://localhost:5001/api"

# Test collections
TEST_COLLECTIONS = [
    {
        "name": "Quick Test Electronics",
        "elements": ["circuit", "modern", "tech"],
        "style": "modern",
        "color": "brand_colors"
    },
    {
        "name": "Quick Test Office",
        "elements": ["desk", "paper", "professional"],
        "style": "minimalist",
        "color": "monochrome"
    },
    {
        "name": "Quick Test Tools", 
        "elements": ["wrench", "industrial", "metal"],
        "style": "detailed",
        "color": "vibrant"
    },
    {
        "name": "Quick Test Cleaning",
        "elements": ["spray", "bubbles", "fresh"],
        "style": "flat",
        "color": "pastel"
    },
    {
        "name": "Quick Test Safety",
        "elements": ["shield", "protective", "secure"],
        "style": "abstract", 
        "color": "natural"
    }
]

async def test_single_generation():
    """Test single icon generation."""
    print("\n🎨 Testing Single Icon Generation")
    print("-" * 50)
    
    collection = TEST_COLLECTIONS[0]
    
    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                "category": collection["name"],
                "style": collection["style"],
                "color_scheme": collection["color"],
                "custom_elements": collection["elements"]
            }
            
            print(f"Generating icon for: {collection['name']}")
            print(f"Style: {collection['style']}, Color: {collection['color']}")
            
            async with session.post(f"{BASE_URL}/icons/generate", json=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("success"):
                        print(f"✅ Success! Generated in {data.get('generation_time', 0):.2f}s")
                        print(f"Image URL: {data.get('image_url')}")
                        return True
                    else:
                        print(f"❌ Failed: {data.get('error')}")
                        return False
                else:
                    print(f"❌ API Error: {resp.status}")
                    print(await resp.text())
                    return False
                    
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False

async def test_batch_generation():
    """Test batch icon generation."""
    print("\n📦 Testing Batch Icon Generation")
    print("-" * 50)
    
    categories = [c["name"] for c in TEST_COLLECTIONS]
    
    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                "categories": categories,
                "style": "modern",
                "color_scheme": "brand_colors",
                "variations_per_category": 1
            }
            
            print(f"Starting batch generation for {len(categories)} categories")
            
            async with session.post(f"{BASE_URL}/icons/generate/batch", json=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    batch_id = data.get("batch_id")
                    
                    if batch_id:
                        print(f"✅ Batch started: {batch_id}")
                        
                        # Monitor progress
                        await monitor_batch(batch_id)
                        return True
                    else:
                        print("❌ No batch ID returned")
                        return False
                else:
                    print(f"❌ API Error: {resp.status}")
                    print(await resp.text())
                    return False
                    
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False

async def monitor_batch(batch_id: str, max_wait: int = 60):
    """Monitor batch progress."""
    print(f"\n📊 Monitoring batch: {batch_id}")
    
    start_time = datetime.now()
    
    while (datetime.now() - start_time).seconds < max_wait:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{BASE_URL}/icons/batch/{batch_id}/status") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        progress = data.get("progress", 0)
                        status = data.get("status", "unknown")
                        
                        print(f"\rProgress: {progress}% - Status: {status}", end="", flush=True)
                        
                        if status == "completed":
                            print(f"\n✅ Batch completed!")
                            print(f"Generated: {data.get('successful', 0)}, Failed: {data.get('failed', 0)}")
                            return True
                        elif status == "failed":
                            print(f"\n❌ Batch failed!")
                            return False
                            
        except Exception as e:
            print(f"\n❌ Monitoring error: {e}")
            
        await asyncio.sleep(2)
    
    print(f"\n⏱️ Monitoring timeout after {max_wait}s")
    return False

async def test_icon_library():
    """Test fetching icon library."""
    print("\n📚 Testing Icon Library")
    print("-" * 50)
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{BASE_URL}/icons/cached") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    print(f"✅ Found {len(data)} cached icons")
                    
                    if data:
                        print("\nSample icons:")
                        for icon in data[:3]:
                            print(f"  - {icon.get('category')} ({icon.get('metadata', {}).get('style')})")
                    
                    return True
                else:
                    print(f"❌ API Error: {resp.status}")
                    return False
                    
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False

async def test_stats():
    """Test fetching generation stats."""
    print("\n📈 Testing Generation Stats")
    print("-" * 50)
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{BASE_URL}/icons/stats") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    print("✅ Generation Statistics:")
                    print(f"  Total Generated: {data.get('total_generated', 0)}")
                    print(f"  Total Failed: {data.get('total_failed', 0)}")
                    print(f"  Active Batches: {data.get('active_batches', 0)}")
                    print(f"  Cached Icons: {data.get('cached_icons', 0)}")
                    print(f"  Avg Generation Time: {data.get('average_generation_time', 0):.2f}s")
                    return True
                else:
                    print(f"❌ API Error: {resp.status}")
                    return False
                    
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False

async def main():
    """Run all quick tests."""
    print("🚀 Quick Icon Generation Tests")
    print("=" * 50)
    
    # Check API health
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{BASE_URL}/health") as resp:
                if resp.status != 200:
                    print("❌ API is not healthy!")
                    return
                print("✅ API is healthy")
    except Exception as e:
        print(f"❌ Cannot connect to API: {e}")
        return
    
    # Run tests
    results = []
    
    # Test 1: Stats
    results.append(("Stats", await test_stats()))
    
    # Test 2: Single generation
    results.append(("Single Generation", await test_single_generation()))
    
    # Test 3: Icon library
    results.append(("Icon Library", await test_icon_library()))
    
    # Test 4: Batch generation
    results.append(("Batch Generation", await test_batch_generation()))
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Test Summary")
    print("-" * 50)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name}: {status}")
    
    print(f"\nTotal: {passed}/{total} passed ({passed/total*100:.0f}%)")
    
    if passed == total:
        print("\n🎉 All tests passed!")
    else:
        print("\n⚠️ Some tests failed")

if __name__ == "__main__":
    asyncio.run(main())