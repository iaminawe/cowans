"""
Shopify Collections Integration Module

This module provides functionality to interact with Shopify collections,
including fetching collections, uploading icons, and updating collection metadata.
"""

import os
import sys
import logging
import base64
import json
import requests
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

# Add the parent directory to the path to import shopify modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scripts.shopify.shopify_base import ShopifyAPIBase

# Configure logging
logger = logging.getLogger(__name__)

# GraphQL Queries for Collections
GET_COLLECTIONS_QUERY = """
query getCollections($first: Int!, $after: String) {
  collections(first: $first, after: $after) {
    edges {
      node {
        id
        handle
        title
        description
        descriptionHtml
        updatedAt
        image {
          id
          url
          altText
          width
          height
        }
        products(first: 1) {
          edges {
            node {
              id
            }
          }
        }
        productsCount {
          count
        }
        seo {
          title
          description
        }
        sortOrder
        templateSuffix
        metafields(first: 10) {
          edges {
            node {
              id
              namespace
              key
              value
              type
            }
          }
        }
      }
      cursor
    }
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}
"""

UPDATE_COLLECTION_IMAGE_MUTATION = """
mutation updateCollectionImage($input: CollectionInput!) {
  collectionUpdate(input: $input) {
    collection {
      id
      handle
      title
      image {
        id
        url
        altText
      }
    }
    userErrors {
      field
      message
    }
  }
}
"""

CREATE_COLLECTION_METAFIELD_MUTATION = """
mutation createCollectionMetafield($id: ID!, $metafields: [MetafieldInput!]!) {
  collectionUpdate(input: { id: $id, metafields: $metafields }) {
    collection {
      id
      metafields(first: 10) {
        edges {
          node {
            id
            namespace
            key
            value
            type
          }
        }
      }
    }
    userErrors {
      field
      message
    }
  }
}
"""

CREATE_STAGED_UPLOAD_MUTATION = """
mutation stagedUploadsCreate($input: [StagedUploadInput!]!) {
  stagedUploadsCreate(input: $input) {
    stagedTargets {
      url
      resourceUrl
      parameters {
        name
        value
      }
    }
    userErrors {
      field
      message
    }
  }
}
"""

CREATE_COLLECTION_MUTATION = """
mutation createCollection($input: CollectionInput!) {
  collectionCreate(input: $input) {
    collection {
      id
      handle
      title
      description
      sortOrder
      templateSuffix
    }
    userErrors {
      field
      message
    }
  }
}
"""

UPDATE_COLLECTION_MUTATION = """
mutation updateCollection($input: CollectionInput!) {
  collectionUpdate(input: $input) {
    collection {
      id
      handle
      title
      description
      sortOrder
      templateSuffix
    }
    userErrors {
      field
      message
    }
  }
}
"""

ADD_PRODUCTS_TO_COLLECTION_MUTATION = """
mutation addProductsToCollection($id: ID!, $productIds: [ID!]!) {
  collectionAddProducts(id: $id, productIds: $productIds) {
    collection {
      id
      handle
      title
      productsCount {
        count
      }
    }
    userErrors {
      field
      message
    }
  }
}
"""

REMOVE_PRODUCTS_FROM_COLLECTION_MUTATION = """
mutation removeProductsFromCollection($id: ID!, $productIds: [ID!]!) {
  collectionRemoveProducts(id: $id, productIds: $productIds) {
    collection {
      id
      handle
      title
      productsCount {
        count
      }
    }
    userErrors {
      field
      message
    }
  }
}
"""

class ShopifyCollectionsManager(ShopifyAPIBase):
    """Manages Shopify collections, including icon uploads and metadata updates."""
    
    def __init__(self, shop_url: str, access_token: str, debug: bool = False):
        """Initialize the collections manager."""
        super().__init__(shop_url, access_token, debug)
        self.logger = logging.getLogger(self.__class__.__name__)
        
    def get_all_collections(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Fetch all collections from Shopify.
        
        Args:
            limit: Number of collections to fetch per page
            
        Returns:
            List of collection dictionaries
        """
        collections = []
        cursor = None
        
        try:
            while True:
                variables = {
                    "first": min(limit, 250),
                    "after": cursor
                }
                
                result = self.execute_graphql(GET_COLLECTIONS_QUERY, variables)
                
                if 'errors' in result:
                    self.logger.error(f"GraphQL errors: {result['errors']}")
                    break
                
                edges = result.get('data', {}).get('collections', {}).get('edges', [])
                page_info = result.get('data', {}).get('collections', {}).get('pageInfo', {})
                
                for edge in edges:
                    collection = edge['node']
                    # Extract Shopify ID from GraphQL ID
                    collection['numeric_id'] = collection['id'].split('/')[-1]
                    collections.append(collection)
                
                if not page_info.get('hasNextPage'):
                    break
                    
                cursor = page_info.get('endCursor')
                
            self.logger.info(f"Fetched {len(collections)} collections")
            return collections
            
        except Exception as e:
            self.logger.error(f"Error fetching collections: {str(e)}")
            raise
    
    def upload_collection_icon(self, collection_id: str, image_path: str, alt_text: Optional[str] = None) -> Dict[str, Any]:
        """
        Upload an icon image for a collection.
        
        Args:
            collection_id: Shopify collection ID (GraphQL format)
            image_path: Local path to the image file
            alt_text: Alternative text for the image
            
        Returns:
            Dictionary with upload result
        """
        try:
            # Read the image file
            with open(image_path, 'rb') as f:
                image_data = f.read()
            
            # Get file info
            file_name = os.path.basename(image_path)
            file_size = len(image_data)
            mime_type = 'image/png' if image_path.endswith('.png') else 'image/jpeg'
            
            # Create staged upload
            staged_upload_input = {
                "resource": "COLLECTION_IMAGE",
                "filename": file_name,
                "mimeType": mime_type,
                "fileSize": str(file_size)
            }
            
            result = self.execute_graphql(CREATE_STAGED_UPLOAD_MUTATION, {"input": [staged_upload_input]})
            
            if 'errors' in result or result.get('data', {}).get('stagedUploadsCreate', {}).get('userErrors'):
                errors = result.get('errors', []) or result.get('data', {}).get('stagedUploadsCreate', {}).get('userErrors', [])
                self.logger.error(f"Staged upload error: {errors}")
                return {"success": False, "error": str(errors)}
            
            staged_target = result['data']['stagedUploadsCreate']['stagedTargets'][0]
            upload_url = staged_target['url']
            resource_url = staged_target['resourceUrl']
            upload_params = {param['name']: param['value'] for param in staged_target['parameters']}
            
            # Upload the file
            files = {'file': (file_name, image_data, mime_type)}
            response = requests.post(upload_url, data=upload_params, files=files)
            
            if response.status_code not in [200, 201, 204]:
                self.logger.error(f"File upload failed: {response.status_code} - {response.text}")
                return {"success": False, "error": f"Upload failed: {response.status_code}"}
            
            # Update collection with the uploaded image
            update_input = {
                "id": collection_id,
                "image": {
                    "src": resource_url
                }
            }
            
            if alt_text:
                update_input["image"]["altText"] = alt_text
            
            update_result = self.execute_graphql(UPDATE_COLLECTION_IMAGE_MUTATION, {"input": update_input})
            
            if 'errors' in update_result or update_result.get('data', {}).get('collectionUpdate', {}).get('userErrors'):
                errors = update_result.get('errors', []) or update_result.get('data', {}).get('collectionUpdate', {}).get('userErrors', [])
                self.logger.error(f"Collection update error: {errors}")
                return {"success": False, "error": str(errors)}
            
            collection = update_result['data']['collectionUpdate']['collection']
            self.logger.info(f"Successfully uploaded icon for collection {collection['title']}")
            
            return {
                "success": True,
                "collection": collection,
                "image_url": collection['image']['url'] if collection.get('image') else None
            }
            
        except Exception as e:
            self.logger.error(f"Error uploading collection icon: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def update_collection_metadata(self, collection_id: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update collection metafields with icon generation metadata.
        
        Args:
            collection_id: Shopify collection ID (GraphQL format)
            metadata: Dictionary of metadata to store
            
        Returns:
            Dictionary with update result
        """
        try:
            # Prepare metafields
            metafields = []
            
            # Store icon generation metadata
            if 'icon_style' in metadata:
                metafields.append({
                    "namespace": "icon_generator",
                    "key": "style",
                    "value": metadata['icon_style'],
                    "type": "single_line_text_field"
                })
            
            if 'icon_color' in metadata:
                metafields.append({
                    "namespace": "icon_generator",
                    "key": "color",
                    "value": metadata['icon_color'],
                    "type": "single_line_text_field"
                })
            
            if 'generated_at' in metadata:
                metafields.append({
                    "namespace": "icon_generator",
                    "key": "generated_at",
                    "value": metadata['generated_at'],
                    "type": "single_line_text_field"
                })
            
            if 'keywords' in metadata:
                metafields.append({
                    "namespace": "icon_generator",
                    "key": "keywords",
                    "value": json.dumps(metadata['keywords']),
                    "type": "json"
                })
            
            if not metafields:
                return {"success": True, "message": "No metadata to update"}
            
            # Update collection metafields
            result = self.execute_graphql(
                CREATE_COLLECTION_METAFIELD_MUTATION,
                {"id": collection_id, "metafields": metafields}
            )
            
            if 'errors' in result or result.get('data', {}).get('collectionUpdate', {}).get('userErrors'):
                errors = result.get('errors', []) or result.get('data', {}).get('collectionUpdate', {}).get('userErrors', [])
                self.logger.error(f"Metafield update error: {errors}")
                return {"success": False, "error": str(errors)}
            
            collection = result['data']['collectionUpdate']['collection']
            self.logger.info(f"Successfully updated metadata for collection {collection['id']}")
            
            return {
                "success": True,
                "collection_id": collection['id'],
                "metafields": collection.get('metafields', {})
            }
            
        except Exception as e:
            self.logger.error(f"Error updating collection metadata: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def get_collection_by_handle(self, handle: str) -> Optional[Dict[str, Any]]:
        """
        Fetch a single collection by its handle.
        
        Args:
            handle: Collection handle
            
        Returns:
            Collection dictionary or None if not found
        """
        query = """
        query getCollectionByHandle($handle: String!) {
          collectionByHandle(handle: $handle) {
            id
            handle
            title
            description
            image {
              id
              url
              altText
            }
            productsCount {
              count
            }
            metafields(first: 10) {
              edges {
                node {
                  namespace
                  key
                  value
                  type
                }
              }
            }
          }
        }
        """
        
        try:
            result = self.execute_graphql(query, {"handle": handle})
            
            if 'errors' in result:
                self.logger.error(f"GraphQL errors: {result['errors']}")
                return None
            
            collection = result.get('data', {}).get('collectionByHandle')
            if collection:
                collection['numeric_id'] = collection['id'].split('/')[-1]
                
            return collection
            
        except Exception as e:
            self.logger.error(f"Error fetching collection by handle: {str(e)}")
            return None
    
    def create_collection(self, collection_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new collection in Shopify.
        
        Args:
            collection_data: Dictionary containing collection information
            
        Returns:
            Dictionary with creation result
        """
        try:
            # Prepare collection input
            collection_input = {
                "title": collection_data.get("title", ""),
                "handle": collection_data.get("handle", ""),
                "description": collection_data.get("description", ""),
                "sortOrder": collection_data.get("sortOrder", "BEST_SELLING"),
            }
            
            # Add optional fields
            if "templateSuffix" in collection_data:
                collection_input["templateSuffix"] = collection_data["templateSuffix"]
            
            # Add SEO data if provided
            if "seo" in collection_data:
                collection_input["seo"] = collection_data["seo"]
            
            # Add metafields if provided
            if "metafields" in collection_data:
                collection_input["metafields"] = collection_data["metafields"]
            
            # Execute the mutation
            result = self.execute_graphql(CREATE_COLLECTION_MUTATION, {"input": collection_input})
            
            if 'errors' in result:
                self.logger.error(f"GraphQL errors: {result['errors']}")
                return {"success": False, "error": str(result['errors'])}
            
            collection_result = result.get('data', {}).get('collectionCreate', {})
            
            if collection_result.get('userErrors'):
                self.logger.error(f"User errors: {collection_result['userErrors']}")
                return {"success": False, "error": str(collection_result['userErrors'])}
            
            collection = collection_result.get('collection', {})
            collection['numeric_id'] = collection['id'].split('/')[-1]
            
            self.logger.info(f"Successfully created collection: {collection['title']}")
            
            return {
                "success": True,
                "collection": collection
            }
            
        except Exception as e:
            self.logger.error(f"Error creating collection: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def update_collection(self, collection_id: str, collection_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update an existing collection in Shopify.
        
        Args:
            collection_id: Shopify collection ID (GraphQL format)
            collection_data: Dictionary containing updated collection information
            
        Returns:
            Dictionary with update result
        """
        try:
            # Prepare collection input
            collection_input = {
                "id": collection_id
            }
            
            # Add fields to update
            if "title" in collection_data:
                collection_input["title"] = collection_data["title"]
            
            if "handle" in collection_data:
                collection_input["handle"] = collection_data["handle"]
            
            if "description" in collection_data:
                collection_input["description"] = collection_data["description"]
            
            if "sortOrder" in collection_data:
                collection_input["sortOrder"] = collection_data["sortOrder"]
            
            if "templateSuffix" in collection_data:
                collection_input["templateSuffix"] = collection_data["templateSuffix"]
            
            if "seo" in collection_data:
                collection_input["seo"] = collection_data["seo"]
            
            if "metafields" in collection_data:
                collection_input["metafields"] = collection_data["metafields"]
            
            # Execute the mutation
            result = self.execute_graphql(UPDATE_COLLECTION_MUTATION, {"input": collection_input})
            
            if 'errors' in result:
                self.logger.error(f"GraphQL errors: {result['errors']}")
                return {"success": False, "error": str(result['errors'])}
            
            collection_result = result.get('data', {}).get('collectionUpdate', {})
            
            if collection_result.get('userErrors'):
                self.logger.error(f"User errors: {collection_result['userErrors']}")
                return {"success": False, "error": str(collection_result['userErrors'])}
            
            collection = collection_result.get('collection', {})
            collection['numeric_id'] = collection['id'].split('/')[-1]
            
            self.logger.info(f"Successfully updated collection: {collection['title']}")
            
            return {
                "success": True,
                "collection": collection
            }
            
        except Exception as e:
            self.logger.error(f"Error updating collection: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def add_products_to_collection(self, collection_id: str, product_ids: List[str]) -> Dict[str, Any]:
        """
        Add products to a collection.
        
        Args:
            collection_id: Shopify collection ID (GraphQL format)
            product_ids: List of Shopify product IDs (GraphQL format)
            
        Returns:
            Dictionary with operation result
        """
        try:
            result = self.execute_graphql(
                ADD_PRODUCTS_TO_COLLECTION_MUTATION,
                {"id": collection_id, "productIds": product_ids}
            )
            
            if 'errors' in result:
                self.logger.error(f"GraphQL errors: {result['errors']}")
                return {"success": False, "error": str(result['errors'])}
            
            collection_result = result.get('data', {}).get('collectionAddProducts', {})
            
            if collection_result.get('userErrors'):
                self.logger.error(f"User errors: {collection_result['userErrors']}")
                return {"success": False, "error": str(collection_result['userErrors'])}
            
            collection = collection_result.get('collection', {})
            
            self.logger.info(f"Successfully added {len(product_ids)} products to collection {collection['title']}")
            
            return {
                "success": True,
                "collection": collection,
                "products_added": len(product_ids)
            }
            
        except Exception as e:
            self.logger.error(f"Error adding products to collection: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def remove_products_from_collection(self, collection_id: str, product_ids: List[str]) -> Dict[str, Any]:
        """
        Remove products from a collection.
        
        Args:
            collection_id: Shopify collection ID (GraphQL format)
            product_ids: List of Shopify product IDs (GraphQL format)
            
        Returns:
            Dictionary with operation result
        """
        try:
            result = self.execute_graphql(
                REMOVE_PRODUCTS_FROM_COLLECTION_MUTATION,
                {"id": collection_id, "productIds": product_ids}
            )
            
            if 'errors' in result:
                self.logger.error(f"GraphQL errors: {result['errors']}")
                return {"success": False, "error": str(result['errors'])}
            
            collection_result = result.get('data', {}).get('collectionRemoveProducts', {})
            
            if collection_result.get('userErrors'):
                self.logger.error(f"User errors: {collection_result['userErrors']}")
                return {"success": False, "error": str(collection_result['userErrors'])}
            
            collection = collection_result.get('collection', {})
            
            self.logger.info(f"Successfully removed {len(product_ids)} products from collection {collection['title']}")
            
            return {
                "success": True,
                "collection": collection,
                "products_removed": len(product_ids)
            }
            
        except Exception as e:
            self.logger.error(f"Error removing products from collection: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def sync_category_to_collection(self, category: Dict[str, Any], product_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Sync a local category to Shopify as a collection.
        
        Args:
            category: Category data from local database
            product_ids: Optional list of product IDs to add to the collection
            
        Returns:
            Dictionary with sync result
        """
        try:
            # Check if collection already exists
            existing_collection = None
            if category.get('shopify_collection_id'):
                # Try to get existing collection to verify it still exists
                collections = self.get_all_collections()
                existing_collection = next(
                    (col for col in collections if col['id'] == category['shopify_collection_id']),
                    None
                )
            
            # Prepare collection data
            collection_data = {
                "title": category.get("name", ""),
                "handle": category.get("slug", "").replace("_", "-"),
                "description": category.get("description", ""),
                "sortOrder": "BEST_SELLING"
            }
            
            # Add metafields for category tracking
            metafields = [
                {
                    "namespace": "category_sync",
                    "key": "local_category_id",
                    "value": str(category.get("id", "")),
                    "type": "single_line_text_field"
                },
                {
                    "namespace": "category_sync",
                    "key": "synced_at",
                    "value": datetime.utcnow().isoformat(),
                    "type": "single_line_text_field"
                }
            ]
            
            collection_data["metafields"] = metafields
            
            # Create or update collection
            if existing_collection:
                result = self.update_collection(category['shopify_collection_id'], collection_data)
            else:
                result = self.create_collection(collection_data)
            
            if not result.get("success"):
                return result
            
            collection = result["collection"]
            
            # Add products to collection if provided
            if product_ids:
                add_result = self.add_products_to_collection(collection["id"], product_ids)
                if not add_result.get("success"):
                    self.logger.warning(f"Failed to add products to collection: {add_result.get('error')}")
            
            return {
                "success": True,
                "collection": collection,
                "operation": "updated" if existing_collection else "created"
            }
            
        except Exception as e:
            self.logger.error(f"Error syncing category to collection: {str(e)}")
            return {"success": False, "error": str(e)}