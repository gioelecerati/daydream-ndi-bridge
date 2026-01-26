# Daydream StreamDiffusionV1 NDI Bridge

Real-time AI video transformation bridge using the [Daydream API](https://docs.daydream.live). Capture video via NDI and transform it with AI in real-time.
[Tutorial using Resolume Arena + Daydream scope](https://app.daydream.live/creators/gioele/resolume-arena-longlive-with-ndi-and-scope)

https://github.com/user-attachments/assets/63260dd5-2756-4a99-8c85-fbf68503a0b8

## Features

- **NDI Input** - Capture video from any NDI source on your network
- **Real-time AI Transformation** - Transform your video feed using StreamDiffusion
- **Multiple AI Models** - Support for SD 1.5, SD Turbo, SDXL Turbo
- **ControlNet Support** - Depth, Canny edge, and Tile ControlNets
- **Web-based Control Panel** - Adjust all parameters in a clean browser UI
- **Low Latency** - WebRTC output for minimal delay

## Requirements

- macOS 10.15+ or Windows 10+ (with NDI SDK)
- Python 3.10+
- [NDI Tools](https://ndi.video/tools/) installed
- Active internet connection

## Installation

```bash
cd daydream-bridge

# Install dependencies
pip install -r requirements.txt

# Run the bridge
python app.py
```

## Authentication

On first run, a browser window will open to sign in to [Daydream](https://app.daydream.live):

1. **Create an account** at [daydream.live](https://daydream.live) if you don't have one. The free trial is 10 hours of video.
2. **Sign in** when the browser opens
3. The app will automatically create and save an API key to `~/.daydream/credentials`

You only need to sign in once — the API key is saved locally and reused on subsequent runs.

## Usage

1. **Start your NDI source** (VirtualDJ, Resolume, OBS, or any NDI-capable app)
2. **Run the bridge** with `python app.py`
3. **Open the control panel** in your browser (opens automatically)
4. **Select your NDI source** from the dropdown
5. **Click "Start Stream"** to begin AI transformation
6. **Adjust parameters** in real-time using the sliders

## Controls

| Parameter | Description |
|-----------|-------------|
| **Prompt** | Text description of desired visual style |
| **Negative Prompt** | What to avoid in generation |
| **Denoise (Delta)** | How much AI transformation to apply |
| **Depth** | Preserve depth/3D structure |
| **Canny** | Preserve edges/outlines |
| **Tile** | Preserve texture patterns |
| **Guidance** | How closely to follow the prompt |

## NDI Sources

The bridge automatically scans for NDI sources on your network. Common sources include:

- **VirtualDJ** - Enable NDI output in VirtualDJ's broadcast settings
- **OBS Studio** - Use the NDI plugin
- **Any NDI-capable application**

## Backend Options

The bridge supports two backends:

### 1. Daydream Cloud (Default)
Uses the Daydream cloud API for processing. Easy to set up, just sign in and go.
- 10 hours free trial
- No GPU required
- StreamDiffusion v1 models

### 2. Scope (Self-Hosted or RunPod)
Use [Daydream Scope](https://github.com/daydreamlive/scope) for more models and no cloud costs.

**Features:**
- StreamDiffusionV2, LongLive, Krea Realtime Video, and more
- LoRA support for custom styles
- Run locally or on RunPod

**Using Scope with this bridge:**

1. **Start Scope** (locally or on RunPod)
   - Local: `uv run daydream-scope` → `http://localhost:8000`
   - RunPod: Use the [RunPod template](https://github.com/daydreamlive/scope#runpod) → get your proxy URL

2. **In the bridge control panel:**
   - Switch to **"Scope (Self-hosted)"** tab
   - Paste your Scope URL (e.g., `https://xxx-8000.proxy.runpod.net`)
   - Click **Test Connection** to verify
   - Select NDI source and start streaming

**RunPod setup:**
1. Deploy the [Scope RunPod template](https://runpod.io/console/deploy?template=xxx)
2. Set `HF_TOKEN` environment variable for TURN servers (required for WebRTC through firewalls)
3. Wait for deployment, get your proxy URL from RunPod
4. Paste the URL in the bridge and stream!

**GPU requirements for self-hosting:**
- Minimum: RTX 3090/4090 (24GB VRAM)
- For Krea Realtime Video: RTX 5090 or better (32GB+ VRAM)

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Credits

- [Daydream](https://daydream.live) - Real-time AI video generation API
- [Daydream Scope](https://github.com/daydreamlive/scope) - Self-hosted AI video generation
- [NDI](https://ndi.video) - Network Device Interface
