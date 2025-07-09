#!/usr/bin/env python3
"""
Analyze product types in the database for collection generation
"""

import psycopg2
import os
from dotenv import load_dotenv
from collections import Counter

load_dotenv()

# Get database connection
db_url = os.getenv('DATABASE_URL')
if db_url.startswith('postgresql+psycopg://'):
    db_url = db_url.replace('postgresql+psycopg://', 'postgresql://')

conn = psycopg2.connect(db_url)
cursor = conn.cursor()

print('=== PRODUCT TYPES ANALYSIS ===\n')

# Get all unique product types
cursor.execute("""
    SELECT DISTINCT product_type, COUNT(*) as count 
    FROM products 
    WHERE product_type IS NOT NULL AND product_type != ''
    GROUP BY product_type 
    ORDER BY count DESC
""")

product_types = cursor.fetchall()

print(f'Total unique product types: {len(product_types)}\n')
print('Top 30 Product Types:')
print('-' * 80)
print(f'{"#":>3}  {"Product Type":<50} {"Count":>10}  {"Potential Collection"}')
print('-' * 80)

for i, (ptype, count) in enumerate(product_types[:30]):
    # Suggest collection name
    collection_name = ptype.replace('&', 'and').title()
    print(f'{i+1:3}. {ptype[:50]:<50} {count:>10}  {collection_name}')

# Show all product types if not too many
if len(product_types) <= 50:
    print('\n\nALL Product Types:')
    print('-' * 80)
    for i, (ptype, count) in enumerate(product_types):
        collection_name = ptype.replace('&', 'and').title()
        print(f'{i+1:3}. {ptype[:50]:<50} {count:>10}  {collection_name}')

# Get products without product type
cursor.execute("""
    SELECT COUNT(*) FROM products 
    WHERE product_type IS NULL OR product_type = ''
""")
no_type_count = cursor.fetchone()[0]

print(f'\n\nSUMMARY:')
print(f'Products without product type: {no_type_count}')

# Get total products
cursor.execute('SELECT COUNT(*) FROM products')
total_products = cursor.fetchone()[0]

print(f'Total products: {total_products:,}')
print(f'Product type coverage: {((total_products - no_type_count) / total_products * 100):.1f}%')

# Check existing collections
cursor.execute("""
    SELECT COUNT(*) FROM categories 
    WHERE name LIKE '%Collection%' 
    OR name IN (SELECT DISTINCT name FROM categories WHERE parent_id IS NULL)
""")
collection_count = cursor.fetchone()[0]
print(f'\nExisting collections/top categories in DB: {collection_count}')

# Analyze product type patterns
print('\n\nPRODUCT TYPE PATTERNS:')
print('-' * 40)

# Count products by major category patterns
patterns = {
    'Pens & Writing': 0,
    'Paper Products': 0,
    'Office Supplies': 0,
    'Technology': 0,
    'Furniture': 0,
    'Cleaning': 0,
    'Food & Beverage': 0,
    'Other': 0
}

for ptype, count in product_types:
    ptype_lower = ptype.lower()
    if 'pen' in ptype_lower or 'pencil' in ptype_lower or 'marker' in ptype_lower:
        patterns['Pens & Writing'] += count
    elif 'paper' in ptype_lower or 'envelope' in ptype_lower or 'pad' in ptype_lower:
        patterns['Paper Products'] += count
    elif 'folder' in ptype_lower or 'binder' in ptype_lower or 'clip' in ptype_lower:
        patterns['Office Supplies'] += count
    elif 'computer' in ptype_lower or 'cable' in ptype_lower or 'electronic' in ptype_lower:
        patterns['Technology'] += count
    elif 'chair' in ptype_lower or 'desk' in ptype_lower or 'table' in ptype_lower:
        patterns['Furniture'] += count
    elif 'clean' in ptype_lower or 'soap' in ptype_lower or 'sanitizer' in ptype_lower:
        patterns['Cleaning'] += count
    elif 'coffee' in ptype_lower or 'tea' in ptype_lower or 'snack' in ptype_lower:
        patterns['Food & Beverage'] += count
    else:
        patterns['Other'] += count

for category, count in sorted(patterns.items(), key=lambda x: x[1], reverse=True):
    print(f'{category:<20} {count:>10,} products')

cursor.close()
conn.close()

print('\n\nRECOMMENDATION:')
print('You can create collections based on:')
print('1. Individual product types (for specific collections)')
print('2. Category patterns (for broader collections)')
print('3. Hybrid approach (main collections with sub-collections)')