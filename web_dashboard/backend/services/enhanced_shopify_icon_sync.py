"""
Enhanced Shopify Icon Sync Service

Provides improved batch synchronization of icons to Shopify collections with:
- Batch upload support for efficiency
- Retry logic with exponential backoff
- GraphQL API support for better performance
- Comprehensive error handling
- Progress tracking and reporting
"""

import os
import sys
import logging
import requests
import json
import base64
import time
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from enum import Enum

# Add parent directory to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
from scripts.shopify.shopify_base import ShopifyAPIBase

logger = logging.getLogger(__name__)


class SyncStatus(Enum):
    """Sync status enumeration."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"
    RETRYING = "retrying"


@dataclass
class IconSyncResult:
    """Result of an icon sync operation."""
    icon_id: int
    collection_id: str
    status: SyncStatus
    shopify_image_id: Optional[str] = None
    shopify_image_url: Optional[str] = None
    error: Optional[str] = None
    retry_count: int = 0
    processing_time: float = 0.0


class EnhancedShopifyIconSync:
    """Enhanced service for syncing icons to Shopify collections."""
    
    # GraphQL mutation for updating collection image
    UPDATE_COLLECTION_IMAGE_MUTATION = """
    mutation collectionUpdate($input: CollectionInput!) {
      collectionUpdate(input: $input) {
        collection {
          id
          title
          image {
            id
            url
            altText
          }
        }
        userErrors {
          field
          message
        }
      }
    }
    """
    
    # GraphQL query for getting collection details
    GET_COLLECTION_QUERY = """
    query getCollection($id: ID!) {
      collection(id: $id) {
        id
        handle
        title
        image {
          id
          url
        }
        productsCount
      }
    }
    """
    
    # GraphQL query for batch collection retrieval
    GET_COLLECTIONS_BATCH_QUERY = """
    query getCollections($ids: [ID!]!) {
      nodes(ids: $ids) {
        ... on Collection {
          id
          handle
          title
          image {
            id
            url
          }
          productsCount
        }
      }
    }
    """
    
    def __init__(self, shop_url: str, access_token: str, 
                 max_retries: int = 3, 
                 batch_size: int = 10,
                 concurrent_uploads: int = 3):
        """
        Initialize the enhanced sync service.
        
        Args:
            shop_url: Shopify store URL
            access_token: Shopify access token
            max_retries: Maximum retry attempts for failed operations
            batch_size: Number of collections to process in batch queries
            concurrent_uploads: Number of concurrent upload threads
        """
        self.shopify_client = ShopifyAPIBase(shop_url, access_token, debug=True)
        self.max_retries = max_retries
        self.batch_size = batch_size
        self.concurrent_uploads = concurrent_uploads
        
        # Ensure shop URL format
        self.shop_url = shop_url
        if not self.shop_url.startswith('https://'):
            self.shop_url = f"https://{self.shop_url}"
        if not self.shop_url.endswith('.myshopify.com'):
            if '.' not in self.shop_url.split('://')[-1]:
                self.shop_url += '.myshopify.com'
        
        # REST API headers
        self.rest_headers = {
            'X-Shopify-Access-Token': access_token,
            'Content-Type': 'application/json'
        }
    
    def sync_icon_to_collection(self, 
                               icon_path: str, 
                               collection_id: str,
                               alt_text: Optional[str] = None,
                               icon_id: Optional[int] = None) -> IconSyncResult:
        """
        Sync a single icon to a Shopify collection.
        
        Args:
            icon_path: Path to the icon file
            collection_id: Shopify collection ID (GraphQL format)
            alt_text: Alternative text for the image
            icon_id: Optional local icon ID for tracking
            
        Returns:
            IconSyncResult with sync status
        """
        start_time = time.time()
        
        # Validate inputs
        if not os.path.exists(icon_path):
            return IconSyncResult(
                icon_id=icon_id or 0,
                collection_id=collection_id,
                status=SyncStatus.FAILED,
                error="Icon file not found",
                processing_time=time.time() - start_time
            )
        
        # Read and encode icon file
        try:
            with open(icon_path, 'rb') as f:
                icon_data = f.read()
            icon_base64 = base64.b64encode(icon_data).decode('utf-8')
        except Exception as e:
            return IconSyncResult(
                icon_id=icon_id or 0,
                collection_id=collection_id,
                status=SyncStatus.FAILED,
                error=f"Failed to read icon file: {str(e)}",
                processing_time=time.time() - start_time
            )
        
        # Prepare GraphQL input
        filename = os.path.basename(icon_path)
        update_input = {
            'id': collection_id,
            'image': {
                'src': f"data:image/png;base64,{icon_base64}",
                'altText': alt_text or f"Collection icon"
            }
        }
        
        # Attempt sync with retries
        for attempt in range(self.max_retries):
            try:
                result = self.shopify_client.execute_graphql(
                    self.UPDATE_COLLECTION_IMAGE_MUTATION,
                    {'input': update_input}
                )
                
                if 'errors' in result:
                    error_msg = json.dumps(result['errors'])
                    logger.error(f"GraphQL errors: {error_msg}")
                    
                    if attempt < self.max_retries - 1:
                        time.sleep(2 ** attempt)  # Exponential backoff
                        continue
                    
                    return IconSyncResult(
                        icon_id=icon_id or 0,
                        collection_id=collection_id,
                        status=SyncStatus.FAILED,
                        error=f"GraphQL errors: {error_msg}",
                        retry_count=attempt + 1,
                        processing_time=time.time() - start_time
                    )
                
                # Check for user errors
                update_result = result.get('data', {}).get('collectionUpdate', {})
                user_errors = update_result.get('userErrors', [])
                
                if user_errors:
                    error_msg = json.dumps(user_errors)
                    
                    if attempt < self.max_retries - 1:
                        time.sleep(2 ** attempt)
                        continue
                    
                    return IconSyncResult(
                        icon_id=icon_id or 0,
                        collection_id=collection_id,
                        status=SyncStatus.FAILED,
                        error=f"User errors: {error_msg}",
                        retry_count=attempt + 1,
                        processing_time=time.time() - start_time
                    )
                
                # Success! Extract image details
                collection = update_result.get('collection', {})
                image = collection.get('image', {})
                
                return IconSyncResult(
                    icon_id=icon_id or 0,
                    collection_id=collection_id,
                    status=SyncStatus.SUCCESS,
                    shopify_image_id=image.get('id'),
                    shopify_image_url=image.get('url'),
                    retry_count=attempt,
                    processing_time=time.time() - start_time
                )
                
            except Exception as e:
                logger.error(f"Error syncing icon (attempt {attempt + 1}): {str(e)}")
                
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                
                return IconSyncResult(
                    icon_id=icon_id or 0,
                    collection_id=collection_id,
                    status=SyncStatus.FAILED,
                    error=f"Exception: {str(e)}",
                    retry_count=attempt + 1,
                    processing_time=time.time() - start_time
                )
    
    def sync_icons_batch(self, 
                        icon_mappings: List[Dict[str, Any]],
                        progress_callback: Optional[callable] = None) -> Dict[str, Any]:
        """
        Sync multiple icons to collections in batch.
        
        Args:
            icon_mappings: List of dicts with keys:
                - icon_path: Path to icon file
                - collection_id: Shopify collection ID
                - alt_text: Optional alt text
                - icon_id: Optional local icon ID
            progress_callback: Optional callback function(completed, total, current_result)
            
        Returns:
            Summary of batch sync results
        """
        start_time = time.time()
        results = []
        
        # Validate collections exist (in batches)
        collection_ids = [m['collection_id'] for m in icon_mappings]
        valid_collections = self._validate_collections_batch(collection_ids)
        
        # Filter mappings to valid collections
        valid_mappings = [
            m for m in icon_mappings 
            if m['collection_id'] in valid_collections
        ]
        
        # Mark invalid collections as failed
        for mapping in icon_mappings:
            if mapping['collection_id'] not in valid_collections:
                results.append(IconSyncResult(
                    icon_id=mapping.get('icon_id', 0),
                    collection_id=mapping['collection_id'],
                    status=SyncStatus.FAILED,
                    error="Collection not found or invalid"
                ))
        
        # Process valid mappings with thread pool
        with ThreadPoolExecutor(max_workers=self.concurrent_uploads) as executor:
            # Submit all tasks
            future_to_mapping = {
                executor.submit(
                    self.sync_icon_to_collection,
                    mapping['icon_path'],
                    mapping['collection_id'],
                    mapping.get('alt_text'),
                    mapping.get('icon_id')
                ): mapping
                for mapping in valid_mappings
            }
            
            # Process completed tasks
            completed = len(results)  # Already processed invalid collections
            total = len(icon_mappings)
            
            for future in as_completed(future_to_mapping):
                result = future.result()
                results.append(result)
                completed += 1
                
                # Call progress callback if provided
                if progress_callback:
                    progress_callback(completed, total, result)
                
                # Log progress
                logger.info(f"Sync progress: {completed}/{total} - "
                          f"Icon {result.icon_id} -> Collection {result.collection_id}: "
                          f"{result.status.value}")
        
        # Generate summary
        summary = self._generate_sync_summary(results, time.time() - start_time)
        
        return summary
    
    def verify_collection_images(self, collection_ids: List[str]) -> Dict[str, Any]:
        """
        Verify which collections have images.
        
        Args:
            collection_ids: List of Shopify collection IDs to verify
            
        Returns:
            Dict mapping collection IDs to image status
        """
        results = {}
        
        # Process in batches
        for i in range(0, len(collection_ids), self.batch_size):
            batch = collection_ids[i:i + self.batch_size]
            
            try:
                result = self.shopify_client.execute_graphql(
                    self.GET_COLLECTIONS_BATCH_QUERY,
                    {'ids': batch}
                )
                
                if 'errors' not in result:
                    nodes = result.get('data', {}).get('nodes', [])
                    for node in nodes:
                        if node:  # Node might be null for invalid IDs
                            has_image = bool(node.get('image'))
                            results[node['id']] = {
                                'has_image': has_image,
                                'image_url': node.get('image', {}).get('url') if has_image else None,
                                'title': node.get('title'),
                                'handle': node.get('handle')
                            }
                
            except Exception as e:
                logger.error(f"Error verifying batch: {str(e)}")
                # Mark batch as error
                for cid in batch:
                    results[cid] = {'error': str(e)}
        
        return results
    
    def _validate_collections_batch(self, collection_ids: List[str]) -> set:
        """
        Validate collections exist in Shopify.
        
        Args:
            collection_ids: List of collection IDs to validate
            
        Returns:
            Set of valid collection IDs
        """
        valid_ids = set()
        
        # Process in batches
        for i in range(0, len(collection_ids), self.batch_size):
            batch = collection_ids[i:i + self.batch_size]
            
            try:
                result = self.shopify_client.execute_graphql(
                    self.GET_COLLECTIONS_BATCH_QUERY,
                    {'ids': batch}
                )
                
                if 'errors' not in result:
                    nodes = result.get('data', {}).get('nodes', [])
                    for node in nodes:
                        if node:  # Node is null for invalid IDs
                            valid_ids.add(node['id'])
                
            except Exception as e:
                logger.error(f"Error validating collections batch: {str(e)}")
        
        return valid_ids
    
    def _generate_sync_summary(self, results: List[IconSyncResult], 
                              total_time: float) -> Dict[str, Any]:
        """Generate summary statistics from sync results."""
        total = len(results)
        successful = sum(1 for r in results if r.status == SyncStatus.SUCCESS)
        failed = sum(1 for r in results if r.status == SyncStatus.FAILED)
        
        # Calculate average processing time
        avg_time = sum(r.processing_time for r in results) / total if total > 0 else 0
        
        # Group errors
        error_summary = {}
        for result in results:
            if result.error:
                error_type = result.error.split(':')[0]
                error_summary[error_type] = error_summary.get(error_type, 0) + 1
        
        return {
            'success': True,
            'summary': {
                'total_icons': total,
                'successful_syncs': successful,
                'failed_syncs': failed,
                'success_rate': (successful / total * 100) if total > 0 else 0,
                'total_processing_time': total_time,
                'average_processing_time': avg_time,
                'total_retries': sum(r.retry_count for r in results),
                'error_summary': error_summary
            },
            'results': [
                {
                    'icon_id': r.icon_id,
                    'collection_id': r.collection_id,
                    'status': r.status.value,
                    'shopify_image_id': r.shopify_image_id,
                    'shopify_image_url': r.shopify_image_url,
                    'error': r.error,
                    'retry_count': r.retry_count,
                    'processing_time': r.processing_time
                }
                for r in results
            ]
        }


# Utility function for CLI usage
def sync_collections_from_csv(csv_file: str, shop_url: str, access_token: str):
    """
    Sync collection images from a CSV file.
    
    CSV format:
    collection_id,icon_path,alt_text
    """
    import csv
    
    # Initialize sync service
    sync_service = EnhancedShopifyIconSync(
        shop_url=shop_url,
        access_token=access_token,
        max_retries=3,
        batch_size=10,
        concurrent_uploads=3
    )
    
    # Read mappings from CSV
    mappings = []
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            mappings.append({
                'collection_id': row['collection_id'],
                'icon_path': row['icon_path'],
                'alt_text': row.get('alt_text', ''),
                'icon_id': int(row.get('icon_id', 0)) if row.get('icon_id') else None
            })
    
    print(f"📋 Loaded {len(mappings)} icon mappings")
    
    # Progress callback
    def progress_callback(completed, total, result):
        status_icon = "✅" if result.status == SyncStatus.SUCCESS else "❌"
        print(f"[{completed}/{total}] {status_icon} Collection {result.collection_id}")
        if result.error:
            print(f"   ⚠️  {result.error}")
    
    # Execute batch sync
    print("🚀 Starting batch sync...")
    results = sync_service.sync_icons_batch(mappings, progress_callback)
    
    # Print summary
    summary = results['summary']
    print(f"\n📊 Sync Summary:")
    print(f"   ✅ Successful: {summary['successful_syncs']}")
    print(f"   ❌ Failed: {summary['failed_syncs']}")
    print(f"   📈 Success Rate: {summary['success_rate']:.1f}%")
    print(f"   ⏱️  Total Time: {summary['total_processing_time']:.1f}s")
    print(f"   🔄 Total Retries: {summary['total_retries']}")
    
    if summary['error_summary']:
        print(f"\n❌ Error Summary:")
        for error_type, count in summary['error_summary'].items():
            print(f"   - {error_type}: {count}")
    
    return results


if __name__ == '__main__':
    # CLI usage example
    import argparse
    
    parser = argparse.ArgumentParser(description='Sync icons to Shopify collections')
    parser.add_argument('--csv', required=True, help='CSV file with icon mappings')
    parser.add_argument('--shop-url', required=True, help='Shopify store URL')
    parser.add_argument('--access-token', required=True, help='Shopify access token')
    
    args = parser.parse_args()
    
    sync_collections_from_csv(args.csv, args.shop_url, args.access_token)