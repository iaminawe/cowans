# SQLite to Supabase PostgreSQL Migration Guide

## Overview

This guide walks you through migrating your SQLite database to Supabase PostgreSQL. The migration includes schema creation, data migration, and validation.

## Prerequisites

1. **Supabase Account**: Create a project at [supabase.com](https://supabase.com)
2. **Database Credentials**: Get your database connection details from Supabase dashboard
3. **Python Dependencies**: Install required packages:
   ```bash
   pip install psycopg2-binary python-dotenv tqdm
   ```

## Step 1: Configure Database Connection

### Get Supabase Database Credentials

1. Go to your Supabase dashboard
2. Navigate to **Settings** → **Database**
3. Find the **Connection string** section
4. Copy the connection details

### Update Environment Variables

Add these to your `.env` file:

```env
# Supabase Database Configuration
SUPABASE_DB_HOST=db.YOUR_PROJECT_ID.supabase.co
SUPABASE_DB_PORT=5432
SUPABASE_DB_NAME=postgres
SUPABASE_DB_USER=postgres
SUPABASE_DB_PASSWORD=your-database-password

# OR use the full connection string
SUPABASE_DB_URL=postgresql://postgres:your-password@db.YOUR_PROJECT_ID.supabase.co:5432/postgres
```

## Step 2: Create Database Schema

Run the schema creation script:

```bash
cd web_dashboard/backend
python create_supabase_schema.py
```

This will:
- Connect to your Supabase database
- Create all tables with proper data types
- Set up indexes and constraints
- Enable Row Level Security (RLS)
- Create triggers for automatic timestamps

Expected output:
```
=== Supabase Schema Creation ===
Connected successfully!
Found 77 SQL statements to execute
Executing statement 1/77: CREATE...
...
✅ Schema creation completed successfully!

Tables in database (17):
  - categories
  - configurations
  - etilize_import_batches
  - etilize_staging_products
  - icons
  - import_rules
  - jobs
  - product_change_logs
  - product_images
  - product_metafields
  - product_sources
  - products
  - shopify_syncs
  - sync_history
  - sync_queue
  - system_logs
  - users
```

## Step 3: Migrate Data

### Review Migration Configuration

Check `supabase_migration_config.py` to ensure:
- Database paths are correct
- Batch size is appropriate (default: 1000)
- Table order respects foreign key dependencies

### Run Data Migration

```bash
python migrations/migrate_sqlite_to_supabase.py
```

This will:
- Create a backup of your SQLite database
- Connect to both databases
- Migrate data table by table
- Handle data type conversions
- Show progress for each table
- Generate a migration report

Expected output:
```
=== SQLite to Supabase Migration ===
Creating backup...
✅ Backup created: database.db.backup_20250107_120000

Connecting to databases...
✅ Connected to SQLite: database.db
✅ Connected to Supabase

Starting migration...
Migrating users: 100%|████████| 150/150 [00:02<00:00, 75.00it/s]
✅ users: 150 records migrated
...

=== Migration Summary ===
Total tables: 17
Total records: 25,685
Duration: 45.2 seconds
```

## Step 4: Validate Migration

Run the validation script to ensure data integrity:

```bash
python migrations/validate_migration.py
```

This will:
- Compare record counts
- Validate sample data
- Check foreign key relationships
- Verify data type conversions
- Generate a validation report

Expected output:
```
=== Migration Validation ===
Validating record counts...
✅ users: 150 records (match)
✅ products: 24,535 records (match)
...

Validating data integrity...
✅ All validations passed!
```

## Step 5: Update Application Configuration

### Update Database URL

In your `.env` file, update the database URL:

```env
# Old SQLite configuration
# DATABASE_URL=sqlite:///database.db

# New Supabase configuration
DATABASE_URL=postgresql://postgres:your-password@db.YOUR_PROJECT_ID.supabase.co:5432/postgres
```

### Update SQLAlchemy Configuration

The migration automatically handles PostgreSQL-specific features:
- JSONB for JSON fields
- Arrays for list fields
- Proper boolean types
- UUID support
- Timezone-aware timestamps

## Step 6: Test Application

1. **Start the application**:
   ```bash
   python app.py
   ```

2. **Test key features**:
   - User authentication
   - Product listing
   - Category browsing
   - Icon generation
   - Sync operations

3. **Monitor logs** for any database-related errors

## Rollback Procedure

If issues occur:

### 1. Restore SQLite (Immediate)
```bash
# The original database is unchanged
# Just revert DATABASE_URL in .env
DATABASE_URL=sqlite:///database.db
```

### 2. Drop Supabase Tables (Clean Slate)
```sql
-- Connect to Supabase SQL Editor and run:
DROP SCHEMA public CASCADE;
CREATE SCHEMA public;
```

### 3. Restore from Backup
```bash
# Backups are created automatically
cp database.db.backup_20250107_120000 database.db
```

## Troubleshooting

### Connection Issues
- Verify database credentials
- Check network connectivity
- Ensure Supabase project is active

### Migration Errors
- Check `migration_report_*.json` for details
- Review error logs
- Verify data types match

### Performance Issues
- Adjust BATCH_SIZE in config
- Check Supabase connection pooling
- Monitor database metrics

## Post-Migration Optimization

### 1. Enable Connection Pooling
In Supabase dashboard:
- Settings → Database → Connection Pooling
- Enable "Session" mode
- Use pooler connection string

### 2. Set Up Indexes
Review slow queries and add indexes:
```sql
-- Example: Add index for common queries
CREATE INDEX idx_products_sku ON products(sku);
CREATE INDEX idx_products_status ON products(status);
```

### 3. Configure RLS Policies
Update Row Level Security policies for your use case:
```sql
-- Example: Users can only see their own data
CREATE POLICY "Users can view own data" ON users
  FOR SELECT USING (auth.uid() = supabase_id);
```

## Monitoring

### Database Metrics
- Monitor in Supabase dashboard
- Set up alerts for slow queries
- Track connection usage

### Application Logs
- Monitor migration-related errors
- Track query performance
- Watch for connection pool exhaustion

## Success Checklist

- [ ] Schema created successfully
- [ ] All data migrated
- [ ] Validation passed
- [ ] Application connects to Supabase
- [ ] Authentication works
- [ ] Key features tested
- [ ] Performance acceptable
- [ ] Monitoring enabled

## Next Steps

1. **Update deployment scripts** to use PostgreSQL
2. **Set up database backups** in Supabase
3. **Configure monitoring** and alerts
4. **Optimize queries** for PostgreSQL
5. **Plan for scaling** with connection pooling

---

**Congratulations!** 🎉 Your database has been successfully migrated to Supabase PostgreSQL.