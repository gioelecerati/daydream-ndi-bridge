# Daydream StreamDiffusionV1 NDI Bridge

Real-time AI video transformation bridge using the [Daydream API](https://docs.daydream.live). Capture video via NDI and transform it with AI in real-time.

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

1. **Create an account** at [app.daydream.live](https://app.daydream.live) if you don't have one. The free trial is 10 hours of video.
2. **Sign in** when the browser opens
3. The app will automatically create and save an API key to `~/.daydream/credentials`

You only need to sign in once — the API key is saved locally and reused on subsequent runs.

## Usage

1. **Start your NDI source** (VirtualDJ, OBS, or any NDI-capable app)
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

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Credits

- [Daydream](https://daydream.live) - Real-time AI video generation API
- [NDI](https://ndi.video) - Network Device Interface
