# Supabase Authentication Implementation Plan

## Overview
This document outlines the implementation plan for replacing the mock JWT authentication with Supabase authentication in the Cowan's Product Management System.

## Implementation Steps

### Phase 1: Backend Integration ✅ 
1. **Install Supabase Client** ✅
   - Added `supabase==2.10.0` to requirements.txt

2. **Create Supabase Auth Service** ✅
   - Created `services/supabase_auth.py` with:
     - User registration and login
     - Token verification
     - Session management
     - Role-based access control decorators

### Phase 2: Update Flask Application (In Progress)
1. **Update Authentication Endpoints**
   - Replace `/api/auth/login` endpoint
   - Replace `/api/auth/register` endpoint
   - Add `/api/auth/refresh` endpoint
   - Update `/api/auth/me` endpoint

2. **Replace JWT Decorators**
   - Replace all `@jwt_required()` with `@supabase_jwt_required`
   - Remove Flask-JWT-Extended initialization
   - Remove dev mode authentication bypass

3. **Update User Management**
   - Add `supabase_id` column to User model
   - Update UserRepository to sync with Supabase
   - Map Supabase users to local database

### Phase 3: Frontend Integration
1. **Install Supabase JS Client**
   ```bash
   cd frontend && npm install @supabase/supabase-js
   ```

2. **Create Supabase Client Service**
   - Initialize Supabase client with env variables
   - Create auth service wrapper

3. **Update AuthContext**
   - Replace custom auth logic with Supabase
   - Use Supabase session management
   - Handle token refresh automatically

4. **Update Components**
   - Update LoginForm.tsx
   - Update RegisterForm.tsx
   - Add password reset functionality
   - Update API request interceptors

### Phase 4: WebSocket Security
1. **Secure WebSocket Connections**
   - Validate Supabase tokens on connection
   - Update SocketIO authentication
   - Handle disconnection on token expiry

### Phase 5: Testing & Deployment
1. **Update Tests**
   - Create test fixtures for Supabase auth
   - Update all auth-related tests
   - Add integration tests

2. **Migration Strategy**
   - Create migration script for existing users
   - Handle transition period
   - Update deployment documentation

## Security Considerations

1. **Token Storage**
   - Use httpOnly cookies for refresh tokens
   - Store access tokens in memory (not localStorage)
   - Implement proper CORS configuration

2. **Role Management**
   - Define roles in Supabase Dashboard
   - Implement role checks in backend
   - Add role-based UI components

3. **Session Management**
   - Auto-refresh tokens before expiry
   - Handle concurrent sessions
   - Implement logout across all devices

## Environment Variables

Required additions to `.env`:
```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-service-key
SUPABASE_JWT_SECRET=your-jwt-secret
```

## Database Schema Updates

```sql
-- Add supabase_id to users table
ALTER TABLE users ADD COLUMN supabase_id VARCHAR(255) UNIQUE;

-- Create index for faster lookups
CREATE INDEX idx_users_supabase_id ON users(supabase_id);

-- Add user roles table
CREATE TABLE user_roles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    role VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

## API Endpoint Changes

### Before (Mock Auth)
```python
@app.route('/api/auth/login', methods=['POST'])
def login():
    # Custom JWT generation
    access_token = create_access_token(identity=user.email)
```

### After (Supabase Auth)
```python
@app.route('/api/auth/login', methods=['POST'])
def login():
    # Supabase handles token generation
    result = auth_service.sign_in(email, password)
    return jsonify(result)
```

## Timeline

- **Phase 1**: ✅ Complete (30 minutes)
- **Phase 2**: In Progress (2-3 hours)
- **Phase 3**: Pending (3-4 hours)
- **Phase 4**: Pending (1-2 hours)
- **Phase 5**: Pending (2-3 hours)

**Total Estimated Time**: 8-12 hours

## Rollback Plan

If issues arise:
1. Keep dev mode bypass as fallback (temporarily)
2. Use feature flags to toggle between auth systems
3. Maintain backward compatibility for 1 week
4. Monitor error rates and user feedback

## Success Criteria

- [ ] All authentication endpoints use Supabase
- [ ] No more mock tokens in production
- [ ] WebSocket connections secured
- [ ] All tests passing
- [ ] Zero authentication errors in production
- [ ] User migration complete