#!/bin/bash

# Update Collections with Descriptions and SEO
# Run this script to add missing descriptions and SEO to collections

source .env

echo "📝 Updating collection descriptions..."
python scripts/shopify/update_collections_descriptions.py \
  --shop-url "$SHOPIFY_SHOP_URL" \
  --access-token "$SHOPIFY_ACCESS_TOKEN" \
  --input-file old_shopify_complete_collections/collections_metadata.csv

echo ""
echo "🔍 Updating collection SEO..."
python scripts/shopify/update_collections_seo.py \
  --shop-url "$SHOPIFY_SHOP_URL" \
  --access-token "$SHOPIFY_ACCESS_TOKEN" \
  --input-file old_shopify_complete_collections/collections_seo.csv

echo ""
echo "✅ Done! Check your collections in Shopify admin."