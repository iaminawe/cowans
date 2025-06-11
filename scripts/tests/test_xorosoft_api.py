import os
import requests
import json
import base64
from datetime import datetime
from dotenv import load_dotenv

def test_xorosoft_api(search_term=None, search_type='base_part'):
    """
    Test connection to Xorosoft API and retrieve sample product data
    
    Args:
        search_term (str, optional): Term to search for
        search_type (str): Type of search - 'base_part', 'handle', or 'description'
    """
    
    # Load environment variables
    load_dotenv()
    
    # API configuration
    base_url = "https://res.xorosoft.io/api/xerp"
    api_key = os.getenv('XOROSOFT_API')
    api_pass = os.getenv('XOROSOFT_PASS')

    if not api_key or not api_pass:
        raise ValueError("Missing API credentials. Please check XOROSOFT_API and XOROSOFT_PASS environment variables.")

    # Create Basic auth header
    auth_string = f"{api_key}:{api_pass}"
    auth_bytes = auth_string.encode('ascii')
    base64_auth = base64.b64encode(auth_bytes).decode('ascii')

    # Headers
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'Authorization': f'Basic {base64_auth}'
    }

    def handle_response(response, endpoint_name):
        """Helper function to handle API responses"""
        print(f"Status: {response.status_code}")
        
        try:
            if response.text.strip():
                data = response.json()
                return data
            else:
                print(f"Empty response from {endpoint_name}")
                return None
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON from {endpoint_name}: {str(e)}")
            print(f"Raw response: {response.text[:500]}...")
            return None

    def test_endpoint(endpoint, method='GET', params=None, json_data=None):
        """Helper function to test different endpoints"""
        url = f"{base_url}/{endpoint}"
        print(f"\nTesting endpoint: {url}")
        print(f"Method: {method}")
        
        if params:
            print(f"Params: {json.dumps(params, indent=2)}")
        if json_data:
            print(f"JSON Data: {json.dumps(json_data, indent=2)}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, params=params)
            else:
                response = requests.post(url, headers=headers, json=json_data)
            
            return handle_response(response, endpoint)
            
        except Exception as e:
            print(f"Error: {str(e)}")
            return None

    # Test different endpoints and methods
    test_cases = []

    # Test Case 1: Basic product list
    test_cases.append({
        'name': 'List Products',
        'endpoint': 'product/getproducts',  # Note: trying getproducts instead of getproduct
        'method': 'GET',
        'params': {
            'page': 1,
            'pageSize': 10
        }
    })

    if search_term:
        # Test Case 2: Filter API with query parameter
        test_cases.append({
            'name': 'Product Search',
            'endpoint': 'product/getproduct',
            'method': 'GET',
            'params': {
                'query': search_term,
                'page': 1,
                'pageSize': 10
            }
        })

        # Test Case 3: Filter API with POST
        test_cases.append({
            'name': 'Product Filter',
            'endpoint': 'product/getfiltered',
            'method': 'POST',
            'json_data': {
                'filter': {
                    'basePartNumber': search_term
                },
                'page': 1,
                'pageSize': 10
            }
        })

        # Test Case 4: Direct lookup by ItemNumber
        test_cases.append({
            'name': 'Direct Product Lookup',
            'endpoint': f'product/{search_term}',
            'method': 'GET'
        })

    results = []
    for test in test_cases:
        print(f"\nTesting: {test['name']}")
        result = test_endpoint(
            test['endpoint'],
            test['method'],
            test.get('params'),
            test.get('json_data')
        )
        
        if result:
            # Save response to file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"data/xorosoft_{test['name'].lower().replace(' ', '_')}_{timestamp}.json"
            
            os.makedirs('data', exist_ok=True)
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2)
            
            print(f"Response saved to: {filename}")
            results.append(result)
            
            # Display sample data if it's a product list
            if isinstance(result, dict):
                if 'Data' in result and isinstance(result['Data'], list):
                    products = result['Data']
                    print(f"\nFound {len(products)} products")
                    for idx, product in enumerate(products[:2]):
                        print_product(product)
                elif 'product' in result:
                    print("\nProduct Details:")
                    print_product(result['product'])

    return len(results) > 0

def print_product(product):
    """Helper function to print product details"""
    print(f"\nProduct:")
    for key in ['BasePartNumber', 'Handle', 'Title', 'Id']:
        if key in product:
            print(f"{key}: {product[key]}")
    
    if product.get('Variants'):
        variant = product['Variants'][0]
        print("\nFirst Variant Details:")
        fields = ['Description', 'ItemNumber', 'ProductCode', 
                'VendorProductNumber', 'UPC', 'UnitPrice']
        for field in fields:
            value = variant.get(field)
            if value:
                print(f"{field}: {value}")
    print("-" * 50)

if __name__ == "__main__":
    print("\nTesting Xorosoft API endpoints...")
    
    # Test 1: Basic list without search
    print("\nTest 1: Basic list of products")
    success = test_xorosoft_api()
    
    if success:
        # Test 2: Search for specific product
        print("\nTest 2: Searching for specific product")
        test_sku = "CAL-E1-2LEG-SL"
        success = test_xorosoft_api(test_sku, 'base_part')
    
    if not success:
        print("\nAPI tests failed. Please check the error messages above.")
    else:
        print("\nAll API tests completed successfully!")
