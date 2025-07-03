"""Icon Generation Service with batch processing and comprehensive management."""
import asyncio
import time
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import json
import uuid
from pathlib import Path

from openai_client import OpenAIImageClient, ImageGenerationRequest, ImageGenerationResult
from prompt_templates import CategoryIconPromptManager, IconStyle, IconColor
from config import Config

logger = logging.getLogger(__name__)

@dataclass
class BatchGenerationRequest:
    """Request for batch icon generation."""
    categories: List[str]
    style: IconStyle = IconStyle.MODERN
    color_scheme: IconColor = IconColor.BRAND_COLORS
    variations_per_category: int = 1
    user_id: Optional[str] = None
    custom_elements: Optional[Dict[str, List[str]]] = None
    metadata: Optional[Dict[str, Any]] = None

@dataclass
class BatchGenerationResult:
    """Result of batch icon generation."""
    batch_id: str
    total_requested: int
    successful: int
    failed: int
    results: List[ImageGenerationResult]
    start_time: datetime
    end_time: Optional[datetime] = None
    duration: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None

@dataclass
class BatchJobStatus:
    """Status of a batch generation job."""
    batch_id: str
    status: str  # pending, running, completed, failed, cancelled
    progress: int  # 0-100
    current_category: Optional[str] = None
    total_categories: int = 0
    completed_categories: int = 0
    estimated_completion: Optional[datetime] = None
    created_at: datetime = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

class IconGenerationService:
    """Comprehensive service for generating category icons with batch processing."""
    
    def __init__(self):
        self.openai_client = None
        self.prompt_manager = CategoryIconPromptManager()
        self.active_batches: Dict[str, BatchJobStatus] = {}
        self.batch_results: Dict[str, BatchGenerationResult] = {}
        self.generation_stats = {
            'total_generated': 0,
            'total_failed': 0,
            'total_batches': 0,
            'average_generation_time': 0.0,
            'last_generation': None
        }
        
    async def __aenter__(self):
        """Async context manager entry."""
        self.openai_client = OpenAIImageClient()
        await self.openai_client.__aenter__()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.openai_client:
            await self.openai_client.__aexit__(exc_type, exc_val, exc_tb)
    
    async def generate_single_icon(
        self,
        category: str,
        style: IconStyle = IconStyle.MODERN,
        color_scheme: IconColor = IconColor.BRAND_COLORS,
        custom_elements: Optional[List[str]] = None,
        user_id: Optional[str] = None
    ) -> ImageGenerationResult:
        """Generate a single category icon."""
        if not self.openai_client:
            raise RuntimeError("Service not initialized. Use async context manager.")
        
        # Generate optimized prompt
        prompt = self.prompt_manager.generate_prompt(
            category=category,
            style=style,
            color_scheme=color_scheme,
            custom_elements=custom_elements
        )
        
        # Create generation request
        request = ImageGenerationRequest(
            prompt=prompt,
            category=category,
            size=Config.OPENAI_IMAGE_SIZE,
            quality=Config.OPENAI_IMAGE_QUALITY,
            user_id=user_id,
            metadata={
                'style': style.value,
                'color_scheme': color_scheme.value,
                'custom_elements': custom_elements
            }
        )
        
        # Generate image
        result = await self.openai_client.generate_image(request)
        
        # Update stats
        self._update_generation_stats(result)
        
        return result
    
    async def generate_batch_icons(
        self,
        batch_request: BatchGenerationRequest,
        progress_callback: Optional[callable] = None
    ) -> str:
        """Start batch icon generation and return batch ID for tracking."""
        if not self.openai_client:
            raise RuntimeError("Service not initialized. Use async context manager.")
        
        batch_id = str(uuid.uuid4())
        
        # Validate categories
        validated_categories = []
        for category in batch_request.categories:
            if category and category.strip():
                validated_categories.append(category.strip())
        
        if not validated_categories:
            raise ValueError("No valid categories provided")
        
        total_requests = len(validated_categories) * batch_request.variations_per_category
        
        # Initialize batch status
        batch_status = BatchJobStatus(
            batch_id=batch_id,
            status="pending",
            progress=0,
            total_categories=len(validated_categories),
            completed_categories=0,
            created_at=datetime.now()
        )
        
        self.active_batches[batch_id] = batch_status
        
        # Start batch processing in background
        asyncio.create_task(self._process_batch(batch_request, batch_id, progress_callback))
        
        logger.info(f"Started batch generation {batch_id} for {total_requests} icons")
        return batch_id
    
    async def _process_batch(
        self,
        batch_request: BatchGenerationRequest,
        batch_id: str,
        progress_callback: Optional[callable] = None
    ):
        """Process batch generation request."""
        start_time = datetime.now()
        
        try:
            # Update status to running
            self.active_batches[batch_id].status = "running"
            self.active_batches[batch_id].started_at = start_time
            
            # Generate prompts for all variations
            generation_requests = []
            
            for category in batch_request.categories:
                custom_elements = None
                if batch_request.custom_elements and category in batch_request.custom_elements:
                    custom_elements = batch_request.custom_elements[category]
                
                for variation in range(batch_request.variations_per_category):
                    # Vary style for multiple variations
                    current_style = batch_request.style
                    if batch_request.variations_per_category > 1 and variation > 0:
                        styles = list(IconStyle) 
                        style_index = (list(IconStyle).index(batch_request.style) + variation) % len(styles)
                        current_style = styles[style_index]
                    
                    prompt = self.prompt_manager.generate_prompt(
                        category=category,
                        style=current_style,
                        color_scheme=batch_request.color_scheme,
                        custom_elements=custom_elements
                    )
                    
                    request = ImageGenerationRequest(
                        prompt=prompt,
                        category=category,
                        size=Config.OPENAI_IMAGE_SIZE,
                        quality=Config.OPENAI_IMAGE_QUALITY,
                        user_id=batch_request.user_id,
                        metadata={
                            'batch_id': batch_id,
                            'style': current_style.value,
                            'color_scheme': batch_request.color_scheme.value,
                            'variation': variation + 1,
                            'total_variations': batch_request.variations_per_category
                        }
                    )
                    
                    generation_requests.append(request)
            
            # Process requests with progress tracking
            results = []
            completed = 0
            
            # Process in smaller batches
            batch_size = Config.BATCH_MAX_CONCURRENT
            current_category = None
            
            for i in range(0, len(generation_requests), batch_size):
                batch_requests = generation_requests[i:i + batch_size]
                
                # Update current category for status
                if batch_requests:
                    current_category = batch_requests[0].category
                    self.active_batches[batch_id].current_category = current_category
                
                # Process batch
                batch_results = await self.openai_client.generate_batch(batch_requests)
                results.extend(batch_results)
                
                completed += len(batch_results)
                progress = int((completed / len(generation_requests)) * 100)
                
                # Update progress
                self.active_batches[batch_id].progress = progress
                self.active_batches[batch_id].completed_categories = completed // batch_request.variations_per_category
                
                # Estimate completion time
                elapsed = (datetime.now() - start_time).total_seconds()
                if completed > 0:
                    rate = completed / elapsed
                    remaining = len(generation_requests) - completed
                    eta_seconds = remaining / rate if rate > 0 else 0
                    self.active_batches[batch_id].estimated_completion = datetime.now() + timedelta(seconds=eta_seconds)
                
                # Call progress callback if provided
                if progress_callback:
                    try:
                        await progress_callback(batch_id, progress, current_category, completed, len(generation_requests))
                    except Exception as e:
                        logger.warning(f"Progress callback error: {e}")
                
                # Brief pause between mini-batches
                if i + batch_size < len(generation_requests):
                    await asyncio.sleep(1)
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            # Count successful/failed
            successful = sum(1 for r in results if r.success)
            failed = len(results) - successful
            
            # Create final result
            batch_result = BatchGenerationResult(
                batch_id=batch_id,
                total_requested=len(generation_requests),
                successful=successful,
                failed=failed,
                results=results,
                start_time=start_time,
                end_time=end_time,
                duration=duration,
                metadata=batch_request.metadata
            )
            
            # Update final status
            self.active_batches[batch_id].status = "completed"
            self.active_batches[batch_id].progress = 100
            self.active_batches[batch_id].completed_at = end_time
            
            # Store result
            self.batch_results[batch_id] = batch_result
            
            # Update service stats
            self.generation_stats['total_generated'] += successful
            self.generation_stats['total_failed'] += failed
            self.generation_stats['total_batches'] += 1
            self.generation_stats['last_generation'] = end_time.isoformat()
            
            # Update average generation time
            if successful > 0:
                avg_time = duration / successful
                current_avg = self.generation_stats['average_generation_time']
                total_generated = self.generation_stats['total_generated']
                self.generation_stats['average_generation_time'] = (
                    (current_avg * (total_generated - successful) + avg_time * successful) / total_generated
                )
            
            logger.info(f"Batch {batch_id} completed: {successful}/{len(generation_requests)} successful in {duration:.1f}s")
            
        except Exception as e:
            logger.error(f"Batch {batch_id} failed: {e}")
            self.active_batches[batch_id].status = "failed"
            self.active_batches[batch_id].completed_at = datetime.now()
            
            # Store error result
            self.batch_results[batch_id] = BatchGenerationResult(
                batch_id=batch_id,
                total_requested=len(batch_request.categories) * batch_request.variations_per_category,
                successful=0,
                failed=len(batch_request.categories) * batch_request.variations_per_category,
                results=[],
                start_time=start_time,
                end_time=datetime.now(),
                metadata={'error': str(e)}
            )
    
    def get_batch_status(self, batch_id: str) -> Optional[BatchJobStatus]:
        """Get status of a batch generation job."""
        return self.active_batches.get(batch_id)
    
    def get_batch_result(self, batch_id: str) -> Optional[BatchGenerationResult]:
        """Get result of a completed batch generation job."""
        return self.batch_results.get(batch_id)
    
    def list_active_batches(self, user_id: str = None) -> List[BatchJobStatus]:
        """List active batch jobs, optionally filtered by user."""
        batches = []
        for batch_status in self.active_batches.values():
            if user_id is None:  # No user filter
                batches.append(batch_status)
            # Note: We'd need to store user_id in BatchJobStatus to filter properly
        
        return sorted(batches, key=lambda x: x.created_at, reverse=True)
    
    def cancel_batch(self, batch_id: str) -> bool:
        """Cancel a running batch job."""
        if batch_id not in self.active_batches:
            return False
        
        batch_status = self.active_batches[batch_id]
        if batch_status.status not in ['pending', 'running']:
            return False
        
        # Update status
        batch_status.status = 'cancelled'
        batch_status.completed_at = datetime.now()
        
        logger.info(f"Cancelled batch {batch_id}")
        return True
    
    def get_cached_icons(self, category: str = None) -> List[Dict[str, Any]]:
        """Get list of cached icons."""
        if not self.openai_client:
            return []
        return self.openai_client.get_cached_images(category)
    
    def clear_cache(self, category: str = None, older_than_days: int = None) -> int:
        """Clear icon cache."""
        if not self.openai_client:
            return 0
        return self.openai_client.clear_cache(category, older_than_days)
    
    def get_generation_stats(self) -> Dict[str, Any]:
        """Get service generation statistics."""
        return {
            **self.generation_stats,
            'active_batches': len([b for b in self.active_batches.values() if b.status in ['pending', 'running']]),
            'total_active_jobs': len(self.active_batches),
            'cached_icons': len(self.get_cached_icons())
        }
    
    def get_category_suggestions(self, partial_name: str = "") -> List[str]:
        """Get category suggestions."""
        return self.prompt_manager.get_category_suggestions(partial_name)
    
    def validate_generation_request(
        self,
        categories: List[str],
        style: str = None,
        color_scheme: str = None
    ) -> Dict[str, Any]:
        """Validate icon generation request parameters."""
        errors = []
        warnings = []
        
        # Validate categories
        if not categories or not any(c.strip() for c in categories):
            errors.append("At least one valid category is required")
        
        validated_categories = []
        for category in categories:
            if category and category.strip():
                validation = self.prompt_manager.validate_prompt_parameters(
                    category.strip(), style, color_scheme
                )
                if validation['warnings']:
                    warnings.extend(validation['warnings'])
                validated_categories.append(category.strip())
        
        # Validate batch size
        max_batch_size = 50  # Reasonable limit
        if len(validated_categories) > max_batch_size:
            errors.append(f"Too many categories. Maximum {max_batch_size} allowed, got {len(validated_categories)}")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
            'validated_categories': validated_categories
        }
    
    def _update_generation_stats(self, result: ImageGenerationResult):
        """Update internal generation statistics."""
        if result.success:
            self.generation_stats['total_generated'] += 1
        else:
            self.generation_stats['total_failed'] += 1
        
        self.generation_stats['last_generation'] = datetime.now().isoformat()
        
        # Update average generation time
        if result.generation_time and result.success:
            current_avg = self.generation_stats['average_generation_time']
            total = self.generation_stats['total_generated']
            if total > 1:
                self.generation_stats['average_generation_time'] = (
                    (current_avg * (total - 1) + result.generation_time) / total
                )
            else:
                self.generation_stats['average_generation_time'] = result.generation_time
    
    def cleanup_old_batches(self, older_than_hours: int = 24) -> int:
        """Clean up old batch data to prevent memory leaks."""
        cutoff_time = datetime.now() - timedelta(hours=older_than_hours)
        
        # Clean up completed batches
        batch_ids_to_remove = []
        for batch_id, batch_status in self.active_batches.items():
            if (batch_status.status in ['completed', 'failed', 'cancelled'] and
                batch_status.completed_at and batch_status.completed_at < cutoff_time):
                batch_ids_to_remove.append(batch_id)
        
        for batch_id in batch_ids_to_remove:
            del self.active_batches[batch_id]
            if batch_id in self.batch_results:
                del self.batch_results[batch_id]
        
        logger.info(f"Cleaned up {len(batch_ids_to_remove)} old batch records")
        return len(batch_ids_to_remove)