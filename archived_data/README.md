# Archived Data Files

This directory contains archived data files, reports, and test data from the development and operation of the Cowans Office Supplies Integration System.

## File Types

### CSV Files
- **product_collection_associations.csv** - Product to collection mapping data
- **current_shopify_products_collections.csv** - Current Shopify product collection data
- **old_shopify_products_collections*.csv** - Historical Shopify data snapshots
- **acrylic_associations.csv** - Specific product category associations
- **test_*.csv** - Test data files for development

### JSON Files
- **collection_mapping.json** - Collection mapping configuration
- **product_collection_association_report_*.json** - Association operation reports
- **collections_sync_report_*.json** - Sync operation reports
- **product_type_population_report_*.json** - Product type population reports

### Test Files
- **test_login.html** - Authentication testing page

## Purpose

These files are archived for:
- Historical data reference
- Backup and recovery
- Development debugging
- Performance analysis
- Audit trails

## Data Retention

- Files contain historical snapshots of system state
- May include sensitive product information
- Review before sharing or external use
- Some files may be large (3MB+)

## Current Data

For current operational data, see:
- `/data/` directory (if exists)
- Database records via web dashboard
- Active sync reports via API endpoints

## Usage Notes

- Data may be in various formats and structures
- Some files represent specific points in time
- Verify data currency before use
- Check file timestamps for relevance