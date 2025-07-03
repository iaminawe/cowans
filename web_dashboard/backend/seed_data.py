"""
Seed Data Module

This module provides functions to generate sample data for testing
and initial category hierarchy setup.
"""

import random
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from faker import Faker

from sqlalchemy.orm import Session
from werkzeug.security import generate_password_hash

from database import db_session_scope, DatabaseUtils
from models import (
    User, Category, Product, Icon, Job, SyncHistory,
    ProductStatus, SyncStatus, IconStatus, JobStatus, Configuration
)

# Configure logging
logger = logging.getLogger(__name__)

# Initialize Faker
fake = Faker()


class CategorySeeder:
    """Seeds category hierarchy data."""
    
    @staticmethod
    def seed_default_categories() -> Dict[str, int]:
        """Create default category hierarchy."""
        stats = {
            'created': 0,
            'skipped': 0,
            'errors': 0
        }
        
        # Define category hierarchy
        category_hierarchy = [
            {
                'name': 'Office Supplies',
                'slug': 'office-supplies',
                'description': 'General office supplies and stationery',
                'children': [
                    {
                        'name': 'Writing Instruments',
                        'slug': 'writing-instruments',
                        'description': 'Pens, pencils, markers, and highlighters',
                        'children': [
                            {'name': 'Pens', 'slug': 'pens', 'description': 'Ballpoint, gel, and fountain pens'},
                            {'name': 'Pencils', 'slug': 'pencils', 'description': 'Wooden and mechanical pencils'},
                            {'name': 'Markers', 'slug': 'markers', 'description': 'Permanent and dry-erase markers'},
                            {'name': 'Highlighters', 'slug': 'highlighters', 'description': 'Fluorescent highlighters'}
                        ]
                    },
                    {
                        'name': 'Paper Products',
                        'slug': 'paper-products',
                        'description': 'Notebooks, notepads, and paper',
                        'children': [
                            {'name': 'Notebooks', 'slug': 'notebooks', 'description': 'Spiral and bound notebooks'},
                            {'name': 'Notepads', 'slug': 'notepads', 'description': 'Legal pads and memo pads'},
                            {'name': 'Copy Paper', 'slug': 'copy-paper', 'description': 'Printer and copier paper'},
                            {'name': 'Specialty Paper', 'slug': 'specialty-paper', 'description': 'Card stock and photo paper'}
                        ]
                    },
                    {
                        'name': 'Desk Accessories',
                        'slug': 'desk-accessories',
                        'description': 'Organizers, holders, and desk tools',
                        'children': [
                            {'name': 'Pen Holders', 'slug': 'pen-holders', 'description': 'Desktop pen and pencil holders'},
                            {'name': 'Desk Organizers', 'slug': 'desk-organizers', 'description': 'Multi-compartment organizers'},
                            {'name': 'Staplers', 'slug': 'staplers', 'description': 'Desktop and handheld staplers'},
                            {'name': 'Tape Dispensers', 'slug': 'tape-dispensers', 'description': 'Desktop tape dispensers'}
                        ]
                    },
                    {
                        'name': 'Filing & Storage',
                        'slug': 'filing-storage',
                        'description': 'File folders, binders, and storage',
                        'children': [
                            {'name': 'File Folders', 'slug': 'file-folders', 'description': 'Manila and hanging folders'},
                            {'name': 'Binders', 'slug': 'binders', 'description': 'Ring binders and portfolios'},
                            {'name': 'Storage Boxes', 'slug': 'storage-boxes', 'description': 'File and storage boxes'},
                            {'name': 'Labels', 'slug': 'labels', 'description': 'File and shipping labels'}
                        ]
                    }
                ]
            },
            {
                'name': 'Technology',
                'slug': 'technology',
                'description': 'Computer accessories and tech products',
                'children': [
                    {
                        'name': 'Computer Accessories',
                        'slug': 'computer-accessories',
                        'description': 'Keyboards, mice, and cables',
                        'children': [
                            {'name': 'Keyboards', 'slug': 'keyboards', 'description': 'Wired and wireless keyboards'},
                            {'name': 'Mice', 'slug': 'mice', 'description': 'Optical and wireless mice'},
                            {'name': 'Cables', 'slug': 'cables', 'description': 'USB, HDMI, and power cables'},
                            {'name': 'USB Drives', 'slug': 'usb-drives', 'description': 'Flash drives and storage'}
                        ]
                    },
                    {
                        'name': 'Printers & Supplies',
                        'slug': 'printers-supplies',
                        'description': 'Printers and ink cartridges',
                        'children': [
                            {'name': 'Inkjet Printers', 'slug': 'inkjet-printers', 'description': 'Home and office inkjet printers'},
                            {'name': 'Laser Printers', 'slug': 'laser-printers', 'description': 'Monochrome and color laser printers'},
                            {'name': 'Ink Cartridges', 'slug': 'ink-cartridges', 'description': 'OEM and compatible ink'},
                            {'name': 'Toner Cartridges', 'slug': 'toner-cartridges', 'description': 'Laser printer toner'}
                        ]
                    }
                ]
            },
            {
                'name': 'Furniture',
                'slug': 'furniture',
                'description': 'Office furniture and seating',
                'children': [
                    {
                        'name': 'Desks', 'slug': 'desks', 'description': 'Computer and writing desks'
                    },
                    {
                        'name': 'Chairs', 'slug': 'chairs', 'description': 'Office and task chairs'
                    },
                    {
                        'name': 'Storage', 'slug': 'storage-furniture', 'description': 'Cabinets and shelving'
                    }
                ]
            }
        ]
        
        try:
            with db_session_scope() as session:
                def create_category(cat_data: dict, parent: Optional[Category] = None, level: int = 0) -> Category:
                    """Recursively create categories."""
                    # Check if category exists
                    existing = session.query(Category).filter_by(slug=cat_data['slug']).first()
                    
                    if existing:
                        stats['skipped'] += 1
                        return existing
                    
                    # Create category
                    category = Category(
                        name=cat_data['name'],
                        slug=cat_data['slug'],
                        description=cat_data.get('description', ''),
                        parent_id=parent.id if parent else None,
                        level=level,
                        sort_order=stats['created'],
                        is_active=True
                    )
                    
                    # Set path
                    if parent:
                        category.path = f"{parent.path}/{category.id}"
                    else:
                        category.path = str(category.id)
                    
                    session.add(category)
                    session.flush()  # Get ID
                    
                    # Update path with actual ID
                    if parent:
                        category.path = f"{parent.path}/{category.id}"
                    else:
                        category.path = str(category.id)
                    
                    stats['created'] += 1
                    
                    # Create children
                    for child_data in cat_data.get('children', []):
                        create_category(child_data, category, level + 1)
                    
                    return category
                
                # Create all categories
                for cat_data in category_hierarchy:
                    try:
                        create_category(cat_data)
                    except Exception as e:
                        logger.error(f"Error creating category {cat_data['name']}: {e}")
                        stats['errors'] += 1
                
                session.commit()
                
            logger.info(f"Category seeding completed: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"Failed to seed categories: {e}")
            raise


class ProductSeeder:
    """Seeds sample product data."""
    
    @staticmethod
    def seed_sample_products(count: int = 100) -> Dict[str, int]:
        """Create sample products."""
        stats = {
            'created': 0,
            'errors': 0
        }
        
        try:
            with db_session_scope() as session:
                # Get all leaf categories
                categories = session.query(Category).filter(
                    ~Category.children.any()
                ).all()
                
                if not categories:
                    logger.warning("No categories found. Creating default categories first.")
                    CategorySeeder.seed_default_categories()
                    categories = session.query(Category).filter(
                        ~Category.children.any()
                    ).all()
                
                # Product templates by category
                product_templates = {
                    'pens': [
                        {'prefix': 'Ballpoint Pen', 'brands': ['BIC', 'Pilot', 'Paper Mate', 'Zebra']},
                        {'prefix': 'Gel Pen', 'brands': ['Pilot', 'Uni-ball', 'Pentel', 'Sakura']},
                        {'prefix': 'Fountain Pen', 'brands': ['Parker', 'Waterman', 'Cross', 'Lamy']}
                    ],
                    'pencils': [
                        {'prefix': 'Wooden Pencil', 'brands': ['Dixon', 'Staedtler', 'Faber-Castell']},
                        {'prefix': 'Mechanical Pencil', 'brands': ['Pentel', 'Pilot', 'Zebra', 'BIC']}
                    ],
                    'notebooks': [
                        {'prefix': 'Spiral Notebook', 'brands': ['Mead', 'Five Star', 'Tops', 'Oxford']},
                        {'prefix': 'Composition Book', 'brands': ['Mead', 'Roaring Spring', 'Tops']}
                    ],
                    'keyboards': [
                        {'prefix': 'Wireless Keyboard', 'brands': ['Logitech', 'Microsoft', 'Apple', 'Dell']},
                        {'prefix': 'Gaming Keyboard', 'brands': ['Razer', 'Corsair', 'SteelSeries', 'HyperX']}
                    ],
                    'mice': [
                        {'prefix': 'Wireless Mouse', 'brands': ['Logitech', 'Microsoft', 'Razer', 'HP']},
                        {'prefix': 'Ergonomic Mouse', 'brands': ['Logitech', 'Microsoft', '3M', 'Evoluent']}
                    ]
                }
                
                for _ in range(count):
                    try:
                        # Random category
                        category = random.choice(categories)
                        
                        # Get product template
                        templates = product_templates.get(category.slug, [
                            {'prefix': 'Generic Product', 'brands': ['Brand A', 'Brand B', 'Brand C']}
                        ])
                        template = random.choice(templates)
                        
                        # Generate product data
                        brand = random.choice(template['brands'])
                        color = random.choice(['Black', 'Blue', 'Red', 'Green', 'White', 'Silver'])
                        model_num = fake.bothify('??-####')
                        
                        product_name = f"{brand} {template['prefix']} - {color}"
                        sku = f"{brand[:3].upper()}-{model_num}-{color[:3].upper()}"
                        
                        # Price generation
                        base_price = random.uniform(2.99, 299.99)
                        price = round(base_price, 2)
                        compare_price = round(price * random.uniform(1.1, 1.5), 2) if random.random() > 0.5 else None
                        
                        # Create product
                        product = Product(
                            sku=sku,
                            name=product_name,
                            description=fake.paragraph(nb_sentences=3),
                            short_description=fake.sentence(nb_words=10),
                            price=price,
                            compare_at_price=compare_price,
                            brand=brand,
                            manufacturer=brand,
                            manufacturer_part_number=model_num,
                            upc=fake.bothify('############'),
                            weight=round(random.uniform(0.1, 5.0), 2),
                            inventory_quantity=random.randint(0, 500),
                            category_id=category.id,
                            status=random.choice([
                                ProductStatus.ACTIVE.value,
                                ProductStatus.ACTIVE.value,
                                ProductStatus.DRAFT.value
                            ]),
                            featured_image_url=f"https://via.placeholder.com/400x400?text={product_name.replace(' ', '+')}"
                        )
                        
                        # Add metafields
                        product.metafields = {
                            'color': color,
                            'material': random.choice(['Plastic', 'Metal', 'Wood', 'Composite']),
                            'warranty': random.choice(['1 Year', '2 Years', '3 Years', 'Lifetime'])
                        }
                        
                        session.add(product)
                        stats['created'] += 1
                        
                    except Exception as e:
                        logger.error(f"Error creating product: {e}")
                        stats['errors'] += 1
                
                session.commit()
                
            logger.info(f"Product seeding completed: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"Failed to seed products: {e}")
            raise


class UserSeeder:
    """Seeds user data."""
    
    @staticmethod
    def seed_test_users() -> Dict[str, int]:
        """Create test users."""
        stats = {
            'created': 0,
            'skipped': 0,
            'errors': 0
        }
        
        test_users = [
            {
                'email': 'admin@example.com',
                'password': 'admin123',
                'first_name': 'Admin',
                'last_name': 'User',
                'is_admin': True
            },
            {
                'email': 'user@example.com',
                'password': 'user123',
                'first_name': 'Regular',
                'last_name': 'User',
                'is_admin': False
            },
            {
                'email': 'test@example.com',
                'password': 'test123',
                'first_name': 'Test',
                'last_name': 'Account',
                'is_admin': False
            }
        ]
        
        try:
            with db_session_scope() as session:
                for user_data in test_users:
                    # Check if user exists
                    existing = session.query(User).filter_by(
                        email=user_data['email']
                    ).first()
                    
                    if existing:
                        stats['skipped'] += 1
                        continue
                    
                    try:
                        # Create user
                        user = User(
                            email=user_data['email'],
                            password_hash=generate_password_hash(user_data['password']),
                            first_name=user_data['first_name'],
                            last_name=user_data['last_name'],
                            is_admin=user_data['is_admin'],
                            is_active=True
                        )
                        
                        session.add(user)
                        stats['created'] += 1
                        
                    except Exception as e:
                        logger.error(f"Error creating user {user_data['email']}: {e}")
                        stats['errors'] += 1
                
                session.commit()
                
            logger.info(f"User seeding completed: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"Failed to seed users: {e}")
            raise


class DevelopmentDataSeeder:
    """Seeds comprehensive development data."""
    
    @staticmethod
    def seed_all(include_large_dataset: bool = False) -> Dict[str, Any]:
        """Seed all development data."""
        results = {
            'timestamp': datetime.now().isoformat(),
            'categories': {},
            'products': {},
            'users': {},
            'jobs': {},
            'sync_history': {}
        }
        
        try:
            # Seed categories
            logger.info("Seeding categories...")
            results['categories'] = CategorySeeder.seed_default_categories()
            
            # Seed users
            logger.info("Seeding users...")
            results['users'] = UserSeeder.seed_test_users()
            
            # Seed products
            logger.info("Seeding products...")
            product_count = 1000 if include_large_dataset else 100
            results['products'] = ProductSeeder.seed_sample_products(product_count)
            
            # Seed job history
            logger.info("Seeding job history...")
            results['jobs'] = DevelopmentDataSeeder._seed_job_history()
            
            # Seed sync history
            logger.info("Seeding sync history...")
            results['sync_history'] = DevelopmentDataSeeder._seed_sync_history()
            
            # Seed initial configuration
            logger.info("Seeding configuration...")
            DatabaseUtils.seed_initial_data()
            
            logger.info(f"Development data seeding completed: {results}")
            return results
            
        except Exception as e:
            logger.error(f"Failed to seed development data: {e}")
            raise
    
    @staticmethod
    def _seed_job_history() -> Dict[str, int]:
        """Create sample job history."""
        stats = {'created': 0}
        
        try:
            with db_session_scope() as session:
                # Get admin user
                admin = session.query(User).filter_by(is_admin=True).first()
                if not admin:
                    logger.warning("No admin user found")
                    return stats
                
                # Create sample jobs
                job_templates = [
                    {
                        'script_name': 'scripts/run_import.py',
                        'display_name': 'Full Product Import',
                        'description': 'Complete product import from FTP'
                    },
                    {
                        'script_name': 'scripts/shopify/shopify_uploader.py',
                        'display_name': 'Shopify Product Sync',
                        'description': 'Sync products to Shopify'
                    },
                    {
                        'script_name': 'scripts/cleanup/cleanup_duplicate_images.py',
                        'display_name': 'Image Cleanup',
                        'description': 'Remove duplicate product images'
                    }
                ]
                
                for _ in range(20):
                    template = random.choice(job_templates)
                    
                    # Random timing
                    created_at = fake.date_time_between(start_date='-30d', end_date='now')
                    duration = random.randint(10, 600)
                    
                    job = Job(
                        job_uuid=fake.uuid4(),
                        script_name=template['script_name'],
                        display_name=template['display_name'],
                        description=template['description'],
                        status=random.choice([
                            JobStatus.COMPLETED.value,
                            JobStatus.COMPLETED.value,
                            JobStatus.FAILED.value
                        ]),
                        progress=100 if random.random() > 0.2 else random.randint(0, 99),
                        created_at=created_at,
                        started_at=created_at + timedelta(seconds=random.randint(1, 10)),
                        completed_at=created_at + timedelta(seconds=duration),
                        actual_duration=duration,
                        user_id=admin.id,
                        result={
                            'items_processed': random.randint(100, 1000),
                            'items_successful': random.randint(80, 999),
                            'items_failed': random.randint(0, 20)
                        }
                    )
                    
                    session.add(job)
                    stats['created'] += 1
                
                session.commit()
                
            return stats
            
        except Exception as e:
            logger.error(f"Failed to seed job history: {e}")
            return stats
    
    @staticmethod
    def _seed_sync_history() -> Dict[str, int]:
        """Create sample sync history."""
        stats = {'created': 0}
        
        try:
            with db_session_scope() as session:
                # Get admin user
                admin = session.query(User).filter_by(is_admin=True).first()
                if not admin:
                    logger.warning("No admin user found")
                    return stats
                
                # Create sample sync records
                sync_types = ['full_import', 'product_sync', 'icon_sync', 'category_sync']
                
                for _ in range(30):
                    sync_type = random.choice(sync_types)
                    total_items = random.randint(50, 500)
                    items_successful = random.randint(int(total_items * 0.8), total_items)
                    items_failed = total_items - items_successful
                    
                    # Random timing
                    started_at = fake.date_time_between(start_date='-30d', end_date='now')
                    duration = random.randint(30, 300)
                    
                    sync = SyncHistory(
                        sync_type=sync_type,
                        sync_source='etilize' if sync_type == 'full_import' else 'manual',
                        sync_target='shopify',
                        status=SyncStatus.SUCCESS.value if items_failed == 0 else SyncStatus.PARTIAL.value,
                        started_at=started_at,
                        completed_at=started_at + timedelta(seconds=duration),
                        duration=duration,
                        total_items=total_items,
                        items_processed=total_items,
                        items_successful=items_successful,
                        items_failed=items_failed,
                        user_id=admin.id
                    )
                    
                    session.add(sync)
                    stats['created'] += 1
                
                session.commit()
                
            return stats
            
        except Exception as e:
            logger.error(f"Failed to seed sync history: {e}")
            return stats


# Export main classes
__all__ = [
    'CategorySeeder',
    'ProductSeeder',
    'UserSeeder',
    'DevelopmentDataSeeder'
]