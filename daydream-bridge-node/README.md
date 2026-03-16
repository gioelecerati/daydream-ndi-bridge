# Daydream Bridge - Node.js

Node.js port of the Daydream Bridge - Captures video from any NDI source and streams to Daydream AI.

## Requirements

- Node.js 18.0.0 or higher
- NDI Tools (optional, for NDI input support)

## Installation

```bash
cd daydream-bridge-node
npm install
```

## Usage

### Start with Web UI (default)

```bash
npm start
```

This will:
1. Start the control panel server
2. Open the control panel in your default browser
3. Wait for you to configure and start streaming via the web UI

### Start with CLI interface

```bash
npm start -- --cli
```

### Start without opening browser

```bash
npm start -- --no-browser
```

## Features

- **Web Control Panel**: Modern UI to configure streaming parameters
- **Daydream Cloud**: Stream to Daydream's cloud AI service
- **Scope Support**: Connect to self-hosted Scope instances (local or RunPod)
- **Multiple Input Sources**:
  - Test pattern (animated gradient)
  - NDI sources (requires NDI Tools)
- **Real-time Parameter Updates**: Change prompts, denoising, guidance, and ControlNet settings on-the-fly

## Architecture

```
src/
├── index.js              # Main entry point
├── api/
│   ├── daydreamApi.js   # Daydream Cloud API client
│   └── scopeClient.js   # Scope WebRTC client
├── ndi/
│   └── ndiClient.js     # NDI client (abstraction layer)
├── server/
│   └── webServer.js     # Express + WebSocket server
└── ui/
    └── templates.js     # HTML templates for control panel and relay
```

## NDI Support

NDI support uses `koffi` (a modern FFI library) to interface directly with the NDI native library - exactly like the Python version uses ctypes.

### Requirements for NDI

1. **Install NDI Tools/SDK**:
   - **macOS**: Install "NDI SDK for Apple" from https://ndi.video/tools/
   - **Windows**: Install "NDI Tools" from https://ndi.video/tools/
   - **Linux**: Install the NDI SDK and ensure `libndi.so` is in your library path

2. **Install npm dependencies**:
   ```bash
   npm install
   ```

   > Note: `koffi` includes prebuilt binaries for most platforms, so native compilation is usually not needed.

### Library Paths

The client looks for the NDI library in these locations:

**macOS:**
- `/Library/NDI SDK for Apple/lib/macOS/libndi.dylib`
- `/Library/NDI SDK for Apple/lib/x64/libndi.dylib`
- `/usr/local/lib/libndi.dylib`

**Windows:**
- `C:\Program Files\NDI\NDI 5 Runtime\v5\Processing.NDI.Lib.x64.dll`
- System PATH

**Linux:**
- `/usr/lib/libndi.so`
- `/usr/local/lib/libndi.so`

### Troubleshooting

If you see "NDI library not found":
1. Verify NDI SDK is installed
2. Check the library exists at the expected path
3. On Linux, you may need to set `LD_LIBRARY_PATH`

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Control panel |
| `/relay` | GET | WebRTC relay page for OBS/streaming |
| `/api/status` | GET | Get current streaming status |
| `/api/sources` | GET | List available NDI sources |
| `/api/stream/start` | POST | Start streaming |
| `/api/stream/update` | POST | Update stream parameters |
| `/api/stream/stop` | POST | Stop streaming |
| `/api/scope/test` | POST | Test Scope connection |
| `/api/scope/pipeline/status` | POST | Get Scope pipeline status |
| `/api/scope/pipeline/load` | POST | Load Scope pipeline |
| `/ws` | WebSocket | Frame streaming |

## Configuration

Stream parameters can be configured via the web UI or programmatically:

```javascript
import { StreamConfig } from './api/daydreamApi.js';

const config = new StreamConfig({
  modelId: 'stabilityai/sdxl-turbo',
  prompt: 'anime style, vibrant colors, detailed',
  negativePrompt: 'blurry, low quality, flat',
  guidanceScale: 1.5,
  delta: 0.7,
  depthScale: 0.45,
  cannyScale: 0.0,
  tileScale: 0.21,
});
```

## License

MIT

