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
        </div>
        
        <div class="controls-panel">
            <div class="controls-header">Controls</div>
            <div class="controls-scroll">
                
                <div class="section">
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
                
                <div class="section">
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
            return {
                prompt: document.getElementById('prompt').value,
                negative_prompt: document.getElementById('negativePrompt').value,
                model_id: document.getElementById('modelId').value,
                guidance_scale: parseFloat(document.getElementById('guidance').value),
                delta: parseFloat(document.getElementById('delta').value),
                depth_scale: parseFloat(document.getElementById('depthScale').value),
                canny_scale: parseFloat(document.getElementById('cannyScale').value),
                tile_scale: parseFloat(document.getElementById('tileScale').value),
                source_index: selectedSource
            };
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
                    frame.src = data.relay_url || '/relay';
                    frame.style.display = 'block';
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
            } catch (e) {
                showToast('Error', 'error');
            }
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

