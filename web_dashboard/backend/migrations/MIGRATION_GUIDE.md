# SQLite to Supabase PostgreSQL Migration Guide

## Overview

This guide provides step-by-step instructions for migrating the web dashboard database from SQLite to Supabase PostgreSQL. The migration has been designed and orchestrated by a specialized ruv-swarm with the following agents:

- **Schema Analyzer** - Analyzed SQLite schema and created PostgreSQL-compatible DDL
- **Data Mapper** - Mapped SQLite data types to PostgreSQL equivalents
- **Migration Orchestrator** - Coordinated the migration process
- **Data Validator** - Validates data integrity after migration
- **Rollback Manager** - Handles backup and rollback procedures

## Prerequisites

1. **Supabase Project**
   - Create a new Supabase project at https://app.supabase.com
   - Note your project URL and service role key

2. **Python Dependencies**
   ```bash
   pip install psycopg2-binary tqdm
   ```

3. **Database Access**
   - Ensure you have read access to the SQLite database
   - Ensure you have write access to the Supabase PostgreSQL database

## Migration Steps

### Step 1: Backup SQLite Database

Always create a backup before migration:

```bash
cp database.db database.db.backup_$(date +%Y%m%d_%H%M%S)
```

### Step 2: Set Up Supabase Database Schema

1. Connect to your Supabase project's SQL Editor
2. Run the schema creation script:
   ```bash
   # In Supabase SQL Editor, paste and run the contents of:
   # migrations/sqlite_to_supabase_migration.sql
   ```

This will create:
- All required tables with proper data types
- Indexes for performance optimization
- Foreign key constraints
- Row Level Security (RLS) policies
- Triggers for automatic timestamp updates
- Custom enums for status fields

### Step 3: Configure Connection String

Create your PostgreSQL connection string:

```
postgresql://postgres.[project-ref]:[password]@[host]:5432/postgres
```

Or use the pooler connection for better performance:
```
postgresql://postgres.[project-ref]:[password]@[host]:6543/postgres?pgbouncer=true
```

### Step 4: Run Data Migration

Execute the migration script:

```bash
cd web_dashboard/backend/migrations

python migrate_sqlite_to_supabase.py \
  --sqlite-path ../database.db \
  --pg-connection "your-connection-string" \
  --batch-size 1000
```

The script will:
- Connect to both databases
- Create a backup of SQLite database
- Migrate tables in dependency order
- Convert data types appropriately
- Handle JSON/JSONB conversions
- Process data in batches for efficiency
- Generate a migration report

### Step 5: Validate Migration

Run the validation script to ensure data integrity:

```bash
python validate_migration.py \
  --sqlite-path ../database.db \
  --pg-connection "your-connection-string" \
  --sample-size 100
```

The validation checks:
- Record counts match between databases
- Data integrity through sampling
- Foreign key constraints are maintained
- Unique constraints are preserved
- Data type conversions are correct

### Step 6: Update Application Configuration

1. Update your `.env` file:
   ```env
   # Remove SQLite configuration
   # DATABASE_URL=sqlite:///database.db
   
   # Add Supabase configuration
   SUPABASE_URL=https://[project-ref].supabase.co
   SUPABASE_ANON_KEY=your-anon-key
   SUPABASE_SERVICE_KEY=your-service-key
   DATABASE_URL=postgresql://postgres.[project-ref]:[password]@[host]:5432/postgres
   ```

2. Update `database.py` to use PostgreSQL:
   ```python
   from sqlalchemy import create_engine
   from sqlalchemy.orm import sessionmaker
   import os
   
   # Use PostgreSQL URL from environment
   DATABASE_URL = os.getenv("DATABASE_URL")
   
   engine = create_engine(
       DATABASE_URL,
       pool_pre_ping=True,
       pool_size=10,
       max_overflow=20
   )
   
   SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
   ```

3. Update SQLAlchemy models if needed:
   - Change `String` to `Text` for unlimited length fields
   - Update any SQLite-specific syntax
   - Add PostgreSQL-specific features if desired

### Step 7: Test Application

1. Start the application with the new database:
   ```bash
   python app.py
   ```

2. Test critical functionality:
   - User authentication
   - Product listing and search
   - Category browsing
   - Sync operations
   - Icon generation
   - Admin functions

### Step 8: Enable Row Level Security (RLS)

For production, configure RLS policies:

```sql
-- Example: Users can only see their own data
CREATE POLICY "Users can view own data" ON sync_history
  FOR SELECT
  USING (auth.uid() = (SELECT supabase_id FROM users WHERE id = user_id));

-- Example: Only admins can modify categories
CREATE POLICY "Admins can modify categories" ON categories
  FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM users
      WHERE users.supabase_id = auth.uid()
      AND users.is_admin = true
    )
  );
```

## Rollback Procedure

If you need to rollback to SQLite:

1. Stop the application
2. Restore the SQLite backup:
   ```bash
   cp database.db.backup_YYYYMMDD_HHMMSS database.db
   ```
3. Revert `.env` configuration
4. Restart the application

## Migration Challenges and Solutions

### 1. Data Type Conversions

| SQLite Type | PostgreSQL Type | Conversion Notes |
|-------------|-----------------|------------------|
| INTEGER (boolean) | BOOLEAN | 0/1 → false/true |
| TEXT (JSON) | JSONB | Parse and validate JSON |
| DATETIME | TIMESTAMPTZ | Add timezone info |
| REAL | DECIMAL | Precision handling |
| VARCHAR | TEXT/VARCHAR | Length constraints |

### 2. UUID Generation

SQLite uses VARCHAR for UUIDs, PostgreSQL has native UUID type:
- New records: Use `uuid_generate_v4()`
- Existing records: Validate format and convert

### 3. Enum Types

PostgreSQL enums provide better type safety:
- `job_status`: pending, running, completed, failed, cancelled, paused
- `sync_status`: pending, in_progress, completed, failed, partial, cancelled
- `product_status`: draft, active, archived, deleted

### 4. Foreign Key Constraints

PostgreSQL enforces FK constraints more strictly:
- Migration handles dependencies in correct order
- Orphaned records are reported in validation

### 5. Case Sensitivity

PostgreSQL is case-sensitive for string comparisons:
- Use CITEXT for case-insensitive emails
- Update queries that rely on case-insensitive matching

## Performance Optimizations

### 1. Connection Pooling

Use Supabase's connection pooler for better performance:
```python
# In database.py
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=20,
    max_overflow=40,
    pool_recycle=3600
)
```

### 2. Batch Operations

For bulk inserts/updates:
```python
from psycopg2.extras import execute_batch

execute_batch(cursor, query, data, page_size=1000)
```

### 3. Indexes

The migration creates indexes for common queries:
- Product SKU lookups
- Category hierarchy traversal
- Sync status filtering
- User authentication

### 4. Materialized Views

Consider creating materialized views for complex queries:
```sql
CREATE MATERIALIZED VIEW product_inventory_summary AS
SELECT 
    c.name as category,
    COUNT(p.id) as product_count,
    SUM(p.inventory_quantity) as total_inventory
FROM products p
JOIN categories c ON p.category_id = c.id
GROUP BY c.id, c.name;

CREATE INDEX idx_product_inventory_category ON product_inventory_summary(category);
```

## Monitoring and Maintenance

### 1. Monitor Performance

Use Supabase dashboard to monitor:
- Query performance
- Database size
- Connection count
- Cache hit ratio

### 2. Regular Maintenance

Schedule regular maintenance:
```sql
-- Analyze tables for query optimization
ANALYZE;

-- Vacuum to reclaim space
VACUUM ANALYZE;

-- Reindex if needed
REINDEX DATABASE postgres;
```

### 3. Backup Strategy

Supabase provides automatic backups:
- Point-in-time recovery (PITR)
- Daily backups retained for 7-30 days
- Manual backups before major changes

## Troubleshooting

### Common Issues

1. **Connection Refused**
   - Check firewall rules
   - Verify connection string
   - Ensure SSL mode if required

2. **Permission Denied**
   - Check RLS policies
   - Verify user roles
   - Use service role key for migrations

3. **Data Type Errors**
   - Review type conversions
   - Check for null values
   - Validate JSON format

4. **Performance Issues**
   - Add missing indexes
   - Optimize queries
   - Enable connection pooling

### Debug Mode

Enable debug logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Next Steps

1. **Implement Supabase Auth**
   - Migrate from JWT to Supabase Auth
   - Update user management

2. **Real-time Features**
   - Enable real-time subscriptions
   - Implement live sync status updates

3. **Edge Functions**
   - Move complex logic to edge functions
   - Implement background jobs

4. **Storage Integration**
   - Migrate file storage to Supabase Storage
   - Update image URLs

## Support

For issues or questions:
- Check Supabase documentation: https://supabase.com/docs
- Review PostgreSQL documentation: https://www.postgresql.org/docs/
- Check migration logs in `migration.log`
- Review validation reports

## Conclusion

This migration provides several benefits:
- Better performance with PostgreSQL
- Native JSON support with JSONB
- Stronger data integrity with constraints
- Row Level Security for multi-tenancy
- Real-time capabilities
- Automatic backups and scaling

The ruv-swarm agents have designed this migration to be safe, efficient, and reversible. Follow the steps carefully and always test in a development environment first.