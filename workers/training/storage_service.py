import logging
from azure.storage.blob import BlobServiceClient, ContentSettings
from azure.core.exceptions import ResourceNotFoundError
import asyncio

logger = logging.getLogger(__name__)

class StorageService:
    """Service for interacting with Azure Blob Storage"""
    
    def __init__(self, connection_string: str, container_name: str):
        self.connection_string = connection_string
        self.container_name = container_name
        self.blob_service_client = None
        self.container_client = None
        self.is_initialized = False
    
    async def initialize(self):
        """Initialize blob storage connection"""
        logger.info(f"Initializing Azure Blob Storage (container: {self.container_name})...")
        
        self.blob_service_client = BlobServiceClient.from_connection_string(
            self.connection_string
        )
        
        self.container_client = self.blob_service_client.get_container_client(
            self.container_name
        )
        
        # Verify container exists
        try:
            await asyncio.to_thread(self.container_client.get_container_properties)
            logger.info(f"Connected to container '{self.container_name}'")
        except ResourceNotFoundError:
            logger.warning(f"Container '{self.container_name}' not found, creating...")
            await asyncio.to_thread(self.container_client.create_container)
            logger.info(f"Created container '{self.container_name}'")
        
        self.is_initialized = True
    
    async def download_blob(self, blob_path: str, local_path: str) -> None:
        """Download a blob to a local file"""
        blob_client = self.blob_service_client.get_blob_client(
            container=self.container_name,
            blob=blob_path
        )
        
        with open(local_path, 'wb') as file:
            blob_data = await asyncio.to_thread(blob_client.download_blob)
            data = await asyncio.to_thread(blob_data.readall)
            file.write(data)
        
        logger.debug(f"Downloaded blob {blob_path} to {local_path}")
    
    async def upload_blob(self, local_path: str, blob_path: str) -> None:
        """Upload a local file to blob storage"""
        blob_client = self.blob_service_client.get_blob_client(
            container=self.container_name,
            blob=blob_path
        )
        
        with open(local_path, 'rb') as file:
            data = file.read()
            
            await asyncio.to_thread(
                blob_client.upload_blob,
                data,
                overwrite=True,
                content_settings=ContentSettings(content_type='application/zip')
            )
        
        logger.info(f"Uploaded {local_path} to blob {blob_path}")
    
    async def blob_exists(self, blob_path: str) -> bool:
        """Check if a blob exists"""
        blob_client = self.blob_service_client.get_blob_client(
            container=self.container_name,
            blob=blob_path
        )
        
        try:
            await asyncio.to_thread(blob_client.get_blob_properties)
            return True
        except ResourceNotFoundError:
            return False
