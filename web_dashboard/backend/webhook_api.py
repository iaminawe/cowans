"""
Webhook API endpoints for managing and monitoring webhook operations
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from flask import Flask, request, jsonify, Blueprint
from flask_cors import CORS
import requests

from shopify_webhook_handler import ShopifyWebhookHandler, WebhookType
from sync_performance_monitor import SyncPerformanceMonitor

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create blueprint
webhook_bp = Blueprint('webhook_api', __name__)
CORS(webhook_bp)

# Global webhook handler instance
webhook_handler: Optional[ShopifyWebhookHandler] = None

def init_webhook_api(app: Flask, webhook_secret: str):
    """Initialize webhook API with app and handler"""
    global webhook_handler
    webhook_handler = ShopifyWebhookHandler(app, webhook_secret)
    app.register_blueprint(webhook_bp, url_prefix='/api/webhooks')
    return webhook_handler

@webhook_bp.route('/status', methods=['GET'])
def get_webhook_status():
    """Get current webhook processing status"""
    try:
        if not webhook_handler:
            return jsonify({"error": "Webhook handler not initialized"}), 500
        
        stats = webhook_handler.get_webhook_stats()
        
        return jsonify({
            "status": "active",
            "queue_size": stats["queue_size"],
            "processing_events": stats["processing_events"],
            "performance_metrics": stats["performance_metrics"],
            "last_processed": stats["last_processed"],
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting webhook status: {str(e)}")
        return jsonify({"error": str(e)}), 500

@webhook_bp.route('/metrics', methods=['GET'])
def get_webhook_metrics():
    """Get detailed webhook processing metrics"""
    try:
        if not webhook_handler:
            return jsonify({"error": "Webhook handler not initialized"}), 500
        
        # Get time range from query params
        hours = request.args.get('hours', 24, type=int)
        start_time = datetime.now() - timedelta(hours=hours)
        
        performance_monitor = webhook_handler.performance_monitor
        
        # Get metrics
        metrics = {
            "webhook_stats": {
                "total_received": performance_monitor.webhook_received_count,
                "total_processed": performance_monitor.webhook_processed_count,
                "success_rate": performance_monitor.get_webhook_success_rate(),
                "average_processing_time": performance_monitor.get_average_processing_time(),
                "error_rate": performance_monitor.get_webhook_error_rate()
            },
            "by_type": performance_monitor.get_webhook_metrics_by_type(),
            "recent_errors": performance_monitor.get_recent_webhook_errors(hours),
            "processing_trends": performance_monitor.get_processing_trends(hours),
            "queue_analysis": {
                "current_size": webhook_handler.event_queue.qsize(),
                "processing_events": len(webhook_handler.processing_events),
                "average_queue_time": performance_monitor.get_average_queue_time()
            }
        }
        
        return jsonify(metrics)
        
    except Exception as e:
        logger.error(f"Error getting webhook metrics: {str(e)}")
        return jsonify({"error": str(e)}), 500

@webhook_bp.route('/events', methods=['GET'])
def get_webhook_events():
    """Get recent webhook events"""
    try:
        if not webhook_handler:
            return jsonify({"error": "Webhook handler not initialized"}), 500
        
        # Get query parameters
        limit = request.args.get('limit', 50, type=int)
        event_type = request.args.get('type', None)
        status = request.args.get('status', None)  # processed, failed, processing
        
        # Get events from performance monitor
        events = webhook_handler.performance_monitor.get_recent_webhook_events(
            limit=limit,
            event_type=event_type,
            status=status
        )
        
        return jsonify({
            "events": events,
            "total": len(events),
            "filters": {
                "type": event_type,
                "status": status,
                "limit": limit
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting webhook events: {str(e)}")
        return jsonify({"error": str(e)}), 500

@webhook_bp.route('/events/<event_id>', methods=['GET'])
def get_webhook_event(event_id: str):
    """Get specific webhook event details"""
    try:
        if not webhook_handler:
            return jsonify({"error": "Webhook handler not initialized"}), 500
        
        # Check if event is currently processing
        if event_id in webhook_handler.processing_events:
            event = webhook_handler.processing_events[event_id]
            return jsonify({
                "event_id": event_id,
                "type": event.type.value,
                "shopify_id": event.shopify_id,
                "status": "processing",
                "timestamp": event.timestamp.isoformat(),
                "retry_count": event.retry_count,
                "error_message": event.error_message,
                "data": event.data
            })
        
        # Get from performance monitor history
        event_details = webhook_handler.performance_monitor.get_webhook_event_details(event_id)
        
        if event_details:
            return jsonify(event_details)
        else:
            return jsonify({"error": "Event not found"}), 404
            
    except Exception as e:
        logger.error(f"Error getting webhook event {event_id}: {str(e)}")
        return jsonify({"error": str(e)}), 500

@webhook_bp.route('/events/<event_id>/retry', methods=['POST'])
def retry_webhook_event(event_id: str):
    """Retry a failed webhook event"""
    try:
        if not webhook_handler:
            return jsonify({"error": "Webhook handler not initialized"}), 500
        
        # Get event details
        event_details = webhook_handler.performance_monitor.get_webhook_event_details(event_id)
        
        if not event_details:
            return jsonify({"error": "Event not found"}), 404
        
        if event_details.get("status") != "failed":
            return jsonify({"error": "Only failed events can be retried"}), 400
        
        # Create new event for retry
        from shopify_webhook_handler import WebhookEvent
        retry_event = WebhookEvent(
            type=WebhookType(event_details["type"]),
            data=event_details["data"],
            shopify_id=event_details["shopify_id"],
            timestamp=datetime.now(),
            retry_count=event_details.get("retry_count", 0)
        )
        
        # Queue for processing
        webhook_handler._queue_event(retry_event)
        
        return jsonify({
            "message": "Event queued for retry",
            "event_id": event_id,
            "retry_count": retry_event.retry_count + 1
        })
        
    except Exception as e:
        logger.error(f"Error retrying webhook event {event_id}: {str(e)}")
        return jsonify({"error": str(e)}), 500

@webhook_bp.route('/config', methods=['GET'])
def get_webhook_config():
    """Get webhook configuration"""
    try:
        if not webhook_handler:
            return jsonify({"error": "Webhook handler not initialized"}), 500
        
        # Get Shopify webhook configuration
        config = {
            "webhook_endpoint": "/webhooks/shopify",
            "supported_events": [event.value for event in WebhookType],
            "processing_config": {
                "max_workers": 5,
                "retry_limit": 3,
                "queue_size_limit": 1000
            },
            "performance_config": {
                "metrics_retention_hours": 24,
                "alert_thresholds": {
                    "queue_size": 100,
                    "processing_time": 30,
                    "error_rate": 0.1
                }
            }
        }
        
        return jsonify(config)
        
    except Exception as e:
        logger.error(f"Error getting webhook config: {str(e)}")
        return jsonify({"error": str(e)}), 500

@webhook_bp.route('/config', methods=['POST'])
def update_webhook_config():
    """Update webhook configuration"""
    try:
        if not webhook_handler:
            return jsonify({"error": "Webhook handler not initialized"}), 500
        
        config_data = request.get_json()
        
        # Update configuration
        if "max_workers" in config_data:
            webhook_handler.executor._max_workers = config_data["max_workers"]
        
        if "alert_thresholds" in config_data:
            webhook_handler.performance_monitor.update_alert_thresholds(
                config_data["alert_thresholds"]
            )
        
        return jsonify({
            "message": "Configuration updated successfully",
            "updated_config": config_data
        })
        
    except Exception as e:
        logger.error(f"Error updating webhook config: {str(e)}")
        return jsonify({"error": str(e)}), 500

@webhook_bp.route('/shopify/webhooks', methods=['GET'])
def list_shopify_webhooks():
    """List webhooks configured in Shopify"""
    try:
        # This would require Shopify API credentials
        # For now, return a placeholder response
        return jsonify({
            "message": "Shopify webhook listing requires API credentials",
            "supported_topics": [event.value for event in WebhookType],
            "webhook_endpoint": "/webhooks/shopify"
        })
        
    except Exception as e:
        logger.error(f"Error listing Shopify webhooks: {str(e)}")
        return jsonify({"error": str(e)}), 500

@webhook_bp.route('/shopify/webhooks/setup', methods=['POST'])
def setup_shopify_webhooks():
    """Setup webhooks in Shopify"""
    try:
        if not webhook_handler:
            return jsonify({"error": "Webhook handler not initialized"}), 500
        
        # Get Shopify API credentials from request
        request_data = request.get_json()
        shop_url = request_data.get("shop_url")
        access_token = request_data.get("access_token")
        
        if not shop_url or not access_token:
            return jsonify({"error": "shop_url and access_token are required"}), 400
        
        # Setup webhooks
        webhook_topics = [event.value for event in WebhookType]
        webhook_endpoint = f"{request.host_url}webhooks/shopify"
        
        results = []
        
        for topic in webhook_topics:
            try:
                webhook_data = {
                    "webhook": {
                        "topic": topic,
                        "address": webhook_endpoint,
                        "format": "json"
                    }
                }
                
                response = requests.post(
                    f"{shop_url}/admin/api/2023-10/webhooks.json",
                    json=webhook_data,
                    headers={
                        "X-Shopify-Access-Token": access_token,
                        "Content-Type": "application/json"
                    }
                )
                
                if response.status_code == 201:
                    results.append({"topic": topic, "status": "created"})
                elif response.status_code == 422:
                    # Webhook might already exist
                    results.append({"topic": topic, "status": "already_exists"})
                else:
                    results.append({
                        "topic": topic, 
                        "status": "failed",
                        "error": response.text
                    })
                    
            except Exception as e:
                results.append({
                    "topic": topic,
                    "status": "error",
                    "error": str(e)
                })
        
        return jsonify({
            "message": "Webhook setup completed",
            "results": results,
            "webhook_endpoint": webhook_endpoint
        })
        
    except Exception as e:
        logger.error(f"Error setting up Shopify webhooks: {str(e)}")
        return jsonify({"error": str(e)}), 500

@webhook_bp.route('/test', methods=['POST'])
def test_webhook():
    """Test webhook processing with dummy data"""
    try:
        if not webhook_handler:
            return jsonify({"error": "Webhook handler not initialized"}), 500
        
        # Get test data from request
        test_data = request.get_json()
        webhook_type = test_data.get("type", "products/create")
        
        # Create test webhook data
        dummy_data = {
            "id": "test_" + str(int(datetime.now().timestamp())),
            "title": "Test Product",
            "body_html": "Test Description",
            "vendor": "Test Vendor",
            "product_type": "Test Type",
            "handle": "test-product",
            "status": "active",
            "tags": "test"
        }
        
        # Create webhook event
        event = webhook_handler._create_webhook_event(webhook_type, dummy_data)
        
        if event:
            webhook_handler._queue_event(event)
            return jsonify({
                "message": "Test webhook queued successfully",
                "event_id": event.shopify_id,
                "type": webhook_type,
                "data": dummy_data
            })
        else:
            return jsonify({"error": "Failed to create test webhook"}), 400
            
    except Exception as e:
        logger.error(f"Error testing webhook: {str(e)}")
        return jsonify({"error": str(e)}), 500

@webhook_bp.route('/alerts', methods=['GET'])
def get_webhook_alerts():
    """Get webhook processing alerts"""
    try:
        if not webhook_handler:
            return jsonify({"error": "Webhook handler not initialized"}), 500
        
        alerts = webhook_handler.performance_monitor.get_active_alerts()
        
        return jsonify({
            "alerts": alerts,
            "total": len(alerts),
            "by_severity": {
                "critical": len([a for a in alerts if a.get("severity") == "critical"]),
                "warning": len([a for a in alerts if a.get("severity") == "warning"]),
                "info": len([a for a in alerts if a.get("severity") == "info"])
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting webhook alerts: {str(e)}")
        return jsonify({"error": str(e)}), 500

@webhook_bp.route('/alerts/<alert_id>/dismiss', methods=['POST'])
def dismiss_webhook_alert(alert_id: str):
    """Dismiss a webhook alert"""
    try:
        if not webhook_handler:
            return jsonify({"error": "Webhook handler not initialized"}), 500
        
        # Dismiss alert
        success = webhook_handler.performance_monitor.dismiss_alert(alert_id)
        
        if success:
            return jsonify({"message": "Alert dismissed successfully"})
        else:
            return jsonify({"error": "Alert not found"}), 404
            
    except Exception as e:
        logger.error(f"Error dismissing webhook alert {alert_id}: {str(e)}")
        return jsonify({"error": str(e)}), 500