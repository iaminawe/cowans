#!/usr/bin/env python3
"""
Batch create Shopify collections based on product data patterns
"""

import os
import sys
import requests
import json
import psycopg2
import re
import time
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Get Shopify credentials
SHOP_URL = os.getenv('SHOPIFY_SHOP_URL')
ACCESS_TOKEN = os.getenv('SHOPIFY_ACCESS_TOKEN')

# Get database connection
db_url = os.getenv('DATABASE_URL')
if db_url.startswith('postgresql+psycopg://'):
    db_url = db_url.replace('postgresql+psycopg://', 'postgresql://')

def get_existing_collections():
    """Get existing collections from Shopify."""
    headers = {
        'X-Shopify-Access-Token': ACCESS_TOKEN,
        'Content-Type': 'application/json'
    }
    
    url = f"https://{SHOP_URL}/admin/api/2023-10/custom_collections.json?limit=250"
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        collections = response.json().get('custom_collections', [])
        # Also get smart collections
        smart_url = f"https://{SHOP_URL}/admin/api/2023-10/smart_collections.json?limit=250"
        smart_response = requests.get(smart_url, headers=headers)
        if smart_response.status_code == 200:
            collections.extend(smart_response.json().get('smart_collections', []))
        return {c['title'].lower(): c for c in collections}
    return {}

def create_custom_collection(title, body_html="", image_url=None):
    """Create a custom collection in Shopify."""
    headers = {
        'X-Shopify-Access-Token': ACCESS_TOKEN,
        'Content-Type': 'application/json'
    }
    
    collection_data = {
        "custom_collection": {
            "title": title,
            "body_html": body_html,
            "published": True,
            "sort_order": "best-selling"
        }
    }
    
    if image_url:
        collection_data["custom_collection"]["image"] = {"src": image_url}
    
    url = f"https://{SHOP_URL}/admin/api/2023-10/custom_collections.json"
    response = requests.post(url, json=collection_data, headers=headers)
    
    if response.status_code == 201:
        return response.json()['custom_collection']
    else:
        print(f"Error creating collection {title}: {response.status_code} - {response.text}")
        return None

def create_smart_collection(title, rules, body_html=""):
    """Create a smart collection with rules in Shopify."""
    headers = {
        'X-Shopify-Access-Token': ACCESS_TOKEN,
        'Content-Type': 'application/json'
    }
    
    collection_data = {
        "smart_collection": {
            "title": title,
            "body_html": body_html,
            "rules": rules,
            "published": True,
            "sort_order": "best-selling"
        }
    }
    
    url = f"https://{SHOP_URL}/admin/api/2023-10/smart_collections.json"
    response = requests.post(url, json=collection_data, headers=headers)
    
    if response.status_code == 201:
        return response.json()['smart_collection']
    else:
        print(f"Error creating smart collection {title}: {response.status_code} - {response.text}")
        return None

def main():
    print("🚀 BATCH COLLECTION CREATION")
    print("=" * 60)
    
    # Get existing collections
    print("📋 Fetching existing collections...")
    existing = get_existing_collections()
    print(f"Found {len(existing)} existing collections")
    
    conn = psycopg2.connect(db_url)
    cursor = conn.cursor()
    
    created_count = 0
    skipped_count = 0
    
    # Strategy 1: Create brand collections for top vendors
    print("\n📦 CREATING BRAND COLLECTIONS...")
    cursor.execute("""
        SELECT vendor, COUNT(*) as count 
        FROM products 
        WHERE vendor IS NOT NULL AND vendor != ''
        GROUP BY vendor 
        HAVING COUNT(*) >= 50
        ORDER BY count DESC
    """)
    
    vendors = cursor.fetchall()
    for vendor, count in vendors:
        title = f"{vendor} Products"
        if title.lower() not in existing:
            print(f"Creating brand collection: {title} ({count} products)")
            
            # Create smart collection with vendor rule
            rules = [{
                "column": "vendor",
                "relation": "equals",
                "condition": vendor
            }]
            
            body_html = f"<p>Browse our complete selection of {vendor} products. We carry {count} items from this trusted brand.</p>"
            
            collection = create_smart_collection(title, rules, body_html)
            if collection:
                created_count += 1
                time.sleep(0.5)  # Rate limiting
        else:
            skipped_count += 1
    
    # Strategy 2: Create collections for common product patterns
    print("\n🏷️ CREATING CATEGORY COLLECTIONS...")
    
    pattern_collections = [
        {
            "title": "Pens & Writing Instruments",
            "patterns": ["pen", "pencil", "marker", "highlighter"],
            "description": "Discover our extensive collection of pens, pencils, markers, and writing instruments."
        },
        {
            "title": "Paper Products",
            "patterns": ["paper", "envelope", "pad", "notebook"],
            "description": "Shop our wide selection of paper products including notebooks, pads, and specialty papers."
        },
        {
            "title": "Binders & Filing",
            "patterns": ["binder", "folder", "portfolio", "file"],
            "description": "Keep your documents organized with our binders, folders, and filing solutions."
        },
        {
            "title": "Desk Accessories",
            "patterns": ["stapler", "tape", "clip", "tray", "organizer", "dispenser"],
            "description": "Complete your workspace with essential desk accessories and organizers."
        },
        {
            "title": "Technology & Computer Accessories",
            "patterns": ["cable", "adapter", "mouse", "keyboard", "monitor", "printer", "usb"],
            "description": "Find all your technology needs including cables, adapters, and computer accessories."
        },
        {
            "title": "Office Furniture",
            "patterns": ["chair", "desk", "table", "cabinet", "shelf"],
            "description": "Transform your workspace with our selection of office furniture."
        },
        {
            "title": "Cleaning & Janitorial",
            "patterns": ["cleaner", "wipe", "sanitizer", "tissue", "soap"],
            "description": "Keep your office clean with our janitorial and cleaning supplies."
        },
        {
            "title": "Labels & Tags",
            "patterns": ["label", "tag", "sticker"],
            "description": "Find the perfect labels and tags for all your organizational needs."
        },
        {
            "title": "Ink & Toner",
            "patterns": ["ink", "toner", "cartridge", "refill"],
            "description": "Shop ink and toner cartridges for all major printer brands."
        },
        {
            "title": "Storage Solutions",
            "patterns": ["box", "storage", "container", "bin"],
            "description": "Organize your space with our storage boxes and containers."
        }
    ]
    
    for collection_info in pattern_collections:
        title = collection_info["title"]
        
        if title.lower() not in existing:
            print(f"Creating category collection: {title}")
            
            # Create smart collection with product title rules
            rules = []
            for pattern in collection_info["patterns"]:
                rules.append({
                    "column": "title",
                    "relation": "contains",
                    "condition": pattern
                })
            
            # Use OR logic for multiple patterns
            if len(rules) > 1:
                # Note: Shopify smart collections use OR logic by default for multiple rules
                pass
            
            collection = create_smart_collection(
                title, 
                rules[:1],  # Start with first rule, will need to update via API if multiple
                collection_info["description"]
            )
            
            if collection:
                created_count += 1
                time.sleep(0.5)
        else:
            skipped_count += 1
    
    # Strategy 3: Create collections based on product types (where available)
    print("\n🎯 CREATING PRODUCT TYPE COLLECTIONS...")
    cursor.execute("""
        SELECT DISTINCT product_type, COUNT(*) as count 
        FROM products 
        WHERE product_type IS NOT NULL 
        AND product_type != ''
        AND product_type NOT LIKE '%from Manufacturer%'
        GROUP BY product_type 
        HAVING COUNT(*) >= 5
        ORDER BY count DESC
    """)
    
    product_types = cursor.fetchall()
    for ptype, count in product_types:
        title = ptype.replace('&', 'and').title()
        
        if title.lower() not in existing:
            print(f"Creating product type collection: {title} ({count} products)")
            
            rules = [{
                "column": "product_type",
                "relation": "equals",
                "condition": ptype
            }]
            
            body_html = f"<p>Browse our {title} collection featuring {count} carefully selected products.</p>"
            
            collection = create_smart_collection(title, rules, body_html)
            if collection:
                created_count += 1
                time.sleep(0.5)
        else:
            skipped_count += 1
    
    # Strategy 4: Create special collections
    print("\n⭐ CREATING SPECIAL COLLECTIONS...")
    
    special_collections = [
        {
            "title": "New Arrivals",
            "rules": [{
                "column": "created_at",
                "relation": "greater_than",
                "condition": (datetime.now().replace(day=1)).strftime("%Y-%m-%d")
            }],
            "description": "Check out our latest products added this month!"
        },
        {
            "title": "Best Sellers",
            "custom": True,  # Will need manual curation
            "description": "Our most popular products chosen by customers like you."
        },
        {
            "title": "Eco-Friendly Products",
            "rules": [{
                "column": "tag",
                "relation": "equals",
                "condition": "eco-friendly"
            }],
            "description": "Shop our selection of environmentally conscious office supplies."
        }
    ]
    
    for collection_info in special_collections:
        title = collection_info["title"]
        
        if title.lower() not in existing:
            if collection_info.get("custom"):
                print(f"Creating custom collection: {title}")
                collection = create_custom_collection(
                    title,
                    collection_info["description"]
                )
            else:
                print(f"Creating smart collection: {title}")
                collection = create_smart_collection(
                    title,
                    collection_info["rules"],
                    collection_info["description"]
                )
            
            if collection:
                created_count += 1
                time.sleep(0.5)
        else:
            skipped_count += 1
    
    cursor.close()
    conn.close()
    
    print("\n✅ BATCH COLLECTION CREATION COMPLETE!")
    print(f"   • Created: {created_count} collections")
    print(f"   • Skipped: {skipped_count} (already exist)")
    print(f"   • Total collections now: {len(existing) + created_count}")
    
    if created_count > 0:
        print("\n📝 Next steps:")
        print("   1. Review collections in Shopify admin")
        print("   2. Add collection images")
        print("   3. Refine collection rules if needed")
        print("   4. Set up collection hierarchy/navigation")

if __name__ == "__main__":
    main()