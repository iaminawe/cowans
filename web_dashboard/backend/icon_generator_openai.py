"""
Enhanced Icon Generator with OpenAI Integration

This module provides both AI-powered and fallback icon generation.
"""

import os
import logging
import asyncio
from typing import Dict, Any, Optional, List
from PIL import Image, ImageDraw, ImageFont
import random
import hashlib
from datetime import datetime

from icon_generation_service import IconGenerationService, BatchGenerationRequest
from prompt_templates import IconStyle, IconColor
from openai_client import ImageGenerationRequest
from gpt4_prompt_enhancer import GPT4PromptEnhancer

logger = logging.getLogger(__name__)

class IconGeneratorOpenAI:
    """Enhanced icon generator with OpenAI integration."""
    
    def __init__(self, output_path: str = "data/category_icons"):
        """Initialize icon generator."""
        self.output_path = output_path
        os.makedirs(output_path, exist_ok=True)
        self.icon_service = None
        self._loop = None
        self.gpt4_enhancer = None
        
        # Initialize GPT-4 enhancer if API key is available
        if os.getenv("OPENAI_API_KEY"):
            try:
                self.gpt4_enhancer = GPT4PromptEnhancer()
                logger.info("GPT-4 prompt enhancer initialized")
            except Exception as e:
                logger.warning(f"Could not initialize GPT-4 enhancer: {e}")
        
    async def initialize(self):
        """Initialize the async OpenAI service."""
        self.icon_service = IconGenerationService()
        await self.icon_service.__aenter__()
        logger.info("OpenAI icon generation service initialized")
        
    async def cleanup(self):
        """Cleanup the OpenAI service."""
        if self.icon_service:
            await self.icon_service.__aexit__(None, None, None)
            
    def _get_style_enum(self, style: str) -> IconStyle:
        """Convert string style to enum."""
        style_map = {
            'flat': IconStyle.FLAT,
            'outlined': IconStyle.MINIMAL,  # Map outlined to minimal
            'filled': IconStyle.DETAILED,   # Map filled to detailed
            'rounded': IconStyle.MODERN,    # Map rounded to modern
            'sharp': IconStyle.MODERN,      # Map sharp to modern
            'modern': IconStyle.MODERN,
            'minimal': IconStyle.MINIMAL,
            'detailed': IconStyle.DETAILED,
            'vintage': IconStyle.VINTAGE,
            'abstract': IconStyle.ABSTRACT,
            'realistic': IconStyle.REALISTIC
        }
        return style_map.get(style.lower(), IconStyle.MODERN)
        
    def _get_color_enum(self, color_scheme: str) -> IconColor:
        """Convert string color scheme to enum."""
        color_map = {
            'monochrome': IconColor.MONOCHROME,
            'brand': IconColor.BRAND,
            'category': IconColor.CATEGORY,
            'auto': IconColor.AUTO
        }
        return color_map.get(color_scheme.lower(), IconColor.AUTO)
    
    def generate_category_icon(
        self,
        category_id: str,
        category_name: str,
        style: str = "modern",
        color: str = "#3B82F6",
        size: int = 128,
        background: str = "transparent",
        use_ai: bool = True
    ) -> Dict[str, Any]:
        """
        Generate an icon for a category using OpenAI or fallback.
        
        This is a synchronous wrapper for the async OpenAI generation.
        """
        # Check if we should use AI generation
        if use_ai and os.getenv("OPENAI_API_KEY"):
            try:
                # Run async function in sync context
                if not self._loop:
                    self._loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(self._loop)
                
                result = self._loop.run_until_complete(
                    self._generate_with_openai(
                        category_id=category_id,
                        category_name=category_name,
                        style=style,
                        color=color
                    )
                )
                
                if result['success']:
                    return result
                else:
                    logger.warning(f"OpenAI generation failed, using fallback: {result.get('error')}")
                    
            except Exception as e:
                logger.error(f"Error with OpenAI generation: {e}")
                logger.info("Falling back to placeholder generation")
        
        # Fallback to placeholder generation
        return self._generate_placeholder(
            category_id=category_id,
            category_name=category_name,
            style=style,
            color=color,
            size=size,
            background=background
        )
    
    async def _generate_with_openai(
        self,
        category_id: str,
        category_name: str,
        style: str,
        color: str,
        description: Optional[str] = None,
        keywords: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Generate icon using GPT-4 enhanced prompts and DALL-E."""
        try:
            # Initialize service if needed
            if not self.icon_service:
                await self.initialize()
            
            # Use GPT-4 to create an optimized prompt if available
            if self.gpt4_enhancer:
                logger.info(f"Using GPT-4 to enhance prompt for {category_name}")
                gpt4_result = self.gpt4_enhancer.create_icon_prompt(
                    category_name=category_name,
                    style=style,
                    description=description,
                    keywords=keywords
                )
                
                if gpt4_result["success"]:
                    # Use the GPT-4 enhanced prompt
                    enhanced_prompt = gpt4_result["prompt"]
                    logger.info(f"GPT-4 enhanced prompt: {enhanced_prompt[:100]}...")
                    
                    # Generate icon with the enhanced prompt
                    result = await self.icon_service.generate_single_icon(
                        category=category_name,
                        style=self._get_style_enum(style),
                        color_scheme=IconColor.BRAND_COLORS,
                        custom_elements=[enhanced_prompt]  # Use the full enhanced prompt
                    )
                    
                    # Add GPT-4 metadata
                    if result.success:
                        result.metadata["gpt4_enhanced"] = True
                        result.metadata["gpt4_metadata"] = gpt4_result["metadata"]
                else:
                    logger.warning("GPT-4 enhancement failed, using standard generation")
                    # Fallback to standard generation
                    result = await self.icon_service.generate_single_icon(
                        category=category_name,
                        style=self._get_style_enum(style),
                        color_scheme=IconColor.BRAND_COLORS,
                        custom_elements=[category_name.lower(), "icon", "simple", "clean"]
                    )
            else:
                # Standard generation without GPT-4
                result = await self.icon_service.generate_icon(
                    category=category_name,
                    style=self._get_style_enum(style),
                    color_scheme=IconColor.AUTO,
                    custom_elements=[category_name.lower(), "icon", "simple", "clean"]
                )
            
            if result.success:
                # Create a unique filename
                name_hash = hashlib.md5(f"{category_id}_{category_name}".encode()).hexdigest()[:8]
                filename = f"icon_{category_id}_{name_hash}.png"
                file_path = os.path.join(self.output_path, filename)
                
                # Copy from temp location to our storage
                if result.local_path and os.path.exists(result.local_path):
                    import shutil
                    shutil.copy2(result.local_path, file_path)
                
                return {
                    'success': True,
                    'file_path': file_path,
                    'url': f"/api/icons/categories/{category_id}/icon",
                    'metadata': {
                        'generated_by': 'openai',
                        'model': 'dall-e-3',
                        'prompt': enhanced_prompt,
                        'timestamp': datetime.now().isoformat()
                    }
                }
            else:
                return {
                    'success': False,
                    'error': result.error or 'Unknown error'
                }
                
        except Exception as e:
            logger.error(f"OpenAI generation error: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _generate_placeholder(
        self,
        category_id: str,
        category_name: str,
        style: str,
        color: str,
        size: int,
        background: str
    ) -> Dict[str, Any]:
        """Generate a placeholder icon (original implementation)."""
        try:
            # Create a unique filename
            name_hash = hashlib.md5(f"{category_id}_{category_name}".encode()).hexdigest()[:8]
            filename = f"icon_{category_id}_{name_hash}.png"
            file_path = os.path.join(self.output_path, filename)
            
            # Create placeholder icon
            img = Image.new('RGBA', (size, size), (0, 0, 0, 0) if background == "transparent" else background)
            draw = ImageDraw.Draw(img)
            
            # Convert hex color to RGB
            if color.startswith('#'):
                color = color[1:]
            r, g, b = int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)
            
            # Style variations
            if style == "modern":
                # Rounded rectangle background
                padding = size // 8
                draw.rounded_rectangle(
                    [padding, padding, size - padding, size - padding],
                    radius=size // 8,
                    fill=(r, g, b, 255)
                )
            elif style == "flat":
                # Simple square
                padding = size // 6
                draw.rectangle(
                    [padding, padding, size - padding, size - padding],
                    fill=(r, g, b, 255)
                )
            elif style == "circle":
                # Circle background
                padding = size // 8
                draw.ellipse(
                    [padding, padding, size - padding, size - padding],
                    fill=(r, g, b, 255)
                )
            
            # Add text (first letter or two)
            text = category_name[:2].upper() if len(category_name) > 1 else category_name[0].upper()
            
            # Try to use a font, fallback to default if not available
            try:
                font_size = size // 3
                font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", font_size)
            except:
                font = ImageFont.load_default()
            
            # Get text bbox for centering
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            
            position = ((size - text_width) // 2, (size - text_height) // 2)
            draw.text(position, text, font=font, fill=(255, 255, 255, 255))
            
            # Save icon
            img.save(file_path, 'PNG')
            
            return {
                'success': True,
                'file_path': file_path,
                'url': f"/api/icons/categories/{category_id}/icon",
                'metadata': {
                    'generated_by': 'placeholder',
                    'style': style,
                    'color': color,
                    'timestamp': datetime.now().isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"Error generating placeholder icon: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def generate_batch(
        self,
        categories: list,
        style: str = "modern",
        color_scheme: str = "auto",
        use_ai: bool = True
    ) -> Dict[str, Any]:
        """Generate icons for multiple categories."""
        if use_ai and os.getenv("OPENAI_API_KEY") and self.icon_service:
            try:
                # Create batch request
                batch_request = BatchGenerationRequest(
                    categories=[cat['name'] for cat in categories],
                    style=self._get_style_enum(style),
                    color_scheme=self._get_color_enum(color_scheme),
                    variations_per_category=1,
                    batch_size=min(10, len(categories))  # Process up to 10 at a time
                )
                
                # Start batch generation
                batch_id = await self.icon_service.generate_batch_icons(batch_request)
                
                return {
                    'success': True,
                    'batch_id': batch_id,
                    'message': f'Batch generation started for {len(categories)} categories'
                }
                
            except Exception as e:
                logger.error(f"Batch generation error: {e}")
                return {
                    'success': False,
                    'error': str(e)
                }
        else:
            # Fallback to generating placeholders one by one
            results = []
            for cat in categories:
                result = self.generate_category_icon(
                    category_id=cat['id'],
                    category_name=cat['name'],
                    style=style,
                    use_ai=False
                )
                results.append(result)
            
            return {
                'success': True,
                'results': results,
                'message': f'Generated {len(results)} placeholder icons'
            }

# Create a singleton instance
icon_generator_openai = IconGeneratorOpenAI()