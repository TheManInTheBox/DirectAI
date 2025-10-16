"""
Script to upload existing separated stems to blob storage
"""
import os
import asyncio
import logging
from pathlib import Path
from storage_service import StorageService

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def upload_stems_for_audio_file(audio_file_id: str, temp_dir: Path):
    """Upload all stems for a specific audio file"""
    storage = StorageService()
    
    stem_types = ['bass', 'drums', 'vocals', 'other']
    uploaded = []
    
    for stem_type in stem_types:
        stem_path = temp_dir / 'stems' / 'htdemucs' / 'original' / f'{stem_type}.wav'
        
        if stem_path.exists():
            logger.info(f"Uploading {stem_type} stem for {audio_file_id}...")
            try:
                blob_url = await storage.upload_stem(audio_file_id, stem_type, stem_path)
                uploaded.append((stem_type, blob_url))
                logger.info(f"✓ Uploaded {stem_type}: {blob_url}")
            except Exception as e:
                logger.error(f"✗ Failed to upload {stem_type}: {e}")
        else:
            logger.warning(f"✗ Stem file not found: {stem_path}")
    
    return uploaded

async def main():
    """Find and upload all existing stems"""
    tmp_dir = Path('/tmp')
    
    # Find all analysis directories
    analysis_dirs = list(tmp_dir.glob('analysis_*'))
    
    # Group by audio file ID
    audio_files = {}
    for dir_path in analysis_dirs:
        dir_name = dir_path.name
        # Extract audio file ID from directory name (e.g., analysis_<guid>_<random>)
        parts = dir_name.split('_')
        if len(parts) >= 2:
            audio_file_id = parts[1]
            if audio_file_id not in audio_files:
                audio_files[audio_file_id] = []
            audio_files[audio_file_id].append(dir_path)
    
    logger.info(f"Found {len(audio_files)} unique audio files with stems")
    
    # Upload stems for each audio file (use the most recent directory)
    for audio_file_id, dirs in audio_files.items():
        # Use the most recent directory
        most_recent = max(dirs, key=lambda p: p.stat().st_mtime)
        logger.info(f"\nProcessing audio file: {audio_file_id}")
        logger.info(f"Using directory: {most_recent}")
        
        uploaded = await upload_stems_for_audio_file(audio_file_id, most_recent)
        
        if uploaded:
            logger.info(f"✓ Successfully uploaded {len(uploaded)} stems for {audio_file_id}")
        else:
            logger.warning(f"✗ No stems uploaded for {audio_file_id}")

if __name__ == "__main__":
    asyncio.run(main())
