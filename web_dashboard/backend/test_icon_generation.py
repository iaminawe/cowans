#!/usr/bin/env python3
"""Test icon generation directly."""

import os
import logging
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Set up logging to see what's happening
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(name)s - %(message)s')

from icon_generator_openai import IconGeneratorOpenAI

def test_icon_generation():
    """Test direct icon generation."""
    print("🧪 Testing Icon Generation")
    print("==========================")
    
    # Check API key
    api_key = os.getenv("OPENAI_API_KEY")
    print(f"✅ API Key: {api_key[:20] if api_key else 'None'}...")
    
    # Create generator
    generator = IconGeneratorOpenAI()
    
    # Test generation
    print("🔄 Generating icon...")
    result = generator.generate_category_icon(
        category_id="999",
        category_name="Test Office Supplies",
        style="modern",
        color="#3B82F6",
        use_ai=True
    )
    
    print(f"📊 Result: {result}")
    
    if result.get('success'):
        print(f"✅ Success! Icon path: {result.get('icon_path')}")
        if 'ai_generated' in result and result['ai_generated']:
            print("🤖 AI Generated!")
        else:
            print("📝 Placeholder Generated")
    else:
        print(f"❌ Failed: {result.get('error')}")

if __name__ == "__main__":
    test_icon_generation()