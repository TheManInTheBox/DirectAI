"""
Storage Service - Handles Azure Blob Storage operations for generated stems
"""
import os
import logging
from pathlib import Path
from typing import Optional
import asyncio

from azure.storage.blob import BlobServiceClient
from azure.identity import DefaultAzureCredential

logger = logging.getLogger(__name__)


class StorageService:
    """Service for Azure Blob Storage operations"""
    
    def __init__(self):
        """Initialize blob storage client"""
        self.connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
        self.account_url = os.getenv("AZURE_STORAGE_ACCOUNT_URL")
        self.container_name = os.getenv("BLOB_CONTAINER_NAME", "audio-files")
        
        if self.connection_string:
            # Local development with Azurite
            logger.info("Using connection string for blob storage (Azurite)")
            self.blob_service_client = BlobServiceClient.from_connection_string(
                self.connection_string
            )
        elif self.account_url:
            # Production with Managed Identity
            logger.info("Using Managed Identity for blob storage")
            credential = DefaultAzureCredential()
            self.blob_service_client = BlobServiceClient(
                account_url=self.account_url,
                credential=credential
            )
        else:
            logger.warning("No blob storage configuration found")
            self.blob_service_client = None
    
    def is_connected(self) -> bool:
        """Check if storage client is configured"""
        return self.blob_service_client is not None
    
    async def upload_generated_stem(
        self,
        generation_request_id: str,
        audio_file_id: str,
        stem_type: str,
        local_path: Path
    ) -> str:
        """
        Upload generated stem file to blob storage
        
        Path structure: {audio_file_id}/generated/{generation_request_id}/{stem_type}.wav
        """
        try:
            if not self.blob_service_client:
                raise RuntimeError("Blob storage client not configured")
            
            # Generate blob name
            blob_name = f"{audio_file_id}/generated/{generation_request_id}/{stem_type}.wav"
            
            logger.info(f"Uploading generated stem: {blob_name}")
            
            # Get blob client
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name,
                blob=blob_name
            )
            
            # Upload file
            from azure.storage.blob import ContentSettings
            
            with open(local_path, "rb") as data:
                await asyncio.to_thread(
                    blob_client.upload_blob,
                    data,
                    overwrite=True,
                    content_settings=ContentSettings(content_type='audio/wav')
                )
            
            # Get blob URL
            blob_url = blob_client.url
            logger.info(f"Uploaded generated stem to {blob_url}")
            
            return blob_url
            
        except Exception as e:
            logger.error(f"Error uploading generated stem: {str(e)}", exc_info=True)
            raise
