/**
 * Local Web Server for Daydream Bridge
 * Handles:
 * - Serving the WebRTC relay page
 * - WebSocket for sending video frames
 * - WHIP/WHEP SDP proxy
 * - Scope proxy
 */

import express from 'express';
import { WebSocketServer } from 'ws';
import http from 'http';
import crypto from 'crypto';
import { ScopeClient, testScopeConnection } from '../api/scopeClient.js';
import { CONTROL_PANEL_HTML, RELAY_HTML } from '../ui/templates.js';

/**
 * Find an available port
 */
export function findFreePort() {
  return new Promise((resolve) => {
    const server = http.createServer();
    server.listen(0, '127.0.0.1', () => {
      const port = server.address().port;
      server.close(() => resolve(port));
    });
  });
}

/**
 * Daydream Server
 */
export class DaydreamServer {
  constructor(port, api, sdpPort) {
    this.port = port;
    this.api = api;
    this.sdpPort = sdpPort;

    // Reference to bridge (set after creation)
    this.bridge = null;

    // Stream state
    this.state = 'IDLE';
    this.streamId = null;
    this.whipUrl = null;
    this.whepUrl = null;

    // Backend mode: 'daydream' or 'scope'
    this.backendMode = 'daydream';
    this.scopeUrl = null;
    this.scopePipelineId = null;

    // Request tracking
    this.whipRequests = new Map();
    this.whepRequests = new Map();
    this.scopeRequests = new Map();

    // WebSocket clients
    this.wsClients = new Set();

    // Relay HTML cache
    this._relayHtmlCache = null;

    // Create Express app
    this.app = express();
    this.app.use(express.json());
    this.app.use(express.text({ type: 'application/sdp' }));

    // Setup routes
    this._setupRoutes();

    // Create HTTP server
    this.server = http.createServer(this.app);

    // Create WebSocket server
    this.wss = new WebSocketServer({ server: this.server, path: '/ws' });
    this._setupWebSocket();
  }

  _setupRoutes() {
    const app = this.app;

    // CORS middleware
    app.use((req, res, next) => {
      res.header('Access-Control-Allow-Origin', '*');
      res.header('Access-Control-Allow-Methods', 'GET, POST, PATCH, DELETE, OPTIONS');
      res.header('Access-Control-Allow-Headers', 'Content-Type');
      if (req.method === 'OPTIONS') {
        return res.sendStatus(204);
      }
      next();
    });

    // Control panel
    app.get('/', (req, res) => {
      res.type('html').send(CONTROL_PANEL_HTML);
    });

    // Relay page
    app.get('/relay', (req, res) => {
      res.type('html').send(this.getRelayHtml());
    });
    app.get('/relay.html', (req, res) => {
      res.type('html').send(this.getRelayHtml());
    });

    // Status endpoints
    app.get('/status', (req, res) => {
      res.json({
        state: this.state,
        stream_id: this.streamId,
        whip_url: this.whipUrl,
        whep_url: this.whepUrl,
        backend_mode: this.backendMode,
        scope_url: this.scopeUrl,
      });
    });

    app.get('/api/status', (req, res) => {
      res.json({
        connected: true,
        streaming: this.state === 'STREAMING',
        stream_id: this.streamId,
      });
    });

    // NDI sources
    app.get('/api/sources', (req, res) => {
      let sources = [];
      if (this.bridge?.ndiSources) {
        sources = this.bridge.ndiSources.map((s) => ({
          name: s.name,
          url: s.url || '',
        }));
      }
      res.json({ sources });
    });

    // Scope ICE servers
    app.get('/scope/ice-servers', async (req, res) => {
      let iceServers = [{ urls: ['stun:stun.l.google.com:19302'] }];

      if (this.scopeUrl) {
        try {
          const client = new ScopeClient(this.scopeUrl);
          const scopeIceServers = await client.getIceServers();
          if (scopeIceServers?.length) {
            iceServers = scopeIceServers;
            console.log(`✓ Got ${iceServers.length} ICE servers from Scope (includes TURN)`);
          }
        } catch (e) {
          console.log(`⚠ Could not get ICE servers from Scope: ${e.message}`);
        }
      }

      res.json({ iceServers });
    });

    // Stream control
    app.post('/api/stream/start', (req, res) => this._handleStreamStart(req, res));
    app.post('/api/stream/update', (req, res) => this._handleStreamUpdate(req, res));
    app.post('/api/stream/stop', (req, res) => this._handleStreamStop(req, res));

    // Scope endpoints
    app.post('/api/scope/test', (req, res) => this._handleScopeTest(req, res));
    app.post('/api/scope/pipeline/status', (req, res) => this._handleScopePipelineStatus(req, res));
    app.post('/api/scope/pipeline/load', (req, res) => this._handleScopePipelineLoad(req, res));

    // WHIP/WHEP proxy
    app.post('/whip', (req, res) => this._handleWhipProxy(req, res));
    app.get('/whip/result/:id', (req, res) => this._serveWhipResult(req, res));
    app.post('/whep', (req, res) => this._handleWhepProxy(req, res));
    app.get('/whep/result/:id', (req, res) => this._serveWhepResult(req, res));

    // Scope proxy
    app.post('/scope/offer', (req, res) => this._handleScopeOffer(req, res));
    app.get('/scope/result/:id', (req, res) => this._serveScopeResult(req, res));
    app.post('/scope/ice-candidate', (req, res) => this._handleScopeIceCandidate(req, res));
  }

  _setupWebSocket() {
    this.wss.on('connection', (ws) => {
      this.wsClients.add(ws);
      console.log(`WebSocket client connected (${this.wsClients.size} total)`);

      ws.on('close', () => {
        this.wsClients.delete(ws);
        console.log(`WebSocket client disconnected (${this.wsClients.size} total)`);
      });

      ws.on('error', () => {
        this.wsClients.delete(ws);
      });
    });
  }

  getRelayHtml() {
    if (!this._relayHtmlCache) {
      this._relayHtmlCache = RELAY_HTML.replace('{{SDP_PORT}}', String(this.sdpPort));
    }
    return this._relayHtmlCache;
  }

  /**
   * Send a JPEG frame to all connected WebSocket clients
   */
  broadcastFrame(jpegData) {
    if (this.wsClients.size === 0) return;

    const deadClients = [];
    for (const client of this.wsClients) {
      try {
        if (client.readyState === 1) {
          // OPEN
          client.send(jpegData);
        } else {
          deadClients.push(client);
        }
      } catch {
        deadClients.push(client);
      }
    }

    for (const client of deadClients) {
      this.wsClients.delete(client);
    }
  }

  /**
   * Update stream information (Daydream Cloud mode)
   */
  setStreamInfo(streamId, whipUrl) {
    this.streamId = streamId;
    this.whipUrl = whipUrl;
    this.backendMode = 'daydream';
    this.state = 'STREAMING';
  }

  /**
   * Update stream information (Scope mode)
   */
  setScopeInfo(scopeUrl, pipelineId = 'streamdiffusionv2') {
    this.scopeUrl = scopeUrl;
    this.scopePipelineId = pipelineId;
    this.backendMode = 'scope';
    this.streamId = 'scope-session';
    this.state = 'STREAMING';
  }

  /**
   * Clear stream information
   */
  clearStreamInfo() {
    this.streamId = null;
    this.whipUrl = null;
    this.whepUrl = null;
    this.scopeUrl = null;
    this.scopePipelineId = null;
    this.backendMode = 'daydream';
    this.state = 'IDLE';
  }

  // Route handlers
  async _handleStreamStart(req, res) {
    try {
      const params = req.body || {};

      if (!this.bridge) {
        throw new Error('Bridge not initialized');
      }

      // Check backend mode
      const backend = params.backend || 'daydream';
      const scopeUrl = params.scope_url || '';

      // Update config
      if (params.prompt) this.bridge.config.prompt = params.prompt;
      if (params.negative_prompt) this.bridge.config.negativePrompt = params.negative_prompt;
      if (params.model_id) this.bridge.config.modelId = params.model_id;
      if (params.delta !== undefined) this.bridge.config.delta = params.delta;
      if (params.depth_scale !== undefined) this.bridge.config.depthScale = params.depth_scale;
      if (params.canny_scale !== undefined) this.bridge.config.cannyScale = params.canny_scale;
      if (params.tile_scale !== undefined) this.bridge.config.tileScale = params.tile_scale;

      // Select NDI source
      const sourceIndex = params.source_index;
      if (sourceIndex !== undefined && this.bridge.ndiSources?.length) {
        if (sourceIndex >= 0 && sourceIndex < this.bridge.ndiSources.length) {
          const selected = this.bridge.ndiSources[sourceIndex];
          if (this.bridge.ndiReceiver) {
            this.bridge.ndiReceiver.connect(selected);
          }
        }
      }

      // Start streaming based on backend
      if (backend === 'scope' && scopeUrl) {
        const pipelineId = params.pipeline_id || 'streamdiffusionv2';
        this.bridge._startStreamingScope(scopeUrl, 'ndi', pipelineId);
      } else {
        this.bridge._startStreaming('ndi');
      }

      res.json({
        success: true,
        stream_id: this.bridge.stream?.id || 'scope-session',
        relay_url: '/relay',
        backend,
      });
    } catch (e) {
      console.error('Stream start error:', e);
      res.json({ success: false, error: e.message });
    }
  }

  async _handleStreamUpdate(req, res) {
    try {
      const params = req.body || {};

      if (!this.bridge) {
        throw new Error('Bridge not initialized');
      }

      // Update config
      if (params.prompt) this.bridge.config.prompt = params.prompt;
      if (params.negative_prompt) this.bridge.config.negativePrompt = params.negative_prompt;
      if (params.model_id) this.bridge.config.modelId = params.model_id;
      if (params.delta !== undefined) this.bridge.config.delta = params.delta;
      if (params.depth_scale !== undefined) this.bridge.config.depthScale = params.depth_scale;
      if (params.canny_scale !== undefined) this.bridge.config.cannyScale = params.canny_scale;
      if (params.tile_scale !== undefined) this.bridge.config.tileScale = params.tile_scale;

      console.log(
        `📝 Updating params: prompt='${this.bridge.config.prompt.slice(0, 30)}...', delta=${this.bridge.config.delta}`
      );

      // Update on Daydream
      if (this.bridge.streaming && this.bridge.stream) {
        const success = await this.bridge.api.updateStream(this.bridge.stream.id, this.bridge.config);
        if (!success) {
          throw new Error('API update failed');
        }
      } else {
        console.log('⚠ Not streaming, config saved for next stream');
      }

      res.json({ success: true });
    } catch (e) {
      console.log(`✗ Update error: ${e.message}`);
      res.json({ success: false, error: e.message });
    }
  }

  async _handleStreamStop(req, res) {
    try {
      if (this.bridge) {
        this.bridge._stopStreaming();
      }
      res.json({ success: true });
    } catch (e) {
      res.json({ success: false, error: e.message });
    }
  }

  async _handleScopeTest(req, res) {
    try {
      const scopeUrl = req.body?.url?.trim();

      if (!scopeUrl) {
        return res.json({ reachable: false, error: 'No URL provided' });
      }

      const result = await testScopeConnection(scopeUrl);
      res.json(result);
    } catch (e) {
      res.json({ reachable: false, error: e.message });
    }
  }

  async _handleScopePipelineStatus(req, res) {
    try {
      const scopeUrl = req.body?.url?.trim();

      if (!scopeUrl) {
        return res.json({ status: 'error', error: 'No URL provided' });
      }

      const client = new ScopeClient(scopeUrl);
      const response = await client.getPipelineStatus();
      console.log(`Pipeline status: ${JSON.stringify(response)}`);
      res.json(response);
    } catch (e) {
      console.log(`Pipeline status error: ${e.message}`);
      res.json({ status: 'error', error: e.message });
    }
  }

  async _handleScopePipelineLoad(req, res) {
    try {
      const scopeUrl = req.body?.url?.trim();
      const pipelineId = req.body?.pipeline_id || 'streamdiffusionv2';

      if (!scopeUrl) {
        return res.json({ success: false, error: 'No URL provided' });
      }

      const client = new ScopeClient(scopeUrl);
      const success = await client.loadPipeline(pipelineId);
      res.json({ success, pipeline_id: pipelineId });
    } catch (e) {
      res.json({ success: false, error: e.message });
    }
  }

  async _handleWhipProxy(req, res) {
    if (!this.whipUrl) {
      return res.status(400).send('No WHIP URL available');
    }

    const offerSdp = req.body;
    const requestId = crypto.randomBytes(8).toString('base64url');

    this.whipRequests.set(requestId, {
      status: 'pending',
      offer: offerSdp,
      answer: null,
      error: null,
    });

    // Process in background
    (async () => {
      try {
        const [answerSdp, headers] = await this.api.exchangeSdp(this.whipUrl, offerSdp, 10000);

        // Extract WHEP URL from response headers
        const playbackUrl = headers['livepeer-playback-url'];
        if (playbackUrl) {
          this.whepUrl = playbackUrl;
          console.log(`✓ Got WHEP URL: ${playbackUrl}`);
        }

        const reqData = this.whipRequests.get(requestId);
        if (reqData) {
          reqData.answer = answerSdp;
          reqData.status = 'ready';
        }
      } catch (e) {
        console.log(`WHIP proxy error: ${e.message}`);
        const reqData = this.whipRequests.get(requestId);
        if (reqData) {
          reqData.error = e.message;
          reqData.status = 'error';
        }
      }
    })();

    res.status(202).json({ id: requestId });
  }

  _serveWhipResult(req, res) {
    const requestId = req.params.id;
    const reqData = this.whipRequests.get(requestId);

    if (!reqData) {
      return res.status(404).send('Request not found');
    }

    if (reqData.status === 'pending') {
      return res.status(202).json({ status: 'pending' });
    }

    if (reqData.status === 'ready') {
      this.whipRequests.delete(requestId);
      return res.type('application/sdp').send(reqData.answer);
    }

    this.whipRequests.delete(requestId);
    return res.status(500).send(reqData.error || 'Unknown error');
  }

  async _handleWhepProxy(req, res) {
    if (!this.whepUrl) {
      return res.status(404).send('No WHEP URL available yet');
    }

    const offerSdp = req.body;
    const requestId = crypto.randomBytes(8).toString('base64url');

    this.whepRequests.set(requestId, {
      status: 'pending',
      offer: offerSdp,
      answer: null,
      error: null,
    });

    // Process in background
    (async () => {
      try {
        const [answerSdp] = await this.api.exchangeSdp(this.whepUrl, offerSdp, 5000);

        const reqData = this.whepRequests.get(requestId);
        if (reqData) {
          reqData.answer = answerSdp;
          reqData.status = 'ready';
        }
      } catch (e) {
        const reqData = this.whepRequests.get(requestId);
        if (reqData) {
          reqData.error = e.message;
          reqData.status = 'error';
        }
      }
    })();

    res.status(202).json({ id: requestId });
  }

  _serveWhepResult(req, res) {
    const requestId = req.params.id;
    const reqData = this.whepRequests.get(requestId);

    if (!reqData) {
      return res.status(404).send('Request not found');
    }

    if (reqData.status === 'pending') {
      return res.status(202).json({ status: 'pending' });
    }

    if (reqData.status === 'ready') {
      this.whepRequests.delete(requestId);
      return res.type('application/sdp').send(reqData.answer);
    }

    this.whepRequests.delete(requestId);
    return res.status(500).send(reqData.error || 'Unknown error');
  }

  async _handleScopeOffer(req, res) {
    if (!this.scopeUrl) {
      return res.status(404).send('No Scope URL configured');
    }

    try {
      const payload = req.body;
      const offerSdp = payload.sdp || '';
      const requestId = crypto.randomBytes(8).toString('base64url');

      this.scopeRequests.set(requestId, {
        status: 'pending',
        answer: null,
        sessionId: null,
        error: null,
      });

      // Process in background
      (async () => {
        try {
          const client = new ScopeClient(this.scopeUrl);

          // Get pipeline_id
          const pipelineId = this.scopePipelineId || 'streamdiffusionv2';

          // Get initial parameters from bridge config
          const initialParams = {};
          if (this.bridge) {
            const cfg = this.bridge.config;
            initialParams.prompts = [cfg.prompt];
            initialParams.negative_prompt = cfg.negativePrompt;
            initialParams.guidance_scale = cfg.guidanceScale;
          }
          initialParams.pipeline_id = pipelineId;

          const answer = await client.sendOffer(offerSdp, 'offer', initialParams);

          const reqData = this.scopeRequests.get(requestId);
          if (reqData) {
            reqData.answer = answer.sdp || '';
            reqData.sessionId = answer.sessionId || '';
            reqData.status = 'ready';
          }
        } catch (e) {
          console.error('Scope offer error:', e);
          const reqData = this.scopeRequests.get(requestId);
          if (reqData) {
            reqData.error = e.message;
            reqData.status = 'error';
          }
        }
      })();

      res.status(202).json({ id: requestId });
    } catch (e) {
      res.status(500).send(e.message);
    }
  }

  _serveScopeResult(req, res) {
    const requestId = req.params.id;
    const reqData = this.scopeRequests.get(requestId);

    if (!reqData) {
      return res.status(404).send('Request not found');
    }

    if (reqData.status === 'pending') {
      return res.status(202).json({ status: 'pending' });
    }

    if (reqData.status === 'ready') {
      this.scopeRequests.delete(requestId);
      return res.json({
        sdp: reqData.answer,
        sessionId: reqData.sessionId,
      });
    }

    this.scopeRequests.delete(requestId);
    return res.status(500).json({ error: reqData.error || 'Unknown error' });
  }

  async _handleScopeIceCandidate(req, res) {
    try {
      const { sessionId, candidate, sdpMid, sdpMLineIndex } = req.body;

      if (!sessionId || !candidate) {
        throw new Error('Missing sessionId or candidate');
      }

      const client = new ScopeClient(this.scopeUrl);
      client.sessionId = sessionId;
      await client.sendIceCandidate(candidate, sdpMid, sdpMLineIndex);

      res.json({ success: true });
    } catch (e) {
      res.status(500).json({ error: e.message });
    }
  }

  /**
   * Start the server
   */
  start() {
    return new Promise((resolve) => {
      this.server.listen(this.port, '127.0.0.1', () => {
        resolve();
      });
    });
  }

  /**
   * Stop the server
   */
  stop() {
    return new Promise((resolve) => {
      this.wss.close();
      this.server.close(() => resolve());
    });
  }
}

export default DaydreamServer;

