# Autonomous Creator

AI-powered multi-language short video generation system.

## Features

- 🎬 **Automated Video Creation**: Story → Video in 3 minutes
- 🌍 **Multi-language Support**: Korean, Thai, English, Japanese, Chinese
- 🎨 **Style Consistency**: IP-Adapter + Seed-based consistency
- 🤖 **AI Video**: Stable Video Diffusion for dynamic scenes
- 📊 **Web Dashboard**: Next.js + FastAPI
- 💻 **CLI Tool**: Quick video generation from terminal

## Quick Start

```bash
# Install
pip install -e .

# Initialize
autonomous init

# Create video
autonomous create --title "My Story" --content "Once upon a time..."

# Or use API
autonomous serve
```

## Architecture

```
autonomous-creator/
├── core/domain/          # Business Logic
├── core/application/     # Use Cases
├── infrastructure/       # External Services
│   ├── tts/             # GPT-SoVITS, Azure, Edge
│   ├── image/           # SD 3.5 + IP-Adapter
│   └── video/           # SVD + MoviePy
└── interfaces/          # API + CLI
```

## TTS Language Support

| Language | Engine | Quality | Cost |
|----------|--------|---------|------|
| Korean | GPT-SoVITS | ⭐⭐⭐⭐⭐ | Free |
| Japanese | GPT-SoVITS | ⭐⭐⭐⭐⭐ | Free |
| Chinese | GPT-SoVITS | ⭐⭐⭐⭐⭐ | Free |
| Thai | Azure TTS | ⭐⭐⭐⭐ | ~$5/mo |
| English | Edge-TTS | ⭐⭐⭐⭐⭐ | Free |

## Requirements

- Python 3.10+
- CUDA-capable GPU (12GB+ VRAM recommended)
- FFmpeg

## License

MIT
