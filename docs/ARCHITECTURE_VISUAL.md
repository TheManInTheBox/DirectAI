# System Architecture Diagram

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                    DIRECTML AI MUSIC GENERATION PLATFORM                      ║
║                     with Music Theory Understanding                           ║
╚══════════════════════════════════════════════════════════════════════════════╝

┌─────────────────────────────────────────────────────────────────────────────┐
│                          USER UPLOADS MP3 FILE                               │
│                               (your_song.mp3)                                │
└──────────────────────────┬──────────────────────────────────────────────────┘
                           │
                           ▼
╔══════════════════════════════════════════════════════════════════════════════╗
║                         ANALYSIS WORKER (Python)                              ║
║                                                                               ║
║  ┌────────────────────────────────────────────────────────────────────────┐ ║
║  │  1. SOURCE SEPARATION (Demucs)                                         │ ║
║  │     → vocals.wav, drums.wav, bass.wav, other.wav                       │ ║
║  └────────────────────────────────────────────────────────────────────────┘ ║
║                           │                                                   ║
║  ┌────────────────────────┴───────────────────────────────────────────────┐ ║
║  │  2. MUSIC INFORMATION RETRIEVAL (librosa, essentia)                    │ ║
║  │     → BPM: 124.5                                                       │ ║
║  │     → Key: C major                                                     │ ║
║  │     → Chords: [C, G, Am, F] with timestamps                           │ ║
║  │     → Beats: [0.0, 0.48, 0.96, ...] (beat positions)                  │ ║
║  │     → Sections: [intro, verse, chorus, ...]                           │ ║
║  └────────────────────────────────────────────────────────────────────────┘ ║
║                           │                                                   ║
║  ┌────────────────────────┴───────────────────────────────────────────────┐ ║
║  │  3. MUSIC THEORY ANALYSIS ⭐ NEW                                       │ ║
║  │                                                                         │ ║
║  │  ╭───────────────────────────────────────────────────────────────────╮ │ ║
║  │  │ Harmonic Analysis:                                                │ │ ║
║  │  │   - Roman Numerals: [I, V, vi, IV]                               │ │ ║
║  │  │   - Functional Harmony: [tonic, dominant, tonic_sub, subdominant]│ │ ║
║  │  │   - Patterns: "I-V-vi-IV" (pop progression)                      │ │ ║
║  │  │   - Cadences: Authentic (V→I), Plagal (IV→I)                     │ │ ║
║  │  │   - Voice Leading Quality: "good" (minimal movement)             │ │ ║
║  │  │   - Harmonic Rhythm: 2 changes per bar                           │ │ ║
║  │  │   - Complexity: 0.57 (moderate)                                  │ │ ║
║  │  ╰───────────────────────────────────────────────────────────────────╯ │ ║
║  │                                                                         │ ║
║  │  ╭───────────────────────────────────────────────────────────────────╮ │ ║
║  │  │ Rhythmic Analysis:                                                │ │ ║
║  │  │   - Syncopation Index: 0.42 (moderate off-beat)                  │ │ ║
║  │  │   - Time Signature: 4/4                                           │ │ ║
║  │  │   - Note Density: 4.5 notes/second                               │ │ ║
║  │  │   - Metric Hierarchy: Strong beats [1,3], Weak [2,4]             │ │ ║
║  │  │   - Polyrhythms: None detected                                   │ │ ║
║  │  │   - Complexity: 0.61 (moderate-complex)                          │ │ ║
║  │  ╰───────────────────────────────────────────────────────────────────╯ │ ║
║  │                                                                         │ ║
║  │  ╭───────────────────────────────────────────────────────────────────╮ │ ║
║  │  │ Genre Detection:                                                  │ │ ║
║  │  │   - Primary: "pop" (85% confidence)                               │ │ ║
║  │  │   - Secondary: "rock" (62% confidence)                            │ │ ║
║  │  │   - Reasons:                                                      │ │ ║
║  │  │     * Uses I-V-vi-IV progression                                 │ │ ║
║  │  │     * BPM 124 matches pop range (100-130)                        │ │ ║
║  │  │     * Instrumentation matches 80%                                │ │ ║
║  │  ╰───────────────────────────────────────────────────────────────────╯ │ ║
║  └────────────────────────────────────────────────────────────────────────┘ ║
╚═══════════════════════════════════════════════════════════════════════════════╝
                           │
                           ▼
        ┌──────────────────────────────────────────────┐
        │  STORED IN DATABASE (PostgreSQL + Blob)      │
        │  - Stems (audio files)                       │
        │  - Analysis results (JSON)                   │
        │  - Music theory features ⭐                   │
        └──────────────────────────────────────────────┘


╔══════════════════════════════════════════════════════════════════════════════╗
║                    GENERATION WORKER (Future Training) ⭐                     ║
║                   Attention-Based Diffusion Architecture                      ║
║                                                                               ║
║  USER REQUEST: "Generate upbeat pop song about summer"                       ║
║                                                                               ║
║  ┌────────────────────────────────────────────────────────────────────────┐ ║
║  │  STAGE 1: Structure Transformer (T5/BART-based)                        │ ║
║  │                                                                         │ ║
║  │  Input: "upbeat pop song about summer" + genre:pop                     │ ║
║  │  Output:                                                                │ ║
║  │    - Structure: [intro, verse, chorus, verse, chorus, bridge, chorus] │ ║
║  │    - Progression: [I, V, vi, IV] (from genre conventions)             │ ║
║  │    - BPM: 125 (upbeat range)                                           │ ║
║  │    - Key: G major (bright key for summer theme)                        │ ║
║  │    - Duration: 180 seconds                                             │ ║
║  └────────────────────────────────────────────────────────────────────────┘ ║
║                           │                                                   ║
║  ┌────────────────────────┴───────────────────────────────────────────────┐ ║
║  │  STAGE 2: Stem Transformers (Attention-based, parallel generation)    │ ║
║  │                                                                         │ ║
║  │  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐      │ ║
║  │  │ Drums Gen  │  │  Bass Gen  │  │ Guitar Gen │  │ Vocals Gen │      │ ║
║  │  │            │  │            │  │            │  │            │      │ ║
║  │  │ → Rock     │  │ → Root     │  │ → Strummed │  │ → Melody   │      │ ║
║  │  │   pattern  │  │   notes    │  │   chords   │  │   line     │      │ ║
║  │  │ → 4/4 time │  │   G-D-Em-C │  │   G-D-Em-C │  │   in G maj │      │ ║
║  │  │ → MIDI out │  │ → MIDI out │  │ → MIDI out │  │ → MIDI out │      │ ║
║  │  └────────────┘  └────────────┘  └────────────┘  └────────────┘      │ ║
║  └────────────────────────────────────────────────────────────────────────┘ ║
║                           │                                                   ║
║  ┌────────────────────────┴───────────────────────────────────────────────┐ ║
║  │  STAGE 3: Music Theory Conditioner ⭐                                  │ ║
║  │                                                                         │ ║
║  │  Encodes musical features into embeddings:                             │ ║
║  │    - Chord embeddings: [I, V, vi, IV] → vectors                       │ ║
║  │    - Roman numeral embeddings: encode harmonic function               │ ║
║  │    - Beat position embeddings: metric hierarchy                       │ ║
║  │    - Genre embeddings: "pop" style characteristics                    │ ║
║  │    - Continuous features: [BPM=125, complexity=0.5, ...]              │ ║
║  │                                                                         │ ║
║  │  Output: notation_features (batch, seq_len, 256)                      │ ║
║  └────────────────────────────────────────────────────────────────────────┘ ║
║                           │                                                   ║
║  ┌────────────────────────┴───────────────────────────────────────────────┐ ║
║  │  STAGE 4: Diffusion Model with Cross-Attention ⭐⭐⭐                  │ ║
║  │                                                                         │ ║
║  │  Diffusion Process (T=50 steps):                                       │ ║
║  │                                                                         │ ║
║  │  Step 50 (pure noise):  [random gaussian noise in latent space]       │ ║
║  │         ↓                                                               │ ║
║  │  Step 40: [mostly noise, slight structure emerging]                   │ ║
║  │         ↓  ← CROSS-ATTENTION: Audio attends to chords [I, V, vi, IV]  │ ║
║  │  Step 30: [rough audio structure visible]                             │ ║
║  │         ↓  ← CROSS-ATTENTION: Audio aligns to beat positions          │ ║
║  │  Step 20: [recognizable melody emerging]                              │ ║
║  │         ↓  ← CROSS-ATTENTION: Audio follows genre "pop" style         │ ║
║  │  Step 10: [clear musical structure]                                   │ ║
║  │         ↓  ← CROSS-ATTENTION: Final refinement                        │ ║
║  │  Step 0:  [high-quality audio latent]                                 │ ║
║  │                                                                         │ ║
║  │  Architecture:                                                         │ ║
║  │  ┌──────────────────────────────────────────────────────────────────┐ │ ║
║  │  │  U-Net Diffusion Model:                                          │ │ ║
║  │  │                                                                   │ │ ║
║  │  │  Encoder:                                                         │ │ ║
║  │  │    Conv → ResBlock → ⚡ Cross-Attn (to notation)                 │ │ ║
║  │  │         → Downsample                                              │ │ ║
║  │  │    Conv → ResBlock → ⚡ Cross-Attn                               │ │ ║
║  │  │         → Downsample                                              │ │ ║
║  │  │                                                                   │ │ ║
║  │  │  Middle:                                                          │ │ ║
║  │  │    ResBlock → 🔄 Self-Attn → ⚡ Cross-Attn → ResBlock          │ │ ║
║  │  │                                                                   │ │ ║
║  │  │  Decoder:                                                         │ │ ║
║  │  │    Upsample → ResBlock → ⚡ Cross-Attn                           │ │ ║
║  │  │    ↑ (skip connection)                                            │ │ ║
║  │  │    Upsample → ResBlock → ⚡ Cross-Attn                           │ │ ║
║  │  │    ↑ (skip connection)                                            │ │ ║
║  │  │    Conv → Output (predicted noise)                               │ │ ║
║  │  │                                                                   │ │ ║
║  │  │  Key:                                                             │ │ ║
║  │  │    ⚡ = Cross-Attention (audio ← notation)                       │ │ ║
║  │  │    🔄 = Self-Attention (audio coherence)                         │ │ ║
║  │  └──────────────────────────────────────────────────────────────────┘ │ ║
║  └────────────────────────────────────────────────────────────────────────┘ ║
║                           │                                                   ║
║  ┌────────────────────────┴───────────────────────────────────────────────┐ ║
║  │  STAGE 5: VAE Decoder                                                  │ ║
║  │                                                                         │ ║
║  │  Latent (4, 32, 128) → Upsampling → Audio (2, 44100, N)              │ ║
║  │                       32x expansion                                    │ ║
║  └────────────────────────────────────────────────────────────────────────┘ ║
║                           │                                                   ║
║  ┌────────────────────────┴───────────────────────────────────────────────┐ ║
║  │  OUTPUT: High-quality audio stems                                      │ ║
║  │    - drums.wav (48kHz stereo)                                          │ ║
║  │    - bass.wav                                                           │ ║
║  │    - guitar.wav                                                         │ ║
║  │    - vocals.wav                                                         │ ║
║  │    - mixed.wav (all stems combined)                                    │ ║
║  └────────────────────────────────────────────────────────────────────────┘ ║
╚═══════════════════════════════════════════════════════════════════════════════╝


╔══════════════════════════════════════════════════════════════════════════════╗
║                    CROSS-ATTENTION MECHANISM DETAIL ⭐                        ║
║                        (The Key Innovation)                                   ║
║                                                                               ║
║  ┌────────────────────────────────────────────────────────────────────────┐ ║
║  │  Audio Features (from diffusion):                                      │ ║
║  │    [time=0.0s, features] → "What audio should I generate here?"       │ ║
║  │    [time=0.5s, features] → "What comes next?"                         │ ║
║  │    [time=1.0s, features] → "What follows?"                            │ ║
║  │    ...                                                                 │ ║
║  │                                                                         │ ║
║  │           ⬇ Query (Q)                                                  │ ║
║  │                                                                         │ ║
║  │    ┌──────────────────────────────────────────────────────────────┐   │ ║
║  │    │         CROSS-ATTENTION COMPUTATION                           │   │ ║
║  │    │                                                               │   │ ║
║  │    │  Attention_weights = softmax(Q @ K^T / √d)                   │   │ ║
║  │    │  Output = Attention_weights @ V                              │   │ ║
║  │    │                                                               │   │ ║
║  │    │  This makes audio "look at" notation to decide what to gen   │   │ ║
║  │    └──────────────────────────────────────────────────────────────┘   │ ║
║  │                                                                         │ ║
║  │           ⬆ Key (K) & Value (V)                                        │ ║
║  │                                                                         │ ║
║  │  Musical Notation (from theory analysis):                              │ ║
║  │    [time=0.0s: chord="I", beat=1, strong]  → "Generate C major chord" │ ║
║  │    [time=0.5s: chord="I", beat=2, weak]    → "Continue C major"       │ ║
║  │    [time=1.0s: chord="V", beat=3, strong]  → "Change to G major"      │ ║
║  │    [time=1.5s: chord="V", beat=4, weak]    → "Continue G major"       │ ║
║  │    ...                                                                 │ ║
║  └────────────────────────────────────────────────────────────────────────┘ ║
║                                                                               ║
║  Result: Generated audio FOLLOWS the musical structure!                      ║
║    - Audio at time=0.0s sounds like C major chord                            ║
║    - Audio transitions to G major at time=1.0s                               ║
║    - Strong beats (1,3) are emphasized                                       ║
║    - Harmonic progression respected throughout                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝


╔══════════════════════════════════════════════════════════════════════════════╗
║                         TRAINING DATA FLOW ⭐                                 ║
║                                                                               ║
║  100,000 MP3 files                                                           ║
║       ↓                                                                       ║
║  [Analysis Worker runs on each]                                              ║
║       ↓                                                                       ║
║  Training Dataset:                                                           ║
║  {                                                                            ║
║    "audio_stems": {                                                          ║
║      "drums.wav": [...],                                                     ║
║      "bass.wav": [...],                                                      ║
║      "other.wav": [...],                                                     ║
║      "vocals.wav": [...]                                                     ║
║    },                                                                         ║
║    "music_theory": {                                                         ║
║      "harmonic": {                                                           ║
║        "roman_numerals": ["I", "V", "vi", "IV"],                            ║
║        "functional_harmony": ["tonic", "dominant", ...],                    ║
║        "cadences": [{"type": "authentic", ...}]                             ║
║      },                                                                       ║
║      "rhythmic": {                                                           ║
║        "syncopation": 0.42,                                                  ║
║        "complexity": 0.61,                                                   ║
║        "time_signature": "4/4"                                               ║
║      },                                                                       ║
║      "genre": {"primary": "pop", "confidence": 0.85}                        ║
║    },                                                                         ║
║    "bpm": 124.5,                                                             ║
║    "key": "C major"                                                          ║
║  }                                                                            ║
║       ↓                                                                       ║
║  [Used to train diffusion model with cross-attention]                        ║
║       ↓                                                                       ║
║  Model learns to:                                                            ║
║    - Generate audio that matches chord progressions                          ║
║    - Follow rhythmic patterns                                                ║
║    - Respect genre conventions                                               ║
║    - Create harmonically coherent music                                      ║
╚═══════════════════════════════════════════════════════════════════════════════╝
```

## Summary

**You now have:**

✅ **Music Theory Analyzer** - Understands harmony, rhythm, genre  
✅ **Cross-Attention Architecture** - Audio follows musical structure  
✅ **Diffusion Model** - High-quality audio generation  
✅ **Complete Pipeline** - From analysis to generation  
✅ **Training-Ready** - Features extracted for ML training  

**Next: Choose your path** (MVP vs Full Training) and we can proceed! 🎵
