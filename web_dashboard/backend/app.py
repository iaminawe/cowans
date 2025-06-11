from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from datetime import timedelta
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "http://localhost:3000"}})

# JWT Configuration
app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY", "dev-secret-key")
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=1)
jwt = JWTManager(app)

# Mock user for testing (replace with Supabase later)
MOCK_USER = {
    "email": "test@example.com",
    "password": "test123"
}

@app.route("/api/auth/login", methods=["POST"])
def login():
    data = request.get_json()
    
    if not data or not data.get("email") or not data.get("password"):
        return jsonify({"message": "Missing email or password"}), 400
        
    if data["email"] == MOCK_USER["email"] and data["password"] == MOCK_USER["password"]:
        access_token = create_access_token(identity=data["email"])
        return jsonify({
            "access_token": access_token,
            "user": {"email": data["email"]}
        })
    
    return jsonify({"message": "Invalid credentials"}), 401

@app.route("/api/sync/trigger", methods=["POST"])
@jwt_required()
def trigger_sync():
    # This will be implemented to trigger the core sync process
    return jsonify({"message": "Sync triggered successfully"})

@app.route("/api/sync/history", methods=["GET"])
@jwt_required()
def get_sync_history():
    # Mock sync history for now
    history = [
        {
            "id": 1,
            "timestamp": "2025-05-29T16:00:00Z",
            "status": "success",
            "message": "Successfully synced 100 products"
        }
    ]
    return jsonify(history)

if __name__ == "__main__":
    app.run(debug=True, port=5000)