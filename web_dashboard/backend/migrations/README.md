# Database Migrations

This directory contains Alembic database migrations for the Product Feed Integration System.

## Overview

We use Alembic for database schema versioning and migrations. Alembic provides:
- Automatic migration generation from SQLAlchemy models
- Version control for database schema changes
- Upgrade and downgrade capabilities
- Support for multiple database backends

## Quick Start

### Initialize Database

To initialize a new database with all migrations:

```bash
# Basic initialization
python init_db.py

# With admin user
python init_db.py --admin-email admin@example.com --admin-password securepassword

# With custom database URL
python init_db.py --database-url postgresql://user:pass@localhost/dbname
```

### Create a New Migration

1. Make changes to models in `models.py`
2. Generate migration automatically:
   ```bash
   alembic revision --autogenerate -m "Description of changes"
   ```
3. Review and edit the generated migration file in `versions/`
4. Apply the migration:
   ```bash
   alembic upgrade head
   ```

### Common Commands

```bash
# Check current migration status
alembic current

# Show migration history
alembic history

# Upgrade to latest migration
alembic upgrade head

# Upgrade to specific revision
alembic upgrade <revision>

# Downgrade one revision
alembic downgrade -1

# Downgrade to specific revision
alembic downgrade <revision>

# Show SQL for migration (without applying)
alembic upgrade head --sql

# Stamp database with specific revision (without running migration)
alembic stamp <revision>
```

## Migration Files

Migration files are stored in the `versions/` directory. Each migration has:
- A unique revision ID
- Upgrade and downgrade functions
- Dependencies on previous migrations

### Migration Structure

```python
"""Description of the migration

Revision ID: abc123
Revises: def456
Create Date: 2025-01-03

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'abc123'
down_revision = 'def456'

def upgrade():
    # Changes to apply
    pass

def downgrade():
    # Changes to reverse
    pass
```

## Best Practices

1. **Always review auto-generated migrations** - Alembic's autogenerate is helpful but not perfect
2. **Test migrations** - Run upgrade and downgrade on a test database
3. **Keep migrations small** - One logical change per migration
4. **Write clear descriptions** - Use meaningful messages for migrations
5. **Don't edit applied migrations** - Create new migrations for changes
6. **Backup before major changes** - Use `init_db.py --backup` or manual backup

## Database Support

The migration system supports:
- SQLite (default for development)
- PostgreSQL (recommended for production)
- MySQL/MariaDB

SQLite-specific features:
- Foreign key constraints are enabled
- WAL mode for better concurrency
- Automatic connection handling for threads

## Troubleshooting

### Migration Conflicts

If you have migration conflicts:
1. Check current status: `alembic current`
2. Review history: `alembic history`
3. Manually resolve in the database if needed
4. Re-stamp if necessary: `alembic stamp <revision>`

### Failed Migrations

If a migration fails:
1. Check the error message
2. Fix the issue in the migration file
3. If partially applied, manually reverse changes
4. Re-run the migration

### Database Lock Issues (SQLite)

If you get "database is locked" errors:
1. Ensure no other processes are accessing the database
2. Check for long-running transactions
3. Consider using PostgreSQL for production

## Environment Variables

- `DATABASE_URL`: Override database connection string
- `MIGRATION_AUTO_UPGRADE`: Auto-run migrations on startup (production)
- `MIGRATION_BACKUP_BEFORE_UPGRADE`: Create backup before migrations

## Integration with Application

The application can automatically run migrations on startup:

```python
from init_db import DatabaseInitializer

# In your app startup
initializer = DatabaseInitializer()
if not initializer.run_migrations():
    raise Exception("Failed to run migrations")
```

## Manual Database Operations

For direct database access:

```python
from database import db_manager, db_session_scope

# Use context manager for transactions
with db_session_scope() as session:
    # Your database operations
    pass
```