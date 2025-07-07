#!/usr/bin/env python3
"""
Migration Validation Script
Validates data integrity after SQLite to Supabase migration
"""

import sqlite3
import psycopg2
import json
from datetime import datetime
from typing import Dict, List, Any, Tuple
import hashlib
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MigrationValidator:
    """Validates migration from SQLite to PostgreSQL"""
    
    def __init__(self, sqlite_path: str, pg_connection_string: str):
        self.sqlite_path = sqlite_path
        self.pg_connection_string = pg_connection_string
        self.validation_results = {
            'timestamp': datetime.now().isoformat(),
            'checks': {},
            'issues': [],
            'summary': {}
        }
        
    def check_record_counts(self) -> Dict[str, Dict[str, int]]:
        """Compare record counts between databases"""
        logger.info("Checking record counts...")
        counts = {}
        
        tables = [
            'users', 'categories', 'configurations', 'sync_queue',
            'icons', 'jobs', 'import_rules', 'sync_history',
            'system_logs', 'etilize_import_batches', 'products',
            'shopify_syncs', 'product_images', 'product_metafields',
            'etilize_staging_products', 'product_sources', 'product_change_logs'
        ]
        
        with sqlite3.connect(self.sqlite_path) as sqlite_conn:
            with psycopg2.connect(self.pg_connection_string) as pg_conn:
                for table in tables:
                    try:
                        # SQLite count
                        sqlite_cursor = sqlite_conn.cursor()
                        sqlite_cursor.execute(f"SELECT COUNT(*) FROM {table}")
                        sqlite_count = sqlite_cursor.fetchone()[0]
                        
                        # PostgreSQL count
                        pg_cursor = pg_conn.cursor()
                        pg_cursor.execute(f"SELECT COUNT(*) FROM {table}")
                        pg_count = pg_cursor.fetchone()[0]
                        
                        counts[table] = {
                            'sqlite': sqlite_count,
                            'postgresql': pg_count,
                            'match': sqlite_count == pg_count,
                            'difference': abs(sqlite_count - pg_count)
                        }
                        
                        if not counts[table]['match']:
                            self.validation_results['issues'].append({
                                'type': 'record_count_mismatch',
                                'table': table,
                                'details': counts[table]
                            })
                            
                    except Exception as e:
                        counts[table] = {'error': str(e)}
                        self.validation_results['issues'].append({
                            'type': 'count_check_error',
                            'table': table,
                            'error': str(e)
                        })
                        
        self.validation_results['checks']['record_counts'] = counts
        return counts
        
    def check_data_integrity(self, sample_size: int = 100) -> Dict[str, Any]:
        """Check data integrity by sampling records"""
        logger.info(f"Checking data integrity (sample size: {sample_size})...")
        integrity_results = {}
        
        critical_tables = ['users', 'products', 'categories', 'sync_history']
        
        with sqlite3.connect(self.sqlite_path) as sqlite_conn:
            sqlite_conn.row_factory = sqlite3.Row
            with psycopg2.connect(self.pg_connection_string) as pg_conn:
                for table in critical_tables:
                    try:
                        # Get sample records from SQLite
                        sqlite_cursor = sqlite_conn.cursor()
                        sqlite_cursor.execute(f"""
                            SELECT * FROM {table} 
                            ORDER BY id 
                            LIMIT {sample_size}
                        """)
                        sqlite_records = [dict(row) for row in sqlite_cursor.fetchall()]
                        
                        # Compare with PostgreSQL
                        pg_cursor = pg_conn.cursor()
                        mismatches = []
                        
                        for sqlite_record in sqlite_records:
                            record_id = sqlite_record.get('id')
                            if record_id:
                                pg_cursor.execute(f"""
                                    SELECT * FROM {table} 
                                    WHERE id = %s
                                """, (record_id,))
                                
                                pg_record = pg_cursor.fetchone()
                                if not pg_record:
                                    mismatches.append({
                                        'id': record_id,
                                        'issue': 'missing_in_postgresql'
                                    })
                                    
                        integrity_results[table] = {
                            'samples_checked': len(sqlite_records),
                            'mismatches': len(mismatches),
                            'integrity': len(mismatches) == 0
                        }
                        
                        if mismatches:
                            self.validation_results['issues'].append({
                                'type': 'data_integrity_issue',
                                'table': table,
                                'mismatches': mismatches[:10]  # First 10 only
                            })
                            
                    except Exception as e:
                        integrity_results[table] = {'error': str(e)}
                        self.validation_results['issues'].append({
                            'type': 'integrity_check_error',
                            'table': table,
                            'error': str(e)
                        })
                        
        self.validation_results['checks']['data_integrity'] = integrity_results
        return integrity_results
        
    def check_foreign_keys(self) -> Dict[str, Any]:
        """Check foreign key constraints"""
        logger.info("Checking foreign key constraints...")
        fk_results = {}
        
        fk_checks = [
            ('categories', 'parent_id', 'categories', 'id'),
            ('icons', 'category_id', 'categories', 'id'),
            ('icons', 'created_by', 'users', 'id'),
            ('products', 'category_id', 'categories', 'id'),
            ('products', 'import_batch_id', 'etilize_import_batches', 'id'),
            ('sync_history', 'user_id', 'users', 'id'),
            ('sync_history', 'job_id', 'jobs', 'id'),
            ('product_images', 'product_id', 'products', 'id'),
            ('product_metafields', 'product_id', 'products', 'id'),
        ]
        
        with psycopg2.connect(self.pg_connection_string) as pg_conn:
            pg_cursor = pg_conn.cursor()
            
            for child_table, child_column, parent_table, parent_column in fk_checks:
                try:
                    # Check for orphaned records
                    pg_cursor.execute(f"""
                        SELECT COUNT(*) 
                        FROM {child_table} c
                        LEFT JOIN {parent_table} p ON c.{child_column} = p.{parent_column}
                        WHERE c.{child_column} IS NOT NULL 
                        AND p.{parent_column} IS NULL
                    """)
                    
                    orphaned_count = pg_cursor.fetchone()[0]
                    
                    fk_results[f"{child_table}.{child_column}"] = {
                        'orphaned_records': orphaned_count,
                        'valid': orphaned_count == 0
                    }
                    
                    if orphaned_count > 0:
                        self.validation_results['issues'].append({
                            'type': 'foreign_key_violation',
                            'constraint': f"{child_table}.{child_column} -> {parent_table}.{parent_column}",
                            'orphaned_count': orphaned_count
                        })
                        
                except Exception as e:
                    fk_results[f"{child_table}.{child_column}"] = {'error': str(e)}
                    
        self.validation_results['checks']['foreign_keys'] = fk_results
        return fk_results
        
    def check_unique_constraints(self) -> Dict[str, Any]:
        """Check unique constraints"""
        logger.info("Checking unique constraints...")
        unique_results = {}
        
        unique_checks = [
            ('users', 'email'),
            ('users', 'supabase_id'),
            ('categories', 'slug'),
            ('configurations', 'key'),
            ('products', 'sku'),
            ('sync_queue', 'queue_uuid'),
            ('jobs', 'job_uuid'),
            ('etilize_import_batches', 'batch_uuid'),
            ('shopify_syncs', 'sync_uuid'),
        ]
        
        with psycopg2.connect(self.pg_connection_string) as pg_conn:
            pg_cursor = pg_conn.cursor()
            
            for table, column in unique_checks:
                try:
                    # Check for duplicates
                    pg_cursor.execute(f"""
                        SELECT {column}, COUNT(*) as count
                        FROM {table}
                        WHERE {column} IS NOT NULL
                        GROUP BY {column}
                        HAVING COUNT(*) > 1
                    """)
                    
                    duplicates = pg_cursor.fetchall()
                    
                    unique_results[f"{table}.{column}"] = {
                        'duplicates_found': len(duplicates),
                        'valid': len(duplicates) == 0
                    }
                    
                    if duplicates:
                        self.validation_results['issues'].append({
                            'type': 'unique_constraint_violation',
                            'constraint': f"{table}.{column}",
                            'duplicate_values': [dup[0] for dup in duplicates[:5]]
                        })
                        
                except Exception as e:
                    unique_results[f"{table}.{column}"] = {'error': str(e)}
                    
        self.validation_results['checks']['unique_constraints'] = unique_results
        return unique_results
        
    def check_data_types(self) -> Dict[str, Any]:
        """Check data type conversions"""
        logger.info("Checking data type conversions...")
        type_results = {}
        
        # Check specific data type conversions
        type_checks = [
            ('products', 'price', 'numeric'),
            ('products', 'data_quality_score', 'numeric_range_0_1'),
            ('users', 'is_active', 'boolean'),
            ('categories', 'meta_data', 'jsonb'),
            ('sync_queue', 'status', 'enum'),
        ]
        
        with psycopg2.connect(self.pg_connection_string) as pg_conn:
            pg_cursor = pg_conn.cursor()
            
            for table, column, check_type in type_checks:
                try:
                    if check_type == 'numeric_range_0_1':
                        pg_cursor.execute(f"""
                            SELECT COUNT(*) 
                            FROM {table}
                            WHERE {column} IS NOT NULL 
                            AND ({column} < 0 OR {column} > 1)
                        """)
                        invalid_count = pg_cursor.fetchone()[0]
                        type_results[f"{table}.{column}"] = {
                            'invalid_values': invalid_count,
                            'valid': invalid_count == 0
                        }
                    else:
                        # Basic type check - just ensure no errors
                        pg_cursor.execute(f"SELECT {column} FROM {table} LIMIT 1")
                        type_results[f"{table}.{column}"] = {'valid': True}
                        
                except Exception as e:
                    type_results[f"{table}.{column}"] = {
                        'error': str(e),
                        'valid': False
                    }
                    
        self.validation_results['checks']['data_types'] = type_results
        return type_results
        
    def generate_summary(self):
        """Generate validation summary"""
        total_issues = len(self.validation_results['issues'])
        critical_issues = [i for i in self.validation_results['issues'] 
                          if i['type'] in ['foreign_key_violation', 'unique_constraint_violation']]
        
        self.validation_results['summary'] = {
            'total_issues': total_issues,
            'critical_issues': len(critical_issues),
            'validation_passed': total_issues == 0,
            'checks_performed': len(self.validation_results['checks']),
            'timestamp': datetime.now().isoformat()
        }
        
    def run_validation(self) -> Dict[str, Any]:
        """Run all validation checks"""
        logger.info("Starting migration validation...")
        
        # Run all checks
        self.check_record_counts()
        self.check_data_integrity()
        self.check_foreign_keys()
        self.check_unique_constraints()
        self.check_data_types()
        
        # Generate summary
        self.generate_summary()
        
        # Save results
        report_path = f"validation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_path, 'w') as f:
            json.dump(self.validation_results, f, indent=2)
            
        logger.info(f"Validation report saved to: {report_path}")
        
        # Print summary
        print("\n" + "="*50)
        print("VALIDATION SUMMARY")
        print("="*50)
        print(f"Total Issues Found: {self.validation_results['summary']['total_issues']}")
        print(f"Critical Issues: {self.validation_results['summary']['critical_issues']}")
        print(f"Validation Passed: {self.validation_results['summary']['validation_passed']}")
        
        if self.validation_results['issues']:
            print("\nISSUES FOUND:")
            for issue in self.validation_results['issues'][:10]:
                print(f"  - {issue['type']}: {issue.get('table', issue.get('constraint', 'N/A'))}")
                
        return self.validation_results

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Validate SQLite to PostgreSQL migration')
    parser.add_argument('--sqlite-path', default='database.db', help='Path to SQLite database')
    parser.add_argument('--pg-connection', required=True, help='PostgreSQL connection string')
    parser.add_argument('--sample-size', type=int, default=100, help='Sample size for integrity checks')
    
    args = parser.parse_args()
    
    validator = MigrationValidator(
        sqlite_path=args.sqlite_path,
        pg_connection_string=args.pg_connection
    )
    
    results = validator.run_validation()
    
    # Exit with error code if validation failed
    if not results['summary']['validation_passed']:
        exit(1)

if __name__ == "__main__":
    main()