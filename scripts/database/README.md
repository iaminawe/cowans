# Database Scripts

This directory contains scripts for database checking, schema validation, and data integrity operations.

## Scripts:
- `check_collections_schema.py` - Validate collections table schema in Supabase
- `check_database_status.py` - Check overall database status and health
- `check_deletion_damage.py` - Assess damage from deletion operations
- `check_product_categories.py` - Validate product categorization
- `check_real_products.py` - Verify real vs test products
- `test_db_connection.py` - Test database connectivity

## Usage:
Run from project root to ensure proper environment loading:

```bash
cd /path/to/cowans
python scripts/database/check_database_status.py
```