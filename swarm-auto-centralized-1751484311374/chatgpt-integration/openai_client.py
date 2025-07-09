"""OpenAI API client with rate limiting and robust error handling."""
import asyncio
import aiohttp
import time
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
import json
import hashlib
import os
import base64
from PIL import Image
import io

import openai
from openai import AsyncOpenAI
from asyncio_throttle import Throttler

from config import Config

# Configure logging
logger = logging.getLogger(__name__)

@dataclass
class ImageGenerationRequest:
    """Data class for image generation requests."""
    prompt: str
    category: str
    size: str = "1024x1024"
    quality: str = "standard"
    style: Optional[str] = None
    n: int = 1
    response_format: str = "url"
    user_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API request."""
        data = {
            "prompt": self.prompt,
            "size": self.size,
            "quality": self.quality,
            "n": self.n,
            "response_format": self.response_format
        }
        if self.style:
            data["style"] = self.style
        return data
    
    def get_cache_key(self) -> str:
        """Generate cache key for the request."""
        key_data = f"{self.prompt}_{self.size}_{self.quality}_{self.style}"
        return hashlib.md5(key_data.encode()).hexdigest()

@dataclass
class ImageGenerationResult:
    """Result of image generation."""
    success: bool
    image_url: Optional[str] = None
    local_path: Optional[str] = None
    error: Optional[str] = None
    request_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    generation_time: Optional[float] = None

class RateLimiter:
    """Rate limiter for OpenAI API calls."""
    
    def __init__(self, requests_per_minute: int = 50, tokens_per_minute: int = 40000):
        self.rpm_throttler = Throttler(rate_limit=requests_per_minute, period=60)
        self.tpm_throttler = Throttler(rate_limit=tokens_per_minute, period=60)
        self.request_times = []
        self.token_usage = []
        
    async def acquire_request_slot(self):
        """Acquire a slot for making a request."""
        await self.rpm_throttler.acquire()
        
    async def acquire_token_slots(self, estimated_tokens: int):
        """Acquire slots for token usage.""" 
        # Estimate tokens needed for DALL-E (roughly prompt length * 1.3)
        for _ in range(max(1, estimated_tokens // 1000)):
            await self.tpm_throttler.acquire()
    
    def track_request(self, tokens_used: int = 0):
        """Track completed request."""
        now = time.time()
        self.request_times.append(now)
        if tokens_used > 0:
            self.token_usage.append((now, tokens_used))
        
        # Clean old entries
        cutoff = now - 60
        self.request_times = [t for t in self.request_times if t > cutoff]
        self.token_usage = [(t, tokens) for t, tokens in self.token_usage if t > cutoff]

class OpenAIImageClient:
    """OpenAI client for image generation with advanced features."""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or Config.OPENAI_API_KEY
        if not self.api_key:
            raise ValueError("OpenAI API key is required")
            
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            timeout=Config.OPENAI_TIMEOUT,
            max_retries=0  # We'll handle retries ourselves
        )
        
        self.rate_limiter = RateLimiter(
            requests_per_minute=Config.OPENAI_RATE_LIMIT_RPM,
            tokens_per_minute=Config.OPENAI_RATE_LIMIT_TPM
        )
        
        self.storage_path = Path(Config.IMAGES_STORAGE_PATH)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # Request cache to avoid duplicate generations
        self.request_cache = {}
        
        # Session for downloading images
        self.session = None
        
    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
    
    async def generate_image(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        """Generate a single image with error handling and retries."""
        start_time = time.time()
        cache_key = request.get_cache_key()
        
        # Check cache first
        if cache_key in self.request_cache:
            cached_result = self.request_cache[cache_key]
            if cached_result.local_path and os.path.exists(cached_result.local_path):
                logger.info(f"Using cached image for request: {cache_key}")
                return cached_result
        
        # Prepare request with rate limiting
        estimated_tokens = len(request.prompt) * 2  # Rough estimate
        await self.rate_limiter.acquire_request_slot()
        await self.rate_limiter.acquire_token_slots(estimated_tokens)
        
        # Attempt generation with retries
        last_error = None
        for attempt in range(Config.OPENAI_MAX_RETRIES):
            try:
                logger.info(f"Generating image (attempt {attempt + 1}/{Config.OPENAI_MAX_RETRIES}): {request.prompt[:50]}...")
                
                # Make API call
                response = await self.client.images.generate(**request.to_dict())
                
                if not response.data:
                    raise ValueError("No image data returned from API")
                
                image_data = response.data[0]
                image_url = image_data.url
                
                # Download and save image
                local_path = await self._download_and_save_image(
                    image_url, request.category, cache_key
                )
                
                # Track successful request
                self.rate_limiter.track_request(estimated_tokens)
                
                generation_time = time.time() - start_time
                result = ImageGenerationResult(
                    success=True,
                    image_url=image_url,
                    local_path=local_path,
                    request_id=cache_key,
                    metadata={
                        'category': request.category,
                        'prompt': request.prompt,
                        'generation_time': generation_time,
                        'attempt': attempt + 1
                    },
                    generation_time=generation_time
                )
                
                # Cache successful result
                self.request_cache[cache_key] = result
                
                logger.info(f"Successfully generated image: {local_path}")
                return result
                
            except openai.RateLimitError as e:
                logger.warning(f"Rate limit hit on attempt {attempt + 1}: {e}")
                if attempt < Config.OPENAI_MAX_RETRIES - 1:
                    # Exponential backoff
                    wait_time = (2 ** attempt) * 5
                    logger.info(f"Waiting {wait_time} seconds before retry...")
                    await asyncio.sleep(wait_time)
                last_error = str(e)
                
            except openai.APIError as e:
                logger.error(f"OpenAI API error on attempt {attempt + 1}: {e}")
                if attempt < Config.OPENAI_MAX_RETRIES - 1:
                    await asyncio.sleep(2 ** attempt)
                last_error = str(e)
                
            except Exception as e:
                logger.error(f"Unexpected error on attempt {attempt + 1}: {e}")
                if attempt < Config.OPENAI_MAX_RETRIES - 1:
                    await asyncio.sleep(1)
                last_error = str(e)
        
        # All attempts failed
        generation_time = time.time() - start_time
        return ImageGenerationResult(
            success=False,
            error=f"Failed after {Config.OPENAI_MAX_RETRIES} attempts: {last_error}",
            metadata={
                'category': request.category,
                'prompt': request.prompt,
                'generation_time': generation_time,
                'attempts': Config.OPENAI_MAX_RETRIES
            },
            generation_time=generation_time
        )
    
    async def generate_batch(self, requests: List[ImageGenerationRequest]) -> List[ImageGenerationResult]:
        """Generate multiple images with concurrent processing."""
        if not requests:
            return []
        
        logger.info(f"Starting batch generation of {len(requests)} images")
        
        # Process in smaller batches to respect rate limits
        batch_size = Config.BATCH_MAX_CONCURRENT
        results = []
        
        for i in range(0, len(requests), batch_size):
            batch = requests[i:i + batch_size]
            logger.info(f"Processing batch {i//batch_size + 1} ({len(batch)} images)")
            
            # Process batch concurrently
            batch_tasks = [self.generate_image(req) for req in batch]
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
            
            # Handle exceptions in results
            for j, result in enumerate(batch_results):
                if isinstance(result, Exception):
                    logger.error(f"Exception in batch item {i + j}: {result}")
                    results.append(ImageGenerationResult(
                        success=False,
                        error=str(result),
                        metadata={'category': batch[j].category, 'prompt': batch[j].prompt}
                    ))
                else:
                    results.append(result)
            
            # Brief pause between batches
            if i + batch_size < len(requests):
                await asyncio.sleep(2)
        
        success_count = sum(1 for r in results if r.success)
        logger.info(f"Batch generation complete: {success_count}/{len(results)} successful")
        
        return results
    
    async def _download_and_save_image(self, image_url: str, category: str, request_id: str) -> str:
        """Download image from URL and save locally."""
        if not self.session:
            raise RuntimeError("HTTP session not initialized. Use async context manager.")
        
        try:
            async with self.session.get(image_url) as response:
                if response.status != 200:
                    raise ValueError(f"Failed to download image: HTTP {response.status}")
                
                image_data = await response.read()
                
                # Validate image
                try:
                    img = Image.open(io.BytesIO(image_data))
                    img.verify()
                except Exception as e:
                    raise ValueError(f"Invalid image data: {e}")
                
                # Create category directory 
                category_dir = self.storage_path / category.lower().replace(' ', '_')
                category_dir.mkdir(exist_ok=True)
                
                # Generate filename
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"{category.lower().replace(' ', '_')}_{timestamp}_{request_id[:8]}.png"
                local_path = category_dir / filename
                
                # Save image
                with open(local_path, 'wb') as f:
                    f.write(image_data)
                
                # Validate saved file
                if not local_path.exists() or local_path.stat().st_size == 0:
                    raise ValueError("Failed to save image file")
                
                logger.debug(f"Saved image: {local_path}")
                return str(local_path)
                
        except Exception as e:
            logger.error(f"Failed to download/save image: {e}")
            raise
    
    def get_cached_images(self, category: str = None) -> List[Dict[str, Any]]:
        """Get list of cached images, optionally filtered by category."""
        images = []
        
        search_dirs = [self.storage_path]
        if category:
            category_dir = self.storage_path / category.lower().replace(' ', '_')
            if category_dir.exists():
                search_dirs = [category_dir]
        
        for search_dir in search_dirs:
            if not search_dir.exists():
                continue
                
            for category_dir in search_dir.iterdir():
                if not category_dir.is_dir():
                    continue
                    
                for image_file in category_dir.glob("*.png"):
                    try:
                        stat = image_file.stat()
                        images.append({
                            'filename': image_file.name,
                            'category': category_dir.name.replace('_', ' ').title(),
                            'path': str(image_file),
                            'size': stat.st_size,
                            'created': datetime.fromtimestamp(stat.st_ctime).isoformat(),
                            'url': f"{Config.IMAGES_BASE_URL}{category_dir.name}/{image_file.name}"
                        })
                    except Exception as e:
                        logger.warning(f"Error processing image {image_file}: {e}")
        
        return sorted(images, key=lambda x: x['created'], reverse=True)
    
    def clear_cache(self, category: str = None, older_than_days: int = None):
        """Clear image cache, optionally filtered by category and age."""
        deleted_count = 0
        cutoff_time = None
        
        if older_than_days:
            cutoff_time = time.time() - (older_than_days * 24 * 60 * 60)
        
        search_dirs = [self.storage_path]
        if category:
            category_dir = self.storage_path / category.lower().replace(' ', '_')
            if category_dir.exists():
                search_dirs = [category_dir]
        
        for search_dir in search_dirs:
            if not search_dir.exists():
                continue
                
            for category_dir in search_dir.iterdir():
                if not category_dir.is_dir():
                    continue
                    
                for image_file in category_dir.glob("*.png"):
                    try:
                        if cutoff_time and image_file.stat().st_ctime > cutoff_time:
                            continue
                            
                        image_file.unlink()
                        deleted_count += 1
                        logger.debug(f"Deleted cached image: {image_file}")
                        
                    except Exception as e:
                        logger.warning(f"Error deleting image {image_file}: {e}")
        
        # Remove empty directories
        for search_dir in search_dirs:
            if search_dir.exists():
                for category_dir in search_dir.iterdir():
                    if category_dir.is_dir():
                        try:
                            category_dir.rmdir()  # Only works if empty
                        except OSError:
                            pass  # Directory not empty
        
        logger.info(f"Cleared {deleted_count} cached images")
        return deleted_count