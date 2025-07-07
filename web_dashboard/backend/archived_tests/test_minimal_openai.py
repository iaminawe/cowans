#!/usr/bin/env python3
"""Minimal OpenAI test."""

import os
from dotenv import load_dotenv

# Load env first
load_dotenv()

# Import OpenAI after loading env
import openai

def test_minimal():
    """Minimal DALL-E test."""
    api_key = os.getenv("OPENAI_API_KEY")
    print(f"API Key: {api_key[:20] if api_key else 'None'}...")
    
    try:
        # Create client with minimal parameters
        client = openai.OpenAI(
            api_key=api_key,
            timeout=60.0
        )
        
        print("🔄 Generating test image...")
        
        response = client.images.generate(
            model="dall-e-3",
            prompt="A simple coffee cup icon",
            size="1024x1024",
            n=1
        )
        
        print(f"✅ Success! Image URL: {response.data[0].url[:50]}...")
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_minimal()