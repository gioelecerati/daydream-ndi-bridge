/**
 * Daydream API Client
 * Adapted from the official Daydream TouchDesigner plugin
 * https://github.com/daydreamlive/daydream-touchdesigner
 */

import fs from 'fs';
import path from 'path';
import os from 'os';
import https from 'https';
import http from 'http';
import crypto from 'crypto';

const VERSION = '1.0.0';

const API_TIMEOUT_CREATE = 15000;
const API_TIMEOUT_UPDATE = 10000;
const API_TIMEOUT_SDP = 5000;

// ControlNet support by model
const CONTROLNET_SUPPORT = {
  'stabilityai/sdxl-turbo': {
    depth: ['xinsir/controlnet-depth-sdxl-1.0', 'depth_tensorrt'],
    canny: ['xinsir/controlnet-canny-sdxl-1.0', 'canny'],
    tile: ['xinsir/controlnet-tile-sdxl-1.0', 'feedback'],
  },
  'stabilityai/sd-turbo': {
    depth: ['thibaud/controlnet-sd21-depth-diffusers', 'depth_tensorrt'],
    canny: ['thibaud/controlnet-sd21-canny-diffusers', 'canny'],
  },
  'Lykon/dreamshaper-8': {
    depth: ['lllyasviel/control_v11f1p_sd15_depth', 'depth_tensorrt'],
    canny: ['lllyasviel/control_v11p_sd15_canny', 'canny'],
    tile: ['lllyasviel/control_v11f1e_sd15_tile', 'feedback'],
  },
};

/**
 * Configuration for a Daydream stream
 */
export class StreamConfig {
  constructor(options = {}) {
    this.modelId = options.modelId || 'stabilityai/sdxl-turbo';
    this.prompt = options.prompt || 'anime style, vibrant colors, detailed';
    this.negativePrompt = options.negativePrompt || 'blurry, low quality, flat, 2d';
    this.guidanceScale = options.guidanceScale ?? 1.0;
    this.delta = options.delta ?? 0.7;
    this.width = options.width || 512;
    this.height = options.height || 512;
    this.numInferenceSteps = options.numInferenceSteps || 50;
    this.doAddNoise = options.doAddNoise ?? true;
    this.tIndexList = options.tIndexList || [11];

    // ControlNet scales
    this.depthScale = options.depthScale ?? 0.45;
    this.cannyScale = options.cannyScale ?? 0.0;
    this.tileScale = options.tileScale ?? 0.21;
  }
}

/**
 * Information about an active stream
 */
export class StreamInfo {
  constructor(options = {}) {
    this.id = options.id || '';
    this.whipUrl = options.whipUrl || '';
    this.whepUrl = options.whepUrl || '';
    this.modelId = options.modelId || '';
  }
}

/**
 * Client for the Daydream API
 */
export class DaydreamAPI {
  static BASE_URL = 'https://api.daydream.live/v1';
  static CREDENTIALS_PATH = path.join(os.homedir(), '.daydream', 'credentials');
  static AUTH_STATES_PATH = path.join(os.homedir(), '.daydream', 'auth_states.json');
  static AUTH_STATE_TTL = 300;

  constructor(apiKey = null) {
    this.apiKey = apiKey;

    // Try to load saved credentials if no key provided
    if (!this.apiKey) {
      this._loadCredentials();
    }
  }

  _getHeaders() {
    if (!this.apiKey) {
      throw new Error('API key not set. Please login first.');
    }
    return {
      'Authorization': `Bearer ${this.apiKey}`,
      'Content-Type': 'application/json',
      'x-client-source': 'virtualdj-bridge-node',
    };
  }

  _loadCredentials() {
    if (!fs.existsSync(DaydreamAPI.CREDENTIALS_PATH)) {
      return;
    }
    try {
      const content = fs.readFileSync(DaydreamAPI.CREDENTIALS_PATH, 'utf-8');
      for (const line of content.split('\n')) {
        const trimmed = line.trim();
        if (trimmed.startsWith('DAYDREAM_API_KEY:')) {
          this.apiKey = trimmed.split(':')[1].trim();
          console.log(`✓ Loaded credentials from ${DaydreamAPI.CREDENTIALS_PATH}`);
          return;
        }
      }
    } catch (e) {
      console.log(`Warning: Could not load credentials: ${e.message}`);
    }
  }

  _saveCredentials(apiKey) {
    const credentialsDir = path.dirname(DaydreamAPI.CREDENTIALS_PATH);
    if (!fs.existsSync(credentialsDir)) {
      fs.mkdirSync(credentialsDir, { recursive: true });
    }
    try {
      fs.writeFileSync(DaydreamAPI.CREDENTIALS_PATH, `DAYDREAM_API_KEY: ${apiKey}\n`);
      console.log(`✓ Saved credentials to ${DaydreamAPI.CREDENTIALS_PATH}`);
    } catch (e) {
      console.log(`Warning: Could not save credentials: ${e.message}`);
    }
  }

  get isLoggedIn() {
    return Boolean(this.apiKey);
  }

  setApiKey(key, save = true) {
    this.apiKey = key;
    if (save) {
      this._saveCredentials(key);
    }
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
        rejectUnauthorized: false, // Skip SSL verification like Python version
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
   * Create a new stream
   */
  async createStream(config) {
    // Build controlnets
    const controlnets = [];
    const support = CONTROLNET_SUPPORT[config.modelId] || {};

    if (support.depth && config.depthScale > 0) {
      const [modelId, preprocessor] = support.depth;
      controlnets.push({
        model_id: modelId,
        conditioning_scale: config.depthScale,
        preprocessor: preprocessor,
        preprocessor_params: {},
        enabled: true,
      });
    }

    if (support.canny && config.cannyScale > 0) {
      const [modelId, preprocessor] = support.canny;
      controlnets.push({
        model_id: modelId,
        conditioning_scale: config.cannyScale,
        preprocessor: preprocessor,
        preprocessor_params: {},
        enabled: true,
      });
    }

    if (support.tile && config.tileScale > 0) {
      const [modelId, preprocessor] = support.tile;
      controlnets.push({
        model_id: modelId,
        conditioning_scale: config.tileScale,
        preprocessor: preprocessor,
        preprocessor_params: {},
        enabled: true,
      });
    }

    // Build params
    const params = {
      model_id: config.modelId,
      prompt: config.prompt,
      negative_prompt: config.negativePrompt,
      guidance_scale: config.guidanceScale,
      delta: config.delta,
      width: config.width,
      height: config.height,
      num_inference_steps: config.numInferenceSteps,
      do_add_noise: config.doAddNoise,
      t_index_list: config.tIndexList,
    };

    if (controlnets.length > 0) {
      params.controlnets = controlnets;
    }

    // Generate unique stream name with timestamp
    const streamName = `ndi_bridge_${Date.now()}`;

    const payload = {
      name: streamName,
      pipeline: 'streamdiffusion',
      params: params,
    };

    const response = await this._request(`${DaydreamAPI.BASE_URL}/streams`, {
      method: 'POST',
      headers: this._getHeaders(),
      body: JSON.stringify(payload),
      timeout: API_TIMEOUT_CREATE,
    });

    if (response.status >= 400) {
      console.log(`✗ API Error ${response.status}: ${response.data}`);
      throw new Error(`API Error ${response.status}: ${response.data}`);
    }

    const responseData = JSON.parse(response.data);

    const stream = new StreamInfo({
      id: responseData.id || '',
      whipUrl: responseData.whip_url || '',
      modelId: responseData.params?.model_id || config.modelId,
    });

    console.log(`✓ Stream created: ${stream.id}`);
    console.log(`  WHIP URL: ${stream.whipUrl}`);

    return stream;
  }

  /**
   * Update stream parameters
   */
  async updateStream(streamId, config) {
    if (!streamId) {
      console.log('Warning: No stream_id for update');
      return false;
    }

    const params = {
      model_id: config.modelId,
      prompt: config.prompt,
      negative_prompt: config.negativePrompt,
      guidance_scale: config.guidanceScale,
      delta: config.delta,
    };

    // Build controlnets
    const support = CONTROLNET_SUPPORT[config.modelId] || {};
    const controlnets = [];

    const cnTypes = [
      ['depth', config.depthScale],
      ['canny', config.cannyScale],
      ['tile', config.tileScale],
    ];

    for (const [cnType, scale] of cnTypes) {
      if (support[cnType]) {
        const [modelId, preprocessor] = support[cnType];
        controlnets.push({
          model_id: modelId,
          conditioning_scale: scale,
          preprocessor: preprocessor,
          preprocessor_params: {},
          enabled: true,
        });
      }
    }

    if (controlnets.length > 0) {
      params.controlnets = controlnets;
    }

    const payload = {
      pipeline: 'streamdiffusion',
      params: params,
    };

    console.log(`→ Updating stream ${streamId}: prompt='${config.prompt.slice(0, 30)}...', delta=${config.delta}`);

    try {
      const response = await this._request(`${DaydreamAPI.BASE_URL}/streams/${streamId}`, {
        method: 'PATCH',
        headers: this._getHeaders(),
        body: JSON.stringify(payload),
        timeout: API_TIMEOUT_UPDATE,
      });

      if (response.status >= 400) {
        console.log(`✗ Update failed ${response.status}: ${response.data}`);
        return false;
      }

      console.log('✓ Stream parameters updated');
      return true;
    } catch (e) {
      console.log(`✗ Update failed: ${e.message}`);
      return false;
    }
  }

  /**
   * Exchange SDP for WHIP/WHEP
   */
  async exchangeSdp(url, offerSdp, timeout = API_TIMEOUT_SDP) {
    const headers = {
      'Content-Type': 'application/sdp',
    };
    if (this.apiKey) {
      headers['Authorization'] = `Bearer ${this.apiKey}`;
    }

    const response = await this._request(url, {
      method: 'POST',
      headers,
      body: offerSdp,
      timeout,
    });

    if (response.status >= 400) {
      throw new Error(`SDP exchange failed: ${response.status}`);
    }

    return [response.data, response.headers];
  }

  /**
   * Delete/stop a stream
   */
  async deleteStream(streamId) {
    try {
      await this._request(`${DaydreamAPI.BASE_URL}/streams/${streamId}`, {
        method: 'DELETE',
        headers: this._getHeaders(),
        timeout: API_TIMEOUT_UPDATE,
      });
      return true;
    } catch {
      return true; // DELETE often returns empty on success
    }
  }

  // OAuth Login Flow
  _loadAuthStates() {
    if (!fs.existsSync(DaydreamAPI.AUTH_STATES_PATH)) {
      return {};
    }
    try {
      const content = fs.readFileSync(DaydreamAPI.AUTH_STATES_PATH, 'utf-8');
      const data = JSON.parse(content);
      const states = data.states || {};
      const now = Date.now() / 1000;
      const filtered = {};
      for (const [s, t] of Object.entries(states)) {
        if (now - t < DaydreamAPI.AUTH_STATE_TTL) {
          filtered[s] = t;
        }
      }
      return filtered;
    } catch {
      return {};
    }
  }

  _saveAuthStates(states) {
    const authDir = path.dirname(DaydreamAPI.AUTH_STATES_PATH);
    if (!fs.existsSync(authDir)) {
      fs.mkdirSync(authDir, { recursive: true });
    }
    try {
      fs.writeFileSync(DaydreamAPI.AUTH_STATES_PATH, JSON.stringify({ states }));
    } catch (e) {
      console.log(`Warning: Could not save auth states: ${e.message}`);
    }
  }

  /**
   * Create and save an auth state for OAuth flow
   */
  createAuthState() {
    const state = crypto.randomBytes(16).toString('base64url');
    const states = this._loadAuthStates();
    states[state] = Date.now() / 1000;
    this._saveAuthStates(states);
    return state;
  }

  /**
   * Validate and consume an auth state
   */
  consumeAuthState(state) {
    if (!state) return false;
    const states = this._loadAuthStates();
    if (!(state in states)) return false;
    delete states[state];
    this._saveAuthStates(states);
    return true;
  }

  /**
   * Create an API key from a JWT token (OAuth callback)
   */
  async createApiKeyFromJwt(jwtToken, name = 'VirtualDJ Bridge Node') {
    const payload = { name, user_type: 'virtualdj' };
    const headers = {
      'Authorization': `Bearer ${jwtToken}`,
      'Content-Type': 'application/json',
      'x-client-source': 'virtualdj-bridge-node',
    };

    const response = await this._request(`${DaydreamAPI.BASE_URL}/api-key`, {
      method: 'POST',
      headers,
      body: JSON.stringify(payload),
      timeout: API_TIMEOUT_UPDATE,
    });

    if (response.status >= 400) {
      console.log(`Error creating API key: ${response.status}: ${response.data}`);
      throw new Error(`Error creating API key: ${response.status}`);
    }

    const result = JSON.parse(response.data);
    const apiKey = result.apiKey;
    if (apiKey) {
      this.setApiKey(apiKey, true);
    }
    return apiKey;
  }
}

export default DaydreamAPI;

