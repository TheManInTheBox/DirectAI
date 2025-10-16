"""
Storage Service - Handles Azure Blob Storage operations
"""
import os
import logging
from pathlib import Path
from typing import Optional
import asyncio

from azure.storage.blob import BlobServiceClient
from azure.identity import DefaultAzureCredential
import aiofiles

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
    
    async def download_blob(self, blob_uri: str, local_path: Path):
        """Download blob from storage to local file"""
        try:
            if not self.blob_service_client:
                raise RuntimeError("Blob storage client not configured")
            
            # Parse blob URI to get container and blob name
            # Format: https://{account}.blob.core.windows.net/{container}/{blob}
            # Or Azurite: http://azurite:10000/devstoreaccount1/{container}/{blob}
            parts = blob_uri.split("/")
            
            # For Azurite (localhost, 127.0.0.1, or azurite hostname)
            if "127.0.0.1" in blob_uri or "localhost" in blob_uri or "azurite" in blob_uri:
                # Find devstoreaccount1 in parts, container is next
                try:
                    account_index = parts.index("devstoreaccount1")
                    container_name = parts[account_index + 1]
                    blob_name = "/".join(parts[account_index + 2:])
                except (ValueError, IndexError):
                    raise ValueError(f"Invalid Azurite blob URI format: {blob_uri}")
            else:
                # Production Azure: https://account.blob.core.windows.net/container/blob/path
                container_name = parts[3]  # After https:// (0), empty (1), domain (2)
                blob_name = "/".join(parts[4:])
            
            logger.info(f"Downloading blob: container={container_name}, blob={blob_name}")
            
            # Get blob client
            blob_client = self.blob_service_client.get_blob_client(
                container=container_name,
                blob=blob_name
            )
            
            # Download blob to file
            with open(local_path, "wb") as file:
                download_stream = await asyncio.to_thread(blob_client.download_blob)
                data = await asyncio.to_thread(download_stream.readall)
                file.write(data)
            
            logger.info(f"Downloaded blob to {local_path} ({local_path.stat().st_size} bytes)")
            
        except Exception as e:
            logger.error(f"Error downloading blob: {str(e)}", exc_info=True)
            raise
    
    async def upload_stem(
        self,
        audio_file_id: str,
        stem_type: str,
        local_path: Path
    ) -> str:
        """Upload stem file to blob storage"""
        try:
            if not self.blob_service_client:
                raise RuntimeError("Blob storage client not configured")
            
            # Generate blob name: {audio_file_id}/stems/{stem_type}.wav
            blob_name = f"{audio_file_id}/stems/{stem_type}.wav"
            
            logger.info(f"Uploading stem: {blob_name}")
            
            # Get blob client
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name,
                blob=blob_name
            )
            
            # Upload file
            with open(local_path, "rb") as data:
                await asyncio.to_thread(
                    blob_client.upload_blob,
                    data,
                    overwrite=True,
                    content_settings={'content_type': 'audio/wav'}
                )
            
            # Get blob URL
            blob_url = blob_client.url
            logger.info(f"Uploaded stem to {blob_url}")
            
            return blob_url
            
        except Exception as e:
            logger.error(f"Error uploading stem: {str(e)}", exc_info=True)
            raise
    
    async def upload_jams(
        self,
        audio_file_id: str,
        local_path: Path
    ) -> str:
        """Upload JAMS annotation file to blob storage"""
        try:
            if not self.blob_service_client:
                raise RuntimeError("Blob storage client not configured")
            
            # Generate blob name: {audio_file_id}/analysis/annotation.jams
            blob_name = f"{audio_file_id}/analysis/annotation.jams"
            
            logger.info(f"Uploading JAMS: {blob_name}")
            
            # Get blob client
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name,
                blob=blob_name
            )
            
            # Upload file
            with open(local_path, "rb") as data:
                await asyncio.to_thread(
                    blob_client.upload_blob,
                    data,
                    overwrite=True,
                    content_settings={'content_type': 'application/json'}
                )
            
            # Get blob URL
            blob_url = blob_client.url
            logger.info(f"Uploaded JAMS to {blob_url}")
            
            return blob_url
            
        except Exception as e:
            logger.error(f"Error uploading JAMS: {str(e)}", exc_info=True)
            raise
