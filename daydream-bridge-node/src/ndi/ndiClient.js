/**
 * Pure Node.js NDI client using koffi
 * Directly interfaces with the NDI SDK library (mirrors Python ctypes implementation)
 */

import { platform } from 'os';
import { existsSync } from 'fs';

// Lazy load koffi (may not be installed)
let koffi;
let koffiAvailable = false;

try {
  koffi = (await import('koffi')).default;
  koffiAvailable = true;
} catch (e) {
  console.log('⚠ koffi not available. Run: npm install');
  console.log(`  Error: ${e.message}`);
}

// NDI library paths by platform
function getNdiLibraryPath() {
  const system = platform();

  if (system === 'darwin') {
    // macOS - look in NDI SDK locations
    const paths = [
      '/Library/NDI SDK for Apple/lib/macOS/libndi.dylib',
      '/Library/NDI SDK for Apple/lib/x64/libndi.4.dylib',
      '/Library/NDI SDK for Apple/lib/x64/libndi.dylib',
      '/usr/local/lib/libndi.dylib',
      '/usr/local/lib/libndi.5.dylib',
    ];
    for (const p of paths) {
      if (existsSync(p)) return p;
    }
  } else if (system === 'win32') {
    // Windows
    const paths = [
      'C:\\Program Files\\NDI\\NDI 5 Runtime\\v5\\Processing.NDI.Lib.x64.dll',
      'Processing.NDI.Lib.x64.dll',
    ];
    for (const p of paths) {
      if (existsSync(p)) return p;
    }
    return 'Processing.NDI.Lib.x64'; // Let system find it
  } else {
    // Linux
    const paths = ['/usr/lib/libndi.so', '/usr/local/lib/libndi.so', '/usr/lib/x86_64-linux-gnu/libndi.so.5'];
    for (const p of paths) {
      if (existsSync(p)) return p;
    }
  }

  return null;
}

// Color format constants
const NDIlib_recv_color_format_BGRX_BGRA = 0;
const NDIlib_recv_color_format_UYVY_BGRA = 1;
const NDIlib_recv_color_format_RGBX_RGBA = 2;
const NDIlib_recv_color_format_UYVY_RGBA = 3;
const NDIlib_recv_color_format_fastest = 100;
const NDIlib_recv_color_format_best = 101;

// Bandwidth constants
const NDIlib_recv_bandwidth_metadata_only = -10;
const NDIlib_recv_bandwidth_audio_only = 10;
const NDIlib_recv_bandwidth_lowest = 0;
const NDIlib_recv_bandwidth_highest = 100;

// Frame type constants
const NDIlib_frame_type_none = 0;
const NDIlib_frame_type_video = 1;
const NDIlib_frame_type_audio = 2;
const NDIlib_frame_type_metadata = 3;
const NDIlib_frame_type_error = 4;
const NDIlib_frame_type_status_change = 100;

// FourCC constants (as integers)
const NDIlib_FourCC_type_UYVY = 0x59565955;
const NDIlib_FourCC_type_BGRA = 0x41524742;
const NDIlib_FourCC_type_BGRX = 0x58524742;
const NDIlib_FourCC_type_RGBA = 0x41424752;
const NDIlib_FourCC_type_RGBX = 0x58424752;

/**
 * Represents a discovered NDI source
 */
export class NDISource {
  constructor(name, url = '') {
    this.name = name;
    this.url = url;
  }
}

/**
 * NDI Client - interfaces with the NDI SDK via koffi
 */
export class NDIClient {
  constructor() {
    this.lib = null;
    this.findInstance = null;
    this.recvInstance = null;
    this.currentSource = null;
    this.ndiAvailable = false;
    this.types = {};
    this.funcs = {};

    this._initialize();
  }

  _initialize() {
    if (!koffiAvailable) {
      console.log('⚠ NDI requires koffi. Install with: npm install');
      return;
    }

    const libPath = getNdiLibraryPath();
    if (!libPath) {
      console.log('⚠ NDI library not found. Please install NDI Tools from https://ndi.video/tools/');
      console.log('  On macOS: Install "NDI SDK for Apple" from the NDI website.');
      return;
    }

    try {
      this._defineTypes();
      this._loadLibrary(libPath);

      // Initialize NDI
      if (!this.funcs.NDIlib_initialize()) {
        throw new Error('Failed to initialize NDI library');
      }

      this.ndiAvailable = true;
      console.log('✓ NDI initialized');
    } catch (e) {
      console.log(`⚠ NDI initialization failed: ${e.message}`);
      this.ndiAvailable = false;
    }
  }

  _defineTypes() {
    // NDIlib_source_t
    this.types.NDIlib_source_t = koffi.struct('NDIlib_source_t', {
      p_ndi_name: 'const char *',
      p_url_address: 'const char *',
    });

    // NDIlib_find_create_t
    this.types.NDIlib_find_create_t = koffi.struct('NDIlib_find_create_t', {
      show_local_sources: 'bool',
      p_groups: 'const char *',
      p_extra_ips: 'const char *',
    });

    // NDIlib_recv_create_v3_t
    this.types.NDIlib_recv_create_v3_t = koffi.struct('NDIlib_recv_create_v3_t', {
      source_to_connect_to: this.types.NDIlib_source_t,
      color_format: 'int',
      bandwidth: 'int',
      allow_video_fields: 'bool',
      p_ndi_recv_name: 'const char *',
    });

    // NDIlib_video_frame_v2_t
    this.types.NDIlib_video_frame_v2_t = koffi.struct('NDIlib_video_frame_v2_t', {
      xres: 'int',
      yres: 'int',
      FourCC: 'int',
      frame_rate_N: 'int',
      frame_rate_D: 'int',
      picture_aspect_ratio: 'float',
      frame_format_type: 'int',
      timecode: 'int64',
      p_data: 'uint8 *',
      line_stride_in_bytes: 'int',
      p_metadata: 'const char *',
      timestamp: 'int64',
    });

    // NDIlib_audio_frame_v2_t
    this.types.NDIlib_audio_frame_v2_t = koffi.struct('NDIlib_audio_frame_v2_t', {
      sample_rate: 'int',
      no_channels: 'int',
      no_samples: 'int',
      timecode: 'int64',
      p_data: 'float *',
      channel_stride_in_bytes: 'int',
      p_metadata: 'const char *',
      timestamp: 'int64',
    });

    // NDIlib_metadata_frame_t
    this.types.NDIlib_metadata_frame_t = koffi.struct('NDIlib_metadata_frame_t', {
      length: 'int',
      timecode: 'int64',
      p_data: 'char *',
    });
  }

  _loadLibrary(libPath) {
    this.lib = koffi.load(libPath);

    // Initialize/destroy
    this.funcs.NDIlib_initialize = this.lib.func('bool NDIlib_initialize()');
    this.funcs.NDIlib_destroy = this.lib.func('void NDIlib_destroy()');

    // Find sources
    this.funcs.NDIlib_find_create_v2 = this.lib.func(
      'void* NDIlib_find_create_v2(const NDIlib_find_create_t *p_create_settings)'
    );
    this.funcs.NDIlib_find_destroy = this.lib.func('void NDIlib_find_destroy(void *p_instance)');
    this.funcs.NDIlib_find_wait_for_sources = this.lib.func(
      'bool NDIlib_find_wait_for_sources(void *p_instance, uint32 timeout_in_ms)'
    );
    this.funcs.NDIlib_find_get_current_sources = this.lib.func(
      'const NDIlib_source_t* NDIlib_find_get_current_sources(void *p_instance, _Out_ uint32 *p_no_sources)'
    );

    // Receiver
    this.funcs.NDIlib_recv_create_v3 = this.lib.func(
      'void* NDIlib_recv_create_v3(const NDIlib_recv_create_v3_t *p_create_settings)'
    );
    this.funcs.NDIlib_recv_destroy = this.lib.func('void NDIlib_recv_destroy(void *p_instance)');
    this.funcs.NDIlib_recv_capture_v2 = this.lib.func(
      'int NDIlib_recv_capture_v2(void *p_instance, _Out_ NDIlib_video_frame_v2_t *p_video_data, _Out_ NDIlib_audio_frame_v2_t *p_audio_data, _Out_ NDIlib_metadata_frame_t *p_metadata, uint32 timeout_in_ms)'
    );
    this.funcs.NDIlib_recv_free_video_v2 = this.lib.func(
      'void NDIlib_recv_free_video_v2(void *p_instance, const NDIlib_video_frame_v2_t *p_video_data)'
    );
  }

  /**
   * Find available NDI sources on the network
   * @param {number} timeoutMs - Timeout in milliseconds
   * @returns {NDISource[]}
   */
  findSources(timeoutMs = 5000) {
    if (!this.ndiAvailable) {
      return [];
    }

    // Create find instance if needed
    if (!this.findInstance) {
      const createSettings = {
        show_local_sources: true,
        p_groups: null,
        p_extra_ips: null,
      };

      this.findInstance = this.funcs.NDIlib_find_create_v2(createSettings);
      if (!this.findInstance) {
        throw new Error('Failed to create NDI find instance');
      }
    }

    // Wait for sources
    this.funcs.NDIlib_find_wait_for_sources(this.findInstance, timeoutMs);

    // Get sources
    const numSourcesOut = [0];
    const sourcesPtr = this.funcs.NDIlib_find_get_current_sources(this.findInstance, numSourcesOut);
    const numSources = numSourcesOut[0];

    if (numSources === 0 || !sourcesPtr) {
      return [];
    }

    // Decode the sources array
    const sources = [];
    const sourceArray = koffi.decode(sourcesPtr, koffi.array(this.types.NDIlib_source_t, numSources));

    for (let i = 0; i < numSources; i++) {
      const source = sourceArray[i];
      const name = source.p_ndi_name || '';
      const url = source.p_url_address || '';
      sources.push(new NDISource(name, url));
    }

    return sources;
  }

  /**
   * Connect to an NDI source
   * @param {NDISource} source
   * @returns {boolean}
   */
  connect(source) {
    if (!this.ndiAvailable) {
      return false;
    }

    // Disconnect existing
    if (this.recvInstance) {
      this.funcs.NDIlib_recv_destroy(this.recvInstance);
      this.recvInstance = null;
    }

    // Create receiver
    const recvCreate = {
      source_to_connect_to: {
        p_ndi_name: source.name,
        p_url_address: source.url || null,
      },
      color_format: NDIlib_recv_color_format_RGBX_RGBA,
      bandwidth: NDIlib_recv_bandwidth_highest,
      allow_video_fields: false,
      p_ndi_recv_name: 'Daydream Bridge Node',
    };

    this.recvInstance = this.funcs.NDIlib_recv_create_v3(recvCreate);
    if (!this.recvInstance) {
      return false;
    }

    this.currentSource = source;
    return true;
  }

  /**
   * Capture a video frame from the connected source.
   * Returns RGBA data as { width, height, data: Buffer, channels: 3 } or null
   * @param {number} timeoutMs
   * @returns {Object|null}
   */
  captureVideoFrame(timeoutMs = 100) {
    if (!this.ndiAvailable || !this.recvInstance) {
      return null;
    }

    // Create output structures
    const videoFrame = {};
    const audioFrame = {};
    const metadataFrame = {};

    const frameType = this.funcs.NDIlib_recv_capture_v2(
      this.recvInstance,
      videoFrame,
      audioFrame,
      metadataFrame,
      timeoutMs
    );

    if (frameType !== NDIlib_frame_type_video) {
      return null;
    }

    try {
      const width = videoFrame.xres;
      const height = videoFrame.yres;
      const stride = videoFrame.line_stride_in_bytes;
      const fourcc = videoFrame.FourCC;
      const dataPtr = videoFrame.p_data;

      if (!dataPtr || width <= 0 || height <= 0) {
        return null;
      }

      // Calculate bytes per pixel based on FourCC
      let bpp = 4;
      if (fourcc === NDIlib_FourCC_type_UYVY) {
        bpp = 2;
      }

      // Read frame data from native memory
      const bufferSize = height * stride;
      const rawData = koffi.decode(dataPtr, koffi.array('uint8', bufferSize));
      const frameData = Buffer.from(rawData);

      // Handle stride/padding if necessary - copy to contiguous buffer
      let pixelData;
      if (stride === width * bpp) {
        pixelData = frameData;
      } else {
        // Row by row copy
        pixelData = Buffer.alloc(height * width * bpp);
        for (let y = 0; y < height; y++) {
          frameData.copy(pixelData, y * width * bpp, y * stride, y * stride + width * bpp);
        }
      }

      // Convert BGRA to RGBA if needed
      if (fourcc === NDIlib_FourCC_type_BGRA || fourcc === NDIlib_FourCC_type_BGRX) {
        for (let i = 0; i < pixelData.length; i += 4) {
          const b = pixelData[i];
          const r = pixelData[i + 2];
          pixelData[i] = r;
          pixelData[i + 2] = b;
        }
      }

      // Convert RGBA to RGB (strip alpha)
      const rgbData = Buffer.alloc(width * height * 3);
      for (let i = 0, j = 0; i < width * height * 4; i += 4, j += 3) {
        rgbData[j] = pixelData[i];
        rgbData[j + 1] = pixelData[i + 1];
        rgbData[j + 2] = pixelData[i + 2];
      }

      return { width, height, data: rgbData, channels: 3 };
    } finally {
      // Free the video frame
      this.funcs.NDIlib_recv_free_video_v2(this.recvInstance, videoFrame);
    }
  }

  /**
   * Disconnect from the current source
   */
  disconnect() {
    if (this.recvInstance) {
      this.funcs.NDIlib_recv_destroy(this.recvInstance);
      this.recvInstance = null;
    }
    this.currentSource = null;
  }

  /**
   * Clean up NDI resources
   */
  close() {
    this.disconnect();

    if (this.findInstance) {
      this.funcs.NDIlib_find_destroy(this.findInstance);
      this.findInstance = null;
    }

    if (this.funcs.NDIlib_destroy) {
      this.funcs.NDIlib_destroy();
    }
  }
}

/**
 * NDI Receiver wrapper for use in the bridge
 */
export class NDIReceiver {
  constructor(client) {
    this.client = client;
    this.source = null;
    this.running = false;
  }

  /**
   * Find available NDI sources on the network
   */
  async findSources(timeoutMs = 5000) {
    if (!this.client) {
      return [];
    }

    const sources = [];
    try {
      const ndiSources = this.client.findSources(timeoutMs);

      for (const src of ndiSources) {
        sources.push({
          name: src.name,
          url: src.url,
          source: src,
        });
      }
    } catch (e) {
      console.log(`Error finding NDI sources: ${e.message}`);
    }

    return sources;
  }

  /**
   * Connect to an NDI source
   */
  connect(source) {
    if (!this.client) {
      return false;
    }

    try {
      const ndiSource = source.source;

      if (this.client.connect(ndiSource)) {
        this.source = ndiSource;
        this.running = true;
        console.log(`✓ Connected to NDI source: ${source.name}`);
        return true;
      }
    } catch (e) {
      console.log(`Error connecting to NDI: ${e.message}`);
    }

    return false;
  }

  /**
   * Get a video frame from the NDI source
   * @returns {Object|null} - { width, height, data: Buffer, channels } or null
   */
  getFrame(timeoutMs = 100) {
    if (!this.client || !this.running) {
      return null;
    }

    try {
      const frame = this.client.captureVideoFrame(timeoutMs);
      return frame; // Already RGB from captureVideoFrame
    } catch (e) {
      if (this.running) {
        console.log(`NDI frame error: ${e.message}`);
      }
    }

    return null;
  }

  /**
   * Disconnect from NDI source
   */
  disconnect() {
    this.running = false;

    if (this.client) {
      this.client.disconnect();
    }

    this.source = null;
  }
}

// Initialize NDI client
let ndiClient = null;
let NDI_AVAILABLE = false;

try {
  ndiClient = new NDIClient();
  NDI_AVAILABLE = ndiClient.ndiAvailable;
  if (NDI_AVAILABLE) {
    console.log('✓ NDI client ready');
  }
} catch (e) {
  console.log(`⚠ NDI not available: ${e.message}`);
}

export { ndiClient, NDI_AVAILABLE };
export default NDIClient;
