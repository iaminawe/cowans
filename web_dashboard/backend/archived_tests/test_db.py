#!/usr/bin/env python3
from database import init_database, get_db
from models import EtilizeImportBatch

# Initialize database
init_database(create_tables=True)

# Test query
db = next(get_db())
try:
    count = db.query(EtilizeImportBatch).count()
    print(f"EtilizeImportBatch count: {count}")
    
    # List all batches
    batches = db.query(EtilizeImportBatch).all()
    for batch in batches:
        print(f"Batch {batch.id}: {batch.source_file_path} - {batch.status}")
        print(f"  UUID: {batch.batch_uuid}")
        print(f"  Type: {batch.import_type}")
finally:
    db.close()