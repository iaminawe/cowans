"""
Shopify Webhook Handler for Real-time Sync Updates
Handles incoming webhooks from Shopify for real-time synchronization
"""

import json
import hmac
import hashlib
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from flask import Flask, request, jsonify
from dataclasses import dataclass
from enum import Enum
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor

from parallel_sync_engine import ParallelSyncEngine
from sync_performance_monitor import SyncPerformanceMonitor
from models import Product, Collection, ProductCollection
from database import db_manager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WebhookType(Enum):
    PRODUCT_CREATE = "products/create"
    PRODUCT_UPDATE = "products/update"  
    PRODUCT_DELETE = "products/delete"
    COLLECTION_CREATE = "collections/create"
    COLLECTION_UPDATE = "collections/update"
    COLLECTION_DELETE = "collections/delete"
    INVENTORY_LEVEL_UPDATE = "inventory_levels/update"
    ORDER_CREATE = "orders/create"
    ORDER_UPDATE = "orders/update"

@dataclass
class WebhookEvent:
    """Represents a webhook event from Shopify"""
    type: WebhookType
    data: Dict[str, Any]
    shopify_id: str
    timestamp: datetime
    processed: bool = False
    retry_count: int = 0
    error_message: Optional[str] = None

class ShopifyWebhookHandler:
    """Handles Shopify webhook events for real-time synchronization"""
    
    def __init__(self, app: Flask, webhook_secret: str):
        self.app = app
        self.webhook_secret = webhook_secret
        self.sync_engine = ParallelSyncEngine()
        self.performance_monitor = SyncPerformanceMonitor()
        self.executor = ThreadPoolExecutor(max_workers=5)
        
        # Event processing queue
        self.event_queue = asyncio.Queue()
        self.processing_events = {}
        
        # Setup webhook routes
        self._setup_routes()
        
        # Start background processor
        self._start_background_processor()
    
    def _setup_routes(self):
        """Setup webhook endpoint routes"""
        
        @self.app.route('/webhooks/shopify', methods=['POST'])
        def handle_shopify_webhook():
            """Main webhook handler endpoint"""
            try:
                # Verify webhook signature
                if not self._verify_webhook_signature():
                    logger.warning("Invalid webhook signature")
                    return jsonify({"error": "Invalid signature"}), 401
                
                # Parse webhook data
                webhook_data = request.get_json()
                webhook_type = request.headers.get('X-Shopify-Topic', '')
                
                logger.info(f"Received webhook: {webhook_type}")
                
                # Create webhook event
                event = self._create_webhook_event(webhook_type, webhook_data)
                if event:
                    # Queue for processing
                    self._queue_event(event)
                    return jsonify({"status": "received"}), 200
                else:
                    return jsonify({"error": "Unsupported webhook type"}), 400
                    
            except Exception as e:
                logger.error(f"Webhook processing error: {str(e)}")
                return jsonify({"error": "Processing failed"}), 500
        
        @self.app.route('/webhooks/status', methods=['GET'])
        def webhook_status():
            """Get webhook processing status"""
            return jsonify({
                "queue_size": self.event_queue.qsize(),
                "processing_events": len(self.processing_events),
                "last_processed": self.performance_monitor.get_last_webhook_time()
            })
    
    def _verify_webhook_signature(self) -> bool:
        """Verify Shopify webhook signature"""
        try:
            signature = request.headers.get('X-Shopify-Hmac-Sha256', '')
            body = request.get_data()
            
            # Calculate expected signature
            expected_signature = hmac.new(
                self.webhook_secret.encode('utf-8'),
                body,
                hashlib.sha256
            ).hexdigest()
            
            return hmac.compare_digest(signature, expected_signature)
            
        except Exception as e:
            logger.error(f"Signature verification error: {str(e)}")
            return False
    
    def _create_webhook_event(self, webhook_type: str, data: Dict[str, Any]) -> Optional[WebhookEvent]:
        """Create a webhook event from incoming data"""
        try:
            # Map webhook type to enum
            webhook_type_mapping = {
                'products/create': WebhookType.PRODUCT_CREATE,
                'products/update': WebhookType.PRODUCT_UPDATE,
                'products/delete': WebhookType.PRODUCT_DELETE,
                'collections/create': WebhookType.COLLECTION_CREATE,
                'collections/update': WebhookType.COLLECTION_UPDATE,
                'collections/delete': WebhookType.COLLECTION_DELETE,
                'inventory_levels/update': WebhookType.INVENTORY_LEVEL_UPDATE,
                'orders/create': WebhookType.ORDER_CREATE,
                'orders/update': WebhookType.ORDER_UPDATE,
            }
            
            webhook_enum = webhook_type_mapping.get(webhook_type)
            if not webhook_enum:
                logger.warning(f"Unsupported webhook type: {webhook_type}")
                return None
            
            # Extract Shopify ID
            shopify_id = str(data.get('id', ''))
            if not shopify_id:
                logger.error("Missing Shopify ID in webhook data")
                return None
            
            return WebhookEvent(
                type=webhook_enum,
                data=data,
                shopify_id=shopify_id,
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Error creating webhook event: {str(e)}")
            return None
    
    def _queue_event(self, event: WebhookEvent):
        """Queue webhook event for processing"""
        try:
            # Use thread-safe queue
            self.executor.submit(self._add_to_queue, event)
            logger.info(f"Queued webhook event: {event.type.value} - {event.shopify_id}")
            
        except Exception as e:
            logger.error(f"Error queuing event: {str(e)}")
    
    def _add_to_queue(self, event: WebhookEvent):
        """Add event to async queue"""
        try:
            # Get or create event loop
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            # Add to queue
            if loop.is_running():
                asyncio.create_task(self.event_queue.put(event))
            else:
                loop.run_until_complete(self.event_queue.put(event))
                
        except Exception as e:
            logger.error(f"Error adding event to queue: {str(e)}")
    
    def _start_background_processor(self):
        """Start background thread for processing webhook events"""
        def run_processor():
            try:
                # Create new event loop for this thread
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                # Run the async processor
                loop.run_until_complete(self._process_webhook_events())
                
            except Exception as e:
                logger.error(f"Background processor error: {str(e)}")
        
        # Start in background thread
        processor_thread = threading.Thread(target=run_processor, daemon=True)
        processor_thread.start()
        logger.info("Started webhook background processor")
    
    async def _process_webhook_events(self):
        """Process webhook events from queue"""
        logger.info("Starting webhook event processor")
        
        while True:
            try:
                # Wait for next event
                event = await self.event_queue.get()
                
                # Process event
                await self._process_single_event(event)
                
                # Mark task as done
                self.event_queue.task_done()
                
            except Exception as e:
                logger.error(f"Event processing error: {str(e)}")
                await asyncio.sleep(1)  # Brief pause before continuing
    
    async def _process_single_event(self, event: WebhookEvent):
        """Process a single webhook event"""
        try:
            # Add to processing events
            self.processing_events[event.shopify_id] = event
            
            # Update performance metrics
            self.performance_monitor.record_webhook_received(event.type.value)
            
            # Route to appropriate handler
            handler_map = {
                WebhookType.PRODUCT_CREATE: self._handle_product_create,
                WebhookType.PRODUCT_UPDATE: self._handle_product_update,
                WebhookType.PRODUCT_DELETE: self._handle_product_delete,
                WebhookType.COLLECTION_CREATE: self._handle_collection_create,
                WebhookType.COLLECTION_UPDATE: self._handle_collection_update,
                WebhookType.COLLECTION_DELETE: self._handle_collection_delete,
                WebhookType.INVENTORY_LEVEL_UPDATE: self._handle_inventory_update,
                WebhookType.ORDER_CREATE: self._handle_order_create,
                WebhookType.ORDER_UPDATE: self._handle_order_update,
            }
            
            handler = handler_map.get(event.type)
            if handler:
                await handler(event)
                event.processed = True
                self.performance_monitor.record_webhook_processed(event.type.value)
                logger.info(f"Processed webhook: {event.type.value} - {event.shopify_id}")
            else:
                logger.warning(f"No handler for webhook type: {event.type.value}")
            
        except Exception as e:
            logger.error(f"Error processing webhook event: {str(e)}")
            event.error_message = str(e)
            event.retry_count += 1
            
            # Retry if not too many attempts
            if event.retry_count < 3:
                await asyncio.sleep(2 ** event.retry_count)  # Exponential backoff
                await self.event_queue.put(event)
        
        finally:
            # Remove from processing events
            self.processing_events.pop(event.shopify_id, None)
    
    async def _handle_product_create(self, event: WebhookEvent):
        """Handle product creation webhook"""
        try:
            product_data = event.data
            
            # Check if product already exists
            existing_product = Product.query.filter_by(
                shopify_id=event.shopify_id
            ).first()
            
            if existing_product:
                logger.info(f"Product {event.shopify_id} already exists, updating instead")
                await self._handle_product_update(event)
                return
            
            # Create new product
            new_product = Product(
                shopify_id=event.shopify_id,
                title=product_data.get('title', ''),
                description=product_data.get('body_html', ''),
                vendor=product_data.get('vendor', ''),
                product_type=product_data.get('product_type', ''),
                handle=product_data.get('handle', ''),
                status=product_data.get('status', 'active'),
                tags=product_data.get('tags', ''),
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            
            with db_manager.get_session() as session:
                session.add(new_product)
                session.commit()
            
            logger.info(f"Created product from webhook: {event.shopify_id}")
            
        except Exception as e:
            logger.error(f"Error handling product create: {str(e)}")
            raise
    
    async def _handle_product_update(self, event: WebhookEvent):
        """Handle product update webhook"""
        try:
            product_data = event.data
            
            # Find existing product
            with db_manager.get_session() as session:
                product = session.query(Product).filter_by(
                    shopify_id=event.shopify_id
                ).first()
            
            if not product:
                logger.info(f"Product {event.shopify_id} not found, creating instead")
                await self._handle_product_create(event)
                return
            
            # Update product fields
            product.title = product_data.get('title', product.title)
            product.description = product_data.get('body_html', product.description)
            product.vendor = product_data.get('vendor', product.vendor)
            product.product_type = product_data.get('product_type', product.product_type)
            product.handle = product_data.get('handle', product.handle)
            product.status = product_data.get('status', product.status)
            product.tags = product_data.get('tags', product.tags)
            product.updated_at = datetime.now()
            
            db.session.commit()
            
            logger.info(f"Updated product from webhook: {event.shopify_id}")
            
        except Exception as e:
            logger.error(f"Error handling product update: {str(e)}")
            raise
    
    async def _handle_product_delete(self, event: WebhookEvent):
        """Handle product deletion webhook"""
        try:
            # Find and delete product
            product = Product.query.filter_by(
                shopify_id=event.shopify_id
            ).first()
            
            if product:
                # Remove from collections first
                ProductCollection.query.filter_by(product_id=product.id).delete()
                
                # Delete the product
                db.session.delete(product)
                db.session.commit()
                
                logger.info(f"Deleted product from webhook: {event.shopify_id}")
            else:
                logger.info(f"Product {event.shopify_id} not found for deletion")
                
        except Exception as e:
            logger.error(f"Error handling product delete: {str(e)}")
            raise
    
    async def _handle_collection_create(self, event: WebhookEvent):
        """Handle collection creation webhook"""
        try:
            collection_data = event.data
            
            # Check if collection already exists
            existing_collection = Collection.query.filter_by(
                shopify_id=event.shopify_id
            ).first()
            
            if existing_collection:
                logger.info(f"Collection {event.shopify_id} already exists, updating instead")
                await self._handle_collection_update(event)
                return
            
            # Create new collection
            new_collection = Collection(
                shopify_id=event.shopify_id,
                name=collection_data.get('title', ''),
                description=collection_data.get('body_html', ''),
                handle=collection_data.get('handle', ''),
                collection_type='manual' if collection_data.get('rules') else 'automatic',
                rules=json.dumps(collection_data.get('rules', [])),
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            
            db.session.add(new_collection)
            db.session.commit()
            
            logger.info(f"Created collection from webhook: {event.shopify_id}")
            
        except Exception as e:
            logger.error(f"Error handling collection create: {str(e)}")
            raise
    
    async def _handle_collection_update(self, event: WebhookEvent):
        """Handle collection update webhook"""
        try:
            collection_data = event.data
            
            # Find existing collection
            collection = Collection.query.filter_by(
                shopify_id=event.shopify_id
            ).first()
            
            if not collection:
                logger.info(f"Collection {event.shopify_id} not found, creating instead")
                await self._handle_collection_create(event)
                return
            
            # Update collection fields
            collection.name = collection_data.get('title', collection.name)
            collection.description = collection_data.get('body_html', collection.description)
            collection.handle = collection_data.get('handle', collection.handle)
            collection.collection_type = 'manual' if collection_data.get('rules') else 'automatic'
            collection.rules = json.dumps(collection_data.get('rules', []))
            collection.updated_at = datetime.now()
            
            db.session.commit()
            
            logger.info(f"Updated collection from webhook: {event.shopify_id}")
            
        except Exception as e:
            logger.error(f"Error handling collection update: {str(e)}")
            raise
    
    async def _handle_collection_delete(self, event: WebhookEvent):
        """Handle collection deletion webhook"""
        try:
            # Find and delete collection
            collection = Collection.query.filter_by(
                shopify_id=event.shopify_id
            ).first()
            
            if collection:
                # Remove product associations first
                ProductCollection.query.filter_by(collection_id=collection.id).delete()
                
                # Delete the collection
                db.session.delete(collection)
                db.session.commit()
                
                logger.info(f"Deleted collection from webhook: {event.shopify_id}")
            else:
                logger.info(f"Collection {event.shopify_id} not found for deletion")
                
        except Exception as e:
            logger.error(f"Error handling collection delete: {str(e)}")
            raise
    
    async def _handle_inventory_update(self, event: WebhookEvent):
        """Handle inventory level update webhook"""
        try:
            inventory_data = event.data
            
            # Find product by variant ID
            variant_id = inventory_data.get('inventory_item_id')
            available = inventory_data.get('available', 0)
            
            # Update inventory for all products with this variant
            # This is a simplified implementation - you might need more complex logic
            logger.info(f"Inventory update for variant {variant_id}: {available} units")
            
            # Could trigger inventory sync here if needed
            
        except Exception as e:
            logger.error(f"Error handling inventory update: {str(e)}")
            raise
    
    async def _handle_order_create(self, event: WebhookEvent):
        """Handle order creation webhook"""
        try:
            order_data = event.data
            
            # Extract order information
            order_id = order_data.get('id')
            line_items = order_data.get('line_items', [])
            
            # Update product sales data or trigger analytics sync
            for item in line_items:
                product_id = item.get('product_id')
                quantity = item.get('quantity', 0)
                
                # Could update sales metrics here
                logger.info(f"Product {product_id} sold {quantity} units in order {order_id}")
            
        except Exception as e:
            logger.error(f"Error handling order create: {str(e)}")
            raise
    
    async def _handle_order_update(self, event: WebhookEvent):
        """Handle order update webhook"""
        try:
            order_data = event.data
            
            # Handle order updates (fulfillment, cancellation, etc.)
            order_id = order_data.get('id')
            financial_status = order_data.get('financial_status')
            fulfillment_status = order_data.get('fulfillment_status')
            
            logger.info(f"Order {order_id} updated: financial={financial_status}, fulfillment={fulfillment_status}")
            
        except Exception as e:
            logger.error(f"Error handling order update: {str(e)}")
            raise
    
    def get_webhook_stats(self) -> Dict[str, Any]:
        """Get webhook processing statistics"""
        return {
            "queue_size": self.event_queue.qsize(),
            "processing_events": len(self.processing_events),
            "performance_metrics": self.performance_monitor.get_webhook_metrics(),
            "last_processed": self.performance_monitor.get_last_webhook_time()
        }
    
    def setup_webhooks_in_shopify(self, shopify_api_client):
        """Setup webhooks in Shopify (helper method)"""
        webhook_topics = [
            'products/create',
            'products/update', 
            'products/delete',
            'collections/create',
            'collections/update',
            'collections/delete',
            'inventory_levels/update',
            'orders/create',
            'orders/update'
        ]
        
        webhook_endpoint = f"{self.app.config.get('BASE_URL', '')}/webhooks/shopify"
        
        for topic in webhook_topics:
            try:
                webhook_data = {
                    "webhook": {
                        "topic": topic,
                        "address": webhook_endpoint,
                        "format": "json"
                    }
                }
                
                response = shopify_api_client.post('/admin/api/2023-10/webhooks.json', json=webhook_data)
                
                if response.status_code == 201:
                    logger.info(f"Successfully created webhook for {topic}")
                else:
                    logger.error(f"Failed to create webhook for {topic}: {response.text}")
                    
            except Exception as e:
                logger.error(f"Error creating webhook for {topic}: {str(e)}")

def create_webhook_handler(app: Flask, webhook_secret: str) -> ShopifyWebhookHandler:
    """Factory function to create webhook handler"""
    return ShopifyWebhookHandler(app, webhook_secret)