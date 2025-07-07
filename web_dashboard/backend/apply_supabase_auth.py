#!/usr/bin/env python3
"""
Apply Supabase Authentication to Flask App

This script updates app.py to use Supabase authentication,
replacing mock JWT authentication with production-ready auth.
"""

import os
import re
import shutil
from datetime import datetime
from pathlib import Path


def backup_file(file_path):
    """Create a timestamped backup of the file."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{file_path}.backup_{timestamp}"
    shutil.copy2(file_path, backup_path)
    print(f"✅ Created backup: {backup_path}")
    return backup_path


def update_imports(content):
    """Update import statements to include Supabase auth."""
    # Find the line with flask_jwt_extended imports
    jwt_import_pattern = r'(from flask_jwt_extended import[^\n]+)'
    jwt_import_match = re.search(jwt_import_pattern, content)
    
    if jwt_import_match:
        # Add Supabase imports after JWT imports
        new_imports = jwt_import_match.group(0) + '\n' + \
                     'from services.supabase_auth import (\n' + \
                     '    auth_service, supabase_jwt_required, supabase_jwt_optional,\n' + \
                     '    get_current_user_id, get_current_user_email, require_role\n' + \
                     ')'
        content = content.replace(jwt_import_match.group(0), new_imports)
        print("✅ Updated imports to include Supabase auth")
    
    return content


def remove_dev_mode_auth(content):
    """Remove all dev mode authentication bypass code."""
    # Pattern to find and remove the dev mode section
    dev_mode_pattern = r'# Development mode auth bypass\s*\n.*?get_jwt_identity = dev_get_jwt_identity\s*\n'
    
    if re.search(dev_mode_pattern, content, re.DOTALL):
        content = re.sub(dev_mode_pattern, '', content, flags=re.DOTALL)
        print("✅ Removed dev mode authentication bypass")
    
    return content


def update_get_user_id(content):
    """Update get_user_id function to use Supabase."""
    old_pattern = r'def get_user_id\(\):[^}]+?return 1'
    
    new_function = '''def get_user_id():
    """Helper function to get user ID from Supabase token."""
    supabase_user_id = get_current_user_id()
    if supabase_user_id:
        with db_session_scope() as session:
            user_repo = UserRepository(session)
            user = user_repo.get_by_supabase_id(supabase_user_id)
            if user:
                return user.id
            # For migration period, return fallback
            return 1
    return None'''
    
    if re.search(old_pattern, content, re.DOTALL):
        content = re.sub(old_pattern, new_function, content, flags=re.DOTALL)
        print("✅ Updated get_user_id function")
    
    return content


def replace_jwt_decorators(content):
    """Replace all @jwt_required() with @supabase_jwt_required."""
    # Count replacements
    count = content.count('@jwt_required()')
    
    # Replace all occurrences
    content = content.replace('@jwt_required()', '@supabase_jwt_required')
    
    if count > 0:
        print(f"✅ Replaced {count} @jwt_required() decorators with @supabase_jwt_required")
    
    return content


def update_auth_endpoints(content):
    """Update login and register endpoints to use Supabase."""
    # Update login endpoint
    login_pattern = r'(@app\.route\("/api/auth/login".*?\ndef login\(\):.*?)return jsonify\(.*?\), 401'
    
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
    
    if re.search(login_pattern, content, re.DOTALL):
        # Find the exact login function and replace it
        login_match = re.search(r'@app\.route\("/api/auth/login".*?\n.*?\n.*?return jsonify.*?\), 401', content, re.DOTALL)
        if login_match:
            content = content.replace(login_match.group(0), new_login)
            print("✅ Updated login endpoint")
    
    # Update register endpoint
    register_pattern = r'(@app\.route\("/api/auth/register".*?\ndef register\(\):.*?)return jsonify\(.*?\), 500'
    
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
    
    if re.search(register_pattern, content, re.DOTALL):
        # Find the exact register function and replace it
        register_match = re.search(r'@app\.route\("/api/auth/register".*?\n.*?\n.*?return jsonify.*?\), 500', content, re.DOTALL)
        if register_match:
            content = content.replace(register_match.group(0), new_register)
            print("✅ Updated register endpoint")
    
    return content


def add_refresh_endpoint(content):
    """Add token refresh endpoint after /api/auth/me."""
    # Check if refresh endpoint already exists
    if '/api/auth/refresh' in content:
        print("ℹ️  Refresh endpoint already exists")
        return content
    
    # Find the /api/auth/me endpoint
    me_pattern = r'(@app\.route\("/api/auth/me".*?\n.*?\n.*?return jsonify.*?\n}[^\n]*\))'
    me_match = re.search(me_pattern, content, re.DOTALL)
    
    if me_match:
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
        return jsonify({"message": "Token refresh failed"}), 500'''
        
        # Insert after the me endpoint
        content = content.replace(me_match.group(0), me_match.group(0) + refresh_endpoint)
        print("✅ Added refresh token endpoint")
    
    return content


def update_websocket_auth(content):
    """Update WebSocket connection handler to use Supabase auth."""
    # Import websocket handlers
    import_pattern = r'(from websocket_service import WebSocketService)'
    if re.search(import_pattern, content):
        new_import = 'from websocket_service import WebSocketService\nfrom websocket_handlers import register_websocket_handlers'
        content = re.sub(import_pattern, new_import, content)
        print("✅ Added WebSocket handlers import")
    
    # Update the connect handler
    connect_pattern = r'@socketio\.on\(\'connect\'\)\ndef handle_connect\(\):.*?emit\(\'connected\'.*?\}\)'
    
    if re.search(connect_pattern, content, re.DOTALL):
        # Add a note about WebSocket auth
        note = '''
# WebSocket authentication is now handled in websocket_handlers.py
# To enable Supabase auth for WebSocket, use:
# register_websocket_handlers(socketio)
'''
        # Find the socketio initialization
        socketio_init = re.search(r'(socketio = SocketIO\([^)]+\))', content)
        if socketio_init:
            content = content.replace(socketio_init.group(0), socketio_init.group(0) + note)
            print("✅ Added WebSocket authentication note")
    
    return content


def main():
    """Apply all Supabase authentication updates."""
    app_path = Path(__file__).parent / 'app.py'
    
    if not app_path.exists():
        print("❌ app.py not found!")
        return
    
    print("\n🚀 Applying Supabase Authentication Updates\n")
    
    # Create backup
    backup_path = backup_file(app_path)
    
    # Read current content
    with open(app_path, 'r') as f:
        content = f.read()
    
    # Apply all updates
    print("\n📝 Applying updates...\n")
    
    content = update_imports(content)
    content = remove_dev_mode_auth(content)
    content = update_get_user_id(content)
    content = replace_jwt_decorators(content)
    content = update_auth_endpoints(content)
    content = add_refresh_endpoint(content)
    content = update_websocket_auth(content)
    
    # Write updated content
    with open(app_path, 'w') as f:
        f.write(content)
    
    print("\n✅ Successfully applied all Supabase authentication updates!")
    print(f"\n📁 Original file backed up to: {backup_path}")
    print("\n⚠️  Next steps:")
    print("1. Review the changes in app.py")
    print("2. Run database migration: alembic upgrade head")
    print("3. Test authentication endpoints")
    print("4. Deploy to production")


if __name__ == "__main__":
    main()