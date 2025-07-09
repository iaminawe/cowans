#!/usr/bin/env python3
"""
Analyze alternative categorization options for creating collections
"""

import psycopg2
import os
from dotenv import load_dotenv
import re

load_dotenv()

db_url = os.getenv('DATABASE_URL')
if db_url.startswith('postgresql+psycopg://'):
    db_url = db_url.replace('postgresql+psycopg://', 'postgresql://')

conn = psycopg2.connect(db_url)
cursor = conn.cursor()

print('=== ALTERNATIVE CATEGORIZATION OPTIONS ===\n')

# Check vendors
cursor.execute("""
    SELECT vendor, COUNT(*) as count 
    FROM products 
    WHERE vendor IS NOT NULL AND vendor != ''
    GROUP BY vendor 
    ORDER BY count DESC 
    LIMIT 20
""")

print('TOP VENDORS (potential brand collections):')
print('-' * 60)
vendors = cursor.fetchall()
for vendor, count in vendors:
    print(f'  {vendor:<40} {count:>6} products')

# Check tags
cursor.execute("""
    SELECT tags, COUNT(*) as count
    FROM products 
    WHERE tags IS NOT NULL AND tags != ''
    GROUP BY tags
    ORDER BY count DESC
    LIMIT 10
""")
print('\n\nSAMPLE TAGS:')
print('-' * 60)
tags = cursor.fetchall()
for tag, count in tags[:5]:
    print(f'  {tag[:80]:<80} {count:>6} products')

# Check how many products have tags
cursor.execute("""
    SELECT COUNT(*) FROM products WHERE tags IS NOT NULL AND tags != ''
""")
tags_count = cursor.fetchone()[0]
print(f'\nTotal products with tags: {tags_count}')

# Check categories
cursor.execute("""
    SELECT c.name, c.id, COUNT(p.id) as product_count
    FROM categories c
    LEFT JOIN products p ON p.category_id = c.id
    GROUP BY c.id, c.name
    ORDER BY product_count DESC
    LIMIT 30
""")

print('\n\nEXISTING CATEGORIES (from category_id):')
print('-' * 60)
categories = cursor.fetchall()
for cat_name, cat_id, count in categories:
    print(f'  [{cat_id:3}] {cat_name:<40} {count:>6} products')

# Analyze product names for patterns
cursor.execute("""
    SELECT name FROM products 
    ORDER BY RANDOM()
    LIMIT 200
""")

print('\n\nPRODUCT NAME PATTERN ANALYSIS:')
print('-' * 60)

product_names = [row[0] for row in cursor.fetchall()]

# Common patterns in product names
patterns = {
    'Pens/Pencils': r'\b(pen|pencil|marker|highlighter)\b',
    'Paper Products': r'\b(paper|envelope|pad|notebook|sheet)\b',
    'Binders/Folders': r'\b(binder|folder|portfolio|file)\b',
    'Desk Accessories': r'\b(stapler|tape|clip|tray|organizer)\b',
    'Technology': r'\b(cable|adapter|mouse|keyboard|monitor|printer)\b',
    'Furniture': r'\b(chair|desk|table|cabinet|shelf)\b',
    'Cleaning': r'\b(cleaner|wipe|sanitizer|tissue)\b',
    'Labels/Tags': r'\b(label|tag|sticker)\b',
    'Bags/Cases': r'\b(bag|case|pouch|backpack)\b',
    'Ink/Toner': r'\b(ink|toner|cartridge|refill)\b'
}

pattern_counts = {pattern: 0 for pattern in patterns}

for name in product_names:
    name_lower = name.lower()
    for pattern_name, pattern_regex in patterns.items():
        if re.search(pattern_regex, name_lower):
            pattern_counts[pattern_name] += 1

print('Product name patterns found (in 200 random samples):')
for pattern, count in sorted(pattern_counts.items(), key=lambda x: x[1], reverse=True):
    percentage = (count / 200) * 100
    print(f'  {pattern:<20} {count:>4} ({percentage:>5.1f}%)')

# Get a broader sample for better analysis
cursor.execute("""
    SELECT name FROM products LIMIT 1000
""")
all_names = [row[0] for row in cursor.fetchall()]

# Extract common words
word_freq = {}
for name in all_names:
    words = re.findall(r'\b\w+\b', name.lower())
    for word in words:
        if len(word) > 3 and word not in ['with', 'from', 'each', 'pack', 'box']:
            word_freq[word] = word_freq.get(word, 0) + 1

print('\n\nMOST COMMON WORDS IN PRODUCT NAMES:')
print('-' * 60)
sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:30]
for word, freq in sorted_words:
    print(f'  {word:<20} {freq:>4} occurrences')

cursor.close()
conn.close()

print('\n\nRECOMMENDATIONS FOR BATCH COLLECTION CREATION:')
print('=' * 60)
print('1. USE EXISTING CATEGORIES: Most products are already categorized')
print('2. CREATE VENDOR/BRAND COLLECTIONS: Strong vendor data available')
print('3. PARSE PRODUCT NAMES: Extract patterns for smart collections')
print('4. HYBRID APPROACH:')
print('   - Main collections from categories')
print('   - Sub-collections from product name patterns')
print('   - Brand collections from vendors')
print('   - Smart collections using tags + name patterns')