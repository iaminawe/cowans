"""
Xorosoft API Service - Integration with Xorosoft inventory API

This service provides methods to interact with the Xorosoft API for
product validation and inventory checking, replacing CSV-based lookups.
"""

import os
import base64
import logging
import requests
from typing import Dict, List, Optional, Any, Tuple, Set
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import json
from functools import lru_cache
import time


class MatchType(Enum):
    """Types of product matching."""
    SKU = "sku"
    BASE_PART_NUMBER = "base_part_number"
    CWS_A = "cws_a"
    CWS_CATALOG = "cws_catalog"
    SPRC = "sprc"


@dataclass
class XorosoftProduct:
    """Xorosoft product data structure."""
    item_number: str
    base_part_number: Optional[str]
    description: Optional[str]
    title: Optional[str]
    handle: Optional[str]
    unit_price: Optional[float]
    vendor_product_number: Optional[str]
    upc: Optional[str]
    product_code: Optional[str]
    variants: List[Dict[str, Any]]
    raw_data: Dict[str, Any]


@dataclass
class ProductMatch:
    """Result of a product match operation."""
    matched: bool
    match_type: Optional[MatchType]
    xorosoft_product: Optional[XorosoftProduct]
    matched_value: Optional[str]
    confidence_score: float


class XorosoftAPIService:
    """Service for interacting with Xorosoft API."""
    
    def __init__(self, api_key: Optional[str] = None, api_pass: Optional[str] = None):
        """Initialize Xorosoft API service."""
        self.api_key = api_key or os.getenv('XOROSOFT_API')
        self.api_pass = api_pass or os.getenv('XOROSOFT_PASS')
        self.base_url = "https://res.xorosoft.io/api/xerp"
        self.logger = logging.getLogger(__name__)
        
        if not self.api_key or not self.api_pass:
            raise ValueError("Missing Xorosoft API credentials")
        
        # Setup authentication
        auth_string = f"{self.api_key}:{self.api_pass}"
        auth_bytes = auth_string.encode('ascii')
        self.auth_header = f"Basic {base64.b64encode(auth_bytes).decode('ascii')}"
        
        # Cache configuration
        self._cache_ttl = 3600  # 1 hour cache
        self._last_cache_clear = datetime.now()
        
        # Rate limiting
        self._requests_per_second = 10
        self._last_request_time = 0
        
    def _get_headers(self) -> Dict[str, str]:
        """Get API request headers."""
        return {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Authorization': self.auth_header
        }
    
    def _rate_limit(self):
        """Apply rate limiting to API requests."""
        current_time = time.time()
        time_since_last_request = current_time - self._last_request_time
        min_interval = 1.0 / self._requests_per_second
        
        if time_since_last_request < min_interval:
            sleep_time = min_interval - time_since_last_request
            time.sleep(sleep_time)
        
        self._last_request_time = time.time()
    
    def _make_request(self, endpoint: str, method: str = 'GET', 
                     params: Optional[Dict] = None, 
                     json_data: Optional[Dict] = None) -> Optional[Dict]:
        """Make API request with error handling and rate limiting."""
        self._rate_limit()
        
        url = f"{self.base_url}/{endpoint}"
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=self._get_headers(), params=params)
            else:
                response = requests.post(url, headers=self._get_headers(), json=json_data)
            
            response.raise_for_status()
            
            if response.text.strip():
                return response.json()
            else:
                self.logger.warning(f"Empty response from {endpoint}")
                return None
                
        except requests.exceptions.RequestException as e:
            self.logger.error(f"API request failed for {endpoint}: {str(e)}")
            return None
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse JSON response from {endpoint}: {str(e)}")
            return None
    
    @lru_cache(maxsize=1000)
    def get_product_by_item_number(self, item_number: str) -> Optional[XorosoftProduct]:
        """Get product by exact ItemNumber match."""
        self.logger.debug(f"Looking up product by ItemNumber: {item_number}")
        
        # Try direct lookup first
        data = self._make_request(f"product/{item_number}")
        
        if data and 'product' in data:
            return self._parse_product(data['product'])
        
        # Fallback to search
        return self.search_products(item_number, search_field='ItemNumber')
    
    @lru_cache(maxsize=1000)
    def get_products_by_base_part_number(self, base_part_number: str) -> List[XorosoftProduct]:
        """Get all products matching a BasePartNumber."""
        self.logger.debug(f"Looking up products by BasePartNumber: {base_part_number}")
        
        data = self._make_request(
            'product/getfiltered',
            method='POST',
            json_data={
                'filter': {
                    'basePartNumber': base_part_number
                },
                'page': 1,
                'pageSize': 100
            }
        )
        
        if data and 'Data' in data:
            return [self._parse_product(p) for p in data['Data'] if p]
        
        return []
    
    def search_products(self, query: str, search_field: Optional[str] = None,
                       page: int = 1, page_size: int = 100) -> Optional[XorosoftProduct]:
        """Search for products with flexible criteria."""
        self.logger.debug(f"Searching products with query: {query}, field: {search_field}")
        
        # Build search parameters
        params = {
            'page': page,
            'pageSize': page_size
        }
        
        if search_field:
            params[search_field] = query
        else:
            params['query'] = query
        
        data = self._make_request('product/getproduct', params=params)
        
        if data and 'Data' in data and data['Data']:
            # Return first match for single product search
            return self._parse_product(data['Data'][0])
        
        return None
    
    def validate_product(self, sku: str, metafields: Optional[Dict[str, str]] = None) -> ProductMatch:
        """
        Validate if a product exists in Xorosoft inventory.
        
        Args:
            sku: Product SKU to validate
            metafields: Optional metafields to check (CWS_A, CWS_Catalog, SPRC)
            
        Returns:
            ProductMatch object with match details
        """
        # Normalize SKU
        normalized_sku = self._normalize_id(sku)
        
        # Try direct SKU match first
        product = self.get_product_by_item_number(normalized_sku)
        if product:
            return ProductMatch(
                matched=True,
                match_type=MatchType.SKU,
                xorosoft_product=product,
                matched_value=sku,
                confidence_score=1.0
            )
        
        # Try metafield matches if provided
        if metafields:
            # Priority order for metafield matching
            metafield_priority = [
                ('CWS_A', MatchType.CWS_A),
                ('CWS_Catalog', MatchType.CWS_CATALOG),
                ('SPRC', MatchType.SPRC)
            ]
            
            for field_name, match_type in metafield_priority:
                if field_name in metafields and metafields[field_name]:
                    normalized_value = self._normalize_id(metafields[field_name])
                    
                    # Try as ItemNumber
                    product = self.get_product_by_item_number(normalized_value)
                    if product:
                        return ProductMatch(
                            matched=True,
                            match_type=match_type,
                            xorosoft_product=product,
                            matched_value=metafields[field_name],
                            confidence_score=0.9
                        )
                    
                    # Try as BasePartNumber
                    products = self.get_products_by_base_part_number(normalized_value)
                    if products:
                        return ProductMatch(
                            matched=True,
                            match_type=match_type,
                            xorosoft_product=products[0],  # Use first match
                            matched_value=metafields[field_name],
                            confidence_score=0.8
                        )
        
        # No match found
        return ProductMatch(
            matched=False,
            match_type=None,
            xorosoft_product=None,
            matched_value=None,
            confidence_score=0.0
        )
    
    def batch_validate_products(self, products: List[Dict[str, Any]], 
                               progress_callback: Optional[callable] = None) -> Dict[str, ProductMatch]:
        """
        Validate multiple products in batch.
        
        Args:
            products: List of product dictionaries with 'sku' and optional metafields
            progress_callback: Optional callback for progress updates
            
        Returns:
            Dictionary mapping SKU to ProductMatch results
        """
        results = {}
        total_products = len(products)
        
        for i, product in enumerate(products):
            sku = product.get('sku', '')
            if not sku:
                continue
            
            # Extract metafields
            metafields = {}
            for field in ['CWS_A', 'CWS_Catalog', 'SPRC']:
                if field in product:
                    metafields[field] = product[field]
            
            # Validate product
            results[sku] = self.validate_product(sku, metafields)
            
            # Report progress
            if progress_callback and i % 10 == 0:
                progress_callback({
                    'current': i + 1,
                    'total': total_products,
                    'percentage': ((i + 1) / total_products) * 100
                })
        
        return results
    
    def get_inventory_status(self, item_number: str) -> Optional[Dict[str, Any]]:
        """Get current inventory status for a product."""
        product = self.get_product_by_item_number(item_number)
        
        if not product or not product.variants:
            return None
        
        # Aggregate inventory from variants
        total_inventory = 0
        inventory_details = []
        
        for variant in product.variants:
            qty = variant.get('QuantityOnHand', 0)
            total_inventory += qty
            
            inventory_details.append({
                'variant_id': variant.get('Id'),
                'item_number': variant.get('ItemNumber'),
                'quantity_on_hand': qty,
                'location': variant.get('Location', 'Default')
            })
        
        return {
            'item_number': item_number,
            'total_inventory': total_inventory,
            'in_stock': total_inventory > 0,
            'variants': inventory_details
        }
    
    def _normalize_id(self, id_str: str) -> str:
        """Normalize an ID by removing hyphens and converting to uppercase."""
        if not id_str:
            return ""
        return id_str.replace("-", "").upper()
    
    def _parse_product(self, data: Dict[str, Any]) -> XorosoftProduct:
        """Parse raw API response into XorosoftProduct object."""
        # Extract first variant for main details
        variants = data.get('Variants', [])
        first_variant = variants[0] if variants else {}
        
        return XorosoftProduct(
            item_number=first_variant.get('ItemNumber', ''),
            base_part_number=data.get('BasePartNumber'),
            description=first_variant.get('Description'),
            title=data.get('Title'),
            handle=data.get('Handle'),
            unit_price=first_variant.get('UnitPrice'),
            vendor_product_number=first_variant.get('VendorProductNumber'),
            upc=first_variant.get('UPC'),
            product_code=first_variant.get('ProductCode'),
            variants=variants,
            raw_data=data
        )
    
    def clear_cache(self):
        """Clear the LRU cache."""
        self.get_product_by_item_number.cache_clear()
        self.get_products_by_base_part_number.cache_clear()
        self._last_cache_clear = datetime.now()
    
    def get_cache_info(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            'item_number_cache': {
                'hits': self.get_product_by_item_number.cache_info().hits,
                'misses': self.get_product_by_item_number.cache_info().misses,
                'size': self.get_product_by_item_number.cache_info().currsize,
                'maxsize': self.get_product_by_item_number.cache_info().maxsize
            },
            'base_part_cache': {
                'hits': self.get_products_by_base_part_number.cache_info().hits,
                'misses': self.get_products_by_base_part_number.cache_info().misses,
                'size': self.get_products_by_base_part_number.cache_info().currsize,
                'maxsize': self.get_products_by_base_part_number.cache_info().maxsize
            },
            'last_cache_clear': self._last_cache_clear.isoformat()
        }