#!/usr/bin/env python3
"""
Enhanced version of run_import.py that uses Xorosoft API instead of CSV comparison.

This script orchestrates the complete import workflow from FTP download to Shopify upload,
using the Xorosoft API for real-time product validation instead of static CSV files.
"""

import os
import sys
import subprocess
from datetime import datetime
import argparse
import time
from colorama import Fore, Style, init
import logging
from pathlib import Path

# Initialize colorama for cross-platform colored output
init(autoreset=True)

def setup_logging():
    """Setup logging configuration."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(f'logs/import_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger(__name__)

logger = setup_logging()

# Stage timing estimates (in seconds)
STAGE_ESTIMATES = {
    'download': 60,
    'filter': 180,    # API validation might take longer than CSV
    'metafields': 120,
    'upload': 300
}

def print_stage_header():
    """Print the stage header with enhanced UI."""
    print(f"\n{Fore.CYAN}{'='*80}{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}🚀 Cowans Product Import Pipeline (API Enhanced){Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'='*80}{Style.RESET_ALL}\n")

def print_stage(stage_num, total_stages, stage_name, estimated_time):
    """Print stage information with progress."""
    print(f"\n{Fore.CYAN}{'─'*60}{Style.RESET_ALL}")
    print(f"{Fore.GREEN}Stage {stage_num}/{total_stages}: {stage_name}{Style.RESET_ALL}")
    print(f"Estimated time: {Fore.YELLOW}{estimated_time//60}m {estimated_time%60}s{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'─'*60}{Style.RESET_ALL}\n")

def check_api_credentials():
    """Check if Xorosoft API credentials are configured."""
    api_key = os.getenv('XOROSOFT_API')
    api_pass = os.getenv('XOROSOFT_PASS')
    
    if not api_key or not api_pass:
        logger.error(f"{Fore.RED}❌ Xorosoft API credentials not found!{Style.RESET_ALL}")
        logger.error("Please set XOROSOFT_API and XOROSOFT_PASS environment variables")
        return False
    
    logger.info(f"{Fore.GREEN}✓{Style.RESET_ALL} Xorosoft API credentials found")
    return True

def test_api_connection():
    """Test Xorosoft API connection."""
    logger.info("Testing Xorosoft API connection...")
    
    try:
        result = subprocess.run(
            ['python', 'scripts/tests/test_xorosoft_api.py'],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            logger.info(f"{Fore.GREEN}✓{Style.RESET_ALL} API connection successful")
            return True
        else:
            logger.error(f"{Fore.RED}❌ API connection failed{Style.RESET_ALL}")
            if result.stderr:
                logger.error(result.stderr)
            return False
            
    except subprocess.TimeoutExpired:
        logger.error(f"{Fore.RED}❌ API connection timeout{Style.RESET_ALL}")
        return False
    except Exception as e:
        logger.error(f"{Fore.RED}❌ API test error: {e}{Style.RESET_ALL}")
        return False

def get_latest_csv(directory):
    """Find the most recently dated CSV file in the given directory."""
    csv_files = [f for f in os.listdir(directory) if f.endswith('.csv') and not f.startswith('Xorosoft')]
    if not csv_files:
        return None
    
    # Sort by modification time
    csv_files.sort(key=lambda x: os.path.getmtime(os.path.join(directory, x)), reverse=True)
    return os.path.join(directory, csv_files[0])

def main():
    parser = argparse.ArgumentParser(
        description='Enhanced import pipeline with Xorosoft API validation',
        formatter_class=argparse.RawTextHelpFormatter
    )
    
    parser.add_argument('--skip-download', action='store_true', 
                       help='Skip FTP download stage')
    parser.add_argument('--skip-filter', action='store_true', 
                       help='Skip product filtering/validation stage')
    parser.add_argument('--skip-metafields', action='store_true',
                       help='Skip metafields creation stage')
    parser.add_argument('--skip-upload', action='store_true',
                       help='Skip Shopify upload stage')
    parser.add_argument('--check-inventory', action='store_true',
                       help='Also check inventory status during validation')
    parser.add_argument('--batch-size', type=int, default=100,
                       help='API validation batch size (default: 100)')
    parser.add_argument('--use-csv-fallback', action='store_true',
                       help='Fall back to CSV validation if API fails')
    
    args = parser.parse_args()
    
    print_stage_header()
    
    # Check API credentials first
    if not args.skip_filter and not check_api_credentials():
        if args.use_csv_fallback:
            logger.warning(f"{Fore.YELLOW}⚠️  Falling back to CSV validation{Style.RESET_ALL}")
        else:
            logger.error("Cannot proceed without API credentials")
            sys.exit(1)
    
    # Test API connection
    if not args.skip_filter and not args.use_csv_fallback:
        if not test_api_connection():
            if args.use_csv_fallback:
                logger.warning(f"{Fore.YELLOW}⚠️  API connection failed, falling back to CSV{Style.RESET_ALL}")
                args.use_csv_fallback = True
            else:
                logger.error("Cannot proceed without API connection")
                sys.exit(1)
    
    # Calculate active stages
    active_stages = 4
    if args.skip_download:
        active_stages -= 1
    if args.skip_filter:
        active_stages -= 1
    if args.skip_metafields:
        active_stages -= 1
    if args.skip_upload:
        active_stages -= 1
    
    # Track file path through stages
    file_path = None
    
    # Stage 1: FTP Download
    if not args.skip_download:
        print_stage(1, active_stages, "Downloading from Etilize FTP", STAGE_ESTIMATES['download'])
        
        logger.info("Starting FTP download...")
        result = subprocess.run(
            ['python', 'scripts/utilities/ftp_downloader.py'],
            check=False,
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            logger.info(f"{Fore.GREEN}✓{Style.RESET_ALL} Download complete!")
            # Extract file path from output
            for line in result.stdout.splitlines():
                if "File saved as:" in line:
                    file_path = line.split(":", 1)[1].strip()
                    break
        else:
            logger.error(f"{Fore.RED}❌ Download failed{Style.RESET_ALL}")
            sys.exit(1)
    
    # Stage 2: Product Filtering/Validation
    if not args.skip_filter:
        current_stage = 1 if args.skip_download else 2
        print_stage(current_stage, active_stages, 
                   "Validating products with Xorosoft API" if not args.use_csv_fallback else "Filtering products against CSV",
                   STAGE_ESTIMATES['filter'])
        
        if not file_path:
            file_path = get_latest_csv("data")
            if not file_path:
                logger.error(f"{Fore.RED}No CSV file found in data/ directory{Style.RESET_ALL}")
                sys.exit(1)
            logger.info(f"Using file: {Fore.CYAN}{file_path}{Style.RESET_ALL}")
        
        if args.use_csv_fallback:
            # Use original CSV-based filtering
            reference_files = [f for f in os.listdir("data") if f.startswith("Xorosoft") and f.endswith(".csv")]
            if not reference_files:
                logger.error(f"{Fore.RED}No Xorosoft reference file found{Style.RESET_ALL}")
                sys.exit(1)
            
            reference_file = os.path.join("data", max(reference_files))
            logger.info(f"Using reference file: {Fore.CYAN}{reference_file}{Style.RESET_ALL}")
            
            cmd = ['python', 'scripts/data_processing/filter_products.py', file_path, reference_file, '--debug']
        else:
            # Use API-based validation
            cmd = ['python', 'scripts/data_processing/filter_products_api.py', file_path, '--debug']
            
            if args.check_inventory:
                cmd.append('--check-inventory')
            
            cmd.extend(['--batch-size', str(args.batch_size)])
        
        logger.info(f"Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, check=False, capture_output=True, text=True)
        
        if result.returncode == 0:
            logger.info(f"{Fore.GREEN}✓{Style.RESET_ALL} Validation complete!")
            
            # Extract output file path
            for line in result.stdout.splitlines():
                if "Filtered products:" in line or "Output written to:" in line:
                    file_path = line.split(":", 1)[1].strip()
                    break
            
            # Show some statistics
            for line in result.stdout.splitlines():
                if "Match rate:" in line or "Products matched:" in line:
                    logger.info(line.strip())
                elif "API Performance:" in line:
                    # Show API performance metrics
                    logger.info(f"{Fore.CYAN}{line.strip()}{Style.RESET_ALL}")
        else:
            logger.error(f"{Fore.RED}❌ Validation failed{Style.RESET_ALL}")
            if result.stderr:
                logger.error(result.stderr)
            sys.exit(1)
    
    # Stage 3: Metafields Creation
    if not args.skip_metafields:
        current_stage = active_stages - (1 if not args.skip_upload else 0)
        print_stage(current_stage, active_stages, "Creating Shopify metafields", STAGE_ESTIMATES['metafields'])
        
        if not file_path:
            file_path = get_latest_csv("data")
            if not file_path:
                logger.error(f"{Fore.RED}No CSV file found{Style.RESET_ALL}")
                sys.exit(1)
        
        logger.info(f"Creating metafields for: {Fore.CYAN}{file_path}{Style.RESET_ALL}")
        result = subprocess.run(
            ['python', 'scripts/data_processing/create_metafields.py', file_path],
            check=False,
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            logger.info(f"{Fore.GREEN}✓{Style.RESET_ALL} Metafields created!")
            # Update file path
            for line in result.stdout.splitlines():
                if "shopify_" in line and ".csv" in line:
                    file_path = line.strip()
                    break
        else:
            logger.error(f"{Fore.RED}❌ Metafields creation failed{Style.RESET_ALL}")
            sys.exit(1)
    
    # Stage 4: Shopify Upload
    if not args.skip_upload:
        print_stage(active_stages, active_stages, "Uploading to Shopify", STAGE_ESTIMATES['upload'])
        
        if not file_path:
            file_path = get_latest_csv("data")
            if not file_path:
                logger.error(f"{Fore.RED}No CSV file found{Style.RESET_ALL}")
                sys.exit(1)
        
        # Check for Shopify credentials
        shop_url = os.getenv('SHOPIFY_SHOP_URL')
        access_token = os.getenv('SHOPIFY_ACCESS_TOKEN')
        
        if not shop_url or not access_token:
            logger.error(f"{Fore.RED}❌ Shopify credentials not found!{Style.RESET_ALL}")
            logger.error("Please set SHOPIFY_SHOP_URL and SHOPIFY_ACCESS_TOKEN")
            sys.exit(1)
        
        logger.info(f"Uploading to Shopify: {Fore.CYAN}{file_path}{Style.RESET_ALL}")
        result = subprocess.run(
            ['python', 'scripts/shopify/shopify_uploader_new.py', 
             file_path, '--shop-url', shop_url, '--access-token', access_token],
            check=False
        )
        
        if result.returncode == 0:
            logger.info(f"{Fore.GREEN}✓{Style.RESET_ALL} Upload complete!")
        else:
            logger.error(f"{Fore.RED}❌ Upload failed{Style.RESET_ALL}")
            sys.exit(1)
    
    # Final summary
    print(f"\n{Fore.CYAN}{'='*80}{Style.RESET_ALL}")
    print(f"{Fore.GREEN}🎉 Import pipeline completed successfully!{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'='*80}{Style.RESET_ALL}\n")
    
    # Show key metrics if available
    if not args.skip_filter and not args.use_csv_fallback:
        logger.info(f"{Fore.YELLOW}API Validation Benefits:{Style.RESET_ALL}")
        logger.info("  • Real-time inventory validation")
        logger.info("  • No need to maintain reference CSV files")
        logger.info("  • Accurate pricing and availability data")
        if args.check_inventory:
            logger.info("  • Current stock levels included")

if __name__ == "__main__":
    main()