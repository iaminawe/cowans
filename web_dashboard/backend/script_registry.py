"""Registry of available scripts and their configurations."""
from typing import Dict, List, Any

SCRIPT_REGISTRY = {
    'ftp_download': {
        'display_name': 'FTP Download',
        'description': 'Download product data from Etilize FTP server',
        'category': 'data_import',
        'parameters': [
            {
                'name': 'force',
                'display_name': 'Force Download',
                'type': 'boolean',
                'required': False,
                'default': False,
                'description': 'Force download even if recent data exists'
            }
        ],
        'estimated_duration': 180,  # seconds
        'requires_auth': True
    },
    'filter_products': {
        'display_name': 'Filter Products',
        'description': 'Filter products against Xorosoft reference data',
        'category': 'data_processing',
        'parameters': [
            {
                'name': 'input_file',
                'display_name': 'Input File',
                'type': 'file',
                'required': True,
                'description': 'CSV file to filter'
            },
            {
                'name': 'reference_file',
                'display_name': 'Reference File',
                'type': 'file',
                'required': False,
                'description': 'Xorosoft reference file (auto-detected if not provided)'
            },
            {
                'name': 'debug',
                'display_name': 'Debug Mode',
                'type': 'boolean',
                'required': False,
                'default': False,
                'description': 'Enable debug output'
            }
        ],
        'estimated_duration': 120,
        'requires_auth': True
    },
    'create_metafields': {
        'display_name': 'Create Metafields',
        'description': 'Generate Shopify metafields from product data',
        'category': 'data_processing',
        'parameters': [
            {
                'name': 'input_file',
                'display_name': 'Input File',
                'type': 'file',
                'required': True,
                'description': 'CSV file to process'
            }
        ],
        'estimated_duration': 300,
        'requires_auth': True
    },
    'shopify_upload': {
        'display_name': 'Shopify Upload',
        'description': 'Upload products to Shopify store',
        'category': 'shopify',
        'parameters': [
            {
                'name': 'csv_file',
                'display_name': 'CSV File',
                'type': 'file',
                'required': True,
                'description': 'Shopify-formatted CSV file'
            },
            {
                'name': 'skip_images',
                'display_name': 'Skip Images',
                'type': 'boolean',
                'required': False,
                'default': False,
                'description': 'Skip image upload for faster processing'
            },
            {
                'name': 'batch_size',
                'display_name': 'Batch Size',
                'type': 'number',
                'required': False,
                'default': 50,
                'description': 'Number of products per batch'
            }
        ],
        'estimated_duration': 600,
        'requires_auth': True
    },
    'cleanup_duplicates': {
        'display_name': 'Cleanup Duplicate Images',
        'description': 'Remove duplicate images from Shopify products',
        'category': 'maintenance',
        'parameters': [
            {
                'name': 'dry_run',
                'display_name': 'Dry Run',
                'type': 'boolean',
                'required': False,
                'default': True,
                'description': 'Preview changes without applying them'
            }
        ],
        'estimated_duration': 300,
        'requires_auth': True
    },
    'categorize_products': {
        'display_name': 'Categorize Products',
        'description': 'Automatically categorize products using taxonomy',
        'category': 'data_processing',
        'parameters': [
            {
                'name': 'input_file',
                'display_name': 'Input File',
                'type': 'file',
                'required': True,
                'description': 'CSV file to categorize'
            },
            {
                'name': 'taxonomy_file',
                'display_name': 'Taxonomy File',
                'type': 'file',
                'required': False,
                'description': 'Custom taxonomy file (optional)'
            }
        ],
        'estimated_duration': 240,
        'requires_auth': True
    },
    'full_import': {
        'display_name': 'Full Import Workflow',
        'description': 'Run complete import workflow from FTP to Shopify',
        'category': 'workflow',
        'parameters': [
            {
                'name': 'skip_download',
                'display_name': 'Skip Download',
                'type': 'boolean',
                'required': False,
                'default': False,
                'description': 'Skip FTP download stage'
            },
            {
                'name': 'skip_filter',
                'display_name': 'Skip Filter',
                'type': 'boolean',
                'required': False,
                'default': False,
                'description': 'Skip product filtering stage'
            },
            {
                'name': 'skip_metafields',
                'display_name': 'Skip Metafields',
                'type': 'boolean',
                'required': False,
                'default': False,
                'description': 'Skip metafields creation stage'
            },
            {
                'name': 'skip_upload',
                'display_name': 'Skip Upload',
                'type': 'boolean',
                'required': False,
                'default': False,
                'description': 'Skip Shopify upload stage'
            }
        ],
        'estimated_duration': 1200,
        'requires_auth': True
    }
}

def get_script_info(script_name: str) -> Dict[str, Any]:
    """Get information about a specific script."""
    return SCRIPT_REGISTRY.get(script_name, None)

def get_scripts_by_category(category: str) -> List[Dict[str, Any]]:
    """Get all scripts in a specific category."""
    scripts = []
    for name, info in SCRIPT_REGISTRY.items():
        if info['category'] == category:
            scripts.append({
                'name': name,
                **info
            })
    return scripts

def get_all_scripts() -> Dict[str, List[Dict[str, Any]]]:
    """Get all scripts organized by category."""
    categories = {}
    for name, info in SCRIPT_REGISTRY.items():
        category = info['category']
        if category not in categories:
            categories[category] = []
        categories[category].append({
            'name': name,
            **info
        })
    return categories

def validate_script_parameters(script_name: str, parameters: List[Dict]) -> tuple[bool, str]:
    """Validate parameters for a script."""
    script_info = get_script_info(script_name)
    if not script_info:
        return False, f"Unknown script: {script_name}"
    
    # Create parameter lookup
    param_lookup = {p['name']: p for p in parameters}
    
    # Check required parameters
    for param_def in script_info['parameters']:
        if param_def['required'] and param_def['name'] not in param_lookup:
            return False, f"Missing required parameter: {param_def['name']}"
        
        # Validate parameter types
        if param_def['name'] in param_lookup:
            param = param_lookup[param_def['name']]
            expected_type = param_def['type']
            value = param['value']
            
            if expected_type == 'number' and not isinstance(value, (int, float)):
                try:
                    float(value)
                except:
                    return False, f"Parameter {param_def['name']} must be a number"
            elif expected_type == 'boolean' and not isinstance(value, bool):
                return False, f"Parameter {param_def['name']} must be a boolean"
    
    return True, "Valid"