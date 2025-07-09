#!/usr/bin/env python3
"""
Preview collections that would be created based on product data
"""

import os
import psycopg2
from dotenv import load_dotenv
from collections import defaultdict

load_dotenv()

db_url = os.getenv('DATABASE_URL')
if db_url.startswith('postgresql+psycopg://'):
    db_url = db_url.replace('postgresql+psycopg://', 'postgresql://')

conn = psycopg2.connect(db_url)
cursor = conn.cursor()

print("🔍 COLLECTION CREATION PREVIEW")
print("=" * 80)

# Preview brand collections
print("\n📦 BRAND COLLECTIONS (vendors with 50+ products):")
print("-" * 80)
cursor.execute("""
    SELECT vendor, COUNT(*) as count 
    FROM products 
    WHERE vendor IS NOT NULL AND vendor != ''
    GROUP BY vendor 
    HAVING COUNT(*) >= 50
    ORDER BY count DESC
""")

total_brand_products = 0
brand_collections = cursor.fetchall()
for i, (vendor, count) in enumerate(brand_collections, 1):
    print(f"{i:3}. {vendor} Products ({count} items)")
    total_brand_products += count

print(f"\nTotal: {len(brand_collections)} brand collections covering {total_brand_products:,} products")

# Preview category collections based on patterns
print("\n\n🏷️ CATEGORY COLLECTIONS (based on product name patterns):")
print("-" * 80)

pattern_collections = [
    ("Pens & Writing Instruments", ["pen", "pencil", "marker", "highlighter"]),
    ("Paper Products", ["paper", "envelope", "pad", "notebook"]),
    ("Binders & Filing", ["binder", "folder", "portfolio", "file"]),
    ("Desk Accessories", ["stapler", "tape", "clip", "tray", "organizer", "dispenser"]),
    ("Technology & Computer Accessories", ["cable", "adapter", "mouse", "keyboard", "monitor", "printer", "usb"]),
    ("Office Furniture", ["chair", "desk", "table", "cabinet", "shelf"]),
    ("Cleaning & Janitorial", ["cleaner", "wipe", "sanitizer", "tissue", "soap"]),
    ("Labels & Tags", ["label", "tag", "sticker"]),
    ("Ink & Toner", ["ink", "toner", "cartridge", "refill"]),
    ("Storage Solutions", ["box", "storage", "container", "bin"])
]

for title, patterns in pattern_collections:
    # Count products matching patterns
    pattern_conditions = " OR ".join([f"LOWER(name) LIKE '%{p}%'" for p in patterns])
    cursor.execute(f"""
        SELECT COUNT(DISTINCT id) 
        FROM products 
        WHERE {pattern_conditions}
    """)
    count = cursor.fetchone()[0]
    print(f"{title:<40} (~{count:,} products)")

# Preview product type collections
print("\n\n🎯 PRODUCT TYPE COLLECTIONS (5+ products):")
print("-" * 80)
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
    print(f"{title:<40} ({count} products)")

# Summary
print("\n\n📊 SUMMARY:")
print("-" * 80)
print(f"Brand Collections:        {len(brand_collections)}")
print(f"Category Collections:     {len(pattern_collections)}")
print(f"Product Type Collections: {len(product_types)}")
print(f"Special Collections:      3 (New Arrivals, Best Sellers, Eco-Friendly)")
print(f"─" * 40)
print(f"TOTAL COLLECTIONS:        {len(brand_collections) + len(pattern_collections) + len(product_types) + 3}")

# Sample products for each category
print("\n\n📝 SAMPLE PRODUCTS FOR KEY CATEGORIES:")
print("-" * 80)

sample_categories = [
    ("Pens", "LOWER(name) LIKE '%pen%'"),
    ("Paper", "LOWER(name) LIKE '%paper%'"),
    ("Ink/Toner", "LOWER(name) LIKE '%ink%' OR LOWER(name) LIKE '%toner%'"),
    ("Technology", "LOWER(name) LIKE '%cable%' OR LOWER(name) LIKE '%usb%'")
]

for category, condition in sample_categories:
    print(f"\n{category}:")
    cursor.execute(f"""
        SELECT name, vendor, price 
        FROM products 
        WHERE {condition}
        ORDER BY RANDOM()
        LIMIT 3
    """)
    for name, vendor, price in cursor.fetchall():
        print(f"  • {name[:60]:<60} [{vendor}] ${price}")

cursor.close()
conn.close()

print("\n\n💡 RECOMMENDATIONS:")
print("-" * 80)
print("1. Start with brand collections (high product counts, clear organization)")
print("2. Category collections will help customers browse by product type")
print("3. Consider adding seasonal collections later")
print("4. Add collection images and SEO descriptions after creation")
print("5. Set up collection hierarchy in navigation menu")