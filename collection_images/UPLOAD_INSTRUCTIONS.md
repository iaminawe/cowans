# Collection Image Upload Instructions

## Automated Upload (via Shopify Admin API)

The migration script will attempt to upload these images automatically.

## Manual Upload (via Shopify Admin)

If automatic upload fails, you can manually upload images:

1. Go to Shopify Admin > Collections
2. Find each collection by handle (filename without extension)
3. Click 'Edit collection'
4. Upload the corresponding image file
5. Set the alt text from the _metadata.txt file

## File Naming Convention

- Image files: `{collection-handle}.{extension}`
- Metadata files: `{collection-handle}_metadata.txt`
