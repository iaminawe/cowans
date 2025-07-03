#!/usr/bin/env python3
"""Test script to verify OpenAI integration is working."""
import os
import asyncio
from dotenv import load_dotenv
import openai
from openai import AsyncOpenAI

# Load environment variables
load_dotenv()

async def test_openai_connection():
    """Test basic OpenAI connection."""
    api_key = os.getenv("OPENAI_API_KEY")
    
    if not api_key:
        print("❌ ERROR: OPENAI_API_KEY not found in environment variables")
        print("Please add your OpenAI API key to the .env file:")
        print("OPENAI_API_KEY=your-api-key-here")
        return False
    
    print(f"✅ OpenAI API key found: {api_key[:8]}...")
    
    try:
        # Initialize client
        client = AsyncOpenAI(api_key=api_key)
        
        # Test with a simple completion
        print("\n🔄 Testing OpenAI connection...")
        response = await client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "Say 'Hello, icon generation is ready!'"}],
            max_tokens=50
        )
        
        print(f"✅ OpenAI Response: {response.choices[0].message.content}")
        
        # Test DALL-E availability
        print("\n🔄 Testing DALL-E image generation...")
        try:
            response = await client.images.generate(
                model="dall-e-3",
                prompt="A simple test icon of a star, minimalist flat design",
                size="1024x1024",
                quality="standard",
                n=1
            )
            print(f"✅ DALL-E 3 is available! Image URL: {response.data[0].url[:50]}...")
            return True
        except Exception as e:
            print(f"⚠️  DALL-E 3 test failed: {str(e)}")
            print("Make sure you have credits for image generation")
            return False
            
    except Exception as e:
        print(f"❌ Error connecting to OpenAI: {str(e)}")
        return False

async def test_icon_generation_service():
    """Test the icon generation service."""
    print("\n" + "="*50)
    print("Testing Icon Generation Service")
    print("="*50)
    
    try:
        from icon_generation_service import IconGenerationService
        from prompt_templates import IconStyle, IconColor
        
        # Initialize service
        service = IconGenerationService()
        
        async with service:
            print("✅ Icon generation service initialized")
            
            # Test generating a single icon
            print("\n🔄 Generating test icon...")
            result = await service.generate_icon(
                category="test-category",
                style=IconStyle.FLAT,
                color_scheme=IconColor.AUTO,
                custom_elements=["star", "simple", "modern"]
            )
            
            print(f"✅ Icon generated successfully!")
            print(f"   - Image URL: {result.image_url[:50]}...")
            print(f"   - Prompt used: {result.prompt[:100]}...")
            print(f"   - Local path: {result.local_path}")
            
            return True
            
    except Exception as e:
        print(f"❌ Error testing icon generation service: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Run all tests."""
    print("🚀 OpenAI Integration Test Suite")
    print("================================\n")
    
    # Test basic connection
    connection_ok = await test_openai_connection()
    
    if connection_ok:
        # Test icon generation service
        service_ok = await test_icon_generation_service()
        
        if service_ok:
            print("\n✅ All tests passed! OpenAI integration is ready.")
            print("\n📝 Next steps:")
            print("1. Navigate to the Icons tab in your dashboard")
            print("2. Click on the Shopify tab")
            print("3. Click 'Generate Icon' for any collection")
            print("4. Watch as AI generates real icons!")
        else:
            print("\n⚠️  Icon generation service test failed.")
            print("Check the error messages above for details.")
    else:
        print("\n❌ OpenAI connection test failed.")
        print("Please check your API key and network connection.")

if __name__ == "__main__":
    asyncio.run(main())