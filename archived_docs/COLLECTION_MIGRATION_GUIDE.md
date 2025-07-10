# Shopify Collection Migration Guide

This guide walks you through migrating collections from one Shopify store to another, including all metadata, images, SEO settings, and product associations.

## Prerequisites

- Python 3.7+
- Access tokens for both old and new Shopify stores
- Exported collection data from the old store

## Step 1: Export Collection Data from Old Store

First, export all collection data from your old Shopify store:

```bash
python scripts/shopify/export_complete_collections_simple.py \
  --shop-url OLD_STORE.myshopify.com \
  --access-token OLD_ACCESS_TOKEN \
  --output-dir old_shopify_complete_collections
```

This creates the following files:
- `collections_metadata.csv` - Core collection properties
- `collections_products.csv` - Product-collection relationships  
- `collections_seo.csv` - SEO metadata
- `collections_images.csv` - Collection images
- `collections_summary.csv` - Overview data
- `collections_complete.json` - Complete raw data

## Step 2: Download Collection Images

Download all collection images locally for upload to the new store:

```bash
python scripts/shopify/download_collection_images.py \
  --input-file old_shopify_complete_collections/collections_images.csv \
  --output-dir collection_images
```

This will:
- Download all collection images
- Save them with descriptive filenames
- Create metadata files for each image
- Generate upload instructions

## Step 3: Create Collections on New Store

Run the migration script to create all collections on the new store:

```bash
python scripts/shopify/migrate_collections.py \
  --shop-url NEW_STORE.myshopify.com \
  --access-token NEW_ACCESS_TOKEN \
  --input-dir old_shopify_complete_collections \
  --images-dir collection_images
```

This will:
- Create all collections with proper metadata
- Set SEO titles and descriptions
- Apply sort orders and templates
- Upload collection images (where possible)
- Generate `collection_mapping.json` (old handle → new ID mapping)
- Generate `product_collection_associations.csv` for the next step

## Step 4: Add Products to Collections

After creating products on the new store, add them to the appropriate collections:

```bash
python scripts/shopify/add_products_to_collections.py \
  --shop-url NEW_STORE.myshopify.com \
  --access-token NEW_ACCESS_TOKEN \
  --associations product_collection_associations.csv \
  --batch-size 100
```

This will:
- Add products to their respective collections
- Maintain product positions in manual collections
- Process in efficient batches

## Manual Steps

### 1. Upload Collection Images (if automatic upload fails)

If automatic image upload fails, manually upload images:

1. Go to Shopify Admin > Collections
2. Find each collection by handle
3. Click "Edit collection"
4. Upload the corresponding image from `collection_images/`
5. Set alt text from the `_metadata.txt` file

### 2. Create Smart Collections

The current scripts create all collections as manual collections. To recreate smart collections:

1. Identify smart collections from the old store
2. Manually recreate the rules in the new store admin
3. Products will be automatically added based on the rules

### 3. Verify Collection Settings

After migration, verify:
- Collection descriptions are formatted correctly
- SEO settings are applied
- Sort orders are correct
- Template suffixes are set (if using custom templates)

## Troubleshooting

### "Collection already exists" errors
- The script will skip existing collections
- Check `collection_mapping.json` for successful mappings

### Missing products in collections
- Ensure products exist in the new store first
- Product handles must match exactly
- Check the script logs for specific errors

### Image upload failures
- Check file permissions in the images directory
- Verify image URLs are still accessible
- Use manual upload as fallback

## Example Workflow

```bash
# 1. Export from old store
python scripts/shopify/export_complete_collections_simple.py \
  --shop-url cowan-office-supplies.myshopify.com \
  --access-token YOUR_SHOPIFY_ACCESS_TOKEN \
  --output-dir old_collections

# 2. Download images
python scripts/shopify/download_collection_images.py \
  --input-file old_collections/collections_images.csv

# 3. Create collections on new store
python scripts/shopify/migrate_collections.py \
  --shop-url e19833-4.myshopify.com \
  --access-token YOUR_SHOPIFY_ACCESS_TOKEN \
  --input-dir old_collections

# 4. Add products to collections
python scripts/shopify/add_products_to_collections.py \
  --shop-url e19833-4.myshopify.com \
  --access-token YOUR_SHOPIFY_ACCESS_TOKEN
```

## Notes

- The migration preserves most collection data except:
  - Smart collection rules (must be recreated manually)
  - Collection metafields (require separate migration)
  - Publication status per sales channel
  
- Always test with a few collections first before running the full migration

- Keep the exported data and mapping files as backup

## Support Files Generated

- `collection_mapping.json` - Maps old handles to new collection IDs
- `product_collection_associations.csv` - Simplified CSV for product associations
- `collection_images/UPLOAD_INSTRUCTIONS.md` - Detailed image upload guide