"""
GPT-4 Enhanced Prompt Generator for DALL-E 3

Uses GPT-4 to create optimized prompts for image generation.
"""

import os
import logging
from typing import Dict, Any, Optional, List
from openai import OpenAI
import json

logger = logging.getLogger(__name__)

class GPT4PromptEnhancer:
    """Uses GPT-4 to create better prompts for DALL-E 3."""
    
    def __init__(self):
        """Initialize the GPT-4 client."""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment")
        
        self.client = OpenAI(api_key=api_key)
        self.model = "gpt-4o"  # Use GPT-4o as requested
        
    def create_icon_prompt(
        self,
        category_name: str,
        style: str = "modern",
        color_scheme: str = "auto",
        description: Optional[str] = None,
        keywords: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Use GPT-4 to create an optimized DALL-E prompt for icon generation.
        
        Args:
            category_name: The category to create an icon for
            style: Visual style (flat, outlined, filled, etc.)
            color_scheme: Color preferences
            description: Optional category description
            keywords: Optional keywords for the category
            
        Returns:
            Dict with prompt and metadata
        """
        try:
            # Build the GPT-4 prompt
            system_prompt = """You are an expert at creating prompts for DALL-E 3 to generate e-commerce category icons.
            
Your prompts should:
1. Be specific and descriptive
2. Focus on simple, recognizable symbols
3. Emphasize clean, professional design
4. Work well at small sizes (icons)
5. Avoid text or letters in the image
6. Use appropriate visual metaphors

Output your response as JSON with the following structure:
{
    "prompt": "The DALL-E 3 prompt",
    "main_elements": ["element1", "element2"],
    "color_suggestions": ["#hex1", "#hex2"],
    "style_notes": "Brief style description",
    "reasoning": "Why this design works for this category"
}"""

            # Build the user prompt with context
            user_prompt_parts = [
                f"Create a DALL-E 3 prompt for an e-commerce category icon.",
                f"Category: {category_name}",
                f"Style: {style} design"
            ]
            
            if description:
                user_prompt_parts.append(f"Description: {description}")
            
            if keywords:
                user_prompt_parts.append(f"Related keywords: {', '.join(keywords)}")
            
            if color_scheme != "auto":
                user_prompt_parts.append(f"Color preference: {color_scheme}")
            
            user_prompt_parts.extend([
                "",
                "The icon should be:",
                "- Simple and recognizable",
                "- Professional and modern",
                "- Work well at 128x128 pixels",
                "- Suitable for e-commerce",
                "- NO text or letters in the image"
            ])
            
            user_prompt = "\n".join(user_prompt_parts)
            
            # Call GPT-4
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=500,
                response_format={"type": "json_object"}
            )
            
            # Parse the response
            result = json.loads(response.choices[0].message.content)
            
            # Enhance the DALL-E prompt with additional instructions
            enhanced_prompt = self._enhance_dalle_prompt(result["prompt"], style)
            
            return {
                "success": True,
                "prompt": enhanced_prompt,
                "original_prompt": result["prompt"],
                "metadata": {
                    "main_elements": result.get("main_elements", []),
                    "color_suggestions": result.get("color_suggestions", []),
                    "style_notes": result.get("style_notes", ""),
                    "reasoning": result.get("reasoning", ""),
                    "gpt4_model": self.model
                }
            }
            
        except Exception as e:
            logger.error(f"GPT-4 prompt generation error: {e}")
            # Fallback to simple prompt
            fallback_prompt = self._create_fallback_prompt(category_name, style)
            return {
                "success": False,
                "prompt": fallback_prompt,
                "error": str(e)
            }
    
    def _enhance_dalle_prompt(self, base_prompt: str, style: str) -> str:
        """Add DALL-E specific instructions to the prompt."""
        style_instructions = {
            "flat": "flat design style, no gradients or shadows, solid colors,",
            "outlined": "line art style, outline only, no fill colors, minimalist,",
            "filled": "filled shapes with subtle depth, slight gradients allowed,",
            "rounded": "rounded corners and soft edges, friendly appearance,",
            "sharp": "sharp edges and angular design, professional look,",
            "modern": "modern minimalist style, clean and simple,"
        }
        
        style_desc = style_instructions.get(style, "modern minimalist style,")
        
        # Combine base prompt with DALL-E instructions
        enhanced = f"{base_prompt.rstrip('.')}. Icon design, {style_desc} suitable for small display sizes, centered composition, white background, professional e-commerce icon."
        
        return enhanced
    
    def _create_fallback_prompt(self, category_name: str, style: str) -> str:
        """Create a simple fallback prompt without GPT-4."""
        return f"A simple {style} icon representing {category_name}, minimalist design, suitable for e-commerce, professional appearance, centered composition, white background"
    
    def create_batch_prompts(
        self,
        categories: List[Dict[str, Any]],
        style: str = "modern",
        color_scheme: str = "auto"
    ) -> List[Dict[str, Any]]:
        """Create prompts for multiple categories efficiently."""
        prompts = []
        
        for category in categories:
            result = self.create_icon_prompt(
                category_name=category.get("name", ""),
                style=style,
                color_scheme=color_scheme,
                description=category.get("description"),
                keywords=category.get("keywords", [])
            )
            
            result["category_id"] = category.get("id")
            result["category_name"] = category.get("name")
            prompts.append(result)
        
        return prompts


# Example usage and testing
def test_gpt4_enhancer():
    """Test the GPT-4 prompt enhancer."""
    enhancer = GPT4PromptEnhancer()
    
    # Test single prompt
    result = enhancer.create_icon_prompt(
        category_name="Office Supplies",
        style="flat",
        description="Pens, pencils, paper, and desk accessories",
        keywords=["stationery", "writing", "desk", "office"]
    )
    
    if result["success"]:
        print("✅ GPT-4 Enhanced Prompt:")
        print(f"   {result['prompt']}")
        print("\n📊 Metadata:")
        print(f"   Main elements: {result['metadata']['main_elements']}")
        print(f"   Colors: {result['metadata']['color_suggestions']}")
        print(f"   Reasoning: {result['metadata']['reasoning']}")
    else:
        print(f"❌ Error: {result.get('error')}")
        print(f"📝 Fallback prompt: {result['prompt']}")


if __name__ == "__main__":
    test_gpt4_enhancer()