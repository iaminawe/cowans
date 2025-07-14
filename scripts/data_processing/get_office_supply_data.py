#!/usr/bin/env python3
"""Script to extract office supply collections and product types from the database."""

import sys
import os
from pathlib import Path

# Add project paths
project_root = Path(__file__).parent
backend_path = project_root / 'web_dashboard' / 'backend'
sys.path.insert(0, str(backend_path))

try:
    from database import db_session_scope, init_database
    from repositories.collection_repository import CollectionRepository
    
    # Initialize database
    init_database(create_tables=False)
    
    print("=== OFFICE SUPPLY DATA ANALYSIS ===\n")
    
    with db_session_scope() as session:
        repo = CollectionRepository(session)
        
        # Get product types summary
        try:
            product_types = repo.get_product_types_summary()
            print(f"=== PRODUCT TYPES ({len(product_types)} total) ===")
            
            # Sort by product count
            product_types.sort(key=lambda x: x['product_count'], reverse=True)
            
            for i, pt in enumerate(product_types[:25], 1):  # Top 25
                avg_price = pt['avg_price'] if pt['avg_price'] else 0
                print(f"{i:2d}. {pt['name']:<30} {pt['product_count']:>4} products (avg: ${avg_price:>6.2f})")
            
            if len(product_types) > 25:
                print(f"    ... and {len(product_types) - 25} more")
                
        except Exception as e:
            print(f"Error getting product types: {e}")
        
        # Get existing collections
        try:
            collections = repo.get_all_with_stats()
            print(f"\n=== EXISTING COLLECTIONS ({len(collections)} total) ===")
            
            # Sort by product count
            collections.sort(key=lambda x: x['products_count'], reverse=True)
            
            for i, col in enumerate(collections[:20], 1):  # Top 20
                status_emoji = "✅" if col['status'] == 'active' else "📝" if col['status'] == 'draft' else "❌"
                sync_status = "🔄" if col['shopify_collection_id'] else "❌"
                print(f"{i:2d}. {col['name']:<35} {col['products_count']:>4} products {status_emoji} {sync_status}")
            
            if len(collections) > 20:
                print(f"    ... and {len(collections) - 20} more")
                
        except Exception as e:
            print(f"Error getting collections: {e}")
        
        print("\n=== SUMMARY ===")
        print(f"Total Product Types: {len(product_types) if 'product_types' in locals() else 'N/A'}")
        print(f"Total Collections: {len(collections) if 'collections' in locals() else 'N/A'}")
        
        # Calculate some stats
        if 'product_types' in locals() and product_types:
            total_products = sum(pt['product_count'] for pt in product_types)
            avg_products_per_type = total_products / len(product_types)
            print(f"Total Products with Types: {total_products}")
            print(f"Average Products per Type: {avg_products_per_type:.1f}")

except ImportError as e:
    print(f"Import error: {e}")
    print("Make sure you're running from the project root directory")
except Exception as e:
    print(f"Error: {e}")