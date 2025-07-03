"""Test script for the enhanced backend API."""
import requests
import json
import time
from socketio import Client

# Configuration
BASE_URL = "http://localhost:3560/api"
WS_URL = "http://localhost:3560"

# Test credentials
TEST_EMAIL = "test@example.com"
TEST_PASSWORD = "test123"

def test_login():
    """Test login endpoint."""
    print("Testing login...")
    response = requests.post(f"{BASE_URL}/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    
    if response.status_code == 200:
        data = response.json()
        print(f"✓ Login successful: {data['user']['email']}")
        return data['access_token']
    else:
        print(f"✗ Login failed: {response.text}")
        return None

def test_get_scripts(token):
    """Test getting available scripts."""
    print("\nTesting script listing...")
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{BASE_URL}/scripts", headers=headers)
    
    if response.status_code == 200:
        scripts = response.json()
        print("✓ Available scripts:")
        for category, script_list in scripts.items():
            print(f"\n  {category}:")
            for script in script_list:
                print(f"    - {script['name']}: {script['description']}")
    else:
        print(f"✗ Failed to get scripts: {response.text}")

def test_execute_script(token):
    """Test script execution."""
    print("\nTesting script execution...")
    headers = {"Authorization": f"Bearer {token}"}
    
    # Execute a simple script (we'll use filter_products as an example)
    response = requests.post(f"{BASE_URL}/scripts/execute", 
        headers=headers,
        json={
            "script_name": "filter_products",
            "parameters": [
                {
                    "name": "debug",
                    "value": True,
                    "type": "boolean"
                }
            ]
        }
    )
    
    if response.status_code == 201:
        data = response.json()
        print(f"✓ Job created: {data['job_id']}")
        return data['job_id']
    else:
        print(f"✗ Failed to execute script: {response.text}")
        return None

def test_job_status(token, job_id):
    """Test job status endpoint."""
    print(f"\nChecking job status for: {job_id}")
    headers = {"Authorization": f"Bearer {token}"}
    
    for i in range(5):
        response = requests.get(f"{BASE_URL}/jobs/{job_id}", headers=headers)
        if response.status_code == 200:
            job = response.json()
            print(f"  Status: {job['status']} | Progress: {job['progress']}%")
            if job['status'] in ['completed', 'failed']:
                break
        time.sleep(2)

def test_websocket(token, job_id):
    """Test WebSocket connection for real-time logs."""
    print(f"\nTesting WebSocket connection for job: {job_id}")
    
    sio = Client()
    
    @sio.on('connect')
    def on_connect():
        print("✓ WebSocket connected")
        sio.emit('subscribe_job', {'job_id': job_id})
    
    @sio.on('job_output')
    def on_output(data):
        print(f"  LOG: {data['line']}")
    
    @sio.on('job_progress')
    def on_progress(data):
        print(f"  PROGRESS: {data['progress']}%")
    
    @sio.on('job_completed')
    def on_completed(data):
        print("✓ Job completed!")
        sio.disconnect()
    
    @sio.on('job_failed')
    def on_failed(data):
        print(f"✗ Job failed: {data['error']}")
        sio.disconnect()
    
    try:
        sio.connect(WS_URL, headers={"Authorization": f"Bearer {token}"})
        sio.wait()
    except Exception as e:
        print(f"✗ WebSocket error: {e}")

def main():
    """Run all tests."""
    print("=== Backend API Test Suite ===\n")
    
    # Test login
    token = test_login()
    if not token:
        print("Cannot proceed without authentication")
        return
    
    # Test script listing
    test_get_scripts(token)
    
    # Test script execution
    job_id = test_execute_script(token)
    if job_id:
        # Test job status
        test_job_status(token, job_id)
        
        # Test WebSocket (commented out as it requires actual job execution)
        # test_websocket(token, job_id)
    
    print("\n=== Test suite completed ===")

if __name__ == "__main__":
    main()