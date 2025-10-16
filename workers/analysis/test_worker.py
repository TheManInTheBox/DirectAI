"""
Simple test script to validate analysis worker functionality
Run with: python test_worker.py
"""
import asyncio
import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from analysis_service import AnalysisService


async def test_analysis_service():
    """Test the analysis service initialization"""
    print("Testing Analysis Service...")
    
    try:
        service = AnalysisService()
        print(f"✓ Analysis service initialized")
        print(f"  - Demucs model: {service.demucs_model}")
        print(f"  - Sample rate: {service.sample_rate}")
        
        # Test JAMS creation (without actual audio)
        print("\n✓ Testing JAMS creation...")
        import jams
        
        test_analysis = {
            "bpm": 120.0,
            "key": "C",
            "tuning_frequency": 440.0,
            "duration_seconds": 180.0,
            "beats": [
                {"time": 0.5, "position": 1, "confidence": 1.0},
                {"time": 1.0, "position": 2, "confidence": 1.0}
            ],
            "sections": [
                {"label": "intro", "start_time": 0.0, "end_time": 10.0, "confidence": 0.8}
            ],
            "chords": [
                {"chord": "C", "start_time": 0.0, "end_time": 2.0, "confidence": 0.7}
            ]
        }
        
        jam = service.create_jams_annotation(
            "test-audio-id",
            Path("test.mp3"),
            test_analysis
        )
        
        print(f"  - Created JAMS with {len(jam.annotations)} annotation types")
        print(f"  - Duration: {jam.file_metadata.duration}s")
        
        print("\n✓ All tests passed!")
        return True
        
    except Exception as e:
        print(f"\n✗ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    result = asyncio.run(test_analysis_service())
    sys.exit(0 if result else 1)
