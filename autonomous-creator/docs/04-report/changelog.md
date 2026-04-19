# Changelog

All notable changes to the Autonomous Creator project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [0.1.1] - 2026-03-30

### Added

- F5-TTS-THAI engine for Thai language (replaces Azure TTS)
  - Zero-shot voice cloning with reference audio
  - Voice presets (female_standard, female_slow, female_fast)
  - Lazy model loading for memory efficiency
  - Dependency checking with installation instructions
- TTSFactory integration for Thai language ("th")

### Changed

- Thai TTS: Azure Cognitive Services (paid) -> F5-TTS-THAI (free, open-source)
- Thai pronunciation: Chinese-like -> Authentic Thai

### Technical

- Package: f5-tts-th v1.0.9
- Model: VIZINTZOR/F5-TTS-THAI (1M steps)
- Sample rate: 24000 Hz
- Design match rate: 100%

---

## [0.1.0] - 2026-03-29

### Added

- Multi-language TTS pipeline with automatic engine selection
  - Korean, Japanese, Chinese: GPT-SoVITS v3
  - Thai: Azure Cognitive Services TTS
  - English: Edge-TTS
- Image generation with style consistency
  - Stable Diffusion 3.5 Medium integration
  - IP-Adapter for style transfer
  - Seed-based consistency fallback
- Hybrid video generation
  - Stable Video Diffusion for key scenes
  - Ken Burns effect for supporting scenes
  - Automatic scene classification
- Clean architecture implementation
  - Domain layer: Entities, Interfaces, Use Cases
  - Application layer: Services, Orchestrator
  - Infrastructure layer: TTS, Image, Video, AI, Persistence
  - Interface layer: CLI, REST API
- CLI interface (`autonomous` command)
  - `autonomous init` - Project initialization
  - `autonomous create` - Video generation from story
  - `autonomous list` - List generated stories
  - `autonomous presets` - List style presets
  - `autonomous recommend` - AI story recommendations
  - `autonomous serve` - Start API server
- REST API (FastAPI)
  - `/api/v1/stories` - Story management
  - `/api/v1/presets` - Preset management
  - `/api/v1/tasks` - Task tracking
  - `/health` - Health check
- Claude AI integration
  - Script generation from stories
  - Story recommendations
  - Prompt enhancement
  - Content translation
  - Trend analysis
- Task tracking system
  - Progress reporting
  - Status management
  - Error handling

### Changed

- Initial release (no previous changes)

### Fixed

- Initial release (no previous fixes)

---

## Version History

| Version | Date | Type | Description |
|---------|------|------|-------------|
| 0.1.1 | 2026-03-30 | Feature | Thai TTS with F5-TTS-THAI (voice cloning) |
| 0.1.0 | 2026-03-29 | Major | Initial release with full pipeline |
