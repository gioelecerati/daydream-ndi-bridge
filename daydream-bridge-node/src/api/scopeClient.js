/**
 * Scope WebRTC Client
 * Connects to a Daydream Scope instance (local or RunPod) via WebRTC
 */

import https from 'https';
import http from 'http';

/**
 * Configuration for Scope connection
 */
export class ScopeConfig {
  constructor(options = {}) {
    this.prompts = options.prompts || [{ text: 'anime style, vibrant colors', weight: 1.0 }];
    this.negativePrompt = options.negativePrompt || 'blurry, low quality';
    this.denoisingStepList = options.denoisingStepList || [1000, 750]; // Default for video mode
    this.guidanceScale = options.guidanceScale ?? 1.0;
    this.inputMode = options.inputMode || 'video'; // "video" for v2v, "text" for t2v
    this.pipelineId = options.pipelineId || 'streamdiffusionv2';

    // Resolution (defaults for Krea: 256x256 for video mode)
    this.width = options.width || 512;
    this.height = options.height || 512;
  }
}

/**
 * Client for connecting to Daydream Scope via WebRTC.
 *
 * Scope uses standard WebRTC (not WHIP/WHEP), so we need to:
 * 1. Get ICE servers from Scope
 * 2. Create offer with our video track
 * 3. Send offer to Scope's /api/v1/webrtc/offer
 * 4. Get answer and connect
 * 5. Send/receive video bidirectionally
 */
export class ScopeClient {
  constructor(scopeUrl) {
    this.scopeUrl = scopeUrl.replace(/\/$/, '');
    this.config = new ScopeConfig();
    this.sessionId = null;
    this.connected = false;
  }

  getApiUrl(endpoint) {
    return `${this.scopeUrl}/api/v1${endpoint}`;
  }

  _getHeaders() {
    return {
      'Accept': 'application/json',
      'Content-Type': 'application/json',
      'Referer': `${this.scopeUrl}/`,
      'Origin': this.scopeUrl,
      'User-Agent': 'DaydreamBridge-Node/1.0',
    };
  }

  /**
   * Make an HTTP request
   */
  _request(url, options = {}) {
    return new Promise((resolve, reject) => {
      const parsedUrl = new URL(url);
      const isHttps = parsedUrl.protocol === 'https:';
      const lib = isHttps ? https : http;

      const reqOptions = {
        hostname: parsedUrl.hostname,
        port: parsedUrl.port || (isHttps ? 443 : 80),
        path: parsedUrl.pathname + parsedUrl.search,
        method: options.method || 'GET',
        headers: options.headers || {},
        timeout: options.timeout || 10000,
        rejectUnauthorized: false, // Skip SSL verification for RunPod proxies
      };

      const req = lib.request(reqOptions, (res) => {
        let data = '';
        res.on('data', (chunk) => (data += chunk));
        res.on('end', () => {
          resolve({
            status: res.statusCode,
            headers: res.headers,
            data,
          });
        });
      });

      req.on('error', reject);
      req.on('timeout', () => {
        req.destroy();
        reject(new Error('Request timeout'));
      });

      if (options.body) {
        req.write(options.body);
      }
      req.end();
    });
  }

  /**
   * Get ICE server configuration from Scope
   */
  async getIceServers() {
    try {
      const url = this.getApiUrl('/webrtc/ice-servers');
      const response = await this._request(url, {
        headers: this._getHeaders(),
        timeout: 10000,
      });

      if (response.status === 200) {
        const data = JSON.parse(response.data);
        return data.iceServers || [];
      }
    } catch (e) {
      console.log(`Warning: Failed to get ICE servers: ${e.message}`);
    }
    // Return default STUN server
    return [{ urls: ['stun:stun.l.google.com:19302'] }];
  }

  /**
   * Send WebRTC offer to Scope and get answer.
   */
  async sendOffer(sdp, sdpType = 'offer', initialParams = null) {
    const url = this.getApiUrl('/webrtc/offer');

    // Build initial parameters from config
    let prompts = this.config.prompts;
    if (initialParams?.prompts) {
      prompts = initialParams.prompts;
    }

    // Convert string prompts to PromptItem format
    const formattedPrompts = [];
    if (Array.isArray(prompts)) {
      for (const p of prompts) {
        if (typeof p === 'string') {
          formattedPrompts.push({ text: p, weight: 1.0 });
        } else if (typeof p === 'object') {
          formattedPrompts.push(p);
        }
      }
    } else if (typeof prompts === 'string') {
      formattedPrompts.push({ text: prompts, weight: 1.0 });
    }

    // Get pipeline_id from params or config
    const pipelineId = initialParams?.pipeline_id || this.config.pipelineId;

    const params = {
      input_mode: this.config.inputMode,
      prompts: formattedPrompts,
      negative_prompt: initialParams?.negative_prompt || this.config.negativePrompt,
      denoising_step_list: this.config.denoisingStepList,
      guidance_scale: initialParams?.guidance_scale ?? this.config.guidanceScale,
      noise_scale: 0.7, // Required for video mode
      noise_controller: true, // Enable automatic noise adjustment
      width: this.config.width,
      height: this.config.height,
      pipeline_ids: [pipelineId], // Specify which pipeline to use
    };

    const payload = {
      sdp: sdp,
      type: sdpType,
      initialParameters: params,
    };

    const response = await this._request(url, {
      method: 'POST',
      headers: this._getHeaders(),
      body: JSON.stringify(payload),
      timeout: 30000,
    });

    if (response.status >= 400) {
      console.log(`Scope offer failed (${response.status}): ${response.data}`);
      throw new Error(`Scope offer failed: ${response.status}`);
    }

    const answer = JSON.parse(response.data);
    this.sessionId = answer.sessionId;
    this.connected = true;
    console.log(`Connected to Scope, session: ${this.sessionId}`);
    return answer;
  }

  /**
   * Send ICE candidate to Scope
   */
  async sendIceCandidate(candidate, sdpMid, sdpMlineIndex) {
    if (!this.sessionId) {
      console.log('Warning: No session ID, cannot send ICE candidate');
      return;
    }

    const url = this.getApiUrl(`/webrtc/offer/${this.sessionId}`);

    const payload = {
      candidates: [
        {
          candidate: candidate,
          sdpMid: sdpMid,
          sdpMLineIndex: sdpMlineIndex,
        },
      ],
    };

    try {
      await this._request(url, {
        method: 'PATCH',
        headers: this._getHeaders(),
        body: JSON.stringify(payload),
        timeout: 10000,
      });
    } catch (e) {
      console.log(`Warning: Failed to send ICE candidate: ${e.message}`);
    }
  }

  /**
   * Update parameters on an active session.
   * Note: In Scope, this is done via WebRTC data channel, not REST API.
   */
  updateParameters(params) {
    if (params.prompts) this.config.prompts = params.prompts;
    if (params.negative_prompt) this.config.negativePrompt = params.negative_prompt;
    if (params.guidance_scale !== undefined) this.config.guidanceScale = params.guidance_scale;
    if (params.denoising_step_list) this.config.denoisingStepList = params.denoising_step_list;
  }

  /**
   * Check if Scope is reachable
   */
  async checkConnection() {
    const headers = this._getHeaders();

    // Try the health endpoint first
    try {
      const response = await this._request(`${this.scopeUrl}/health`, {
        headers,
        timeout: 10000,
      });
      if (response.status === 200) return true;
    } catch {
      // Continue to next endpoint
    }

    // Try the ICE servers endpoint
    try {
      const response = await this._request(this.getApiUrl('/webrtc/ice-servers'), {
        headers,
        timeout: 10000,
      });
      if (response.status === 200) return true;
    } catch {
      // Continue to next endpoint
    }

    // Try pipeline status endpoint
    try {
      const response = await this._request(this.getApiUrl('/pipeline/status'), {
        headers,
        timeout: 10000,
      });
      if (response.status === 200) return true;
    } catch {
      // Continue to next endpoint
    }

    // Try the main page as last resort
    try {
      const response = await this._request(this.scopeUrl, {
        headers,
        timeout: 10000,
      });
      if (response.status === 200) return true;
    } catch {
      return false;
    }

    return false;
  }

  /**
   * Get available pipelines from Scope
   */
  async getPipelines() {
    try {
      const url = this.getApiUrl('/pipelines/schemas');
      const response = await this._request(url, {
        headers: this._getHeaders(),
        timeout: 10000,
      });

      if (response.status === 200) {
        const data = JSON.parse(response.data);
        const pipelines = data.pipelines || {};
        return Object.keys(pipelines);
      }
    } catch (e) {
      console.log(`Warning: Failed to get pipelines: ${e.message}`);
    }
    return [];
  }

  /**
   * Load a pipeline on Scope (must be called before streaming)
   */
  async loadPipeline(pipelineId) {
    try {
      const url = this.getApiUrl('/pipeline/load');
      const payload = {
        pipeline_ids: [pipelineId],
      };

      const response = await this._request(url, {
        method: 'POST',
        headers: this._getHeaders(),
        body: JSON.stringify(payload),
        timeout: 30000,
      });

      if (response.status >= 400) {
        console.log(`Failed to load pipeline (${response.status}): ${response.data}`);
        return false;
      }

      const result = JSON.parse(response.data);
      console.log(`Pipeline load initiated: ${JSON.stringify(result)}`);
      return true;
    } catch (e) {
      console.log(`Failed to load pipeline: ${e.message}`);
      return false;
    }
  }

  /**
   * Get current pipeline status from Scope
   */
  async getPipelineStatus() {
    try {
      const url = this.getApiUrl('/pipeline/status');
      const response = await this._request(url, {
        headers: this._getHeaders(),
        timeout: 10000,
      });

      if (response.status === 200) {
        return JSON.parse(response.data);
      }
    } catch (e) {
      console.log(`Warning: Failed to get pipeline status: ${e.message}`);
    }
    return { status: 'unknown' };
  }

  /**
   * Wait for pipeline to be loaded
   */
  async waitForPipelineLoaded(timeout = 120000) {
    const start = Date.now();
    while (Date.now() - start < timeout) {
      const status = await this.getPipelineStatus();
      if (status.status === 'loaded') {
        console.log('Pipeline loaded successfully');
        return true;
      } else if (status.status === 'error') {
        console.log(`Pipeline loading failed: ${JSON.stringify(status)}`);
        return false;
      }
      console.log(`Waiting for pipeline... status: ${status.status}`);
      await new Promise((resolve) => setTimeout(resolve, 2000));
    }
    console.log('Timeout waiting for pipeline to load');
    return false;
  }

  /**
   * Disconnect from Scope
   */
  disconnect() {
    this.connected = false;
    this.sessionId = null;
  }
}

/**
 * Test connection to a Scope instance.
 */
export async function testScopeConnection(url) {
  const client = new ScopeClient(url);

  const result = {
    reachable: false,
    url: url,
    pipelines: [],
    iceServers: [],
    error: null,
  };

  try {
    // Test basic connectivity
    try {
      const response = await client._request(url, {
        headers: client._getHeaders(),
        timeout: 15000,
      });
      if (response.status === 200 || response.status === 404 || response.status === 500) {
        result.reachable = true;
      }
    } catch (e) {
      if (e.code === 'ECONNREFUSED' || e.code === 'ENOTFOUND') {
        result.error = `Cannot reach URL: ${e.message}`;
        return result;
      }
      // HTTP errors mean we reached the server
      result.reachable = true;
    }

    // If reachable, try to get more info
    if (result.reachable) {
      try {
        result.pipelines = await client.getPipelines();
      } catch {
        // Ignore
      }

      try {
        result.iceServers = await client.getIceServers();
      } catch {
        // Ignore
      }
    }
  } catch (e) {
    result.error = e.message;
  }

  return result;
}

export default ScopeClient;

