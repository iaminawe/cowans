#!/usr/bin/env python3
"""Simple script to update authentication in app.py"""

import re
import shutil
from datetime import datetime

# Backup the file first
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backup_path = f"app.py.backup_{timestamp}"
shutil.copy2('app.py', backup_path)
print(f"✅ Created backup: {backup_path}")

# Read the file
with open('app.py', 'r') as f:
    content = f.read()

print("\n📝 Applying updates...")

# 1. Add Supabase imports after flask_jwt_extended imports
jwt_import_line = 'from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity'
if jwt_import_line in content and 'supabase_auth' not in content:
    supabase_imports = '''from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from services.supabase_auth import (
    auth_service, supabase_jwt_required, supabase_jwt_optional,
    get_current_user_id, get_current_user_email, require_role
)'''
    content = content.replace(jwt_import_line, supabase_imports)
    print("✅ Added Supabase imports")

# 2. Replace all @jwt_required() with @supabase_jwt_required
count = content.count('@jwt_required()')
content = content.replace('@jwt_required()', '@supabase_jwt_required')
print(f"✅ Replaced {count} @jwt_required() decorators")

# 3. Comment out dev mode auth instead of removing (safer)
if 'DEV_MODE = ' in content:
    # Find the dev mode section and comment it out
    lines = content.split('\n')
    new_lines = []
    in_dev_mode = False
    
    for line in lines:
        if '# Development mode auth bypass' in line:
            in_dev_mode = True
            new_lines.append('# DISABLED: ' + line)
        elif in_dev_mode and 'get_jwt_identity = dev_get_jwt_identity' in line:
            new_lines.append('# DISABLED: ' + line)
            in_dev_mode = False
        elif in_dev_mode:
            new_lines.append('# DISABLED: ' + line)
        else:
            new_lines.append(line)
    
    content = '\n'.join(new_lines)
    print("✅ Disabled dev mode authentication")

# Write the updated content
with open('app.py', 'w') as f:
    f.write(content)

print("\n✅ Basic updates completed!")
print("\n⚠️  Manual steps required:")
print("1. Update login/register endpoints to use auth_service")
print("2. Add refresh token endpoint")
print("3. Update get_user_id() function")
print("4. Test authentication endpoints")