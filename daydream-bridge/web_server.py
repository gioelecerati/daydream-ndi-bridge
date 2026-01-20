"""
Local Web Server for Daydream Bridge
Handles:
- Serving the WebRTC relay page
- WebSocket for sending video frames
- WHIP/WHEP SDP proxy
"""

import http.server
import socketserver
import threading
import json
import secrets
import socket
from typing import Optional, Callable, Dict, Set
from urllib.parse import urlparse, parse_qs
import struct
import hashlib
import base64

from daydream_api import DaydreamAPI, StreamConfig
from control_panel import CONTROL_PANEL_HTML


def find_free_port() -> int:
    """Find an available port"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


class WebSocketHandler:
    """Simple WebSocket handler for frame streaming"""
    
    GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
    
    def __init__(self, request, client_address, server):
        self.request = request
        self.client_address = client_address
        self.server = server
        self.handshake_done = False
    
    @classmethod
    def is_websocket_request(cls, headers: Dict[str, str]) -> bool:
        return (
            headers.get('Upgrade', '').lower() == 'websocket' and
            'Sec-WebSocket-Key' in headers
        )
    
    def do_handshake(self, headers: Dict[str, str]) -> bytes:
        """Perform WebSocket handshake"""
        key = headers.get('Sec-WebSocket-Key', '')
        accept = base64.b64encode(
            hashlib.sha1((key + self.GUID).encode()).digest()
        ).decode()
        
        response = (
            "HTTP/1.1 101 Switching Protocols\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Accept: {accept}\r\n"
            "\r\n"
        )
        self.handshake_done = True
        return response.encode()
    
    @staticmethod
    def encode_frame(data: bytes, opcode: int = 0x02) -> bytes:
        """Encode a WebSocket frame (binary by default)"""
        length = len(data)
        
        if length <= 125:
            header = struct.pack('BB', 0x80 | opcode, length)
        elif length <= 65535:
            header = struct.pack('!BBH', 0x80 | opcode, 126, length)
        else:
            header = struct.pack('!BBQ', 0x80 | opcode, 127, length)
        
        return header + data
    
    @staticmethod
    def decode_frame(data: bytes) -> tuple:
        """Decode a WebSocket frame, returns (opcode, payload, consumed)"""
        if len(data) < 2:
            return None, None, 0
        
        opcode = data[0] & 0x0F
        masked = bool(data[1] & 0x80)
        length = data[1] & 0x7F
        
        offset = 2
        if length == 126:
            if len(data) < 4:
                return None, None, 0
            length = struct.unpack('!H', data[2:4])[0]
            offset = 4
        elif length == 127:
            if len(data) < 10:
                return None, None, 0
            length = struct.unpack('!Q', data[2:10])[0]
            offset = 10
        
        if masked:
            if len(data) < offset + 4:
                return None, None, 0
            mask = data[offset:offset+4]
            offset += 4
        
        if len(data) < offset + length:
            return None, None, 0
        
        payload = data[offset:offset+length]
        
        if masked:
            payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        
        return opcode, payload, offset + length


class DaydreamHTTPHandler(http.server.BaseHTTPRequestHandler):
    """HTTP handler for the Daydream bridge server"""
    
    protocol_version = 'HTTP/1.1'
    
    def log_message(self, format, *args):
        # Quieter logging
        pass
    
    def _send_cors_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
    
    def do_OPTIONS(self):
        self.send_response(204)
        self._send_cors_headers()
        self.end_headers()
    
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        
        if path == '/':
            self._serve_control_panel()
        elif path == '/relay' or path == '/relay.html':
            self._serve_relay_html()
        elif path == '/status':
            self._serve_status()
        elif path == '/api/status':
            self._serve_api_status()
        elif path == '/api/sources':
            self._serve_ndi_sources()
        elif path.startswith('/whip/result/'):
            self._serve_whip_result(path.split('/whip/result/')[-1])
        elif path.startswith('/whep/result/'):
            self._serve_whep_result(path.split('/whep/result/')[-1])
        elif path == '/ws':
            self._handle_websocket_upgrade()
        else:
            self.send_error(404)
    
    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length) if content_length > 0 else b''
        
        if path == '/whip':
            self._handle_whip_proxy(body)
        elif path == '/whep':
            self._handle_whep_proxy(body)
        elif path == '/api/stream/start':
            self._handle_stream_start(body)
        elif path == '/api/stream/update':
            self._handle_stream_update(body)
        elif path == '/api/stream/stop':
            self._handle_stream_stop()
        else:
            self.send_error(404)
    
    def _serve_relay_html(self):
        """Serve the WebRTC relay HTML page"""
        html = self.server.get_relay_html()
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', len(html))
        self.end_headers()
        self.wfile.write(html)
    
    def _serve_control_panel(self):
        """Serve the control panel HTML page"""
        html = CONTROL_PANEL_HTML.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', len(html))
        self.end_headers()
        self.wfile.write(html)
    
    def _serve_api_status(self):
        """Serve API status (JSON)"""
        status = {
            'connected': True,
            'streaming': self.server.state == "STREAMING",
            'stream_id': self.server.stream_id,
        }
        data = json.dumps(status).encode()
        self.send_response(200)
        self._send_cors_headers()
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', len(data))
        self.end_headers()
        self.wfile.write(data)
    
    def _serve_ndi_sources(self):
        """Serve list of NDI sources"""
        sources = []
        if hasattr(self.server, 'bridge') and self.server.bridge:
            bridge = self.server.bridge
            if hasattr(bridge, 'ndi_sources'):
                sources = [{'name': s['name'], 'url': s.get('url', '')} for s in bridge.ndi_sources]
        
        data = json.dumps({'sources': sources}).encode()
        self.send_response(200)
        self._send_cors_headers()
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', len(data))
        self.end_headers()
        self.wfile.write(data)
    
    def _handle_stream_start(self, body: bytes):
        """Start streaming with given config"""
        try:
            params = json.loads(body.decode('utf-8')) if body else {}
            
            if not hasattr(self.server, 'bridge') or not self.server.bridge:
                raise ValueError("Bridge not initialized")
            
            bridge = self.server.bridge
            
            # Update config
            bridge.config.prompt = params.get('prompt', bridge.config.prompt)
            bridge.config.negative_prompt = params.get('negative_prompt', bridge.config.negative_prompt)
            bridge.config.model_id = params.get('model_id', bridge.config.model_id)
            bridge.config.delta = params.get('delta', bridge.config.delta)
            bridge.config.depth_scale = params.get('depth_scale', bridge.config.depth_scale)
            bridge.config.canny_scale = params.get('canny_scale', bridge.config.canny_scale)
            bridge.config.tile_scale = params.get('tile_scale', bridge.config.tile_scale)
            
            # Select NDI source
            source_index = params.get('source_index')
            if source_index is not None and bridge.ndi_sources:
                if 0 <= source_index < len(bridge.ndi_sources):
                    selected = bridge.ndi_sources[source_index]
                    if bridge.ndi_receiver:
                        bridge.ndi_receiver.connect(selected)
            
            # Start streaming
            bridge._start_streaming('ndi')
            
            port = self.server.server_address[1]
            
            response = {
                'success': True,
                'stream_id': bridge.stream.id if bridge.stream else None,
                'relay_url': f'/relay'
            }
            
        except Exception as e:
            response = {'success': False, 'error': str(e)}
        
        data = json.dumps(response).encode()
        self.send_response(200)
        self._send_cors_headers()
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', len(data))
        self.end_headers()
        self.wfile.write(data)
    
    def _handle_stream_update(self, body: bytes):
        """Update stream parameters"""
        try:
            params = json.loads(body.decode('utf-8')) if body else {}
            
            if not hasattr(self.server, 'bridge') or not self.server.bridge:
                raise ValueError("Bridge not initialized")
            
            bridge = self.server.bridge
            
            # Update config
            bridge.config.prompt = params.get('prompt', bridge.config.prompt)
            bridge.config.negative_prompt = params.get('negative_prompt', bridge.config.negative_prompt)
            bridge.config.model_id = params.get('model_id', bridge.config.model_id)
            bridge.config.delta = params.get('delta', bridge.config.delta)
            bridge.config.depth_scale = params.get('depth_scale', bridge.config.depth_scale)
            bridge.config.canny_scale = params.get('canny_scale', bridge.config.canny_scale)
            bridge.config.tile_scale = params.get('tile_scale', bridge.config.tile_scale)
            
            print(f"📝 Updating params: prompt='{bridge.config.prompt[:30]}...', delta={bridge.config.delta}")
            
            # Update on Daydream
            if bridge.streaming and bridge.stream:
                success = bridge.api.update_stream(bridge.stream.id, bridge.config)
                if not success:
                    raise ValueError("API update failed")
            else:
                print("⚠ Not streaming, config saved for next stream")
            
            response = {'success': True}
            
        except Exception as e:
            print(f"✗ Update error: {e}")
            response = {'success': False, 'error': str(e)}
        
        data = json.dumps(response).encode()
        self.send_response(200)
        self._send_cors_headers()
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', len(data))
        self.end_headers()
        self.wfile.write(data)
    
    def _handle_stream_stop(self):
        """Stop streaming"""
        try:
            if hasattr(self.server, 'bridge') and self.server.bridge:
                self.server.bridge._stop_streaming()
            response = {'success': True}
        except Exception as e:
            response = {'success': False, 'error': str(e)}
        
        data = json.dumps(response).encode()
        self.send_response(200)
        self._send_cors_headers()
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', len(data))
        self.end_headers()
        self.wfile.write(data)
    
    def _serve_status(self):
        """Serve current stream status"""
        status = {
            'state': self.server.state,
            'stream_id': self.server.stream_id,
            'whip_url': self.server.whip_url,
            'whep_url': self.server.whep_url
        }
        data = json.dumps(status).encode()
        self.send_response(200)
        self._send_cors_headers()
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', len(data))
        self.end_headers()
        self.wfile.write(data)
    
    def _handle_whip_proxy(self, body: bytes):
        """Proxy WHIP offer to Daydream and return answer"""
        if not self.server.whip_url:
            self.send_error(400, "No WHIP URL available")
            return
        
        offer_sdp = body.decode('utf-8')
        request_id = secrets.token_urlsafe(8)
        
        # Store request for async processing
        self.server.whip_requests[request_id] = {
            'status': 'pending',
            'offer': offer_sdp,
            'answer': None,
            'error': None
        }
        
        # Process in background
        def exchange_async():
            try:
                answer_sdp, headers = self.server.api.exchange_sdp(
                    self.server.whip_url, 
                    offer_sdp,
                    timeout=10
                )
                
                # Extract WHEP URL from response headers
                for k, v in headers.items():
                    if k.lower() == 'livepeer-playback-url':
                        self.server.whep_url = v
                        print(f"✓ Got WHEP URL: {v}")
                        break
                
                self.server.whip_requests[request_id]['answer'] = answer_sdp
                self.server.whip_requests[request_id]['status'] = 'ready'
                
            except Exception as e:
                print(f"WHIP proxy error: {e}")
                self.server.whip_requests[request_id]['error'] = str(e)
                self.server.whip_requests[request_id]['status'] = 'error'
        
        threading.Thread(target=exchange_async, daemon=True).start()
        
        # Return request ID for polling
        response = json.dumps({'id': request_id}).encode()
        self.send_response(202)
        self._send_cors_headers()
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', len(response))
        self.end_headers()
        self.wfile.write(response)
    
    def _serve_whip_result(self, request_id: str):
        """Serve WHIP result (polling)"""
        req_data = self.server.whip_requests.get(request_id)
        
        if not req_data:
            self.send_error(404, "Request not found")
            return
        
        if req_data['status'] == 'pending':
            response = json.dumps({'status': 'pending'}).encode()
            self.send_response(202)
            self._send_cors_headers()
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', len(response))
            self.end_headers()
            self.wfile.write(response)
        elif req_data['status'] == 'ready':
            answer = req_data['answer'].encode()
            self.send_response(200)
            self._send_cors_headers()
            self.send_header('Content-Type', 'application/sdp')
            self.send_header('Content-Length', len(answer))
            self.end_headers()
            self.wfile.write(answer)
            del self.server.whip_requests[request_id]
        else:
            error = (req_data['error'] or 'Unknown error').encode()
            self.send_response(500)
            self._send_cors_headers()
            self.send_header('Content-Type', 'text/plain')
            self.send_header('Content-Length', len(error))
            self.end_headers()
            self.wfile.write(error)
            del self.server.whip_requests[request_id]
    
    def _handle_whep_proxy(self, body: bytes):
        """Proxy WHEP offer"""
        if not self.server.whep_url:
            self.send_error(404, "No WHEP URL available yet")
            return
        
        offer_sdp = body.decode('utf-8')
        request_id = secrets.token_urlsafe(8)
        
        self.server.whep_requests[request_id] = {
            'status': 'pending',
            'offer': offer_sdp,
            'answer': None,
            'error': None
        }
        
        def exchange_async():
            try:
                answer_sdp, _ = self.server.api.exchange_sdp(
                    self.server.whep_url,
                    offer_sdp,
                    timeout=5
                )
                self.server.whep_requests[request_id]['answer'] = answer_sdp
                self.server.whep_requests[request_id]['status'] = 'ready'
            except Exception as e:
                self.server.whep_requests[request_id]['error'] = str(e)
                self.server.whep_requests[request_id]['status'] = 'error'
        
        threading.Thread(target=exchange_async, daemon=True).start()
        
        response = json.dumps({'id': request_id}).encode()
        self.send_response(202)
        self._send_cors_headers()
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', len(response))
        self.end_headers()
        self.wfile.write(response)
    
    def _serve_whep_result(self, request_id: str):
        """Serve WHEP result (polling)"""
        req_data = self.server.whep_requests.get(request_id)
        
        if not req_data:
            self.send_error(404, "Request not found")
            return
        
        if req_data['status'] == 'pending':
            response = json.dumps({'status': 'pending'}).encode()
            self.send_response(202)
            self._send_cors_headers()
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', len(response))
            self.end_headers()
            self.wfile.write(response)
        elif req_data['status'] == 'ready':
            answer = req_data['answer'].encode()
            self.send_response(200)
            self._send_cors_headers()
            self.send_header('Content-Type', 'application/sdp')
            self.send_header('Content-Length', len(answer))
            self.end_headers()
            self.wfile.write(answer)
            del self.server.whep_requests[request_id]
        else:
            error = (req_data['error'] or 'Unknown error').encode()
            self.send_response(500)
            self._send_cors_headers()
            self.send_header('Content-Type', 'text/plain')
            self.send_header('Content-Length', len(error))
            self.end_headers()
            self.wfile.write(error)
            del self.server.whep_requests[request_id]
    
    def _handle_websocket_upgrade(self):
        """Upgrade connection to WebSocket"""
        headers = {k: v for k, v in self.headers.items()}
        
        if not WebSocketHandler.is_websocket_request(headers):
            self.send_error(400, "Not a WebSocket request")
            return
        
        ws = WebSocketHandler(self.request, self.client_address, self.server)
        handshake = ws.do_handshake(headers)
        self.wfile.write(handshake)
        
        # Register client
        self.server.ws_clients.add(self.request)
        print(f"WebSocket client connected ({len(self.server.ws_clients)} total)")
        
        try:
            # Keep connection open
            buffer = b''
            while True:
                try:
                    data = self.request.recv(4096)
                    if not data:
                        break
                    buffer += data
                    
                    while buffer:
                        opcode, payload, consumed = WebSocketHandler.decode_frame(buffer)
                        if opcode is None:
                            break
                        buffer = buffer[consumed:]
                        
                        if opcode == 0x08:  # Close
                            break
                        elif opcode == 0x09:  # Ping
                            pong = WebSocketHandler.encode_frame(payload, 0x0A)
                            self.request.sendall(pong)
                except:
                    break
        finally:
            self.server.ws_clients.discard(self.request)
            print(f"WebSocket client disconnected ({len(self.server.ws_clients)} total)")


class DaydreamServer(socketserver.ThreadingTCPServer):
    """Multi-threaded server for Daydream bridge"""
    
    allow_reuse_address = True
    daemon_threads = True
    
    def __init__(self, port: int, api: DaydreamAPI, sdp_port: int):
        super().__init__(('127.0.0.1', port), DaydreamHTTPHandler)
        
        self.api = api
        self.sdp_port = sdp_port
        
        # Reference to bridge (set after creation)
        self.bridge = None
        
        # Stream state
        self.state = "IDLE"
        self.stream_id = None
        self.whip_url = None
        self.whep_url = None
        
        # Request tracking
        self.whip_requests: Dict[str, dict] = {}
        self.whep_requests: Dict[str, dict] = {}
        
        # WebSocket clients
        self.ws_clients: Set = set()
        self._ws_lock = threading.Lock()
        
        # Relay HTML cache
        self._relay_html_cache = None
    
    def get_relay_html(self) -> bytes:
        """Get the relay HTML page with SDP port substituted"""
        if self._relay_html_cache is None:
            self._relay_html_cache = RELAY_HTML.replace(
                '{{SDP_PORT}}', str(self.sdp_port)
            ).encode('utf-8')
        return self._relay_html_cache
    
    def broadcast_frame(self, jpeg_data: bytes):
        """Send a JPEG frame to all connected WebSocket clients"""
        with self._ws_lock:
            clients = list(self.ws_clients)
        
        if not clients:
            return
        
        frame = WebSocketHandler.encode_frame(jpeg_data, 0x02)  # Binary
        
        dead_clients = []
        for client in clients:
            try:
                client.sendall(frame)
            except:
                dead_clients.append(client)
        
        if dead_clients:
            with self._ws_lock:
                for client in dead_clients:
                    self.ws_clients.discard(client)
    
    def set_stream_info(self, stream_id: str, whip_url: str):
        """Update stream information"""
        self.stream_id = stream_id
        self.whip_url = whip_url
        self.state = "STREAMING"
    
    def clear_stream_info(self):
        """Clear stream information"""
        self.stream_id = None
        self.whip_url = None
        self.whep_url = None
        self.state = "IDLE"


# Minimal relay HTML - handles WebRTC WHIP/WHEP
RELAY_HTML = '''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Daydream VDJ Bridge</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            background: #0a0a0a; 
            width: 512px; 
            height: 512px; 
            overflow: hidden;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        }
        #output-video {
            width: 512px;
            height: 512px;
            object-fit: cover;
            display: block;
        }
        #input-canvas { display: none; }
        #status {
            position: absolute;
            inset: 0;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            pointer-events: none;
            transition: opacity 0.5s;
        }
        #status.hidden { opacity: 0; }
        #status-text {
            color: rgba(255,255,255,0.9);
            font-size: 18px;
            font-weight: 500;
            text-shadow: 0 2px 8px rgba(0,0,0,0.8);
        }
        .spinner {
            width: 40px;
            height: 40px;
            border: 3px solid rgba(255,255,255,0.2);
            border-top-color: #fff;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin-bottom: 16px;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
    </style>
</head>
<body>
    <video id="output-video" autoplay playsinline muted></video>
    <canvas id="input-canvas" width="512" height="512"></canvas>
    <div id="status">
        <div class="spinner"></div>
        <div id="status-text">Connecting...</div>
    </div>
    
    <script>
        const SDP_PORT = '{{SDP_PORT}}';
        const WS_URL = `ws://${location.host}/ws`;
        const WHIP_URL = `http://${location.hostname}:${SDP_PORT}/whip`;
        const WHEP_URL = `http://${location.hostname}:${SDP_PORT}/whep`;
        
        const canvas = document.getElementById('input-canvas');
        const ctx = canvas.getContext('2d');
        const video = document.getElementById('output-video');
        const statusEl = document.getElementById('status');
        const statusText = document.getElementById('status-text');
        
        let ws = null;
        let whipPc = null;
        let whepPc = null;
        let canvasStream = null;
        let pendingBitmap = null;
        let processingBitmap = null;
        
        function setStatus(text) {
            statusText.textContent = text;
            console.log('[Relay]', text);
        }
        
        function hideStatus() {
            statusEl.classList.add('hidden');
        }
        
        // WebSocket for receiving frames
        function connectWebSocket() {
            ws = new WebSocket(WS_URL);
            ws.binaryType = 'arraybuffer';
            
            ws.onopen = () => {
                console.log('[Relay] WebSocket connected');
                pollStatus();
            };
            
            ws.onmessage = (e) => {
                if (e.data instanceof ArrayBuffer) {
                    pendingBitmap = e.data;
                    processFrame();
                }
            };
            
            ws.onclose = () => {
                console.log('[Relay] WebSocket closed, reconnecting...');
                setTimeout(connectWebSocket, 1000);
            };
        }
        
        function processFrame() {
            if (!pendingBitmap || processingBitmap) return;
            
            const data = pendingBitmap;
            pendingBitmap = null;
            processingBitmap = true;
            
            createImageBitmap(new Blob([data], { type: 'image/jpeg' }))
                .then(bitmap => {
                    ctx.drawImage(bitmap, 0, 0, 512, 512);
                    bitmap.close();
                })
                .catch(() => {})
                .finally(() => {
                    processingBitmap = false;
                    if (pendingBitmap) processFrame();
                });
        }
        
        // Poll server status
        async function pollStatus() {
            try {
                const resp = await fetch('/status');
                const status = await resp.json();
                
                if (status.state === 'STREAMING' && status.whip_url) {
                    setStatus('Starting WHIP...');
                    await startWHIP();
                } else {
                    setTimeout(pollStatus, 500);
                }
            } catch (e) {
                setTimeout(pollStatus, 1000);
            }
        }
        
        // WHIP connection
        async function startWHIP() {
            canvasStream = canvas.captureStream(30);
            const videoTrack = canvasStream.getVideoTracks()[0];
            
            whipPc = new RTCPeerConnection({
                iceServers: [{ urls: 'stun:stun.l.google.com:19302' }]
            });
            
            const transceiver = whipPc.addTransceiver(videoTrack, { direction: 'sendonly' });
            setH264Preference(transceiver);
            
            whipPc.oniceconnectionstatechange = () => {
                console.log('[Relay] WHIP ICE:', whipPc.iceConnectionState);
                if (whipPc.iceConnectionState === 'connected') {
                    setStatus('Connected! Waiting for AI...');
                    startWHEP();
                }
            };
            
            const offer = await whipPc.createOffer();
            await whipPc.setLocalDescription(offer);
            
            // Send offer and poll for answer
            const resp = await fetch(WHIP_URL, {
                method: 'POST',
                headers: { 'Content-Type': 'application/sdp' },
                body: whipPc.localDescription.sdp
            });
            
            if (resp.status === 202) {
                const { id } = await resp.json();
                await pollWHIPResult(id);
            } else if (resp.ok) {
                const answer = await resp.text();
                await whipPc.setRemoteDescription({ type: 'answer', sdp: answer });
            }
        }
        
        async function pollWHIPResult(requestId) {
            while (true) {
                const resp = await fetch(`http://${location.hostname}:${SDP_PORT}/whip/result/${requestId}`);
                
                if (resp.status === 202) {
                    await new Promise(r => setTimeout(r, 100));
                    continue;
                }
                
                if (resp.ok) {
                    const answer = await resp.text();
                    await whipPc.setRemoteDescription({ type: 'answer', sdp: answer });
                    return;
                }
                
                throw new Error('WHIP failed');
            }
        }
        
        function setH264Preference(transceiver) {
            if (!transceiver.setCodecPreferences) return;
            try {
                const caps = RTCRtpSender.getCapabilities('video');
                if (!caps?.codecs?.length) return;
                const h264 = caps.codecs.filter(c => c.mimeType.toLowerCase().includes('h264'));
                if (h264.length) transceiver.setCodecPreferences(h264);
            } catch (e) {}
        }
        
        // WHEP connection (receive AI output)
        async function startWHEP() {
            let retries = 0;
            const maxRetries = 30;
            
            while (retries < maxRetries) {
                try {
                    whepPc = new RTCPeerConnection({
                        iceServers: [{ urls: 'stun:stun.l.google.com:19302' }]
                    });
                    
                    whepPc.ontrack = (e) => {
                        console.log('[Relay] WHEP track:', e.track.kind);
                        if (e.track.kind === 'video') {
                            video.srcObject = e.streams[0] || new MediaStream([e.track]);
                        }
                    };
                    
                    whepPc.addTransceiver('video', { direction: 'recvonly' });
                    whepPc.addTransceiver('audio', { direction: 'recvonly' });
                    
                    const offer = await whepPc.createOffer();
                    await whepPc.setLocalDescription(offer);
                    
                    const resp = await fetch(WHEP_URL, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/sdp' },
                        body: whepPc.localDescription.sdp
                    });
                    
                    if (resp.status === 202) {
                        const { id } = await resp.json();
                        await pollWHEPResult(id);
                        return;
                    } else if (resp.ok) {
                        const answer = await resp.text();
                        await whepPc.setRemoteDescription({ type: 'answer', sdp: answer });
                        return;
                    }
                    
                    throw new Error('WHEP not ready');
                } catch (e) {
                    retries++;
                    await new Promise(r => setTimeout(r, 200));
                }
            }
        }
        
        async function pollWHEPResult(requestId) {
            while (true) {
                const resp = await fetch(`http://${location.hostname}:${SDP_PORT}/whep/result/${requestId}`);
                
                if (resp.status === 202) {
                    await new Promise(r => setTimeout(r, 100));
                    continue;
                }
                
                if (resp.ok) {
                    const answer = await resp.text();
                    await whepPc.setRemoteDescription({ type: 'answer', sdp: answer });
                    return;
                }
                
                throw new Error('WHEP failed');
            }
        }
        
        // When video starts playing
        video.onplaying = () => {
            console.log('[Relay] Video playing!');
            hideStatus();
        };
        
        // Start
        ctx.fillStyle = '#000';
        ctx.fillRect(0, 0, 512, 512);
        connectWebSocket();
    </script>
</body>
</html>
'''


if __name__ == '__main__':
    from daydream_api import DaydreamAPI
    
    api = DaydreamAPI()
    port = find_free_port()
    sdp_port = find_free_port()
    
    server = DaydreamServer(port, api, sdp_port)
    
    print(f"Server running on http://localhost:{port}")
    print(f"SDP proxy on port {sdp_port}")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()

