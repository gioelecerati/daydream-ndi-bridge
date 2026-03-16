#!/usr/bin/env node

/**
 * Daydream Bridge - Node.js
 * Captures video from any NDI source and streams to Daydream AI
 *
 * Usage:
 *    node src/index.js
 *    node src/index.js --cli
 *    node src/index.js --no-browser
 */

import http from 'http';
import readline from 'readline';
import open from 'open';
import sharp from 'sharp';

import { DaydreamAPI, StreamConfig, StreamInfo } from './api/daydreamApi.js';
import { DaydreamServer, findFreePort } from './server/webServer.js';

// Import NDI with error handling (ffi-napi may not be installed)
let NDIClient, NDIReceiver, ndiClient, NDI_AVAILABLE;
try {
  const ndiModule = await import('./ndi/ndiClient.js');
  NDIClient = ndiModule.NDIClient;
  NDIReceiver = ndiModule.NDIReceiver;
  ndiClient = ndiModule.ndiClient;
  NDI_AVAILABLE = ndiModule.NDI_AVAILABLE;
} catch (e) {
  console.log('⚠ NDI module failed to load:', e.message);
  console.log('  Install dependencies with: npm install');
  NDI_AVAILABLE = false;
  ndiClient = null;
}

/**
 * Main application class
 */
class DaydreamBridge {
  constructor() {
    this.api = new DaydreamAPI();
    this.config = new StreamConfig();
    this.stream = null;

    // Server ports
    this.httpPort = null;
    this.sdpPort = null;
    this.authPort = null;

    // Servers
    this.server = null;
    this.sdpServer = null;
    this.authServer = null;

    // State
    this.running = false;
    this.streaming = false;
    this.frameCount = 0;
    this.captureMode = 'test';

    // NDI
    this.ndiReceiver = (NDI_AVAILABLE && ndiClient && NDIReceiver) ? new NDIReceiver(ndiClient) : null;
    this.ndiSources = [];
  }

  async start(openBrowser = true, useCli = false) {
    console.log('\n' + '='.repeat(50));
    console.log('  Daydream Bridge - Node.js');
    console.log('='.repeat(50));

    // Check login
    if (!this.api.isLoggedIn) {
      console.log('\n⚠ Not logged in to Daydream');
      await this._startLoginFlow();
      return;
    }

    console.log('\n✓ Logged in to Daydream');

    // Assign ports
    this.httpPort = await findFreePort();
    this.sdpPort = await findFreePort();
    this.authPort = await findFreePort();

    // Start servers
    await this._startServers();

    // Scan for NDI sources
    if (NDI_AVAILABLE) {
      await this._scanNdiSources();
    }

    // Open control panel in browser
    if (openBrowser) {
      console.log('\n🌐 Opening control panel in browser...');
      await open(`http://localhost:${this.httpPort}`);
    }

    // Show menu or keep running
    if (useCli) {
      this._showMenu();
    } else {
      this._runHeadless();
    }
  }

  async _startLoginFlow() {
    console.log('\nStarting login flow...');

    const authState = this.api.createAuthState();
    this.authPort = await findFreePort();

    return new Promise((resolve) => {
      this.authServer = http.createServer((req, res) => {
        const url = new URL(req.url, `http://localhost:${this.authPort}`);
        const token = url.searchParams.get('token');
        const state = url.searchParams.get('state');

        if (!token) {
          res.writeHead(400);
          res.end('No token received');
          return;
        }

        if (!this.api.consumeAuthState(state)) {
          res.writeHead(400);
          res.end('Invalid state');
          return;
        }

        this.api
          .createApiKeyFromJwt(token)
          .then(() => {
            res.writeHead(302, { Location: 'https://app.daydream.live/sign-in/local/success' });
            res.end();
            console.log('\n✓ Login successful!');

            // Close auth server and restart
            this.authServer.close();
            setTimeout(() => this.start(), 1000);
            resolve();
          })
          .catch((e) => {
            res.writeHead(500);
            res.end(`Error: ${e.message}`);
          });
      });

      this.authServer.listen(this.authPort, '127.0.0.1', async () => {
        const authUrl = `https://app.daydream.live/sign-in/local?port=${this.authPort}&state=${authState}`;
        console.log('\nOpening browser for login...');
        await open(authUrl);

        console.log('\nWaiting for login... (Press Ctrl+C to cancel)');
      });
    });
  }

  async _startServers() {
    console.log('\nStarting servers...');

    this.server = new DaydreamServer(this.httpPort, this.api, this.sdpPort);
    this.server.bridge = this;
    await this.server.start();

    this.sdpServer = new DaydreamServer(this.sdpPort, this.api, this.sdpPort);
    this.sdpServer.bridge = this;
    await this.sdpServer.start();

    console.log(`  Control Panel: http://localhost:${this.httpPort}`);
    console.log(`  Relay page: http://localhost:${this.httpPort}/relay`);
  }

  async _scanNdiSources() {
    if (!this.ndiReceiver) {
      return;
    }

    console.log('\nScanning for NDI sources...');
    this.ndiSources = await this.ndiReceiver.findSources(3000);

    if (this.ndiSources.length > 0) {
      console.log(`Found ${this.ndiSources.length} source(s):`);
      for (let i = 0; i < this.ndiSources.length; i++) {
        console.log(`  ${i + 1}. ${this.ndiSources[i].name}`);
      }
    } else {
      console.log('No NDI sources found');
    }
  }

  _runHeadless() {
    console.log('\n' + '-'.repeat(50));
    console.log('Control panel is running at:');
    console.log(`  → http://localhost:${this.httpPort}`);
    console.log('-'.repeat(50));
    console.log('\nPress Ctrl+C to quit\n');

    this.running = true;

    process.on('SIGINT', () => {
      console.log('\nShutting down...');
      this._stopStreaming();
      if (NDI_AVAILABLE && ndiClient) {
        ndiClient.close();
      }
      console.log('Goodbye!');
      process.exit(0);
    });
  }

  _showMenu() {
    console.log('\n' + '-'.repeat(50));
    console.log('Commands:');
    console.log('  1. Start streaming (test pattern)');
    if (NDI_AVAILABLE) {
      console.log('  2. Start streaming from NDI');
      console.log('  3. Rescan NDI sources');
    }
    console.log('  p. Configure prompt');
    console.log('  o. Open output in browser');
    console.log('  s. Stop streaming');
    console.log('  q. Quit');
    console.log('-'.repeat(50));

    this.running = true;

    const rl = readline.createInterface({
      input: process.stdin,
      output: process.stdout,
    });

    const prompt = () => {
      rl.question('\n> ', async (cmd) => {
        cmd = cmd.trim().toLowerCase();

        if (cmd === '1') {
          this._startStreaming('test');
        } else if (cmd === '2' && NDI_AVAILABLE) {
          await this._selectNdiAndStream(rl);
        } else if (cmd === '3' && NDI_AVAILABLE) {
          await this._scanNdiSources();
        } else if (cmd === 'p') {
          await this._configurePrompt(rl);
        } else if (cmd === 'o') {
          await open(`http://localhost:${this.httpPort}`);
        } else if (cmd === 's') {
          this._stopStreaming();
        } else if (cmd === 'q') {
          this._stopStreaming();
          this.running = false;
          if (NDI_AVAILABLE && ndiClient) {
            ndiClient.close();
          }
          console.log('\nGoodbye!');
          rl.close();
          process.exit(0);
          return;
        } else {
          console.log('Unknown command');
        }

        if (this.running) {
          prompt();
        }
      });
    };

    prompt();
  }

  async _selectNdiAndStream(rl) {
    if (this.ndiSources.length === 0) {
      console.log('\nNo NDI sources found. Rescanning...');
      await this._scanNdiSources();
      if (this.ndiSources.length === 0) {
        return;
      }
    }

    console.log('\n' + '-'.repeat(50));
    console.log('Select NDI source:');
    console.log('-'.repeat(50));

    for (let i = 0; i < this.ndiSources.length; i++) {
      console.log(`  ${i + 1}. ${this.ndiSources[i].name}`);
    }

    return new Promise((resolve) => {
      rl.question('\nEnter number (or 0 to cancel): ', (answer) => {
        const choice = parseInt(answer.trim(), 10);
        if (choice === 0 || isNaN(choice)) {
          resolve();
          return;
        }
        if (choice >= 1 && choice <= this.ndiSources.length) {
          const selected = this.ndiSources[choice - 1];
          if (this.ndiReceiver.connect(selected)) {
            this._startStreaming('ndi');
          }
        } else {
          console.log('Invalid selection');
        }
        resolve();
      });
    });
  }

  async _configurePrompt(rl) {
    console.log(`\nCurrent prompt: ${this.config.prompt}`);

    return new Promise((resolve) => {
      rl.question('New prompt (or Enter to keep): ', async (newPrompt) => {
        newPrompt = newPrompt.trim();
        if (newPrompt) {
          this.config.prompt = newPrompt;
          console.log('✓ Prompt updated');

          if (this.streaming && this.stream) {
            await this.api.updateStream(this.stream.id, this.config);
            console.log('✓ Stream parameters updated');
          }
        }
        resolve();
      });
    });
  }

  async _startStreaming(captureMode = 'test') {
    if (this.streaming) {
      console.log("Already streaming. Stop first with 's'");
      return;
    }

    console.log('\nCreating stream...');

    try {
      this.stream = await this.api.createStream(this.config);

      this.server.setStreamInfo(this.stream.id, this.stream.whipUrl);
      this.sdpServer.setStreamInfo(this.stream.id, this.stream.whipUrl);

      this.streaming = true;
      this.captureMode = captureMode;
      this.frameCount = 0;

      // Start frame loop
      this._frameLoop();

      console.log('\n✓ Streaming started!');
      console.log(`  Stream ID: ${this.stream.id}`);
      console.log(`  Capture: ${captureMode}`);
      console.log("  Press 'o' to open output in browser");
    } catch (e) {
      console.log(`✗ Failed to start stream: ${e.message}`);
    }
  }

  _startStreamingScope(scopeUrl, captureMode = 'ndi', pipelineId = 'streamdiffusionv2') {
    if (this.streaming) {
      console.log("Already streaming. Stop first with 's'");
      return;
    }

    console.log(`\nConnecting to Scope: ${scopeUrl}`);
    console.log(`  Pipeline: ${pipelineId}`);

    try {
      this.server.setScopeInfo(scopeUrl, pipelineId);
      this.sdpServer.setScopeInfo(scopeUrl, pipelineId);

      this.streaming = true;
      this.captureMode = captureMode;
      this.frameCount = 0;
      this.stream = null; // No Daydream stream for Scope mode

      // Start frame loop
      this._frameLoop();

      console.log('\n✓ Streaming to Scope started!');
      console.log(`  Scope URL: ${scopeUrl}`);
      console.log(`  Capture: ${captureMode}`);
      console.log("  Press 'o' to open output in browser");
    } catch (e) {
      console.log(`✗ Failed to start Scope stream: ${e.message}`);
    }
  }

  _stopStreaming() {
    if (!this.streaming) {
      return;
    }

    console.log('\nStopping stream...');
    this.streaming = false;

    if (this.ndiReceiver) {
      this.ndiReceiver.disconnect();
    }

    if (this.stream) {
      this.api.deleteStream(this.stream.id).catch(() => {});
      this.stream = null;
    }

    this.server.clearStreamInfo();
    this.sdpServer.clearStreamInfo();

    console.log('✓ Stream stopped');
  }

  async _frameLoop() {
    const fps = 30;
    const frameTime = 1000 / fps;
    let noFrameCount = 0;

    while (this.streaming) {
      const start = Date.now();

      try {
        let frame = null;

        // Get frame based on capture mode
        if (this.captureMode === 'ndi' && this.ndiReceiver) {
          frame = this.ndiReceiver.getFrame();
          
          // If no NDI frame, use test pattern as fallback
          if (!frame) {
            noFrameCount++;
            if (noFrameCount === 1 || noFrameCount % 100 === 0) {
              console.log('  ⚠ No NDI frame received, using test pattern');
            }
            frame = this._generateTestFrame();
          } else {
            if (noFrameCount > 0) {
              console.log('  ✓ NDI frames receiving');
              noFrameCount = 0;
            }
          }
        } else {
          frame = this._generateTestFrame();
        }

        if (frame) {
          // Resize to 512x512 preserving aspect ratio (letterbox)
          const resized = await this._resizeWithLetterbox(frame, 512, 512);

          // Convert to JPEG
          const jpegData = await this._frameToJpeg(resized);

          // Send to WebSocket clients
          this.server.broadcastFrame(jpegData);

          this.frameCount++;

          if (this.frameCount % 150 === 0) {
            console.log(`  📤 ${this.frameCount} frames sent`);
          }
        }
      } catch (e) {
        if (this.streaming) {
          console.log(`Frame error: ${e.message}`);
        }
      }

      const elapsed = Date.now() - start;
      const sleepTime = frameTime - elapsed;
      if (sleepTime > 0) {
        await new Promise((resolve) => setTimeout(resolve, sleepTime));
      }
    }
  }

  /**
   * Generate animated test pattern
   * @returns {Object} - Object with width, height, and raw RGB buffer
   */
  _generateTestFrame() {
    const width = 512;
    const height = 512;
    const t = this.frameCount * 0.03;

    // Create RGB buffer
    const buffer = Buffer.alloc(width * height * 3);

    for (let y = 0; y < height; y++) {
      for (let x = 0; x < width; x++) {
        const idx = (y * width + x) * 3;

        const r = Math.floor(127 + 127 * Math.sin(x * 0.02 + t));
        const g = Math.floor(127 + 127 * Math.sin(y * 0.02 + t * 1.3));
        const b = Math.floor(127 + 127 * Math.sin((x + y) * 0.01 + t * 0.7));

        buffer[idx] = r;
        buffer[idx + 1] = g;
        buffer[idx + 2] = b;
      }
    }

    return { width, height, data: buffer, channels: 3 };
  }

  /**
   * Resize frame to target size while preserving aspect ratio (letterbox/pillarbox)
   */
  async _resizeWithLetterbox(frame, targetW, targetH) {
    const { width, height, data, channels } = frame;

    // If already correct size, return as-is
    if (width === targetW && height === targetH) {
      return frame;
    }

    try {
      // Use sharp to resize with fit: 'contain' (letterbox)
      const resized = await sharp(data, { raw: { width, height, channels } })
        .resize(targetW, targetH, {
          fit: 'contain',
          background: { r: 0, g: 0, b: 0 },
        })
        .raw()
        .toBuffer();

      return { width: targetW, height: targetH, data: resized, channels: 3 };
    } catch (e) {
      // If sharp fails, return original
      return frame;
    }
  }

  /**
   * Convert frame to JPEG
   */
  async _frameToJpeg(frame, quality = 70) {
    const { width, height, data, channels } = frame;

    return sharp(data, { raw: { width, height, channels } })
      .jpeg({ quality })
      .toBuffer();
  }
}

// Parse command line arguments
const args = process.argv.slice(2);
const useCli = args.includes('--cli');
const noBrowser = args.includes('--no-browser');

// Start the bridge
const bridge = new DaydreamBridge();
bridge.start(!noBrowser, useCli);

