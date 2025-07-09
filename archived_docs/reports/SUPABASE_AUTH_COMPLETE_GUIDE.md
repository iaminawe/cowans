# Complete Supabase Authentication Implementation Guide

## Overview
This guide provides step-by-step instructions for implementing Supabase authentication in the Cowan's Product Management System, replacing the current mock JWT authentication.

## Backend Implementation

### 1. Install Dependencies
```bash
cd web_dashboard/backend
pip install supabase==2.10.0
```

### 2. Environment Variables
Ensure these are set in your `.env` file:
```env
SUPABASE_URL=https://gqozcvqgsjaagnnjukmo.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-service-key
SUPABASE_JWT_SECRET=your-jwt-secret
```

### 3. Database Migration
Run the migration to add `supabase_id` column:
```bash
cd web_dashboard/backend
alembic upgrade head
```

Or manually:
```sql
ALTER TABLE users ADD COLUMN supabase_id VARCHAR(255) UNIQUE;
CREATE INDEX idx_users_supabase_id ON users(supabase_id);
ALTER TABLE users ALTER COLUMN password_hash DROP NOT NULL;
```

### 4. Update app.py

#### Step 4.1: Update Imports
Replace the Flask-JWT imports section with:
```python
from flask_jwt_extended import JWTManager  # Keep for backward compatibility
from services.supabase_auth import (
    auth_service, supabase_jwt_required, supabase_jwt_optional,
    get_current_user_id, get_current_user_email, require_role
)
```

#### Step 4.2: Remove Dev Mode Bypass
Delete these sections from app.py:
- Lines ~153-182: Development mode auth bypass
- The `dev_jwt_required` function
- The `dev_get_jwt_identity` function
- The line `jwt_required = dev_jwt_required`

#### Step 4.3: Update get_user_id Function
Replace the existing `get_user_id` function with:
```python
def get_user_id():
    """Helper function to get user ID from Supabase token."""
    supabase_user_id = get_current_user_id()
    if supabase_user_id:
        with db_session_scope() as session:
            user_repo = UserRepository(session)
            user = user_repo.get_by_supabase_id(supabase_user_id)
            if user:
                return user.id
            # Fallback for migration period
            return 1
    return None
```

#### Step 4.4: Update Authentication Endpoints
Replace the login endpoint:
```python
@app.route("/api/auth/login", methods=["POST"])
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
        return jsonify({"message": "Invalid credentials"}), 401
```

Replace the register endpoint:
```python
@app.route("/api/auth/register", methods=["POST"])
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
        return jsonify({"message": "Registration failed"}), 500
```

Add refresh token endpoint after `/api/auth/me`:
```python
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
```

#### Step 4.5: Replace JWT Decorators
Find and replace all occurrences:
- `@jwt_required()` → `@supabase_jwt_required`
- `get_jwt_identity()` → `get_current_user_id()`

### 5. Update WebSocket Authentication
In the WebSocket connection handler:
```python
@socketio.on('connect')
def handle_connect(auth):
    """Handle WebSocket connection with Supabase auth."""
    if auth and 'token' in auth:
        is_valid, user_data = auth_service.verify_token(auth['token'])
        if is_valid:
            user_id = user_data['id']
            # Continue with connection
        else:
            disconnect()
    else:
        disconnect()
```

## Frontend Implementation

### 1. Install Supabase JS Client
```bash
cd frontend
npm install @supabase/supabase-js
```

### 2. Create Supabase Client
Create `frontend/src/services/supabase.ts`:
```typescript
import { createClient } from '@supabase/supabase-js'

const supabaseUrl = process.env.REACT_APP_SUPABASE_URL!
const supabaseAnonKey = process.env.REACT_APP_SUPABASE_ANON_KEY!

export const supabase = createClient(supabaseUrl, supabaseAnonKey, {
  auth: {
    autoRefreshToken: true,
    persistSession: true,
    detectSessionInUrl: true
  }
})
```

### 3. Update AuthContext
Replace `frontend/src/contexts/AuthContext.tsx`:
```typescript
import React, { createContext, useContext, useEffect, useState } from 'react'
import { User, Session } from '@supabase/supabase-js'
import { supabase } from '../services/supabase'

interface AuthContextType {
  user: User | null
  session: Session | null
  signIn: (email: string, password: string) => Promise<void>
  signUp: (email: string, password: string, metadata?: any) => Promise<void>
  signOut: () => Promise<void>
  loading: boolean
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [session, setSession] = useState<Session | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // Get initial session
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session)
      setUser(session?.user ?? null)
      setLoading(false)
    })

    // Listen for auth changes
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session)
      setUser(session?.user ?? null)
    })

    return () => subscription.unsubscribe()
  }, [])

  const signIn = async (email: string, password: string) => {
    const { error } = await supabase.auth.signInWithPassword({ email, password })
    if (error) throw error
  }

  const signUp = async (email: string, password: string, metadata?: any) => {
    const { error } = await supabase.auth.signUp({ 
      email, 
      password,
      options: { data: metadata }
    })
    if (error) throw error
  }

  const signOut = async () => {
    const { error } = await supabase.auth.signOut()
    if (error) throw error
  }

  return (
    <AuthContext.Provider value={{ user, session, signIn, signUp, signOut, loading }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
```

### 4. Update API Client
Update `frontend/src/services/api.ts` to use Supabase session:
```typescript
import { supabase } from './supabase'

class ApiClient {
  private baseURL: string

  constructor() {
    this.baseURL = process.env.REACT_APP_API_URL || 'http://localhost:5003/api'
  }

  private async getAuthHeader() {
    const { data: { session } } = await supabase.auth.getSession()
    if (session) {
      return { 'Authorization': `Bearer ${session.access_token}` }
    }
    return {}
  }

  async request(endpoint: string, options: RequestInit = {}) {
    const authHeader = await this.getAuthHeader()
    
    const response = await fetch(`${this.baseURL}${endpoint}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...authHeader,
        ...options.headers,
      },
    })

    if (response.status === 401) {
      // Token expired, try to refresh
      const { data: { session } } = await supabase.auth.refreshSession()
      if (session) {
        // Retry with new token
        return this.request(endpoint, options)
      }
    }

    if (!response.ok) {
      throw new Error(`API Error: ${response.statusText}`)
    }

    return response.json()
  }
}

export const apiClient = new ApiClient()
```

### 5. Update Components
Update LoginForm.tsx:
```typescript
import { useAuth } from '../contexts/AuthContext'

function LoginForm() {
  const { signIn } = useAuth()
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setLoading(true)
    
    try {
      await signIn(email, password)
      // Redirect or update UI
    } catch (error) {
      console.error('Login failed:', error)
      // Show error message
    } finally {
      setLoading(false)
    }
  }
}
```

## Testing the Implementation

### 1. Test Authentication Flow
```bash
# Start backend
cd web_dashboard/backend
python app.py

# Start frontend
cd frontend
npm start
```

### 2. Verify Endpoints
- Test login: POST `/api/auth/login`
- Test register: POST `/api/auth/register`
- Test refresh: POST `/api/auth/refresh`
- Test protected endpoints with Supabase token

### 3. Check Database
Verify that users have `supabase_id` populated after login/register.

## Rollback Plan

If issues occur:
1. Restore original app.py from backup
2. Re-enable dev mode authentication temporarily
3. Remove supabase_id column from database
4. Revert frontend changes

## Security Checklist

- [ ] Remove all dev mode authentication code
- [ ] Ensure all endpoints use `@supabase_jwt_required`
- [ ] WebSocket connections validate Supabase tokens
- [ ] Refresh tokens are handled securely
- [ ] No passwords stored in local database
- [ ] CORS configured correctly
- [ ] Environment variables are secure

## Common Issues & Solutions

### Issue: "Invalid token" errors
**Solution**: Ensure `SUPABASE_JWT_SECRET` matches your Supabase project's JWT secret.

### Issue: Users can't login after migration
**Solution**: Run migration script to populate `supabase_id` for existing users.

### Issue: WebSocket disconnects
**Solution**: Ensure WebSocket auth handler validates Supabase tokens correctly.

### Issue: Token refresh fails
**Solution**: Check that refresh tokens are stored and sent correctly from frontend.

## Next Steps

1. Implement role-based access control
2. Add password reset functionality
3. Enable social auth providers
4. Set up email verification
5. Add multi-factor authentication
6. Monitor authentication metrics