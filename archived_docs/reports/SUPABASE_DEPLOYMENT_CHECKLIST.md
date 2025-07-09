# Supabase Authentication Deployment Checklist

## Pre-Deployment Tasks ✅

### Backend Preparation
- [x] Install Supabase Python client (`supabase==2.10.0`)
- [x] Create authentication service (`services/supabase_auth.py`)
- [x] Update User model with `supabase_id` column
- [x] Update UserRepository with Supabase methods
- [x] Create database migration (`004_add_supabase_auth.py`)
- [x] Create WebSocket handlers with auth (`websocket_handlers.py`)
- [x] Write comprehensive tests (`test_supabase_auth.py`)
- [x] Replace `@jwt_required()` decorators (60 replaced)
- [x] Disable dev mode authentication

### Frontend Preparation
- [x] Install Supabase JS client (`@supabase/supabase-js`)
- [x] Create Supabase service (`services/supabase.ts`)
- [x] Create Supabase auth context (`SupabaseAuthContext.tsx`)
- [x] Update API client (`supabaseApi.ts`)
- [x] Create secure WebSocket context (`SupabaseWebSocketContext.tsx`)

### Documentation
- [x] Implementation guide (`SUPABASE_AUTH_COMPLETE_GUIDE.md`)
- [x] Implementation summary (`SUPABASE_AUTH_IMPLEMENTATION_SUMMARY.md`)
- [x] Deployment checklist (this file)

## Deployment Steps 🚀

### 1. Database Migration (5 minutes)
```bash
cd web_dashboard/backend

# Run the migration to add supabase_id column
alembic upgrade head

# Or manually:
sqlite3 database.db
ALTER TABLE users ADD COLUMN supabase_id VARCHAR(255) UNIQUE;
CREATE INDEX idx_users_supabase_id ON users(supabase_id);
```

### 2. Environment Variables (5 minutes)
Ensure these are set in production:

**Backend (.env)**:
```env
SUPABASE_URL=https://gqozcvqgsjaagnnjukmo.supabase.co
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
SUPABASE_JWT_SECRET=your-jwt-secret-from-supabase-dashboard
```

**Frontend (.env)**:
```env
REACT_APP_SUPABASE_URL=https://gqozcvqgsjaagnnjukmo.supabase.co
REACT_APP_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### 3. Backend Updates (15 minutes)
The following manual updates are still needed in `app.py`:

1. **Update Login Endpoint** (lines ~240-276):
   - Replace current login logic with `auth_service.sign_in()`
   - Add Supabase ID syncing

2. **Update Register Endpoint** (lines ~278-323):
   - Replace with `auth_service.sign_up()`
   - Create local user with Supabase ID

3. **Add Refresh Endpoint** (after /api/auth/me):
   ```python
   @app.route("/api/auth/refresh", methods=["POST"])
   def refresh_token():
       # Implementation in SUPABASE_AUTH_COMPLETE_GUIDE.md
   ```

4. **Update get_user_id()** function:
   - Use `get_current_user_id()` from Supabase auth
   - Map to local user ID

### 4. Frontend Deployment (10 minutes)
```bash
cd frontend

# Build with Supabase integration
npm run build

# Deploy to production
# (your deployment command here)
```

### 5. Testing (20 minutes)

#### Backend Tests
```bash
cd web_dashboard/backend

# Run auth tests
pytest tests/test_supabase_auth.py -v

# Test auth endpoints manually
curl -X POST http://localhost:3560/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password"}'
```

#### Frontend Tests
1. Test login flow
2. Test registration
3. Test token refresh
4. Test protected routes
5. Test WebSocket connections

### 6. Monitoring (Ongoing)

Monitor these metrics post-deployment:
- [ ] Authentication success rate
- [ ] Token refresh frequency
- [ ] WebSocket connection stability
- [ ] API response times
- [ ] Error rates

## Rollback Plan 🔄

If issues occur:

1. **Quick Rollback** (5 minutes):
   ```bash
   # Restore backup
   cp app.py.backup_20250707_105611 app.py
   
   # Restart services
   ./start_dashboard.sh
   ```

2. **Gradual Rollback**:
   - Re-enable dev mode temporarily
   - Use feature flags to control auth method
   - Monitor and fix issues

## Post-Deployment Tasks 📋

### Week 1
- [ ] Monitor authentication metrics
- [ ] Gather user feedback
- [ ] Fix any authentication issues
- [ ] Update documentation

### Week 2
- [ ] Enable email verification
- [ ] Configure password policies
- [ ] Set up user roles in Supabase
- [ ] Add forgot password flow

### Month 1
- [ ] Add social auth providers
- [ ] Implement MFA
- [ ] Add user profile management
- [ ] Complete security audit

## Success Criteria ✅

The deployment is successful when:
- [ ] All users can login with Supabase
- [ ] No authentication errors in logs
- [ ] WebSocket connections are stable
- [ ] All protected endpoints work
- [ ] Performance metrics are acceptable

## Support Resources 📚

- [Supabase Documentation](https://supabase.com/docs)
- [Implementation Guide](./SUPABASE_AUTH_COMPLETE_GUIDE.md)
- [Test Suite](./tests/test_supabase_auth.py)
- [Troubleshooting Guide](./SUPABASE_AUTH_IMPLEMENTATION_SUMMARY.md#common-issues--solutions)

## Emergency Contacts 🚨

- DevOps Team: (your contact)
- Backend Lead: (your contact)
- Frontend Lead: (your contact)
- Supabase Support: support@supabase.io

---

**Remember**: Take backups before each step and test thoroughly!