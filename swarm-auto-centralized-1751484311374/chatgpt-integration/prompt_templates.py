"""Prompt templates and optimization for category-specific icon generation."""
import re
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class IconStyle(Enum):
    """Available icon styles."""
    MINIMAL = "minimal"
    DETAILED = "detailed"  
    FLAT = "flat"
    MODERN = "modern"
    VINTAGE = "vintage"
    ABSTRACT = "abstract"
    REALISTIC = "realistic"

class IconColor(Enum):
    """Available color schemes."""
    MONOCHROME = "monochrome"
    COLORFUL = "colorful"
    BLUE_TONES = "blue_tones"
    WARM_TONES = "warm_tones"
    COOL_TONES = "cool_tones"
    BRAND_COLORS = "brand_colors"

@dataclass
class PromptTemplate:
    """Template for generating category-specific prompts."""
    base_template: str
    style_modifiers: Dict[IconStyle, str]
    color_modifiers: Dict[IconColor, str]
    category_specific: Dict[str, str]
    quality_enhancers: List[str]
    negative_prompts: List[str]

class CategoryIconPromptManager:
    """Manages prompt templates for different product categories."""
    
    def __init__(self):
        self.templates = self._initialize_templates()
        self.category_mappings = self._initialize_category_mappings()
        
    def _initialize_templates(self) -> Dict[str, PromptTemplate]:
        """Initialize prompt templates for different use cases."""
        
        # Base template for product category icons
        base_template = (
            "Create a professional {style} icon representing {category}. "
            "The icon should be {color_scheme} and suitable for use in a product catalog interface. "
            "{category_specific} "
            "Icon style: clean, modern, scalable vector graphics suitable for web use. "
            "{quality_enhancers}"
        )
        
        # Style modifiers
        style_modifiers = {
            IconStyle.MINIMAL: "minimalist and clean",
            IconStyle.DETAILED: "detailed and comprehensive", 
            IconStyle.FLAT: "flat design with simple shapes",
            IconStyle.MODERN: "modern and contemporary",
            IconStyle.VINTAGE: "vintage and classic",
            IconStyle.ABSTRACT: "abstract and artistic",
            IconStyle.REALISTIC: "realistic and photographic"
        }
        
        # Color scheme modifiers
        color_modifiers = {
            IconColor.MONOCHROME: "monochrome with shades of gray",
            IconColor.COLORFUL: "vibrant and colorful",
            IconColor.BLUE_TONES: "using blue color palette",
            IconColor.WARM_TONES: "using warm colors (red, orange, yellow)",
            IconColor.COOL_TONES: "using cool colors (blue, green, purple)",
            IconColor.BRAND_COLORS: "using professional brand colors"
        }
        
        # Category-specific additions
        category_specific = {
            "office_supplies": "Include elements like pens, paper, staplers, or desk accessories. Focus on workplace productivity items.",
            "electronics": "Show modern devices, circuits, or tech symbols. Emphasize innovation and connectivity.",
            "tools": "Display construction or repair tools. Show craftsmanship and utility.",
            "automotive": "Feature car parts, vehicles, or automotive symbols. Emphasize motion and mechanics.",
            "home_garden": "Include plants, tools, or home improvement items. Show growth and care.",
            "sports": "Show athletic equipment, activity symbols, or sporting goods. Emphasize movement and energy.",
            "clothing": "Display fashion items, textiles, or accessories. Show style and comfort.",
            "food_beverage": "Feature food items, cooking utensils, or dining elements. Show freshness and appeal.",
            "health_beauty": "Include wellness symbols, cosmetics, or care items. Show vitality and self-care.",
            "books_media": "Show books, media devices, or educational symbols. Emphasize knowledge and learning.",
            "toys_games": "Feature playful elements, gaming symbols, or entertainment items. Show fun and creativity.",
            "jewelry_accessories": "Display elegant accessories, gems, or fashion elements. Show luxury and style.",
            "industrial": "Show machinery, industrial equipment, or manufacturing symbols. Emphasize efficiency and power.",
            "agricultural": "Feature farming equipment, crops, or agricultural symbols. Show growth and sustainability.",
            "medical": "Include medical symbols, healthcare equipment, or wellness icons. Show care and precision.",
            "default": "Generic product or service representation with clear visual elements."
        }
        
        # Quality enhancers
        quality_enhancers = [
            "High contrast for visibility",
            "Scalable design suitable for different sizes",
            "Clear and recognizable at small sizes",
            "Professional appearance",
            "Consistent visual style",
            "Optimized for digital display"
        ]
        
        # Negative prompts (what to avoid)
        negative_prompts = [
            "blurry",
            "pixelated", 
            "cluttered",
            "confusing",
            "low quality",
            "distorted",
            "illegible text",
            "inappropriate content",
            "copyrighted logos",
            "trademarked symbols"
        ]
        
        return {
            "standard": PromptTemplate(
                base_template=base_template,
                style_modifiers=style_modifiers,
                color_modifiers=color_modifiers,
                category_specific=category_specific,
                quality_enhancers=quality_enhancers,
                negative_prompts=negative_prompts
            )
        }
    
    def _initialize_category_mappings(self) -> Dict[str, str]:
        """Map various category names to standardized categories."""
        return {
            # Office & Business
            "office supplies": "office_supplies",
            "office": "office_supplies", 
            "business": "office_supplies",
            "stationery": "office_supplies",
            "paper products": "office_supplies",
            
            # Technology
            "electronics": "electronics",
            "computers": "electronics",
            "tech": "electronics",
            "gadgets": "electronics",
            "devices": "electronics",
            
            # Tools & Hardware  
            "tools": "tools",
            "hardware": "tools",
            "construction": "tools",
            "repair": "tools",
            "maintenance": "tools",
            
            # Automotive
            "automotive": "automotive",
            "auto": "automotive",
            "car": "automotive",
            "vehicle": "automotive",
            "transportation": "automotive",
            
            # Home & Garden
            "home": "home_garden",
            "garden": "home_garden", 
            "home improvement": "home_garden",
            "gardening": "home_garden",
            "outdoor": "home_garden",
            
            # Sports & Recreation
            "sports": "sports",
            "fitness": "sports",
            "recreation": "sports",
            "outdoor sports": "sports",
            "exercise": "sports",
            
            # Fashion & Apparel
            "clothing": "clothing",
            "apparel": "clothing",
            "fashion": "clothing",
            "textiles": "clothing",
            "accessories": "jewelry_accessories",
            
            # Food & Beverage
            "food": "food_beverage",
            "beverage": "food_beverage",
            "drinks": "food_beverage",
            "kitchen": "food_beverage",
            "cooking": "food_beverage",
            
            # Health & Beauty
            "health": "health_beauty",
            "beauty": "health_beauty",
            "cosmetics": "health_beauty", 
            "personal care": "health_beauty",
            "wellness": "health_beauty",
            
            # Books & Media
            "books": "books_media",
            "media": "books_media",
            "entertainment": "books_media",
            "education": "books_media",
            "learning": "books_media",
            
            # Toys & Games
            "toys": "toys_games",
            "games": "toys_games",
            "children": "toys_games",
            "kids": "toys_games",
            "play": "toys_games",
            
            # Jewelry & Accessories
            "jewelry": "jewelry_accessories",
            "watches": "jewelry_accessories",
            "luxury": "jewelry_accessories",
            
            # Industrial
            "industrial": "industrial",
            "manufacturing": "industrial",
            "machinery": "industrial",
            "equipment": "industrial",
            
            # Agricultural
            "agriculture": "agricultural",
            "farming": "agricultural",
            "agricultural equipment": "agricultural",
            
            # Medical
            "medical": "medical",
            "healthcare": "medical",
            "pharmaceutical": "medical"
        }
    
    def normalize_category(self, category: str) -> str:
        """Normalize category name to standardized format."""
        if not category:
            return "default"
        
        category_lower = category.lower().strip()
        
        # Direct mapping
        if category_lower in self.category_mappings:
            return self.category_mappings[category_lower]
        
        # Fuzzy matching for partial matches
        for key, value in self.category_mappings.items():
            if key in category_lower or category_lower in key:
                return value
        
        # Return sanitized category name if no mapping found
        return re.sub(r'[^a-zA-Z0-9_]', '_', category_lower)
    
    def generate_prompt(
        self,
        category: str,
        style: IconStyle = IconStyle.MODERN,
        color_scheme: IconColor = IconColor.BRAND_COLORS,
        custom_elements: Optional[List[str]] = None,
        template_name: str = "standard"
    ) -> str:
        """Generate optimized prompt for category icon."""
        
        if template_name not in self.templates:
            template_name = "standard"
        
        template = self.templates[template_name]
        normalized_category = self.normalize_category(category)
        
        # Get style and color modifiers
        style_text = template.style_modifiers.get(style, "modern")
        color_text = template.color_modifiers.get(color_scheme, "professional brand colors")
        
        # Get category-specific text
        category_specific_text = template.category_specific.get(
            normalized_category, 
            template.category_specific["default"]
        )
        
        # Add custom elements if provided
        if custom_elements:
            custom_text = " Include: " + ", ".join(custom_elements) + "."
            category_specific_text += custom_text
        
        # Select quality enhancers (use a subset to avoid overly long prompts)
        quality_enhancers = ". ".join(template.quality_enhancers[:3])
        
        # Build final prompt
        prompt = template.base_template.format(
            style=style_text,
            category=category.title(),
            color_scheme=color_text,
            category_specific=category_specific_text,
            quality_enhancers=quality_enhancers
        )
        
        return self._optimize_prompt(prompt)
    
    def _optimize_prompt(self, prompt: str) -> str:
        """Optimize prompt for better results."""
        # Remove redundant spaces and formatting
        prompt = re.sub(r'\s+', ' ', prompt.strip())
        
        # Ensure prompt ends with a period
        if not prompt.endswith('.'):
            prompt += '.'
        
        # Limit prompt length (DALL-E works better with concise prompts)
        if len(prompt) > 1000:
            sentences = prompt.split('. ')
            truncated = '. '.join(sentences[:3]) + '.'
            logger.warning(f"Prompt truncated from {len(prompt)} to {len(truncated)} characters")
            prompt = truncated
        
        return prompt
    
    def generate_batch_prompts(
        self, 
        categories: List[str],
        style: IconStyle = IconStyle.MODERN,
        color_scheme: IconColor = IconColor.BRAND_COLORS,
        variations_per_category: int = 1
    ) -> List[Dict[str, Any]]:
        """Generate prompts for multiple categories."""
        prompts = []
        
        for category in categories:
            for variation in range(variations_per_category):
                # Vary style slightly for multiple variations
                current_style = style
                if variations_per_category > 1 and variation > 0:
                    styles = list(IconStyle)
                    style_index = (styles.index(style) + variation) % len(styles)
                    current_style = styles[style_index]
                
                prompt = self.generate_prompt(
                    category=category,
                    style=current_style,
                    color_scheme=color_scheme
                )
                
                prompts.append({
                    "category": category,
                    "prompt": prompt,
                    "style": current_style.value,
                    "color_scheme": color_scheme.value,
                    "variation": variation + 1
                })
        
        return prompts
    
    def get_category_suggestions(self, partial_name: str) -> List[str]:
        """Get category suggestions based on partial name."""
        if not partial_name:
            return list(set(self.category_mappings.values()))
        
        partial_lower = partial_name.lower()
        suggestions = []
        
        # Find matching categories
        for category_name, normalized in self.category_mappings.items():
            if partial_lower in category_name:
                suggestions.append(category_name.title())
        
        # Remove duplicates and sort
        return sorted(list(set(suggestions)))
    
    def validate_prompt_parameters(
        self,
        category: str,
        style: str = None,
        color_scheme: str = None
    ) -> Dict[str, Any]:
        """Validate and normalize prompt parameters."""
        errors = []
        warnings = []
        
        # Validate category
        normalized_category = self.normalize_category(category)
        if normalized_category == "default" and category.lower() != "default":
            warnings.append(f"Category '{category}' not recognized, using default")
        
        # Validate style
        valid_style = IconStyle.MODERN
        if style:
            try:
                valid_style = IconStyle(style.lower())
            except ValueError:
                errors.append(f"Invalid style '{style}'. Valid options: {[s.value for s in IconStyle]}")
        
        # Validate color scheme
        valid_color = IconColor.BRAND_COLORS
        if color_scheme:
            try:
                valid_color = IconColor(color_scheme.lower())
            except ValueError:
                errors.append(f"Invalid color scheme '{color_scheme}'. Valid options: {[c.value for c in IconColor]}")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "normalized_category": normalized_category,
            "validated_style": valid_style,
            "validated_color": valid_color
        }