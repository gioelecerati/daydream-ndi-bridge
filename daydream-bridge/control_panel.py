"""
Control Panel Web UI for Daydream Bridge
"""

CONTROL_PANEL_HTML = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Daydream Bridge</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500&family=Space+Grotesk:wght@400;500;600&display=swap" rel="stylesheet">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        :root {
            --bg: #0a0a0a;
            --bg-card: #111;
            --bg-input: #181818;
            --border: #2a2a2a;
            --text: #fff;
            --text-dim: #666;
            --accent: #fff;
        }
        
        html, body {
            height: 100%;
            overflow: hidden;
        }
        
        body {
            font-family: 'Space Grotesk', sans-serif;
            background: var(--bg);
            color: var(--text);
        }
        
        .app {
            display: flex;
            height: 100vh;
        }
        
        /* Left Panel - Video */
        .video-panel {
            width: 50%;
            min-width: 400px;
            background: #000;
            display: flex;
            flex-direction: column;
            border-right: 1px solid var(--border);
        }
        
        .video-header {
            padding: 16px 24px;
            border-bottom: 1px solid var(--border);
            display: flex;
            align-items: center;
            justify-content: space-between;
            background: var(--bg);
        }
        
        .logo {
            font-size: 14px;
            font-weight: 600;
            letter-spacing: -0.02em;
        }
        
        .logo span {
            color: var(--text-dim);
            font-weight: 400;
            margin-left: 8px;
        }
        
        .status {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 12px;
            font-family: 'JetBrains Mono', monospace;
            color: var(--text-dim);
        }
        
        .status-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: var(--text-dim);
        }
        
        .status-dot.live {
            background: #fff;
            animation: pulse 1.5s infinite;
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.4; }
        }
        
        .video-container {
            flex: 1;
            display: flex;
            align-items: center;
            justify-content: center;
            background: #000;
            position: relative;
        }
        
        .video-container iframe {
            width: 512px;
            height: 512px;
            max-width: 100%;
            max-height: 100%;
            border: none;
        }
        
        .video-placeholder {
            text-align: center;
            color: var(--text-dim);
        }
        
        .video-placeholder svg {
            width: 80px;
            height: 80px;
            margin-bottom: 16px;
            opacity: 0.3;
        }
        
        .video-actions {
            padding: 16px 24px;
            border-top: 1px solid var(--border);
            background: var(--bg);
            display: flex;
            gap: 12px;
        }
        
        .url-bar {
            padding: 12px 24px;
            border-top: 1px solid var(--border);
            background: var(--bg);
            display: flex;
            gap: 8px;
            align-items: center;
        }
        
        .url-bar input {
            flex: 1;
            padding: 10px 12px;
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 4px;
            color: var(--text);
            font-family: 'JetBrains Mono', monospace;
            font-size: 11px;
        }
        
        .url-bar .btn {
            padding: 10px 16px;
            font-size: 12px;
        }
        
        /* Backend tabs */
        .backend-tabs {
            display: flex;
            gap: 4px;
            background: var(--bg-card);
            padding: 4px;
            border-radius: 6px;
        }
        
        .backend-tab {
            flex: 1;
            padding: 10px;
            background: transparent;
            border: none;
            color: var(--text-dim);
            font-family: inherit;
            font-size: 12px;
            border-radius: 4px;
            cursor: pointer;
            transition: all 0.15s;
        }
        
        .backend-tab:hover {
            color: var(--text);
        }
        
        .backend-tab.active {
            background: var(--bg-input);
            color: var(--text);
        }
        
        #scopeConfig input[type="text"] {
            width: 100%;
            padding: 12px;
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 4px;
            color: var(--text);
        }
        
        #scopeConfig input[type="text"]:focus {
            outline: none;
            border-color: var(--text-dim);
        }
        
        /* Right Panel - Controls */
        .controls-panel {
            flex: 1;
            min-width: 360px;
            display: flex;
            flex-direction: column;
            background: var(--bg);
        }
        
        .controls-header {
            padding: 16px 24px;
            border-bottom: 1px solid var(--border);
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            color: var(--text-dim);
        }
        
        .controls-scroll {
            flex: 1;
            overflow-y: auto;
            padding: 24px;
        }
        
        .section {
            margin-bottom: 32px;
        }
        
        .section:last-child {
            margin-bottom: 0;
        }
        
        .section-title {
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.12em;
            color: var(--text-dim);
            margin-bottom: 16px;
            padding-bottom: 8px;
            border-bottom: 1px solid var(--border);
        }
        
        /* Buttons */
        .btn {
            padding: 14px 24px;
            font-family: inherit;
            font-size: 13px;
            font-weight: 500;
            border: 1px solid var(--border);
            border-radius: 6px;
            cursor: pointer;
            transition: all 0.15s;
            background: var(--bg-input);
            color: var(--text);
        }
        
        .btn:hover {
            background: var(--border);
        }
        
        .btn:disabled {
            opacity: 0.3;
            cursor: not-allowed;
        }
        
        .btn-primary {
            flex: 1;
            background: var(--text);
            color: var(--bg);
            border-color: var(--text);
        }
        
        .btn-primary:hover {
            background: #ccc;
        }
        
        .btn-danger {
            border-color: #f33;
            color: #f33;
            background: transparent;
        }
        
        .btn-danger:hover {
            background: #f33;
            color: #000;
        }
        
        /* Slider */
        .slider-row {
            display: flex;
            align-items: center;
            gap: 16px;
            margin-bottom: 20px;
            padding: 16px;
            background: var(--bg-card);
            border-radius: 8px;
        }
        
        .slider-row:last-child {
            margin-bottom: 0;
        }
        
        .slider-label {
            width: 80px;
            font-size: 13px;
            color: var(--text);
        }
        
        .slider-track {
            flex: 1;
            position: relative;
        }
        
        input[type="range"] {
            width: 100%;
            height: 6px;
            background: var(--border);
            border-radius: 3px;
            appearance: none;
            cursor: pointer;
        }
        
        input[type="range"]::-webkit-slider-thumb {
            appearance: none;
            width: 18px;
            height: 18px;
            background: #fff;
            border-radius: 50%;
            cursor: pointer;
            box-shadow: 0 2px 8px rgba(0,0,0,0.3);
            transition: transform 0.1s;
        }
        
        input[type="range"]::-webkit-slider-thumb:hover {
            transform: scale(1.15);
        }
        
        .slider-value {
            width: 50px;
            text-align: right;
            font-family: 'JetBrains Mono', monospace;
            font-size: 13px;
            color: var(--text-dim);
        }
        
        /* Source List */
        .source-list {
            display: flex;
            flex-direction: column;
            gap: 8px;
        }
        
        .source-item {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 14px 16px;
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 6px;
            cursor: pointer;
            transition: all 0.15s;
        }
        
        .source-item:hover {
            border-color: var(--text-dim);
        }
        
        .source-item.selected {
            border-color: var(--text);
            background: var(--bg-input);
        }
        
        .source-item .radio {
            width: 16px;
            height: 16px;
            border: 2px solid var(--text-dim);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        
        .source-item.selected .radio {
            border-color: var(--text);
        }
        
        .source-item.selected .radio::after {
            content: '';
            width: 8px;
            height: 8px;
            background: var(--text);
            border-radius: 50%;
        }
        
        .source-name {
            flex: 1;
            font-size: 13px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        
        .source-refresh {
            padding: 8px 12px;
            font-size: 11px;
            margin-top: 12px;
        }
        
        /* Text Input */
        .input-group {
            margin-bottom: 16px;
        }
        
        .input-group:last-child {
            margin-bottom: 0;
        }
        
        .input-label {
            display: block;
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            color: var(--text-dim);
            margin-bottom: 8px;
        }
        
        textarea, select {
            width: 100%;
            padding: 14px 16px;
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 6px;
            color: var(--text);
            font-family: 'JetBrains Mono', monospace;
            font-size: 13px;
            resize: vertical;
            transition: border-color 0.15s;
        }
        
        textarea:focus, select:focus {
            outline: none;
            border-color: var(--text-dim);
        }
        
        textarea {
            min-height: 100px;
        }
        
        select {
            cursor: pointer;
            appearance: none;
            background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%23666' stroke-width='2'%3E%3Cpath d='M6 9l6 6 6-6'/%3E%3C/svg%3E");
            background-repeat: no-repeat;
            background-position: right 14px center;
            padding-right: 40px;
        }
        
        /* Toast */
        .toast {
            position: fixed;
            bottom: 24px;
            left: 50%;
            transform: translateX(-50%) translateY(100px);
            padding: 14px 24px;
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 6px;
            font-size: 13px;
            opacity: 0;
            transition: all 0.2s;
            z-index: 1000;
        }
        
        .toast.show {
            transform: translateX(-50%) translateY(0);
            opacity: 1;
        }
        
        .toast.error {
            border-color: #f33;
            color: #f33;
        }
        
        /* Scrollbar */
        .controls-scroll::-webkit-scrollbar {
            width: 6px;
        }
        
        .controls-scroll::-webkit-scrollbar-track {
            background: transparent;
        }
        
        .controls-scroll::-webkit-scrollbar-thumb {
            background: var(--border);
            border-radius: 3px;
        }
        
        /* Responsive */
        @media (max-width: 900px) {
            .app {
                flex-direction: column;
            }
            
            .video-panel {
                width: 100%;
                min-width: auto;
                height: 50vh;
                border-right: none;
                border-bottom: 1px solid var(--border);
            }
            
            .controls-panel {
                min-width: auto;
                height: 50vh;
            }
        }
    </style>
</head>
<body>
    <div class="app">
        <div class="video-panel">
            <div class="video-header">
                <div class="logo">Daydream Bridge <span>NDI</span></div>
                <div class="status">
                    <div class="status-dot" id="statusDot"></div>
                    <span id="statusText">offline</span>
                </div>
            </div>
            <div class="video-container" id="videoContainer">
                <iframe id="outputFrame" style="display: none;"></iframe>
                <div class="video-placeholder" id="placeholder">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                        <rect x="2" y="2" width="20" height="20" rx="2"/>
                        <circle cx="8" cy="8" r="2"/>
                        <path d="M21 15l-5-5L5 21"/>
                    </svg>
                    <p>Start streaming to see output</p>
                </div>
            </div>
            <div class="video-actions">
                <button class="btn btn-primary" id="startBtn" onclick="startStream()">Start Stream</button>
                <button class="btn" id="updateBtn" onclick="updateParams()" disabled>Update</button>
                <button class="btn btn-danger" id="stopBtn" onclick="stopStream()" disabled>Stop</button>
                <button class="btn" onclick="openFullscreen()">↗</button>
            </div>
            <div class="url-bar" id="urlBar" style="display: none;">
                <input type="text" id="relayUrl" readonly onclick="this.select()">
                <button class="btn" onclick="copyUrl()">Copy</button>
            </div>
        </div>
        
        <div class="controls-panel">
            <div class="controls-header">Controls</div>
            <div class="controls-scroll">
                
                <!-- Daydream Cloud Controls -->
                <div class="section daydream-controls" id="daydreamControls">
                    <div class="section-title">Processing</div>
                    <div class="slider-row">
                        <span class="slider-label">Denoise</span>
                        <div class="slider-track">
                            <input type="range" id="delta" min="0" max="1" step="0.01" value="0.7">
                        </div>
                        <span class="slider-value" id="deltaValue">0.70</span>
                    </div>
                    <div class="slider-row">
                        <span class="slider-label">Guidance</span>
                        <div class="slider-track">
                            <input type="range" id="guidance" min="1" max="15" step="0.1" value="1.5">
                        </div>
                        <span class="slider-value" id="guidanceValue">1.5</span>
                    </div>
                </div>
                
                <div class="section daydream-controls" id="controlnetsSection">
                    <div class="section-title">ControlNets</div>
                    <div class="slider-row">
                        <span class="slider-label">Depth</span>
                        <div class="slider-track">
                            <input type="range" id="depthScale" min="0" max="1" step="0.01" value="0.45">
                        </div>
                        <span class="slider-value" id="depthScaleValue">0.45</span>
                    </div>
                    <div class="slider-row">
                        <span class="slider-label">Canny</span>
                        <div class="slider-track">
                            <input type="range" id="cannyScale" min="0" max="1" step="0.01" value="0">
                        </div>
                        <span class="slider-value" id="cannyScaleValue">0.00</span>
                    </div>
                    <div class="slider-row">
                        <span class="slider-label">Tile</span>
                        <div class="slider-track">
                            <input type="range" id="tileScale" min="0" max="1" step="0.01" value="0.21">
                        </div>
                        <span class="slider-value" id="tileScaleValue">0.21</span>
                    </div>
                </div>
                
                <!-- Scope Controls (hidden by default) -->
                <div class="section scope-controls" id="scopeControls" style="display: none;">
                    <div class="section-title">Scope Parameters</div>
                    <div class="slider-row">
                        <span class="slider-label">Noise Scale</span>
                        <div class="slider-track">
                            <input type="range" id="noiseScale" min="0" max="1" step="0.01" value="0.7" oninput="updateScopeSlider('noiseScale', 'noise_scale')">
                        </div>
                        <span class="slider-value" id="noiseScaleValue">0.70</span>
                    </div>
                    <div class="slider-row">
                        <span class="slider-label">Guidance</span>
                        <div class="slider-track">
                            <input type="range" id="scopeGuidance" min="1" max="15" step="0.1" value="1.0" oninput="updateScopeSlider('scopeGuidance', 'guidance_scale')">
                        </div>
                        <span class="slider-value" id="scopeGuidanceValue">1.0</span>
                    </div>
                    <div class="slider-row">
                        <span class="slider-label">Cache Bias</span>
                        <div class="slider-track">
                            <input type="range" id="kvCacheBias" min="0.01" max="1" step="0.01" value="1.0" oninput="updateScopeSlider('kvCacheBias', 'kv_cache_attention_bias')">
                        </div>
                        <span class="slider-value" id="kvCacheBiasValue">1.00</span>
                    </div>
                    <div class="input-group" style="margin-top: 16px;">
                        <label class="input-label">Prompt</label>
                        <textarea id="scopePrompt" style="min-height: 80px;">anime style, vibrant colors, detailed</textarea>
                    </div>
                    <button class="btn" onclick="updateScopePrompt()" style="margin-top: 8px; width: 100%;">Update Prompt</button>
                </div>
                
                <div class="section">
                    <div class="section-title">Backend</div>
                    <div class="backend-tabs">
                        <button class="backend-tab active" id="tabDaydream" onclick="switchBackend('daydream')">Daydream Cloud</button>
                        <button class="backend-tab" id="tabScope" onclick="switchBackend('scope')">Scope (Self-hosted)</button>
                    </div>
                    <div id="scopeConfig" style="display: none; margin-top: 12px;">
                        <div class="input-group">
                            <label class="input-label">Scope URL (RunPod or local)</label>
                            <input type="text" id="scopeUrl" placeholder="https://xxx-8000.proxy.runpod.net" style="font-family: 'JetBrains Mono', monospace; font-size: 12px;">
                        </div>
                        <button class="btn" onclick="testScopeConnection()" style="margin-top: 8px; width: 100%;">Test Connection</button>
                        <div id="scopeStatus" style="margin-top: 8px; font-size: 11px; color: var(--text-dim);"></div>
                        
                        <div class="input-group" style="margin-top: 16px;">
                            <label class="input-label">Pipeline</label>
                            <select id="scopePipeline">
                                <option value="streamdiffusionv2">StreamDiffusion V2 (512x512)</option>
                                <option value="longlive">LongLive (320x576)</option>
                                <option value="krea-realtime-video">Krea Realtime Video (320x576)</option>
                            </select>
                        </div>
                        <button class="btn" id="loadPipelineBtn" onclick="loadPipeline()" style="margin-top: 8px; width: 100%;">Load Pipeline</button>
                        <div id="pipelineStatus" style="margin-top: 8px; font-size: 11px; color: var(--text-dim);"></div>
                    </div>
                </div>
                
                <div class="section">
                    <div class="section-title">NDI Source</div>
                    <div class="source-list" id="sourceList">
                        <div class="source-item" style="justify-content: center; color: var(--text-dim);">
                            Scanning for sources...
                        </div>
                    </div>
                    <button class="btn source-refresh" onclick="refreshSources()">Refresh Sources</button>
                </div>
                
                <div class="section">
                    <div class="section-title">Prompt</div>
                    <div class="input-group">
                        <label class="input-label">Style Prompt</label>
                        <textarea id="prompt">anime style, vibrant colors, detailed</textarea>
                    </div>
                    <div class="input-group">
                        <label class="input-label">Negative Prompt</label>
                        <textarea id="negativePrompt" style="min-height: 60px;">blurry, low quality, flat</textarea>
                    </div>
                </div>
                
                <div class="section">
                    <div class="section-title">Model</div>
                    <select id="modelId">
                        <option value="stabilityai/sdxl-turbo">SDXL Turbo (Recommended)</option>
                        <option value="stabilityai/sd-turbo">SD Turbo (Fast)</option>
                        <option value="Lykon/dreamshaper-8">Dreamshaper 8</option>
                    </select>
                </div>
                
            </div>
        </div>
    </div>
    
    <div class="toast" id="toast"></div>
    
    <script>
        let selectedSource = null;
        let isStreaming = false;
        let backendMode = 'daydream';  // 'daydream' or 'scope'
        
        // Backend switching
        function switchBackend(mode) {
            backendMode = mode;
            document.getElementById('tabDaydream').classList.toggle('active', mode === 'daydream');
            document.getElementById('tabScope').classList.toggle('active', mode === 'scope');
            document.getElementById('scopeConfig').style.display = mode === 'scope' ? 'block' : 'none';
            
            // Show/hide backend-specific controls
            const modelSection = document.getElementById('modelId').parentElement;
            modelSection.style.display = mode === 'daydream' ? 'block' : 'none';
            
            // Daydream controls (Processing, ControlNets)
            document.getElementById('daydreamControls').style.display = mode === 'daydream' ? 'block' : 'none';
            document.getElementById('controlnetsSection').style.display = mode === 'daydream' ? 'block' : 'none';
            
            // Scope controls
            document.getElementById('scopeControls').style.display = mode === 'scope' ? 'block' : 'none';
        }
        
        async function testScopeConnection() {
            const url = document.getElementById('scopeUrl').value.trim();
            const statusEl = document.getElementById('scopeStatus');
            
            if (!url) {
                statusEl.innerHTML = '<span style="color: #f33;">Please enter a Scope URL</span>';
                return;
            }
            
            statusEl.innerHTML = 'Testing connection...';
            
            try {
                const resp = await fetch('/api/scope/test', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url })
                });
                const data = await resp.json();
                
                if (data.reachable) {
                    statusEl.innerHTML = `<span style="color: #4f4;">✓ Connected!</span> ${data.pipelines?.length || 0} pipelines available`;
                    // Check pipeline status after connection test
                    checkPipelineStatus();
                } else {
                    statusEl.innerHTML = `<span style="color: #f33;">✗ ${data.error || 'Connection failed'}</span>`;
                }
            } catch (e) {
                statusEl.innerHTML = `<span style="color: #f33;">✗ ${e.message}</span>`;
            }
        }
        
        let pipelineStatusInterval = null;
        
        async function checkPipelineStatus() {
            const url = document.getElementById('scopeUrl').value.trim();
            const statusEl = document.getElementById('pipelineStatus');
            const loadBtn = document.getElementById('loadPipelineBtn');
            
            if (!url) return;
            
            console.log('[Pipeline] Checking status...');
            
            try {
                const resp = await fetch('/api/scope/pipeline/status', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url })
                });
                const data = await resp.json();
                console.log('[Pipeline] Status response:', data);
                
                if (data.status === 'loaded') {
                    statusEl.innerHTML = `<span style="color: #4f4;">✓ Pipeline loaded:</span> ${data.pipeline_id || 'unknown'}`;
                    loadBtn.disabled = false;
                    loadBtn.textContent = 'Load Pipeline';
                    if (pipelineStatusInterval) {
                        clearInterval(pipelineStatusInterval);
                        pipelineStatusInterval = null;
                        console.log('[Pipeline] Stopped polling - pipeline loaded');
                    }
                } else if (data.status === 'loading') {
                    statusEl.innerHTML = '<span style="color: #fa0;">⏳ Loading pipeline... (this may take a few minutes)</span>';
                    loadBtn.disabled = true;
                    loadBtn.textContent = 'Loading...';
                } else if (data.status === 'not_loaded') {
                    statusEl.innerHTML = '<span style="color: var(--text-dim);">No pipeline loaded</span>';
                    loadBtn.disabled = false;
                    loadBtn.textContent = 'Load Pipeline';
                } else if (data.status === 'error') {
                    statusEl.innerHTML = `<span style="color: #f33;">✗ Error: ${data.error || 'Unknown error'}</span>`;
                    loadBtn.disabled = false;
                    loadBtn.textContent = 'Retry Load';
                } else {
                    console.log('[Pipeline] Unknown status:', data.status);
                    statusEl.innerHTML = `<span style="color: var(--text-dim);">Status: ${data.status || 'unknown'}</span>`;
                }
            } catch (e) {
                console.error('[Pipeline] Status check error:', e);
                statusEl.innerHTML = `<span style="color: #f33;">✗ ${e.message}</span>`;
            }
        }
        
        async function loadPipeline() {
            const url = document.getElementById('scopeUrl').value.trim();
            const pipelineId = document.getElementById('scopePipeline').value;
            const statusEl = document.getElementById('pipelineStatus');
            const loadBtn = document.getElementById('loadPipelineBtn');
            
            if (!url) {
                statusEl.innerHTML = '<span style="color: #f33;">Please enter a Scope URL first</span>';
                return;
            }
            
            console.log('[Pipeline] Loading pipeline:', pipelineId);
            statusEl.innerHTML = '<span style="color: #fa0;">⏳ Initiating pipeline load...</span>';
            loadBtn.disabled = true;
            loadBtn.textContent = 'Loading...';
            
            try {
                const resp = await fetch('/api/scope/pipeline/load', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url, pipeline_id: pipelineId })
                });
                const data = await resp.json();
                console.log('[Pipeline] Load response:', data);
                
                if (data.success) {
                    statusEl.innerHTML = '<span style="color: #fa0;">⏳ Loading pipeline... (this may take a few minutes)</span>';
                    // Start polling for status
                    if (pipelineStatusInterval) clearInterval(pipelineStatusInterval);
                    pipelineStatusInterval = setInterval(checkPipelineStatus, 3000);
                    console.log('[Pipeline] Started polling every 3s');
                    // Also check immediately
                    checkPipelineStatus();
                } else {
                    statusEl.innerHTML = `<span style="color: #f33;">✗ ${data.error || 'Failed to load'}</span>`;
                    loadBtn.disabled = false;
                    loadBtn.textContent = 'Load Pipeline';
                }
            } catch (e) {
                console.error('[Pipeline] Load error:', e);
                statusEl.innerHTML = `<span style="color: #f33;">✗ ${e.message}</span>`;
                loadBtn.disabled = false;
                loadBtn.textContent = 'Load Pipeline';
            }
        }
        
        // Scope parameter updates via data channel
        function getRelayWindow() {
            // Get the relay iframe by ID
            const iframe = document.getElementById('outputFrame');
            if (iframe && iframe.src && iframe.contentWindow) {
                return iframe.contentWindow;
            }
            return null;
        }
        
        function updateScopeSlider(sliderId, paramName) {
            const slider = document.getElementById(sliderId);
            const value = parseFloat(slider.value);
            
            // Update the display value
            const valueEl = document.getElementById(sliderId + 'Value');
            if (valueEl) {
                valueEl.textContent = value.toFixed(2);
            }
            
            // Update slider fill
            updateSlider(slider);
            
            // Send to Scope via relay data channel
            const relayWindow = getRelayWindow();
            if (relayWindow && relayWindow.sendScopeParams) {
                const params = {};
                params[paramName] = value;
                relayWindow.sendScopeParams(params);
                console.log('[Scope] Sent param:', paramName, value);
            } else {
                console.log('[Scope] Relay not ready for param update');
            }
        }
        
        function updateScopePrompt() {
            const prompt = document.getElementById('scopePrompt').value.trim();
            if (!prompt) return;
            
            const relayWindow = getRelayWindow();
            if (relayWindow && relayWindow.sendScopeParams) {
                // Scope expects prompts as [{text: "...", weight: 1.0}]
                relayWindow.sendScopeParams({
                    prompts: [{ text: prompt, weight: 1.0 }]
                });
                console.log('[Scope] Sent prompt:', prompt);
                showToast('Prompt updated', 'success');
            } else {
                showToast('Not connected to Scope', 'error');
            }
        }

        // Slider fill effect
        function updateSlider(slider) {
            const pct = ((slider.value - slider.min) / (slider.max - slider.min)) * 100;
            slider.style.background = `linear-gradient(90deg, #fff ${pct}%, #2a2a2a ${pct}%)`;
            
            const valueEl = document.getElementById(slider.id + 'Value');
            if (valueEl) {
                valueEl.textContent = parseFloat(slider.value).toFixed(2);
            }
        }
        
        document.querySelectorAll('input[type="range"]').forEach(s => {
            updateSlider(s);
            s.addEventListener('input', () => updateSlider(s));
        });
        
        // Toast
        function showToast(msg, type = '') {
            const t = document.getElementById('toast');
            t.textContent = msg;
            t.className = 'toast show ' + type;
            setTimeout(() => t.className = 'toast', 3000);
        }
        
        // Status
        function setStatus(status, text) {
            document.getElementById('statusDot').className = 'status-dot ' + status;
            document.getElementById('statusText').textContent = text;
        }
        
        // Sources
        async function refreshSources() {
            const list = document.getElementById('sourceList');
            list.innerHTML = '<div class="source-item" style="justify-content:center;color:var(--text-dim)">Scanning...</div>';
            
            try {
                const resp = await fetch('/api/sources');
                const data = await resp.json();
                
                if (data.sources?.length) {
                    list.innerHTML = data.sources.map((s, i) => `
                        <div class="source-item ${selectedSource === i ? 'selected' : ''}" onclick="selectSource(${i}, '${s.name}')">
                            <div class="radio"></div>
                            <span class="source-name">${s.name}</span>
                        </div>
                    `).join('');
                    
                    if (selectedSource === null) selectSource(0, data.sources[0].name);
                } else {
                    list.innerHTML = '<div class="source-item" style="justify-content:center;color:var(--text-dim)">No NDI sources found</div>';
                }
            } catch (e) {
                list.innerHTML = '<div class="source-item" style="justify-content:center;color:#f33">Connection error</div>';
            }
        }
        
        function selectSource(i, name) {
            selectedSource = i;
            document.querySelectorAll('.source-item').forEach((el, idx) => {
                el.classList.toggle('selected', idx === i);
            });
        }
        
        // Config
        function getConfig() {
            const config = {
                backend: backendMode,
                prompt: document.getElementById('prompt').value,
                negative_prompt: document.getElementById('negativePrompt').value,
                guidance_scale: parseFloat(document.getElementById('guidance').value),
                delta: parseFloat(document.getElementById('delta').value),
                depth_scale: parseFloat(document.getElementById('depthScale').value),
                canny_scale: parseFloat(document.getElementById('cannyScale').value),
                tile_scale: parseFloat(document.getElementById('tileScale').value),
                source_index: selectedSource
            };
            
            if (backendMode === 'daydream') {
                config.model_id = document.getElementById('modelId').value;
            } else {
                config.scope_url = document.getElementById('scopeUrl').value.trim();
                config.pipeline_id = document.getElementById('scopePipeline').value;
            }
            
            return config;
        }
        
        // Stream control
        async function startStream() {
            if (selectedSource === null) {
                showToast('Select an NDI source first', 'error');
                return;
            }
            
            const btn = document.getElementById('startBtn');
            btn.disabled = true;
            btn.textContent = 'Starting...';
            
            try {
                const resp = await fetch('/api/stream/start', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(getConfig())
                });
                const data = await resp.json();
                
                if (data.success) {
                    isStreaming = true;
                    setStatus('live', 'streaming');
                    showToast('Stream started');
                    
                    btn.style.display = 'none';
                    document.getElementById('updateBtn').disabled = false;
                    document.getElementById('stopBtn').disabled = false;
                    
                    document.getElementById('placeholder').style.display = 'none';
                    const frame = document.getElementById('outputFrame');
                    const relayUrl = data.relay_url || '/relay';
                    frame.src = relayUrl;
                    frame.style.display = 'block';
                    
                    // Show URL bar with full URL for OBS
                    const fullUrl = window.location.origin + '/relay';
                    document.getElementById('relayUrl').value = fullUrl;
                    document.getElementById('urlBar').style.display = 'flex';
                } else {
                    throw new Error(data.error || 'Failed');
                }
            } catch (e) {
                showToast('Error: ' + e.message, 'error');
                btn.disabled = false;
                btn.textContent = 'Start Stream';
            }
        }
        
        async function updateParams() {
            try {
                const resp = await fetch('/api/stream/update', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(getConfig())
                });
                const data = await resp.json();
                
                if (data.success) {
                    showToast('Parameters updated');
                } else {
                    throw new Error(data.error || 'Failed');
                }
            } catch (e) {
                showToast('Error: ' + e.message, 'error');
            }
        }
        
        async function stopStream() {
            try {
                await fetch('/api/stream/stop', { method: 'POST' });
                isStreaming = false;
                setStatus('', 'offline');
                showToast('Stream stopped');
                
                document.getElementById('startBtn').style.display = 'block';
                document.getElementById('startBtn').disabled = false;
                document.getElementById('startBtn').textContent = 'Start Stream';
                document.getElementById('updateBtn').disabled = true;
                document.getElementById('stopBtn').disabled = true;
                
                document.getElementById('outputFrame').style.display = 'none';
                document.getElementById('placeholder').style.display = 'block';
                document.getElementById('urlBar').style.display = 'none';
            } catch (e) {
                showToast('Error', 'error');
            }
        }
        
        function copyUrl() {
            const urlInput = document.getElementById('relayUrl');
            urlInput.select();
            navigator.clipboard.writeText(urlInput.value);
            showToast('URL copied to clipboard');
        }
        
        function openFullscreen() {
            const frame = document.getElementById('outputFrame');
            window.open(frame.src || '/relay', '_blank', 'width=512,height=512');
        }
        
        // Status polling
        async function pollStatus() {
            try {
                const resp = await fetch('/api/status');
                const data = await resp.json();
                
                if (data.streaming !== isStreaming) {
                    if (data.streaming) {
                        isStreaming = true;
                        setStatus('live', 'streaming');
                        document.getElementById('startBtn').style.display = 'none';
                        document.getElementById('updateBtn').disabled = false;
                        document.getElementById('stopBtn').disabled = false;
                    } else {
                        isStreaming = false;
                        setStatus('', 'offline');
                        document.getElementById('startBtn').style.display = 'block';
                        document.getElementById('startBtn').disabled = false;
                        document.getElementById('startBtn').textContent = 'Start Stream';
                        document.getElementById('updateBtn').disabled = true;
                        document.getElementById('stopBtn').disabled = true;
                    }
                }
            } catch (e) {}
        }
        
        // Init
        refreshSources();
        setInterval(pollStatus, 2000);
        setStatus('', 'ready');
    </script>
</body>
</html>
'''

