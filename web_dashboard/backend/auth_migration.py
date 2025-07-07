"""
Authentication Migration Script

This script helps migrate from mock JWT authentication to Supabase authentication.
It updates the Flask app configuration and replaces authentication decorators.
"""

import os
import re
from pathlib import Path


def update_imports(content):
    """Update import statements to include Supabase auth"""
    # Find the Flask-JWT-Extended import line
    jwt_import_pattern = r'from flask_jwt_extended import.*'
    jwt_import_match = re.search(jwt_import_pattern, content)
    
    if jwt_import_match:
        # Keep the original import but add Supabase imports after
        new_imports = jwt_import_match.group(0) + '\n' + \
                     'from services.supabase_auth import (\n' + \
                     '    auth_service, supabase_jwt_required, supabase_jwt_optional,\n' + \
                     '    get_current_user_id, get_current_user_email, require_role\n' + \
                     ')'
        content = content.replace(jwt_import_match.group(0), new_imports)
    
    return content


def remove_dev_mode_bypass(content):
    """Remove the development mode authentication bypass"""
    # Remove DEV_MODE variable and related code
    patterns_to_remove = [
        # DEV_MODE definition
        r'# Development mode auth bypass\nDEV_MODE = .*\n.*\n',
        # dev_jwt_required function
        r'def dev_jwt_required\(\):\n(?:    .*\n)*?    return decorator\n',
        # jwt_required replacement
        r'# Replace jwt_required with our dev version\njwt_required = dev_jwt_required\n',
        # dev_get_jwt_identity function
        r'# Also bypass get_jwt_identity in dev mode\n.*\ndef dev_get_jwt_identity\(\):\n(?:    .*\n)*?\nget_jwt_identity = dev_get_jwt_identity\n',
    ]
    
    for pattern in patterns_to_remove:
        content = re.sub(pattern, '', content, flags=re.MULTILINE)
    
    return content


def update_get_user_id_function(content):
    """Update get_user_id function to use Supabase"""
    old_function = r'def get_user_id\(\):\n(?:    .*\n)*?            return 1'
    
    new_function = '''def get_user_id():
    """Helper function to get user ID from Supabase token."""
    user_id = get_current_user_id()
    if user_id:
        # For backward compatibility with local database
        # We'll need to map Supabase IDs to local user IDs
        with db_session_scope() as session:
            user_repo = UserRepository(session)
            user = user_repo.get_by_supabase_id(user_id)
            if user:
                return user.id
            # If user doesn't exist locally, create them
            # This helps with migration period
            return 1  # Fallback for now
    return None'''
    
    content = re.sub(old_function, new_function, content, flags=re.MULTILINE)
    return content


def update_auth_endpoints(content):
    """Update authentication endpoints to use Supabase"""
    # Update login endpoint
    login_pattern = r'@app\.route\("/api/auth/login".*?\n(?:.*\n)*?        return jsonify.*?\n'
    login_match = re.search(login_pattern, content, re.MULTILINE | re.DOTALL)
    
    if login_match:
        new_login = '''@app.route("/api/auth/login", methods=["POST"])
def login():
    """Handle user login with Supabase."""
    try:
        data = login_schema.load(request.get_json())
    except Exception as e:
        return jsonify({"message": "Invalid request data", "errors": str(e)}), 400
    
    try:
        # Authenticate with Supabase
        result = auth_service.sign_in(data["email"], data["password"])
        
        # Sync user with local database
        with db_session_scope() as session:
            user_repo = UserRepository(session)
            user = user_repo.get_by_email(data["email"])
            
            if not user:
                # Create local user record
                user = user_repo.create_user(
                    email=data["email"],
                    password="",  # No password stored locally
                    first_name=result["user"].get("user_metadata", {}).get("first_name", ""),
                    last_name=result["user"].get("user_metadata", {}).get("last_name", ""),
                    supabase_id=result["user"]["id"]
                )
                session.commit()
            elif not user.supabase_id:
                # Update existing user with Supabase ID
                user.supabase_id = result["user"]["id"]
                session.commit()
            
            app.logger.info(f"User logged in: {user.email}")
            
            return jsonify({
                "access_token": result["session"]["access_token"],
                "refresh_token": result["session"]["refresh_token"],
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "is_admin": user.is_admin
                }
            })
            
    except Exception as e:
        app.logger.warning(f"Failed login attempt for: {data['email']} - {str(e)}")
        return jsonify({"message": "Invalid credentials"}), 401'''
        
        content = content.replace(login_match.group(0), new_login + '\n')
    
    # Update register endpoint
    register_pattern = r'@app\.route\("/api/auth/register".*?\n(?:.*\n)*?        return jsonify.*?\n'
    register_match = re.search(register_pattern, content, re.MULTILINE | re.DOTALL)
    
    if register_match:
        new_register = '''@app.route("/api/auth/register", methods=["POST"])
def register():
    """Handle user registration with Supabase."""
    try:
        data = register_schema.load(request.get_json())
    except Exception as e:
        return jsonify({"message": "Invalid request data", "errors": str(e)}), 400
    
    try:
        # Register with Supabase
        metadata = {
            "first_name": data["first_name"],
            "last_name": data["last_name"]
        }
        result = auth_service.sign_up(data["email"], data["password"], metadata)
        
        # Create local user record
        with db_session_scope() as session:
            user_repo = UserRepository(session)
            
            # Check if user already exists locally
            existing_user = user_repo.get_by_email(data["email"])
            if existing_user:
                return jsonify({"message": "User with this email already exists"}), 409
            
            # Create new user
            user = user_repo.create_user(
                email=data["email"],
                password="",  # No password stored locally
                first_name=data["first_name"],
                last_name=data["last_name"],
                is_admin=False,
                supabase_id=result["user"]["id"]
            )
            session.commit()
            
            app.logger.info(f"New user registered: {user.email}")
            
            return jsonify({
                "message": "User registered successfully",
                "access_token": result["session"]["access_token"] if result.get("session") else None,
                "refresh_token": result["session"]["refresh_token"] if result.get("session") else None,
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "is_admin": user.is_admin
                }
            }), 201
            
    except Exception as e:
        app.logger.error(f"Registration failed: {str(e)}")
        return jsonify({"message": "Registration failed"}), 500'''
        
        content = content.replace(register_match.group(0), new_register + '\n')
    
    return content


def update_jwt_decorators(content):
    """Replace @jwt_required() with @supabase_jwt_required"""
    # Simple replacement for now
    content = content.replace('@jwt_required()', '@supabase_jwt_required')
    return content


def add_refresh_endpoint(content):
    """Add token refresh endpoint"""
    # Find a good place to add the endpoint (after /api/auth/me)
    me_endpoint = re.search(r'(@app\.route\("/api/auth/me".*?\n(?:.*\n)*?    return jsonify.*?\n)', 
                           content, re.MULTILINE | re.DOTALL)
    
    if me_endpoint:
        refresh_endpoint = '''
@app.route("/api/auth/refresh", methods=["POST"])
def refresh_token():
    """Refresh access token using refresh token."""
    try:
        data = request.get_json()
        refresh_token = data.get("refresh_token")
        
        if not refresh_token:
            return jsonify({"message": "Refresh token required"}), 400
        
        result = auth_service.refresh_token(refresh_token)
        
        if result:
            return jsonify({
                "access_token": result["access_token"],
                "refresh_token": result["refresh_token"]
            })
        else:
            return jsonify({"message": "Invalid refresh token"}), 401
            
    except Exception as e:
        app.logger.error(f"Token refresh error: {str(e)}")
        return jsonify({"message": "Token refresh failed"}), 500
'''
        content = content.replace(me_endpoint.group(0), 
                                 me_endpoint.group(0) + refresh_endpoint)
    
    return content


def main():
    """Run the migration"""
    app_path = Path(__file__).parent / 'app.py'
    
    print("Starting authentication migration...")
    
    # Read the current app.py
    with open(app_path, 'r') as f:
        content = f.read()
    
    # Apply updates
    print("1. Updating imports...")
    content = update_imports(content)
    
    print("2. Removing dev mode bypass...")
    content = remove_dev_mode_bypass(content)
    
    print("3. Updating get_user_id function...")
    content = update_get_user_id_function(content)
    
    print("4. Updating authentication endpoints...")
    content = update_auth_endpoints(content)
    
    print("5. Updating JWT decorators...")
    content = update_jwt_decorators(content)
    
    print("6. Adding refresh endpoint...")
    content = add_refresh_endpoint(content)
    
    # Save to a new file first for safety
    backup_path = app_path.with_suffix('.py.backup')
    with open(backup_path, 'w') as f:
        f.write(content)
    
    print(f"Migration complete! Backup saved to {backup_path}")
    print("Review the changes and then replace app.py with the backup file.")
    
    return content


if __name__ == "__main__":
    main()