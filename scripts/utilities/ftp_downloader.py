"""
FTP Downloader Module - Downloads product data files from FTP server

This module handles FTP connection and file download functionality for the Product Feed Integration System.
It follows the architecture defined in docs/architecture.md and implements the FTP Downloader component.

Features:
- Secure FTP connection with credentials from environment variables
- Configurable connection parameters
- Download progress monitoring and performance metrics
- Robust error handling without masking underlying issues
- Detailed logging of operations
"""

import ftplib
import os
import logging
import time
import zipfile
import subprocess
from pathlib import Path
from typing import Optional, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_REMOTE_FILE = "CowanOfficeSupplies.zip"

class FTPDownloader:
    """Handles FTP connection and file downloads from Etilize server"""
    
    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        remote_path: str = "/",
        local_path: Path = Path("data")
    ):
        """
        Initialize FTP downloader with connection parameters
        
        Args:
            host: FTP server hostname
            username: FTP username
            password: FTP password
            remote_path: Remote directory path on FTP server
            local_path: Local directory to save downloaded files
        
        Raises:
            ValueError: If any required parameters are empty or invalid
        """
        # Validate input parameters
        if not host or not isinstance(host, str):
            raise ValueError("Host must be a non-empty string")
        if not username or not isinstance(username, str):
            raise ValueError("Username must be a non-empty string")
        if not password or not isinstance(password, str):
            raise ValueError("Password must be a non-empty string")
            
        self.host = host
        self.username = username
        self.password = password
        self.remote_path = remote_path
        self.local_path = Path(local_path)
        self.ftp: Optional[ftplib.FTP] = None
        self.processed_file: Optional[Path] = None
        
        # Ensure local download directory exists
        self.local_path.mkdir(parents=True, exist_ok=True)

    def connect(self) -> bool:
        """
        Establish connection to FTP server
        
        Returns:
            bool: True if connection successful, False otherwise
            
        Raises:
            RuntimeError: If connection or login fails
        """
        try:
            logger.info(f"Connecting to FTP server: {self.host}")
            self.ftp = ftplib.FTP(self.host)
            self.ftp.login(self.username, self.password)
            
            # Set binary mode
            logger.debug("Setting binary transfer mode")
            self.ftp.voidcmd('TYPE I')
            
            if self.remote_path != "/":
                self.ftp.cwd(self.remote_path)
                
            # List directory contents
            logger.debug("Directory contents:")
            self.ftp.retrlines('LIST', lambda x: logger.debug(f"  {x}"))
            logger.info("Successfully connected to FTP server")
            return True
            
        except Exception as e:
            logger.error(f"FTP connection failed: {str(e)}")
            raise RuntimeError(f"Failed to connect to FTP server: {str(e)}")

    def download(self, remote_filename: str = DEFAULT_REMOTE_FILE) -> Path:
        """
        Download file from FTP server
        
        Args:
            remote_filename: Name of file to download from FTP server
            
        Returns:
            Path: Path to downloaded file
            
        Raises:
            RuntimeError: If download fails
            FileNotFoundError: If remote file doesn't exist
            ValueError: If remote_filename is invalid
        """
        if not remote_filename or not isinstance(remote_filename, str):
            raise ValueError("Remote filename must be a non-empty string")
            
        if not self.ftp:
            raise RuntimeError("Not connected to FTP server. Call connect() first.")
            
        local_file = self.local_path / remote_filename
        
        try:
            logger.info(f"Starting download of {remote_filename}")
            
            # Ensure binary mode for file operations
            logger.debug("Setting binary transfer mode before file operations")
            self.ftp.voidcmd('TYPE I')
            
            # Get file size for progress tracking
            logger.debug(f"Checking size of {remote_filename}")
            file_size = self.ftp.size(remote_filename)
            if not file_size:
                raise FileNotFoundError(f"Remote file {remote_filename} not found")
                
            downloaded_size = 0
            start_time = time.time()

            # Initialize the file
            with open(local_file, 'wb') as f:
                pass  # Create empty file
            
            def callback(data):
                nonlocal downloaded_size
                downloaded_size += len(data)
                
                # Append data to file
                with open(local_file, 'ab') as f:
                    f.write(data)
                
                # Log progress periodically
                if downloaded_size % (1024 * 1024) == 0:  # Log every MB
                    progress = (downloaded_size / file_size) * 100
                    speed = downloaded_size / (time.time() - start_time)
                    logger.info(f"Download progress: {progress:.1f}% ({speed/1024:.1f} KB/s)")
            
            # Start download with progress tracking
            self.ftp.retrbinary(f"RETR {remote_filename}", callback)
            
            download_time = time.time() - start_time
            final_speed = file_size / download_time
            logger.info(f"Download completed: {file_size/1024/1024:.1f}MB in {download_time:.1f}s ({final_speed/1024/1024:.1f}MB/s)")
            
            if remote_filename.lower().endswith('.zip'):
                logger.info("Extracting zip file contents...")
                self.extract_zip(local_file)
                
            return local_file
            
        except ftplib.error_perm as e:
            logger.error(f"Permission error during download: {str(e)}")
            raise RuntimeError(f"Permission denied: {str(e)}")
        except Exception as e:
            logger.error(f"Download failed: {str(e)}")
            # Clean up partial download on failure
            if local_file.exists():
                local_file.unlink()
            raise RuntimeError(f"Failed to download file: {str(e)}")

    def extract_zip(self, zip_path: Path) -> None:
        """
        Extract contents of downloaded zip file
        
        Args:
            zip_path: Path to the zip file to extract
            
        Raises:
            RuntimeError: If extraction fails
        """
        try:
            extract_dir = zip_path.parent
            # Generate timestamped filename
            timestamp = time.strftime("%Y%m%d")
            output_file = extract_dir / f"CowansOfficeSupplies_{timestamp}.csv"
            
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                logger.info(f"Extracting {len(zip_ref.namelist())} files to {extract_dir}")
                
                # Extract and rename the first CSV file found
                csv_files = [f for f in zip_ref.namelist() if f.lower().endswith('.csv')]
                if not csv_files:
                    raise RuntimeError("No CSV file found in the zip archive")
                    
                with zip_ref.open(csv_files[0]) as source, open(output_file, 'wb') as target:
                    target.write(source.read())
                    
            # Clean up zip file after successful extraction
            logger.info(f"Removing zip file {zip_path}")
            zip_path.unlink()
            
            logger.info(f"File extracted and renamed to {output_file.name}")
            self.processed_file = output_file
            
            # Return the processed file path (workflow is now handled by run_import.py)
            # self.process_workflow(output_file)  # Disabled - now handled by run_import.py
            
        except Exception as e:
            logger.error(f"Failed to extract zip file: {str(e)}")
            raise RuntimeError(f"Failed to extract zip file: {str(e)}")

    def process_workflow(self, data_dir: Path) -> None:
        """
        This method is now deprecated and disabled.
        Workflow processing is now handled by run_import.py
        """
        # This functionality has been moved to run_import.py
        logger.info("Workflow processing is now handled by run_import.py")
        pass

    def __del__(self):
        """Ensure FTP connection is closed on object cleanup"""
        if self.ftp:
            try:
                self.ftp.quit()
            except:
                pass