"""
Temporary Flask app with authentication disabled for testing
"""
import os
import sys

# Monkey patch jwt_required to be a no-op decorator
from flask_jwt_extended import jwt_required as original_jwt_required

def fake_jwt_required(*args, **kwargs):
    def decorator(fn):
        return fn
    return decorator

# Replace the jwt_required import
sys.modules['flask_jwt_extended'].jwt_required = fake_jwt_required

# Now import the app
from app import app, socketio

if __name__ == '__main__':
    # Set a fake JWT identity for testing
    os.environ['JWT_SECRET_KEY'] = 'test-secret-key'
    
    # Run the app
    socketio.run(app, host='0.0.0.0', port=3560, debug=True, allow_unsafe_werkzeug=True)