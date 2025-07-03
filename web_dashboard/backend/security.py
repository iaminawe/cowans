"""Security module for parameter validation and sanitization."""
import os
import re
from typing import Any, Dict, List, Tuple
from pathlib import Path

class ParameterValidator:
    """Validates and sanitizes script parameters."""
    
    # Allowed file extensions for different parameter types
    ALLOWED_EXTENSIONS = {
        'csv': ['.csv'],
        'image': ['.jpg', '.jpeg', '.png', '.gif', '.webp'],
        'text': ['.txt', '.log'],
        'any': ['.csv', '.txt', '.log', '.json']
    }
    
    # Regex patterns for validation
    PATTERNS = {
        'email': re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'),
        'url': re.compile(r'^https?://[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'),
        'alphanumeric': re.compile(r'^[a-zA-Z0-9_-]+$'),
        'number': re.compile(r'^-?\d+(\.\d+)?$'),
        'boolean': re.compile(r'^(true|false|yes|no|1|0)$', re.IGNORECASE)
    }
    
    @staticmethod
    def validate_file_path(path: str, allowed_types: List[str] = None) -> Tuple[bool, str]:
        """Validate file path for security."""
        try:
            # Convert to Path object
            file_path = Path(path)
            
            # Check for path traversal attempts
            if '..' in file_path.parts:
                return False, "Path traversal detected"
            
            # Ensure absolute path
            if not file_path.is_absolute():
                # Convert to absolute path within data directory
                from config import Config
                file_path = Path(Config.DATA_PATH) / file_path
            
            # Check if file exists
            if not file_path.exists():
                return False, f"File not found: {file_path}"
            
            # Check file extension
            if allowed_types:
                allowed_exts = []
                for file_type in allowed_types:
                    allowed_exts.extend(ParameterValidator.ALLOWED_EXTENSIONS.get(file_type, []))
                
                if file_path.suffix.lower() not in allowed_exts:
                    return False, f"Invalid file type. Allowed: {', '.join(allowed_exts)}"
            
            # Check file size (max 100MB)
            if file_path.stat().st_size > 100 * 1024 * 1024:
                return False, "File too large (max 100MB)"
            
            return True, str(file_path)
            
        except Exception as e:
            return False, f"Invalid file path: {str(e)}"
    
    @staticmethod
    def validate_string(value: str, pattern: str = None, max_length: int = 1000) -> Tuple[bool, str]:
        """Validate string parameter."""
        if not isinstance(value, str):
            return False, "Value must be a string"
        
        if len(value) > max_length:
            return False, f"String too long (max {max_length} characters)"
        
        # Check for SQL injection patterns
        sql_patterns = ['--', ';', '/*', '*/', 'xp_', 'sp_', 'exec', 'execute', 'drop', 'truncate']
        value_lower = value.lower()
        for pattern in sql_patterns:
            if pattern in value_lower:
                return False, f"Potentially unsafe pattern detected: {pattern}"
        
        # Validate against specific pattern if provided
        if pattern and pattern in ParameterValidator.PATTERNS:
            if not ParameterValidator.PATTERNS[pattern].match(value):
                return False, f"Value does not match required pattern: {pattern}"
        
        return True, value
    
    @staticmethod
    def validate_number(value: Any, min_val: float = None, max_val: float = None) -> Tuple[bool, float]:
        """Validate numeric parameter."""
        try:
            num_value = float(value)
            
            if min_val is not None and num_value < min_val:
                return False, f"Value must be >= {min_val}"
            
            if max_val is not None and num_value > max_val:
                return False, f"Value must be <= {max_val}"
            
            return True, num_value
            
        except (TypeError, ValueError):
            return False, "Invalid number format"
    
    @staticmethod
    def validate_boolean(value: Any) -> Tuple[bool, bool]:
        """Validate boolean parameter."""
        if isinstance(value, bool):
            return True, value
        
        if isinstance(value, str):
            value_lower = value.lower()
            if value_lower in ['true', 'yes', '1']:
                return True, True
            elif value_lower in ['false', 'no', '0']:
                return True, False
        
        return False, "Invalid boolean value"
    
    @staticmethod
    def validate_parameters(script_name: str, parameters: List[Dict[str, Any]]) -> Tuple[bool, str, List[Dict[str, Any]]]:
        """Validate and sanitize all parameters for a script."""
        from script_registry import get_script_info
        
        script_info = get_script_info(script_name)
        if not script_info:
            return False, f"Unknown script: {script_name}", []
        
        # Create parameter lookup
        param_lookup = {p['name']: p for p in parameters}
        validated_params = []
        
        # Validate each parameter
        for param_def in script_info['parameters']:
            param_name = param_def['name']
            
            # Check if required parameter is missing
            if param_def.get('required', False) and param_name not in param_lookup:
                return False, f"Missing required parameter: {param_name}", []
            
            if param_name in param_lookup:
                param_value = param_lookup[param_name]['value']
                param_type = param_def['type']
                
                # Validate based on type
                if param_type == 'file':
                    valid, result = ParameterValidator.validate_file_path(
                        param_value,
                        param_def.get('allowed_types', ['any'])
                    )
                    if not valid:
                        return False, f"Parameter '{param_name}': {result}", []
                    validated_value = result
                    
                elif param_type == 'string':
                    valid, result = ParameterValidator.validate_string(
                        param_value,
                        param_def.get('pattern'),
                        param_def.get('max_length', 1000)
                    )
                    if not valid:
                        return False, f"Parameter '{param_name}': {result}", []
                    validated_value = result
                    
                elif param_type == 'number':
                    valid, result = ParameterValidator.validate_number(
                        param_value,
                        param_def.get('min'),
                        param_def.get('max')
                    )
                    if not valid:
                        return False, f"Parameter '{param_name}': {result}", []
                    validated_value = result
                    
                elif param_type == 'boolean':
                    valid, result = ParameterValidator.validate_boolean(param_value)
                    if not valid:
                        return False, f"Parameter '{param_name}': {result}", []
                    validated_value = result
                    
                else:
                    return False, f"Unknown parameter type: {param_type}", []
                
                validated_params.append({
                    'name': param_name,
                    'value': validated_value,
                    'type': param_type
                })
            elif param_def.get('default') is not None:
                # Use default value
                validated_params.append({
                    'name': param_name,
                    'value': param_def['default'],
                    'type': param_def['type']
                })
        
        return True, "Valid", validated_params

class ScriptSandbox:
    """Provides sandboxing for script execution."""
    
    @staticmethod
    def get_safe_environment(script_name: str) -> Dict[str, str]:
        """Get safe environment variables for script execution."""
        from config import Config
        
        # Base safe environment
        safe_env = os.environ.copy()
        
        # Remove sensitive variables
        sensitive_vars = ['AWS_SECRET_ACCESS_KEY', 'DATABASE_URL', 'SECRET_KEY']
        for var in sensitive_vars:
            safe_env.pop(var, None)
        
        # Add script-specific environment
        safe_env.update({
            'PYTHONPATH': Config.SCRIPTS_BASE_PATH,
            'SCRIPT_NAME': script_name,
            'DATA_PATH': Config.DATA_PATH,
            'LOG_PATH': Config.LOG_PATH,
            'PYTHONUNBUFFERED': '1'  # Ensure output is not buffered
        })
        
        # Add credentials only for scripts that need them
        if script_name in ['ftp_download', 'full_import']:
            safe_env['FTP_HOST'] = Config.FTP_HOST
            safe_env['FTP_USERNAME'] = Config.FTP_USERNAME
            safe_env['FTP_PASSWORD'] = Config.FTP_PASSWORD
        
        if script_name in ['shopify_upload', 'cleanup_duplicates', 'full_import']:
            safe_env['SHOPIFY_SHOP_URL'] = Config.SHOPIFY_SHOP_URL
            safe_env['SHOPIFY_ACCESS_TOKEN'] = Config.SHOPIFY_ACCESS_TOKEN
        
        return safe_env
    
    @staticmethod
    def get_resource_limits() -> Dict[str, Any]:
        """Get resource limits for script execution."""
        return {
            'max_cpu_time': 3600,  # 1 hour
            'max_memory': 2 * 1024 * 1024 * 1024,  # 2GB
            'max_file_size': 100 * 1024 * 1024,  # 100MB
            'max_processes': 10
        }