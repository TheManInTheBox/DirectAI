#!/usr/bin/env python3
"""
Export Training Dataset from DirectAI MP3 Collection

This script exports all analyzed MP3s from your DirectAI platform
into a training dataset for AI music generation models.
"""

import asyncio
import json
import os
import requests
from pathlib import Path
from typing import Dict, List, Any
import argparse
from datetime import datetime

# Configuration
API_BASE_URL = "http://localhost:5000/api"
OUTPUT_DIR = Path("./training_data")
STEMS_DIR = OUTPUT_DIR / "stems"
FEATURES_DIR = OUTPUT_DIR / "features"


async def get_all_songs() -> List[Dict[str, Any]]:
    """Fetch all songs from the API"""
    try:
        response = requests.get(f"{API_BASE_URL}/audio")
        response.raise_for_status()
        songs = response.json()
        print(f"Found {len(songs)} songs in collection")
        return songs
    except Exception as e:
        print(f"Error fetching songs: {e}")
        return []


async def get_song_analysis(song_id: str) -> Dict[str, Any]:
    """Get analysis data for a specific song"""
    try:
        response = requests.get(f"{API_BASE_URL}/audio/{song_id}/analysis")
        if response.status_code == 200:
            return response.json()
        else:
            print(f"No analysis data for song {song_id}")
            return {}
    except Exception as e:
        print(f"Error fetching analysis for {song_id}: {e}")
        return {}


async def get_song_stems(song_id: str) -> Dict[str, str]:
    """Get stem file URLs for a song"""
    try:
        response = requests.get(f"{API_BASE_URL}/audio/{song_id}/stems")
        if response.status_code == 200:
            return response.json()
        else:
            print(f"No stems available for song {song_id}")
            return {}
    except Exception as e:
        print(f"Error fetching stems for {song_id}: {e}")
        return {}


async def download_stems(song_id: str, stems_data: Dict[str, str]) -> Dict[str, str]:
    """Download stem files for a song"""
    local_stems = {}
    song_stems_dir = STEMS_DIR / song_id
    song_stems_dir.mkdir(parents=True, exist_ok=True)
    
    for stem_type, stem_url in stems_data.items():
        if stem_url and stem_type in ['vocals', 'drums', 'bass', 'other']:
            try:
                response = requests.get(stem_url)
                response.raise_for_status()
                
                local_path = song_stems_dir / f"{stem_type}.wav"
                with open(local_path, 'wb') as f:
                    f.write(response.content)
                
                local_stems[stem_type] = str(local_path)
                print(f"  Downloaded {stem_type} stem ({len(response.content)} bytes)")
                
            except Exception as e:
                print(f"  Error downloading {stem_type} stem: {e}")
    
    return local_stems


def extract_training_features(song: Dict[str, Any], analysis: Dict[str, Any]) -> Dict[str, Any]:
    """Extract features suitable for training"""
    
    # Basic song info
    basic_features = {
        "id": song.get("id"),
        "title": song.get("originalFileName", "").replace(".mp3", ""),
        "artist": song.get("artist"),
        "album": song.get("album"),
        "year": song.get("year"),
        "genre_tag": song.get("genre"),
        "duration_seconds": song.get("duration", "00:00:00"),
        "bpm": song.get("bpm"),
        "key": song.get("key"),
        "time_signature": song.get("timeSignature", "4/4")
    }
    
    # Music theory features (if available from new analysis)
    music_theory = {}
    if "harmonic_analysis" in analysis:
        music_theory["harmonic"] = analysis["harmonic_analysis"]
    
    if "rhythmic_analysis" in analysis:
        music_theory["rhythmic"] = analysis["rhythmic_analysis"]
    
    if "genre_analysis" in analysis:
        music_theory["genre"] = analysis["genre_analysis"]
    
    # MIR features
    mir_features = {}
    for key in ["bpm", "key", "beats", "sections", "chords"]:
        if key in analysis:
            mir_features[key] = analysis[key]
    
    # Metadata for training
    metadata = {
        "upload_date": song.get("uploadedAt"),
        "file_size": song.get("sizeBytes"),
        "bitrate": song.get("bitrate"),
        "sample_rate": song.get("sampleRate"),
        "channels": song.get("channels")
    }
    
    return {
        "basic": basic_features,
        "music_theory": music_theory,
        "mir_features": mir_features,
        "metadata": metadata
    }


async def export_song(song: Dict[str, Any], include_stems: bool = True) -> Dict[str, Any]:
    """Export a single song's training data"""
    song_id = song["id"]
    title = song.get("originalFileName", song_id)
    
    print(f"\nProcessing: {title}")
    
    # Get analysis data
    analysis = await get_song_analysis(song_id)
    
    # Extract training features
    training_features = extract_training_features(song, analysis)
    
    # Download stems if requested
    local_stems = {}
    if include_stems:
        stems_data = await get_song_stems(song_id)
        if stems_data:
            print(f"  Downloading stems...")
            local_stems = await download_stems(song_id, stems_data)
        else:
            print(f"  No stems available")
    
    # Create training sample
    training_sample = {
        "song_id": song_id,
        "features": training_features,
        "stems": local_stems,
        "has_analysis": bool(analysis),
        "has_stems": bool(local_stems),
        "export_timestamp": datetime.now().isoformat()
    }
    
    # Save individual feature file
    feature_file = FEATURES_DIR / f"{song_id}.json"
    with open(feature_file, 'w') as f:
        json.dump(training_sample, f, indent=2)
    
    return training_sample


async def export_dataset(include_stems: bool = True, min_songs: int = 1) -> Dict[str, Any]:
    """Export the complete training dataset"""
    print("=== DirectAI Training Dataset Export ===\n")
    
    # Create output directories
    OUTPUT_DIR.mkdir(exist_ok=True)
    STEMS_DIR.mkdir(exist_ok=True)
    FEATURES_DIR.mkdir(exist_ok=True)
    
    # Get all songs
    songs = await get_all_songs()
    
    if len(songs) < min_songs:
        print(f"Error: Only {len(songs)} songs found, need at least {min_songs}")
        return {}
    
    # Process each song
    training_samples = []
    successful_exports = 0
    
    for song in songs:
        try:
            sample = await export_song(song, include_stems)
            training_samples.append(sample)
            
            if sample["has_analysis"] and (sample["has_stems"] or not include_stems):
                successful_exports += 1
        
        except Exception as e:
            print(f"Error processing {song.get('originalFileName', song['id'])}: {e}")
    
    # Create dataset summary
    dataset_summary = {
        "export_info": {
            "export_date": datetime.now().isoformat(),
            "total_songs": len(songs),
            "successful_exports": successful_exports,
            "include_stems": include_stems,
            "output_directory": str(OUTPUT_DIR.absolute())
        },
        "dataset_stats": analyze_dataset_stats(training_samples),
        "training_samples": training_samples
    }
    
    # Save complete dataset
    dataset_file = OUTPUT_DIR / "training_dataset.json"
    with open(dataset_file, 'w') as f:
        json.dump(dataset_summary, f, indent=2)
    
    # Create readable summary
    create_dataset_summary(dataset_summary)
    
    print(f"\n=== Export Complete ===")
    print(f"Total songs processed: {len(songs)}")
    print(f"Successful exports: {successful_exports}")
    print(f"Output directory: {OUTPUT_DIR.absolute()}")
    print(f"Dataset file: {dataset_file}")
    
    return dataset_summary


def analyze_dataset_stats(samples: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyze dataset statistics"""
    stats = {
        "total_samples": len(samples),
        "with_analysis": sum(1 for s in samples if s["has_analysis"]),
        "with_stems": sum(1 for s in samples if s["has_stems"]),
        "genres": {},
        "years": {},
        "keys": {},
        "bpm_range": {"min": float('inf'), "max": 0},
        "duration_total": 0
    }
    
    for sample in samples:
        features = sample["features"]["basic"]
        
        # Genre distribution
        genre = features.get("genre_tag", "Unknown")
        stats["genres"][genre] = stats["genres"].get(genre, 0) + 1
        
        # Year distribution
        year = features.get("year", "Unknown")
        stats["years"][str(year)] = stats["years"].get(str(year), 0) + 1
        
        # Key distribution
        key = features.get("key", "Unknown")
        stats["keys"][key] = stats["keys"].get(key, 0) + 1
        
        # BPM range
        bpm = features.get("bpm", 0)
        if bpm > 0:
            stats["bpm_range"]["min"] = min(stats["bpm_range"]["min"], bpm)
            stats["bpm_range"]["max"] = max(stats["bpm_range"]["max"], bpm)
        
        # Total duration (parse MM:SS format)
        duration_str = features.get("duration_seconds", "00:00:00")
        if ":" in str(duration_str):
            try:
                parts = str(duration_str).split(":")
                if len(parts) == 3:  # HH:MM:SS
                    seconds = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
                else:  # MM:SS
                    seconds = int(parts[0]) * 60 + int(parts[1])
                stats["duration_total"] += seconds
            except:
                pass
    
    # Fix infinite min BPM
    if stats["bpm_range"]["min"] == float('inf'):
        stats["bpm_range"]["min"] = 0
    
    return stats


def create_dataset_summary(dataset: Dict[str, Any]):
    """Create a human-readable dataset summary"""
    summary_file = OUTPUT_DIR / "DATASET_SUMMARY.md"
    
    stats = dataset["dataset_stats"]
    export_info = dataset["export_info"]
    
    content = f"""# DirectAI Training Dataset Summary

Generated: {export_info["export_date"]}

## Dataset Overview

- **Total Songs**: {stats["total_samples"]}
- **With Analysis**: {stats["with_analysis"]} ({stats["with_analysis"]/stats["total_samples"]*100:.1f}%)
- **With Stems**: {stats["with_stems"]} ({stats["with_stems"]/stats["total_samples"]*100:.1f}%)
- **Total Duration**: {stats["duration_total"]//3600}h {(stats["duration_total"]%3600)//60}m {stats["duration_total"]%60}s

## Genre Distribution

"""
    
    for genre, count in sorted(stats["genres"].items(), key=lambda x: x[1], reverse=True):
        percentage = count / stats["total_samples"] * 100
        content += f"- **{genre}**: {count} songs ({percentage:.1f}%)\n"
    
    content += f"""
## Musical Characteristics

- **BPM Range**: {stats["bpm_range"]["min"]:.1f} - {stats["bpm_range"]["max"]:.1f}
- **Keys Found**: {len(stats["keys"])} different keys
- **Years Covered**: {len(stats["years"])} different years

## Top Keys

"""
    
    for key, count in sorted(stats["keys"].items(), key=lambda x: x[1], reverse=True)[:10]:
        percentage = count / stats["total_samples"] * 100
        content += f"- **{key}**: {count} songs ({percentage:.1f}%)\n"
    
    content += """
## Files Structure

```
training_data/
├── training_dataset.json      # Complete dataset with all metadata
├── DATASET_SUMMARY.md         # This summary file
├── features/                  # Individual song features
│   ├── {song_id}.json
│   └── ...
└── stems/                     # Audio stems (if downloaded)
    ├── {song_id}/
    │   ├── vocals.wav
    │   ├── drums.wav
    │   ├── bass.wav
    │   └── other.wav
    └── ...
```

## Training Readiness

"""
    
    ready_count = sum(1 for s in dataset["training_samples"] 
                     if s["has_analysis"] and s["has_stems"])
    
    content += f"""- **Training-Ready Songs**: {ready_count}/{stats["total_samples"]}
- **Minimum for MVP**: 1,000 songs (need {max(0, 1000-ready_count)} more)
- **Recommended**: 10,000 songs (need {max(0, 10000-ready_count)} more)
- **Enterprise-grade**: 100,000 songs (need {max(0, 100000-ready_count)} more)

## Next Steps

1. **Upload more MP3s** to reach your target dataset size
2. **Choose training approach**: MVP, Hybrid, or Full Training
3. **Set up training infrastructure** (GPUs, storage)
4. **Begin model training** with this dataset

---

*Generated by DirectAI Training Dataset Exporter*
"""
    
    with open(summary_file, 'w') as f:
        f.write(content)
    
    print(f"Summary created: {summary_file}")


async def main():
    parser = argparse.ArgumentParser(description="Export DirectAI MP3 collection as training dataset")
    parser.add_argument("--no-stems", action="store_true", help="Skip downloading audio stems")
    parser.add_argument("--min-songs", type=int, default=1, help="Minimum number of songs required")
    parser.add_argument("--output", type=str, default="./training_data", help="Output directory")
    
    args = parser.parse_args()
    
    global OUTPUT_DIR, STEMS_DIR, FEATURES_DIR
    OUTPUT_DIR = Path(args.output)
    STEMS_DIR = OUTPUT_DIR / "stems"
    FEATURES_DIR = OUTPUT_DIR / "features"
    
    include_stems = not args.no_stems
    
    dataset = await export_dataset(include_stems=include_stems, min_songs=args.min_songs)
    
    if dataset:
        print(f"\n✅ Dataset export successful!")
        print(f"Ready to train with {dataset['dataset_stats']['with_analysis']} analyzed songs")
    else:
        print(f"\n❌ Dataset export failed")


if __name__ == "__main__":
    asyncio.run(main())
