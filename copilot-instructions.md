# GitHub Copilot Instructions for this repository

These instructions help Copilot (and contributors) work effectively in this codebase. Prefer concrete, incremental changes, keep public APIs stable, and validate via build/tests before concluding work.

## Project overview
- **DirectAI**: A Generative Audio Workstation (GAW) combining AI-powered music generation with professional DAW functionality
- Solution: `DirectML.AI.Platform.sln`
- Architecture: API (.NET), Workers (Python), WinUI Client, Infrastructure (Bicep/K8s), local dev via Docker Compose.
- Local stack: API + Postgres + Azurite + analysis/generation workers + pgAdmin.

## Vision: Generative Audio Workstation
Building a next-generation audio production platform that combines:
1. **DAW-like Interface**: Multitrack timeline with drag-and-drop stems, visual waveform editing, tempo-aligned grid
2. **AI Generation**: Transformer-based models (MusicGen, MelodyFlow) for stem generation, variation engine for creative options
3. **Professional Audio**: Stem extraction (Demucs), beat detection, mixdown with compression/EQ/reverb, mastering presets
4. **Workflow Integration**: Prompt-to-music composer, stem editor with pitch/timing control, recording module for live input

### Core Architecture
**Frontend (WinUI 3):**
- Multitrack timeline with SUNO Studio-style dark UI
- Drag-and-drop stem management with visual waveforms
- Prompt composer for text-to-music generation
- Genre/style selectors and variation browser

**Generative Engine (Python Workers):**
- Model orchestration: MusicGen, diffusion models for high-fidelity stems
- Stem generator modules: bassline, percussion, melody, vocal synthesis
- Variation engine: multiple stem variants per prompt with user refinement

**Audio Processing Pipeline:**
- Stem extraction via Demucs (vocals, drums, bass, other)
- Beat detection and grid alignment (tempo-aware)
- Mixdown engine with professional effects chain
- Recording integration for live input capture

## Tech stack by area
- API: ASP.NET Core (C#), EF Core (Npgsql), SignalR hubs, REST controllers.
- Domain: C# models; changes require EF migrations in `src/MusicPlatform.Api`.
- Client: .NET MAUI (Windows target), consuming API endpoints.
- Workers: Python 3.11; analysis uses librosa/demucs, generation uses MusicGen; FastAPI service.
- Storage: Azurite for local Blob emulation; Bark training JSON written to blob.
- Infra: Bicep and Kubernetes manifests under `infrastructure/`.

## Where to put code changes
- New API endpoints: `src/MusicPlatform.Api/Controllers/` (keep routes under `api/`).
- Business logic/services: `src/MusicPlatform.Api/Services/`.
- DB models/entities: `src/MusicPlatform.Domain/Models/`; update migrations in API project.
- Worker analysis pipeline: `workers/analysis/` (main.py, analysis_service.py).
- Worker generation pipeline: `workers/generation/` - AI model integration for stem generation.
- WinUI Client UI/ViewModels: `src/MusicPlatform.WinUI/` - DAW interface, mixing page, timeline controls.
- Audio services: `src/MusicPlatform.WinUI/Services/` - AudioPlaybackService, AudioCacheService.
- Infra changes: `infrastructure/` and `infrastructure/kubernetes/`.

## Coding conventions
- C#:
  - Use async/await, cancellation tokens where appropriate.
  - Keep controllers thin; prefer services and DI.
  - EF Core: prefer owned types/child collections for annotations; avoid breaking schema unless paired with migration.
- Python (workers):
  - Python 3.11, type hints preferred, log clearly and catch exceptions to avoid crashing jobs.
  - The analysis pipeline must be resilient: timeouts, fallbacks, and non-fatal optional features.
- General: small PRs, comprehensive logging, and idempotent job handling.

## Build, run, and validate (local)
- Use Docker Compose to run the stack (Azurite, Postgres, API, workers). The API is on http://localhost:5000.
- Azurite endpoints are automatically translated for the client (API replaces `http://azurite:10000` with `http://localhost:10000`).
- Validate before finishing work:
  - API: build `MusicPlatform.Api` and run the container; hit `/health` (if present) and controller endpoints.
  - Workers: rebuild the worker image if Python code changed; ensure container health is OK.
  - WinUI Client: build `MusicPlatform.WinUI` for `net9.0-windows10.0.19041.0`; test mixing page and audio playback.

## Data and jobs
- Analysis results persist BPM/Key/Mode/Tuning, beats/sections/chords, and Flamingo insights JSON.
- Jobs are idempotent and tracked in the API (`/api/jobs`); worker calls back to `/api/audio/{id}/analysis-complete`.
- Bark training dataset JSON is uploaded to blob under `audio-files/{id}/bark_training/`.

## Migrations (EF Core)
- Add/modify models → create migration in API project, apply to Postgres used by the API container.
- Keep migration names descriptive; do not break existing seed or assume clean DB.

## Workers: analysis guidelines
- Keep Audio Flamingo optional and non-fatal. If the model isn’t available, skip and continue the pipeline. Do not crash the job.
- Demucs separation: expect 4 stems (vocals, drums, bass, other).
- MIR steps should have timeouts and fallbacks (synthetic beats, simple sections) to avoid long stalls.
- Export Bark dataset JSON even when some advanced insights are missing.

## Client (MAUI) guidelines
- Use existing API client services; keep routes consistent with `src/MusicPlatform.Api`.
- Notation models align with worker schema (events/pitch_contour/chord_progression/melody).

## Audio Caching
- **AudioCacheService**: Provides local file caching (up to 500MB) with LRU eviction.
- Cache location: `ApplicationData.Current.LocalCacheFolder/AudioCache/`
- Cache keys: Use format `audio_{audioFileId}` for originals, `stem_{stemId}` for stems.
- **AudioPlaybackService**: Automatically caches audio files on first load; subsequent loads are served from cache.
- Use `LoadTrackFromCacheAsync()` instead of `LoadTrackAsync()` to leverage caching.
- Cache is persistent across app sessions and survives restarts.

## WinUI 3 XAML guidelines
- **CRITICAL:** WinUI 3 does NOT support `RelativeSource` binding syntax (e.g., `RelativeSource={RelativeSource AncestorType=Page}`).
- Use `ElementName` binding instead: Add `x:Name="Root"` to the Page element, then use `ElementName=Root` in bindings.
- Example: `Command="{Binding DataContext.MyCommand, ElementName=Root}"` instead of `Command="{Binding DataContext.MyCommand, RelativeSource={RelativeSource AncestorType=Page}}"`
- **BorderDashArray is NOT supported** in WinUI 3. Use solid borders only.
- This is a common source of silent XAML compiler failures with exit code 1.

## Testing and quality gates
- API tests: `tests/DirectML.AI.Tests/` (extend when changing public behavior).
- Quality gates for every change:
  - Build: PASS for API and workers.
  - Lint/Typecheck: N/A for C# beyond build; Python type hints preferred.
  - Tests: run existing tests; add minimal cases for new logic.

## Security and secrets
- Do not hardcode secrets. Use Azurite dev connection string for local only.
- Never commit real keys or credentials.

## Preferred patterns for Copilot
- Before editing many files, summarize intended changes and their file paths.
- Make conservative, localized changes first. If a call references a missing helper, implement a minimal, self-contained helper matching existing patterns.
- For flaky or heavy ML dependencies (e.g., Audio Flamingo), keep them optional and guarded by try/except; never fail the main pipeline due to their absence.
- Align MAUI models with worker output; avoid introducing breaking wire format changes.

## Non-goals and anti-patterns
- Don’t introduce new external services without adding them to Docker Compose.
- Don’t block analysis completion on optional AI models.
- Don’t change public API contracts without updating the MAUI client and tests.

## Useful paths and routes
- Upload: `POST /api/audio/upload`
- Trigger analysis: `POST /api/audio/{id}/analyze`
- Get analysis: `GET /api/audio/{id}/analysis`
- Get insights (Bark JSON): `GET /api/audio/{id}/insights`
- Stems: `GET /api/audio/{id}/stems`
- Jobs: `GET /api/jobs`, `GET /api/jobs/{id}`

## PR guidance (for automated changes)
- Keep PRs focused and list files changed with a short purpose per file.
- Include a short verification section (what was built, what ran, expected outputs).
- Note any follow-ups separately if they are larger/riskier.

