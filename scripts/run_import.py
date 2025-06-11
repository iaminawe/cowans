#!/usr/bin/env python3
"""
Launch script for Cowan's product import workflow.
Provides colorful progress tracking through each stage.
"""

import os
import sys
import time
from datetime import datetime
import logging
import argparse
import subprocess
from colorama import init, Fore, Style
try:
    import simpleaudio as sa
    import numpy as np
except ImportError:
    print("simpleaudio or numpy not installed, sound notifications disabled.")

from dotenv import load_dotenv
load_dotenv()

from utilities.ftp_downloader import FTPDownloader

# Stage time estimates in seconds (based on typical runs)
STAGE_ESTIMATES = {
    'download': 180,  # 3 minutes
    'filter': 120,   # 2 minutes
    'metafields': 300,  # 5 minutes
    'upload': 600,  # 10 minutes
}

# Configure colored logging
class ColoredFormatter(logging.Formatter):
    """Custom formatter for colored log output"""
    
    COLORS = {
        'INFO': Fore.GREEN,
        'WARNING': Fore.YELLOW,
        'ERROR': Fore.RED,
        'CRITICAL': Fore.RED + Style.BRIGHT,
        'DEBUG': Fore.CYAN
    }
    
    def format(self, record):
        levelname = record.levelname
        if levelname in self.COLORS:
            record.levelname = f"{self.COLORS[levelname]}{levelname}{Style.RESET_ALL}"
        return super().format(record)

def setup_logging():
    """Configure logging with colors and formatting"""
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    ch = logging.StreamHandler()
    formatter = ColoredFormatter(
        f'{Fore.BLUE}%(asctime)s{Style.RESET_ALL} - %(levelname)s - %(message)s'
    )
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    
    return logger

def play_success_sound():
    """Play a success notification sound"""
    try:
        import simpleaudio as sa
        import numpy as np
        frequency = 440  # A4 note
        duration = 500  # ms
        samples = 44100  # CD quality audio
        t = np.linspace(0, duration/1000, int(samples*duration/1000))
        wave = np.sin(2*np.pi*frequency*t)
        audio = np.int16(wave*32767)
        play_obj = sa.play_buffer(audio, 1, 2, samples)
        play_obj.wait_done()
    except Exception as e:
        print("Sound playback failed, ensure simpleaudio and numpy are installed.")

def print_stage(number: int, total: int, description: str, estimated_time: int):
    """Print a workflow stage header with time estimate"""
    print(f"\n{Fore.CYAN}{'='*80}{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}Stage {number}/{total}: {description}")
    print(f"Estimated time: {estimated_time//60} minutes {estimated_time%60} seconds{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'='*80}{Style.RESET_ALL}\n")
    
def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Run Cowan\'s product import workflow')
    parser.add_argument('--skip-download', action='store_true', help='Skip FTP download stage')
    parser.add_argument('--skip-filter', action='store_true', help='Skip product filtering stage')
    parser.add_argument('--skip-metafields', action='store_true', help='Skip metafields creation stage')
    parser.add_argument('--skip-upload', action='store_true', help='Skip Shopify upload stage')
    parser.add_argument('--no-sound', action='store_true', help='Disable sound notifications')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    return parser.parse_args()

def get_latest_csv(directory, prefix=None):
    """Find the most recently modified CSV file in a directory, optionally with a prefix"""
    csv_files = [os.path.join(directory, f) for f in os.listdir(directory) if f.endswith('.csv')]
    if prefix:
        csv_files = [f for f in csv_files if os.path.basename(f).startswith(prefix)]
    if not csv_files:
        return None
    return max(csv_files, key=os.path.getmtime)

def main():
    """Main workflow execution"""
    args = parse_args()
    logger = setup_logging()
    active_stages = 4 - sum([args.skip_download, args.skip_metafields, args.skip_upload])

    try:
        file_path = None
        start_time = time.time()

        # Prompt for FTP sync
        proceed_with_ftp = False
        if not args.skip_download:
            proceed_with_ftp = input("Do you want to proceed with the FTP sync? (y/n): ").lower().strip() == 'y'

        # Stage 1: FTP Download
        if not args.skip_download and proceed_with_ftp:
            print_stage(1, active_stages, "Downloading product data from FTP", STAGE_ESTIMATES['download'])
            
            FTP_HOST = os.getenv('FTP_HOST')
            FTP_USERNAME = os.getenv('FTP_USERNAME')
            FTP_PASSWORD = os.getenv('FTP_PASSWORD')
            
            if not (FTP_HOST and FTP_USERNAME and FTP_PASSWORD):
                logger.error(f"{Fore.RED}Missing FTP credentials in environment variables{Style.RESET_ALL}")
                sys.exit(1)
            
            downloader = FTPDownloader(
                FTP_HOST,
                FTP_USERNAME,
                FTP_PASSWORD
            )
            downloader.connect()
            # The download method returns the path to the zip file, not the extracted CSV
            downloader.download()
            # Get the latest CSV file which should be the one just extracted
            file_path = get_latest_csv("data")
            if not file_path:
                logger.error(f"{Fore.RED}No CSV file found in data/ directory after download. Aborting.{Style.RESET_ALL}")
                sys.exit(1)
            logger.info(f"Using extracted file: {Fore.CYAN}{file_path}{Style.RESET_ALL}")
            logger.info(f"{Fore.GREEN}✓{Style.RESET_ALL} Download complete!")
        else:
            logger.info("Skipping FTP Download stage.")

        # Stage 2: Product Filtering
        proceed_with_filter = False
        if not args.skip_filter:
            if not proceed_with_ftp and not args.skip_download:
                proceed_with_filter = input("Do you want to proceed with the Product filtering? (y/n): ").lower().strip() == 'y'
            else:
                proceed_with_filter = True
        
        # Handle skipping filtering and getting correct input file
        filtered_file_path = None
        if not args.skip_filter and proceed_with_filter:
            print_stage(1 if (proceed_with_ftp or args.skip_download) else 1, active_stages, "Filtering products against reference data", STAGE_ESTIMATES['filter'])
            
            if not file_path:
                # Find the most recently dated CSV in the data directory
                file_path = get_latest_csv("data")
                if not file_path:
                    logger.error(f"{Fore.RED}No CSV file found in data/ directory. Aborting.{Style.RESET_ALL}")
                    sys.exit(1)
                logger.info(f"Using the most recent CSV file found: {Fore.CYAN}{file_path}{Style.RESET_ALL}")
            
            # Find the Xorosoft reference file
            reference_files = [f for f in os.listdir("data") if f.startswith("Xorosoft") and f.endswith(".csv")]
            if not reference_files:
                logger.error(f"{Fore.RED}No Xorosoft reference file found in data/ directory. Aborting.{Style.RESET_ALL}")
                sys.exit(1)
            
            reference_file = os.path.join("data", max(reference_files))
            logger.info(f"Using reference file: {Fore.CYAN}{reference_file}{Style.RESET_ALL}")
            
            logger.info(f"Filtering products from {Fore.CYAN}{file_path}{Style.RESET_ALL} against reference data...")
            result = subprocess.run(
                ['python', 'scripts/data_processing/filter_products.py', file_path, reference_file, '--debug'],
                check=False,
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                logger.info(f"{Fore.GREEN}✓{Style.RESET_ALL} Product filtering complete!")
                # Extract the output file path from the result
                for line in result.stdout.splitlines():
                    if "Filtered products:" in line:
                        filtered_file_path = line.split(":", 1)[1].strip()
                        break
                
                if filtered_file_path:
                    file_path = filtered_file_path
                    logger.info(f"Using filtered file for next stage: {Fore.CYAN}{file_path}{Style.RESET_ALL}")
                else:
                    logger.warning(f"{Fore.YELLOW}Could not determine filtered output file, using original file.{Style.RESET_ALL}")
            else:
                logger.error(f"{Fore.RED}Product filtering failed with return code {result.returncode}{Style.RESET_ALL}")
                logger.error("=== Error Details ===")
                if result.stdout:
                    logger.error("Standard Output:")
                    for line in result.stdout.splitlines():
                        if line.strip():
                            logger.error(f"  {line}")
                if result.stderr:
                    logger.error("Error Output:")
                    for line in result.stderr.splitlines():
                        if line.strip():
                            logger.error(f"  {line}")
                logger.error("=================")
                sys.exit(1)
        else:
            logger.info("Skipping Product Filtering stage.")
        
        # Stage 3: Metafields Creation
        proceed_with_metafields = False
        if not args.skip_metafields:
            if (not proceed_with_ftp and not args.skip_download) or (not proceed_with_filter and not args.skip_filter):
                proceed_with_metafields = input("Do you want to proceed with the Metafields creation? (y/n): ").lower().strip() == 'y'
            else:
                proceed_with_metafields = True
        
        # Handle skipping metafields and getting correct input file
        if not proceed_with_metafields and not args.skip_metafields:
            logger.info("Skipping Metafields creation stage.")

        if not args.skip_metafields and proceed_with_metafields:
            print_stage(
                1 + (1 if (proceed_with_ftp or args.skip_download) else 0) + (1 if (proceed_with_filter or args.skip_filter) else 0),
                active_stages,
                "Creating Shopify metafields",
                STAGE_ESTIMATES['metafields']
            )
            
            if not file_path:
                # Find the most recently dated CSV in the data directory
                file_path = get_latest_csv("data")
                if not file_path:
                    logger.error(f"{Fore.RED}No CSV file found in data/ directory. Aborting.{Style.RESET_ALL}")
                    sys.exit(1)
                logger.info(f"Using the most recent CSV file found: {Fore.CYAN}{file_path}{Style.RESET_ALL}")
        
            logger.info(f"Processing file: {Fore.CYAN}{file_path}{Style.RESET_ALL}")
            result = subprocess.run(['python', 'scripts/data_processing/create_metafields.py', file_path], check=True, capture_output=True, text=True)
            logger.info(result.stdout)
            
            if result.returncode != 0:
                logger.error(f"{Fore.RED}Metafields creation failed. See details below: {Style.RESET_ALL}")
                logger.error(result.stderr)
                sys.exit(1)

            logger.info(f"{Fore.GREEN}✓{Style.RESET_ALL} Metafields creation complete!")
        
        # Stage 3: Shopify Upload
        proceed_with_upload = False
        if not args.skip_upload:
            # Determine if we need to ask about upload
            if (not proceed_with_ftp and not args.skip_download) or (not proceed_with_metafields and not args.skip_metafields):
                proceed_with_upload = input("Do you want to proceed with the Shopify upload? (y/n): ").lower().strip() == 'y'
            else:
                proceed_with_upload = True

            # If both previous stages are skipped or not used, get the latest shopify_ prefixed file
            if (args.skip_download or not proceed_with_ftp) and (args.skip_metafields or not proceed_with_metafields):
                file_path = get_latest_csv("data", "shopify_")
                if not file_path:
                    logger.error(f"{Fore.RED}No shopify_ prefixed CSV file found in data/ directory. Aborting.{Style.RESET_ALL}")
                    sys.exit(1)
                logger.info(f"Using the most recent shopify_ prefixed CSV file found: {Fore.CYAN}{file_path}{Style.RESET_ALL}")
                
            if proceed_with_upload:
                print_stage(
                    1 + (1 if (proceed_with_ftp or args.skip_download) else 0) + 
                    (1 if (proceed_with_filter or args.skip_filter) else 0) + 
                    (1 if (proceed_with_metafields or args.skip_metafields) else 0),
                    active_stages,
                    "Uploading to Shopify",
                    STAGE_ESTIMATES['upload']
                )
                
                if file_path is None:
                    # Get the latest shopify_ prefixed file if no file_path is set
                    file_path = get_latest_csv("data", "shopify_")
                    if not file_path:
                        logger.error(f"{Fore.RED}No shopify_ prefixed CSV file found in data/ directory. Aborting.{Style.RESET_ALL}")
                        sys.exit(1)
                    logger.info(f"Using the most recent shopify_ prefixed CSV file found: {Fore.CYAN}{file_path}{Style.RESET_ALL}")

                output_file = file_path
                if not os.path.basename(output_file).startswith("shopify_"):
                    output_file = os.path.join(
                        os.path.dirname(file_path),
                        f"shopify_{os.path.basename(file_path)}"
                    )

                # Ensure output file exists
                if not os.path.exists(output_file):
                    logger.error(f"{Fore.RED}CSV file not found: {output_file}{Style.RESET_ALL}")
                    sys.exit(1)
                
                # Check Shopify credentials
                shop_url = os.getenv("SHOPIFY_SHOP_URL")
                access_token = os.getenv("SHOPIFY_ACCESS_TOKEN")
                
                if not shop_url or not access_token:
                    logger.error(f"{Fore.RED}Missing Shopify credentials in environment variables{Style.RESET_ALL}")
                    logger.error("Required environment variables:")
                    logger.error("  - SHOPIFY_SHOP_URL")
                    logger.error("  - SHOPIFY_ACCESS_TOKEN")
                    sys.exit(1)
                
                logger.info(f"Using file for Shopify upload: {Fore.CYAN}{output_file}{Style.RESET_ALL}")
                logger.info("Starting Shopify upload process...")
                
                # Verify file content before upload
                try:
                    with open(output_file, 'r', encoding='utf-8') as f:
                        first_line = f.readline().strip()
                        logger.info(f"CSV header: {Fore.CYAN}{first_line}{Style.RESET_ALL}")
                except Exception as e:
                    logger.error(f"{Fore.RED}Failed to read CSV file: {str(e)}{Style.RESET_ALL}")
                    sys.exit(1)
                
                # Run uploader with debug flag and required credentials
                logger.info("Executing shopify_uploader.py...")
                result = subprocess.run(
                    [
                        'python', 'scripts/shopify/shopify_uploader.py', 
                        output_file, 
                        '--shop-url', shop_url,
                        '--access-token', access_token,
                        '--debug',
                        '--data-source', 'etilize'  # Use etilize mapping for Cowans data
                    ],
                    check=False,
                    capture_output=False,  # Enable real-time output
                    text=True,
                )
                
                # Enhanced result logging
                logger.info(f"Upload process completed with return code: {result.returncode}")
                
                if result.returncode == 0:
                    logger.info(f"{Fore.GREEN}✓{Style.RESET_ALL} Shopify upload complete!")
                else:
                    logger.error(f"{Fore.RED}Shopify upload failed with return code {result.returncode}{Style.RESET_ALL}")
                    sys.exit(1)
            else:
                logger.info("Skipping Shopify Upload stage.")
        else:
             logger.info("Skipping Shopify Upload stage.")

        # Workflow complete
        total_time = time.time() - start_time
        print(f"\n{Fore.GREEN}{'='*80}")
        print(f"🎉 Product import workflow completed successfully!")
        print(f"Total time: {total_time//60:.0f} minutes {total_time%60:.0f} seconds")
        print(f"{'='*80}{Style.RESET_ALL}")
        
    except Exception as e:
        logger.error(f"{Fore.RED}Workflow failed: {str(e)}{Style.RESET_ALL}")
        sys.exit(1)

if __name__ == "__main__":
    main()