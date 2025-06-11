import pytest
import os
import csv
from scripts.filter_products import filter_products, detect_encoding

def create_test_csv(filename, data, encoding='utf-8'):
    """Helper function to create test CSV files"""
    with open(filename, 'w', newline='', encoding=encoding) as f:
        writer = csv.writer(f)
        for row in data:
            writer.writerow(row)

def test_filter_products(tmp_path):
    """Test filtering products based on matching SKUs"""
    # Create test files
    primary_data = [
        ['title', 'sku', 'price'],
        ['Product 1', 'SKU001', '10.00'],
        ['Product 2', 'SKU002', '20.00'],
        ['Product 3', 'SKU003', '30.00']
    ]
    
    reference_data = [
        ['BasePartNumber', 'Description'],
        ['SKU001', 'Test Product 1'],
        ['SKU003', 'Test Product 3']
    ]
    
    # Create temporary test files
    primary_file = tmp_path / "primary.csv"
    reference_file = tmp_path / "reference.csv"
    create_test_csv(primary_file, primary_data)
    create_test_csv(reference_file, reference_data)
    
    # Run filter
    output_file = filter_products(str(primary_file), str(reference_file))
    
    # Verify results
    with open(output_file, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        rows = list(reader)
        
        # Check header
        assert rows[0] == ['title', 'sku', 'price']
        
        # Check filtered content
        skus = [row[1] for row in rows[1:]]  # Get SKUs from all rows except header
        assert 'SKU001' in skus
        assert 'SKU002' not in skus
        assert 'SKU003' in skus
        assert len(rows) == 3  # Header + 2 matching products

    # Cleanup
    os.remove(output_file)

def test_empty_reference_file(tmp_path):
    """Test handling of empty reference file"""
    primary_data = [
        ['title', 'sku', 'price'],
        ['Product 1', 'SKU001', '10.00']
    ]
    
    reference_data = [
        ['BasePartNumber', 'Description']
    ]
    
    primary_file = tmp_path / "primary.csv"
    reference_file = tmp_path / "reference.csv"
    create_test_csv(primary_file, primary_data)
    create_test_csv(reference_file, reference_data)
    
    output_file = filter_products(str(primary_file), str(reference_file))
    
    with open(output_file, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        rows = list(reader)
        assert len(rows) == 1  # Only header, no products
    
    # Cleanup
    os.remove(output_file)

def test_detect_encoding(tmp_path):
    """Test encoding detection"""
    # Test UTF-8
    utf8_file = tmp_path / "utf8.csv"
    create_test_csv(utf8_file, [['test', 'data']], encoding='utf-8')
    assert detect_encoding(str(utf8_file)) == 'utf-8'
    
    # Test Latin-1
    latin1_file = tmp_path / "latin1.csv"
    create_test_csv(latin1_file, [['tést', 'dàta']], encoding='latin1')
    encoding = detect_encoding(str(latin1_file))
    assert encoding in ['latin1', 'iso-8859-1', 'cp1252']