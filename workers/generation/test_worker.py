"""
Simple test script to validate generation worker functionality
Run with: python test_worker.py
"""
import asyncio
import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from generation_service import GenerationService


async def test_generation_service():
    """Test the generation service initialization and AI model loading"""
    print("Testing Generation Service...")
    
    try:
        print("Initializing service (this will download MusicGen model on first run)...")
        service = GenerationService()
        print(f"✓ Generation service initialized")
        print(f"  - Sample rate: {service.sample_rate}")
        print(f"  - Use GPU: {service.use_gpu}")
        print(f"  - Has MusicGen: {service.has_musicgen}")
        print(f"  - Has Stable Audio: {service.has_stable_audio}")
        
        if not service.has_musicgen and not service.has_stable_audio:
            print("✗ No AI models loaded - service cannot generate audio")
            return False
        
        # Test AI audio generation (short duration)
        print("\n✓ Testing AI audio generation (this may take 30-60 seconds)...")
        
        import tempfile
        temp_dir = Path(tempfile.mkdtemp())
        
        test_params = {
            "target_bpm": 120.0,
            "duration_seconds": 5.0,  # 5 seconds for AI generation
            "style": "rock",
            "prompt": "energetic rock music"
        }
        
        # Test one stem type (AI generation is slow)
        stem_types = ["guitar"]
        
        for stem_type in stem_types:
            print(f"  - Generating {stem_type}...")
            audio_path = await service.generate_stem(
                stem_type=stem_type,
                parameters=test_params,
                output_dir=temp_dir
            )
            
            if audio_path and audio_path.exists():
                size_kb = audio_path.stat().st_size / 1024
                print(f"    ✓ Generated {audio_path.name} ({size_kb:.1f} KB)")
            else:
                print(f"    ✗ Failed to generate {stem_type}")
                return False
        
        # Cleanup
        import shutil
        shutil.rmtree(temp_dir)
        
        print("\n✓ All tests passed!")
        return True
        
    except Exception as e:
        print(f"\n✗ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    result = asyncio.run(test_generation_service())
    sys.exit(0 if result else 1)
