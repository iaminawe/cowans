#!/usr/bin/env python3
"""Simple OpenAI test without the complex async setup."""

import os
from dotenv import load_dotenv
import openai

load_dotenv()

def test_simple_dalle():
    """Test DALL-E generation with simple sync client."""
    api_key = os.getenv("OPENAI_API_KEY")
    
    if not api_key:
        print("❌ No API key found")
        return False
        
    print(f"✅ API key found: {api_key[:20]}...")
    
    try:
        # Use sync client for simplicity
        client = openai.OpenAI(api_key=api_key)
        
        print("🔄 Testing DALL-E 3 image generation...")
        
        response = client.images.generate(
            model="dall-e-3",
            prompt="A simple flat icon of a coffee mug, minimalist design, suitable for e-commerce, professional appearance, white background",
            size="1024x1024",
            quality="standard",
            n=1
        )
        
        image_url = response.data[0].url
        print(f"✅ DALL-E 3 generated image!")
        print(f"   Image URL: {image_url[:50]}...")
        
        # Download the image to test
        import requests
        img_response = requests.get(image_url)
        if img_response.status_code == 200:
            with open('test_generated_icon.png', 'wb') as f:
                f.write(img_response.content)
            print(f"✅ Image downloaded to test_generated_icon.png ({len(img_response.content)} bytes)")
            return True
        else:
            print(f"❌ Failed to download image: {img_response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ DALL-E test failed: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Simple OpenAI DALL-E Test")
    print("============================")
    
    success = test_simple_dalle()
    
    if success:
        print("\n🎉 SUCCESS! AI image generation is working!")
        print("Your icon generator will now create real AI icons!")
    else:
        print("\n⚠️  AI generation failed, but placeholder icons still work.")