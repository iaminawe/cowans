#!/usr/bin/env python3
"""Clean OpenAI test without any other imports."""

import os
import sys

# Set API key from environment or default
if not os.environ.get('OPENAI_API_KEY'):
    print("❌ OPENAI_API_KEY not set in environment")
    sys.exit(1)

print("🧪 Clean OpenAI Test")
print("===================")

try:
    import openai
    print(f"✅ OpenAI imported: v{openai.__version__}")
    
    # Create client
    print("🔄 Creating client...")
    client = openai.OpenAI()
    print("✅ Client created successfully!")
    
    # Test a simple completion to verify it works
    print("🔄 Testing image generation...")
    response = client.images.generate(
        model="dall-e-3",
        prompt="A simple red circle on white background",
        size="1024x1024",
        n=1
    )
    
    print(f"✅ Image generation successful!")
    print(f"   URL: {response.data[0].url[:50]}...")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n🎉 SUCCESS! OpenAI client is working properly!")