#!/usr/bin/env python3
"""
Initialize database with test data for development.

This script creates the database tables and optionally seeds them with test data.
"""

import sys
import os
from datetime import datetime, timedelta
import random

# Add backend directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import init_database, db_session_scope, DatabaseUtils
from models import User, Category, Product, Icon, Job, SyncHistory, ProductStatus, IconStatus, JobStatus
from repositories import (
    UserRepository, CategoryRepository, ProductRepository, 
    IconRepository, JobRepository, SyncHistoryRepository
)

def create_test_users():
    """Create test users."""
    print("Creating test users...")
    
    with db_session_scope() as session:
        user_repo = UserRepository(session)
        
        # Create admin user
        if not user_repo.get_by_email("admin@example.com"):
            admin = user_repo.create_user(
                email="admin@example.com",
                password="admin123",
                first_name="Admin",
                last_name="User",
                is_admin=True
            )
            print(f"Created admin user: {admin.email}")
        
        # Create regular user
        if not user_repo.get_by_email("test@example.com"):
            test_user = user_repo.create_user(
                email="test@example.com",
                password="test123",
                first_name="Test",
                last_name="User",
                is_admin=False
            )
            print(f"Created test user: {test_user.email}")
        
        session.commit()

def create_test_categories():
    """Create test category hierarchy."""
    print("\nCreating test categories...")
    
    with db_session_scope() as session:
        category_repo = CategoryRepository(session)
        
        # Root categories
        categories = [
            ("Office Supplies", "office-supplies", "Essential office supplies and equipment"),
            ("Technology", "technology", "Computer and technology products"),
            ("Furniture", "furniture", "Office furniture and storage solutions"),
            ("Paper Products", "paper-products", "Paper, notebooks, and printing supplies")
        ]
        
        created_categories = {}
        
        for name, slug, description in categories:
            if not category_repo.get_by_slug(slug):
                category = category_repo.create_with_path(
                    name=name,
                    slug=slug,
                    description=description
                )
                created_categories[slug] = category
                print(f"Created category: {name}")
        
        # Sub-categories
        subcategories = [
            ("Pens & Pencils", "pens-pencils", "Writing instruments", "office-supplies"),
            ("Notebooks", "notebooks", "Notebooks and notepads", "paper-products"),
            ("Printers", "printers", "Printers and accessories", "technology"),
            ("Desks", "desks", "Office desks and workstations", "furniture"),
            ("Staplers", "staplers", "Staplers and staples", "office-supplies"),
            ("Paper", "paper", "Printer and copy paper", "paper-products")
        ]
        
        for name, slug, description, parent_slug in subcategories:
            if not category_repo.get_by_slug(slug):
                parent = created_categories.get(parent_slug) or category_repo.get_by_slug(parent_slug)
                if parent:
                    subcategory = category_repo.create_with_path(
                        name=name,
                        slug=slug,
                        description=description,
                        parent_id=parent.id
                    )
                    print(f"Created subcategory: {name} under {parent.name}")
        
        session.commit()

def create_test_products():
    """Create test products."""
    print("\nCreating test products...")
    
    with db_session_scope() as session:
        category_repo = CategoryRepository(session)
        product_repo = ProductRepository(session)
        
        # Get categories
        pens_category = category_repo.get_by_slug("pens-pencils")
        notebooks_category = category_repo.get_by_slug("notebooks")
        printers_category = category_repo.get_by_slug("printers")
        
        if not pens_category or not notebooks_category or not printers_category:
            print("Categories not found, skipping product creation")
            return
        
        # Sample products
        products = [
            # Pens
            {
                "sku": "PEN001",
                "name": "BIC Cristal Original Ballpoint Pen - Blue",
                "description": "Classic ballpoint pen with transparent barrel",
                "price": 0.25,
                "brand": "BIC",
                "manufacturer": "BIC Corporation",
                "category_id": pens_category.id,
                "inventory_quantity": 1000,
                "status": ProductStatus.ACTIVE.value
            },
            {
                "sku": "PEN002",
                "name": "Pilot G2 Gel Pen - Black",
                "description": "Premium gel pen with smooth writing experience",
                "price": 2.50,
                "brand": "Pilot",
                "manufacturer": "Pilot Corporation",
                "category_id": pens_category.id,
                "inventory_quantity": 500,
                "status": ProductStatus.ACTIVE.value
            },
            # Notebooks
            {
                "sku": "NB001",
                "name": "Moleskine Classic Notebook - Large",
                "description": "Classic hardcover notebook with elastic closure",
                "price": 24.95,
                "brand": "Moleskine",
                "manufacturer": "Moleskine SpA",
                "category_id": notebooks_category.id,
                "inventory_quantity": 200,
                "status": ProductStatus.ACTIVE.value
            },
            {
                "sku": "NB002",
                "name": "Rhodia Dot Pad - A4",
                "description": "Premium dot grid notepad for sketching and notes",
                "price": 18.00,
                "brand": "Rhodia",
                "manufacturer": "Clairefontaine",
                "category_id": notebooks_category.id,
                "inventory_quantity": 150,
                "status": ProductStatus.ACTIVE.value
            },
            # Printers
            {
                "sku": "PRNT001",
                "name": "HP LaserJet Pro M404n",
                "description": "Business laser printer with network connectivity",
                "price": 299.99,
                "brand": "HP",
                "manufacturer": "Hewlett-Packard",
                "category_id": printers_category.id,
                "inventory_quantity": 25,
                "status": ProductStatus.ACTIVE.value
            },
            {
                "sku": "PRNT002",
                "name": "Canon PIXMA TR8620",
                "description": "All-in-one wireless printer for home office",
                "price": 179.99,
                "brand": "Canon",
                "manufacturer": "Canon Inc.",
                "category_id": printers_category.id,
                "inventory_quantity": 30,
                "status": ProductStatus.ACTIVE.value
            }
        ]
        
        for product_data in products:
            if not product_repo.get_by_sku(product_data['sku']):
                product = product_repo.create(**product_data)
                print(f"Created product: {product.name}")
        
        session.commit()

def create_test_icons():
    """Create test icon records."""
    print("\nCreating test icon records...")
    
    with db_session_scope() as session:
        category_repo = CategoryRepository(session)
        icon_repo = IconRepository(session)
        user_repo = UserRepository(session)
        
        # Get admin user
        admin = user_repo.get_by_email("admin@example.com")
        if not admin:
            print("Admin user not found, skipping icon creation")
            return
        
        # Get categories
        categories = category_repo.get_all(limit=5)
        
        for category in categories:
            # Check if category already has an icon
            existing_icon = icon_repo.get_active_by_category(category.id)
            if not existing_icon:
                icon = icon_repo.create(
                    category_id=category.id,
                    filename=f"category_{category.id}_icon.png",
                    file_path=f"/data/category_icons/{category.slug}.png",
                    width=128,
                    height=128,
                    format="PNG",
                    prompt=f"Modern icon for {category.name} category",
                    style="modern",
                    color="#3B82F6",
                    background="transparent",
                    model="placeholder",
                    status=IconStatus.ACTIVE.value,
                    created_by=admin.id
                )
                print(f"Created icon for category: {category.name}")
        
        session.commit()

def create_test_jobs():
    """Create test job records."""
    print("\nCreating test job records...")
    
    with db_session_scope() as session:
        job_repo = JobRepository(session)
        user_repo = UserRepository(session)
        
        # Get admin user
        admin = user_repo.get_by_email("admin@example.com")
        if not admin:
            print("Admin user not found, skipping job creation")
            return
        
        # Create some completed jobs
        jobs = [
            {
                "script_name": "full_product_sync",
                "display_name": "Full Product Sync",
                "description": "Complete product synchronization from FTP",
                "status": JobStatus.COMPLETED.value,
                "progress": 100
            },
            {
                "script_name": "icon_generation_batch",
                "display_name": "Batch Icon Generation",
                "description": "Generated icons for 10 categories",
                "status": JobStatus.COMPLETED.value,
                "progress": 100
            },
            {
                "script_name": "shopify_upload",
                "display_name": "Shopify Product Upload",
                "description": "Upload products to Shopify",
                "status": JobStatus.RUNNING.value,
                "progress": 45
            }
        ]
        
        for job_data in jobs:
            job = job_repo.create_job(
                script_name=job_data["script_name"],
                user_id=admin.id,
                display_name=job_data["display_name"],
                description=job_data["description"]
            )
            
            # Update job status
            if job_data["status"] == JobStatus.RUNNING.value:
                job_repo.start_job(job.id)
                job_repo.update_progress(job.id, job_data["progress"])
            elif job_data["status"] == JobStatus.COMPLETED.value:
                job_repo.start_job(job.id)
                job_repo.complete_job(job.id)
            
            print(f"Created job: {job_data['display_name']}")
        
        session.commit()

def create_test_sync_history():
    """Create test sync history records."""
    print("\nCreating test sync history records...")
    
    with db_session_scope() as session:
        sync_repo = SyncHistoryRepository(session)
        user_repo = UserRepository(session)
        
        # Get admin user
        admin = user_repo.get_by_email("admin@example.com")
        if not admin:
            print("Admin user not found, skipping sync history creation")
            return
        
        # Create sync records
        sync = sync_repo.create_sync_record(
            sync_type="full_import",
            user_id=admin.id,
            sync_source="etilize_ftp",
            sync_target="shopify"
        )
        
        sync_repo.start_sync(sync.id, total_items=100)
        sync_repo.update_progress(sync.id, 100, 95, 5, 0)
        sync_repo.update_sync_counts(sync.id, products_synced=95, categories_synced=10)
        sync_repo.complete_sync(sync.id, "Sync completed with 5 errors")
        
        print("Created sync history record")
        
        session.commit()

def main():
    """Main function to initialize database and create test data."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Initialize the database')
    parser.add_argument('--force', action='store_true', help='Force reinitialize the database')
    parser.add_argument('--skip-prompt', action='store_true', help='Skip interactive prompts (for Docker)')
    parser.add_argument('--with-test-data', action='store_true', help='Create test data')
    
    args = parser.parse_args()
    
    print("Initializing database...")
    
    # Initialize database (creates tables)
    init_database(create_tables=True)
    print("Database tables created successfully")
    
    # Seed initial configuration
    DatabaseUtils.seed_initial_data()
    print("Initial configuration seeded")
    
    # Determine if we should create test data
    create_test = False
    if args.with_test_data:
        create_test = True
    elif not args.skip_prompt:
        response = input("\nDo you want to create test data? (y/n): ").lower()
        create_test = response == 'y'
    
    if create_test:
        create_test_users()
        create_test_categories()
        create_test_products()
        create_test_icons()
        create_test_jobs()
        create_test_sync_history()
        
        print("\nTest data created successfully!")
        print("\nYou can now login with:")
        print("  Admin: admin@example.com / admin123")
        print("  User: test@example.com / test123")
    else:
        print("\nDatabase initialized without test data.")
        print("Creating default admin user...")
        
        # Create at least one admin user
        with db_session_scope() as session:
            user_repo = UserRepository(session)
            if not user_repo.get_by_email("admin@cowans.com"):
                admin = user_repo.create_user(
                    email="admin@cowans.com",
                    password="changeme123",
                    first_name="Admin",
                    last_name="User",
                    is_admin=True
                )
                session.commit()
                print(f"\nCreated admin user: admin@cowans.com / changeme123")
                print("Please change the password after first login!")

if __name__ == "__main__":
    main()