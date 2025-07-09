#!/bin/bash

# Complete Shopify Collections Migration Script
# This script migrates collections from old to new Shopify store

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Load environment variables
source .env

# Check if required variables are set
if [ -z "$OLD_SHOPIFY_SHOP_URL" ] || [ -z "$OLD_SHOPIFY_ADMIN_API_KEY" ] || [ -z "$SHOPIFY_SHOP_URL" ] || [ -z "$SHOPIFY_ACCESS_TOKEN" ]; then
    echo -e "${RED}Error: Required environment variables not set${NC}"
    echo "Please ensure the following are set in your .env file:"
    echo "  OLD_SHOPIFY_SHOP_URL"
    echo "  OLD_SHOPIFY_ADMIN_API_KEY"
    echo "  SHOPIFY_SHOP_URL"
    echo "  SHOPIFY_ACCESS_TOKEN"
    exit 1
fi

echo -e "${GREEN}🚀 Starting Complete Collection Migration${NC}"
echo "From: $OLD_SHOPIFY_SHOP_URL"
echo "To: $SHOPIFY_SHOP_URL"
echo ""

# Step 1: Export collections from old store
echo -e "${YELLOW}Step 1: Exporting collections from old store...${NC}"
python scripts/shopify/export_complete_collections_simple.py \
  --shop-url "$OLD_SHOPIFY_SHOP_URL" \
  --access-token "$OLD_SHOPIFY_ADMIN_API_KEY" \
  --output-dir old_shopify_complete_collections

if [ $? -ne 0 ]; then
    echo -e "${RED}Export failed!${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Export completed${NC}"
echo ""

# Step 2: Download collection images
echo -e "${YELLOW}Step 2: Downloading collection images...${NC}"
python scripts/shopify/download_collection_images.py \
  --input-file old_shopify_complete_collections/collections_images.csv \
  --output-dir collection_images

if [ $? -ne 0 ]; then
    echo -e "${RED}Image download failed!${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Images downloaded${NC}"
echo ""

# Step 3: Create collections on new store
echo -e "${YELLOW}Step 3: Creating collections on new store...${NC}"
python scripts/shopify/migrate_collections.py \
  --shop-url "$SHOPIFY_SHOP_URL" \
  --access-token "$SHOPIFY_ACCESS_TOKEN" \
  --input-dir old_shopify_complete_collections \
  --images-dir collection_images

if [ $? -ne 0 ]; then
    echo -e "${RED}Collection creation failed!${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Collections created${NC}"
echo ""

# Step 4: Update collection images
echo -e "${YELLOW}Step 4: Updating collection images...${NC}"
python scripts/shopify/update_collections_images.py \
  --shop-url "$SHOPIFY_SHOP_URL" \
  --access-token "$SHOPIFY_ACCESS_TOKEN" \
  --input-file old_shopify_complete_collections/collections_images.csv

if [ $? -ne 0 ]; then
    echo -e "${RED}Image update failed!${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Images updated${NC}"
echo ""

# Step 5: Update collection SEO
echo -e "${YELLOW}Step 5: Updating collection SEO...${NC}"
python scripts/shopify/update_collections_seo.py \
  --shop-url "$SHOPIFY_SHOP_URL" \
  --access-token "$SHOPIFY_ACCESS_TOKEN" \
  --input-file old_shopify_complete_collections/collections_seo.csv

if [ $? -ne 0 ]; then
    echo -e "${RED}SEO update failed!${NC}"
    exit 1
fi

echo -e "${GREEN}✓ SEO updated${NC}"
echo ""

echo -e "${GREEN}🎉 Collection migration completed!${NC}"
echo ""
echo "Next steps:"
echo "1. Review collections in Shopify admin"
echo "2. Import products to the new store"
echo "3. Run product-collection associations:"
echo ""
echo "   python scripts/shopify/add_products_to_collections.py \\"
echo "     --shop-url $SHOPIFY_SHOP_URL \\"
echo "     --access-token $SHOPIFY_ACCESS_TOKEN \\"
echo "     --associations product_collection_associations.csv"
echo ""
echo "Files generated:"
echo "  - collection_mapping.json (old handle → new ID mapping)"
echo "  - product_collection_associations.csv (for adding products later)"