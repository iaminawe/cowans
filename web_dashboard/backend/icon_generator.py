"""
Icon Generator Module

Generates icons for categories using AI or placeholder images.
Integrated with SQLite database for icon management and caching.
"""

import os
import logging
import time
from typing import Dict, Any, Optional
from PIL import Image, ImageDraw, ImageFont
import random
import hashlib
import asyncio
import shutil
import uuid
from openai_client import OpenAIImageClient, ImageGenerationRequest

from icon_storage import IconStorage
from repositories.icon_repository import IconRepository
from database import get_db

logger = logging.getLogger(__name__)


class IconGenerator:
    """Generates icons for categories with database integration."""
    
    def __init__(self, output_path: str = "data/generated_icons"):
        """Initialize icon generator."""
        self.output_path = output_path
        os.makedirs(output_path, exist_ok=True)
        self.openai_client = OpenAIImageClient()
        self.storage = IconStorage(output_path)
        self.repository = IconRepository()
    
    def generate_category_icon(
        self,
        category_id: str,
        category_name: str,
        style: str = "modern",
        color: str = "#3B82F6",
        size: int = 128,
        background: str = "transparent",
        model: str = "gpt-image-1",
        user_id: int = 1,
        force_regenerate: bool = False
    ) -> Dict[str, Any]:
        """
        Generate an icon for a category using OpenAI's image generation.
        Falls back to placeholder if OpenAI fails.
        Checks database for existing icons before generating.
        """
        start_time = time.time()
        
        # Check for existing icon in database if not forcing regeneration
        if not force_regenerate:
            existing_icon = self.repository.get_latest_icon_for_category(int(category_id))
            if existing_icon and os.path.exists(existing_icon.file_path):
                logger.info(f"Using existing icon for category {category_name}")
                return {
                    "success": True,
                    "file_path": existing_icon.file_path,
                    "filename": existing_icon.filename,
                    "size": size,
                    "style": existing_icon.style,
                    "color": existing_icon.color,
                    "ai_generated": existing_icon.model != "unknown",
                    "cached": True,
                    "icon_id": existing_icon.id
                }
        
        try:
            # Map size based on the selected model
            if model == "gpt-image-1":
                # gpt-image-1 supports: 1024x1024, 1024x1536, 1536x1024, auto
                if size <= 1024:
                    openai_size = "1024x1024"
                elif size <= 1536:
                    openai_size = "1024x1536"  # Portrait format
                else:
                    openai_size = "1024x1024"  # Default to square
            else:  # dall-e-3
                # DALL-E 3 supports: 1024x1024, 1024x1792, 1792x1024
                if size <= 1024:
                    openai_size = "1024x1024"
                elif size <= 1792:
                    openai_size = "1024x1792"  # Portrait format
                else:
                    openai_size = "1024x1024"  # Default to square
            
            # Create a prompt for the icon
            style_descriptions = {
                "modern": "modern, clean, minimalist",
                "flat": "flat design, simple, 2D",
                "outlined": "line art, outlined, stroke-based",
                "minimal": "extremely minimalist, essential elements only"
            }
            
            style_desc = style_descriptions.get(style, "modern, clean")
            
            # Enhanced prompt for better icon generation
            prompt = f"Create a {style_desc} icon for '{category_name}' category. The icon should be simple, recognizable, and suitable for use in a user interface. Use {color} as the primary color. The design should be centered and balanced, with clear visual elements that represent {category_name}. Professional icon design, suitable for web and mobile applications."
            
            # Create request
            request = ImageGenerationRequest(
                prompt=prompt,
                category=category_name,
                size=openai_size,
                style=style,
                model=model,
                metadata={
                    "category_id": category_id,
                    "color": color,
                    "background": background
                }
            )
            
            # Run async generation in sync context
            async def generate():
                async with self.openai_client as client:
                    return await client.generate_image(request)
            
            result = asyncio.run(generate())
            
            if result.success and result.local_path:
                # Move file to our output directory
                name_hash = hashlib.md5(f"{category_id}_{category_name}".encode()).hexdigest()[:8]
                filename = f"icon_{category_id}_{name_hash}.png"
                final_path = os.path.join(self.output_path, filename)
                
                # Copy the file
                shutil.move(result.local_path, final_path)
                
                # Calculate generation time and estimate cost
                generation_time = time.time() - start_time
                generation_cost = self._estimate_generation_cost(model, openai_size)
                
                # Save to database via storage
                icon_metadata = {
                    "style": style,
                    "color": color,
                    "background": background,
                    "model": model,
                    "ai_generated": True,
                    "prompt": prompt,
                    "generation_time": generation_time,
                    "generation_cost": generation_cost
                }
                
                icon_record = self.storage.save_icon(
                    category_id=category_id,
                    category_name=category_name,
                    file_path=final_path,
                    metadata=icon_metadata,
                    created_by=user_id
                )
                
                logger.info(f"Generated AI icon for {category_name} at {final_path}")
                
                return {
                    "success": True,
                    "file_path": final_path,
                    "filename": filename,
                    "size": size,
                    "style": style,
                    "color": color,
                    "ai_generated": True,
                    "cached": False,
                    "icon_id": icon_record["id"]
                }
            else:
                # Fall back to placeholder if AI generation fails
                logger.warning(f"AI generation failed for {category_name}: {result.error}")
                return self._generate_placeholder_icon(
                    category_id, category_name, style, color, size, background, user_id
                )
            
        except Exception as e:
            logger.error(f"Error generating AI icon for {category_name}: {str(e)}")
            # Fall back to placeholder
            return self._generate_placeholder_icon(
                category_id, category_name, style, color, size, background, user_id
            )
    
    def _generate_placeholder_icon(
        self,
        category_id: str,
        category_name: str,
        style: str = "modern",
        color: str = "#3B82F6",
        size: int = 128,
        background: str = "transparent",
        user_id: int = 1
    ) -> Dict[str, Any]:
        """Generate a simple placeholder icon with initials."""
        start_time = time.time()
        
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
            r, g, b = tuple(int(color[i:i+2], 16) for i in (0, 2, 4))
            
            # Draw a circle background
            margin = size // 8
            draw.ellipse(
                [margin, margin, size - margin, size - margin],
                fill=(r, g, b, 255),
                outline=(max(0, r-50), max(0, g-50), max(0, b-50), 255),
                width=2
            )
            
            # Add initials
            initials = ''.join(word[0].upper() for word in category_name.split()[:2])
            if not initials:
                initials = category_name[0].upper()
            
            # Try to use a font, fall back to default if not available
            try:
                font_size = size // 3
                font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", font_size)
            except:
                font = ImageFont.load_default()
            
            # Get text bbox for centering
            bbox = draw.textbbox((0, 0), initials, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            
            # Draw text centered
            text_x = (size - text_width) // 2
            text_y = (size - text_height) // 2
            draw.text((text_x, text_y), initials, fill=(255, 255, 255, 255), font=font)
            
            # Save the image
            img.save(file_path, 'PNG')
            
            # Calculate generation time
            generation_time = time.time() - start_time
            
            # Save to database via storage
            icon_metadata = {
                "style": style,
                "color": color,
                "background": background,
                "model": "placeholder",
                "ai_generated": False,
                "generation_time": generation_time,
                "generation_cost": 0.0
            }
            
            icon_record = self.storage.save_icon(
                category_id=category_id,
                category_name=category_name,
                file_path=file_path,
                metadata=icon_metadata,
                created_by=user_id
            )
            
            logger.info(f"Generated placeholder icon for {category_name} at {file_path}")
            
            return {
                "success": True,
                "file_path": file_path,
                "filename": filename,
                "size": size,
                "style": style,
                "color": color,
                "ai_generated": False,
                "cached": False,
                "icon_id": icon_record["id"]
            }
            
        except Exception as e:
            logger.error(f"Error generating placeholder icon for {category_name}: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def generate_batch(
        self,
        categories: list,
        options: Dict[str, Any],
        user_id: int = 1
    ) -> list:
        """Generate icons for multiple categories."""
        results = []
        batch_id = str(uuid.uuid4())
        
        for category in categories:
            # Add batch ID to metadata
            result = self.generate_category_icon(
                category_id=category['id'],
                category_name=category['name'],
                style=options.get('style', 'modern'),
                color=options.get('color', '#3B82F6'),
                size=options.get('size', 128),
                background=options.get('background', 'transparent'),
                model=options.get('model', 'gpt-image-1'),
                user_id=user_id,
                force_regenerate=options.get('force_regenerate', False)
            )
            
            # Add batch ID to result
            if result.get("success") and result.get("icon_id"):
                # Update icon with batch ID
                db = next(get_db())
                icon = self.repository.get_icon_by_id(result["icon_id"])
                if icon:
                    icon.generation_batch_id = batch_id
                    db.commit()
            
            results.append({
                "category_id": category['id'],
                "category_name": category['name'],
                "result": result
            })
        
        return results
    
    def _estimate_generation_cost(self, model: str, size: str) -> float:
        """Estimate the cost of image generation based on model and size."""
        # Rough cost estimates per image (in USD)
        cost_map = {
            "gpt-image-1": {
                "1024x1024": 0.02,
                "1024x1536": 0.04,
                "1536x1024": 0.04
            },
            "dall-e-3": {
                "1024x1024": 0.04,
                "1024x1792": 0.08,
                "1792x1024": 0.08
            }
        }
        
        model_costs = cost_map.get(model, cost_map["gpt-image-1"])
        return model_costs.get(size, 0.02)