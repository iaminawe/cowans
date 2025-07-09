#!/bin/bash

# Associate Products with Collections
# Run this after importing products to the new store

source .env

echo "🔗 Associating products with collections..."
echo ""

# Check if the associations file exists
if [ ! -f "product_collection_associations.csv" ]; then
    echo "❌ Error: product_collection_associations.csv not found!"
    echo "This file should have been created when you ran the collection migration."
    exit 1
fi

# Run the association script
python scripts/shopify/add_products_to_collections.py \
  --shop-url "$SHOPIFY_SHOP_URL" \
  --access-token "$SHOPIFY_ACCESS_TOKEN" \
  --associations product_collection_associations.csv \
  --batch-size 100

echo ""
echo "✅ Product-collection associations complete!"
echo ""
echo "Note: This script will only work if:"
echo "1. The products exist in the new store with the same handles"
echo "2. The collections were created using the migration script"
echo "3. The product_collection_associations.csv file is present"