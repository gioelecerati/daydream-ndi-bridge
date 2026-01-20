#!/usr/bin/env python3
"""
Daydream Bridge
Captures video from any NDI source and streams to Daydream AI

Usage:
    python app.py
"""

import sys
import os
import threading
import time
import webbrowser
from io import BytesIO
from typing import Optional, List

# Check for required modules
try:
    from PIL import Image
    import numpy as np
except ImportError:
    print("Installing required packages...")
    os.system(f"{sys.executable} -m pip install pillow numpy")
    from PIL import Image
    import numpy as np

from daydream_api import DaydreamAPI, StreamConfig, StreamInfo
from web_server import DaydreamServer, find_free_port

# Try to import NDI
NDI_AVAILABLE = False
ndi_client = None
try:
    from ndi_client import NDIClient
    ndi_client = NDIClient()
    NDI_AVAILABLE = True
    print("✓ NDI initialized")
except RuntimeError as e:
    print(f"⚠ NDI runtime not found")
    print(f"  {e}")
except Exception as e:
    print(f"⚠ NDI error: {e}")

# Try to import screen capture (macOS fallback)
SCREEN_CAPTURE_AVAILABLE = False
try:
    from Quartz import (
        CGWindowListCopyWindowInfo, kCGWindowListOptionOnScreenOnly, kCGNullWindowID,
        CGWindowListCreateImage, kCGWindowImageDefault, CGRectNull,
        CGImageGetWidth, CGImageGetHeight, CGImageGetDataProvider, CGDataProviderCopyData
    )
    SCREEN_CAPTURE_AVAILABLE = True
    print("✓ Screen capture available (fallback)")
except ImportError:
    pass


class NDIReceiver:
    """Receives video frames from an NDI source using our pure Python client"""
    
    def __init__(self, client):
        self.client = client
        self.source = None
        self.running = False
    
    def find_sources(self, timeout_ms: int = 5000) -> List[dict]:
        """Find available NDI sources on the network"""
        if not self.client:
            return []
        
        sources = []
        try:
            ndi_sources = self.client.find_sources(timeout_ms=timeout_ms)
            
            for src in ndi_sources:
                sources.append({
                    'name': src.name,
                    'url': src.url,
                    'source': src
                })
            
        except Exception as e:
            print(f"Error finding NDI sources: {e}")
        
        return sources
    
    def connect(self, source: dict) -> bool:
        """Connect to an NDI source"""
        if not self.client:
            return False
        
        try:
            ndi_source = source['source']
            
            if self.client.connect(ndi_source):
                self.source = ndi_source
                self.running = True
                print(f"✓ Connected to NDI source: {source['name']}")
                return True
            
        except Exception as e:
            print(f"Error connecting to NDI: {e}")
        
        return False
    
    def get_frame(self, timeout_ms: int = 100) -> Optional[np.ndarray]:
        """Get a video frame from the NDI source"""
        if not self.client or not self.running:
            return None
        
        try:
            frame = self.client.capture_video_frame(timeout_ms=timeout_ms)
            
            if frame is not None:
                # Convert RGBA to RGB
                return frame[:, :, :3]
        
        except Exception as e:
            if self.running:
                print(f"NDI frame error: {e}")
        
        return None
    
    def disconnect(self):
        """Disconnect from NDI source"""
        self.running = False
        
        if self.client:
            self.client.disconnect()
        
        self.source = None


class DaydreamBridge:
    """Main application class"""
    
    def __init__(self):
        self.api = DaydreamAPI()
        self.config = StreamConfig()
        self.stream: Optional[StreamInfo] = None
        
        # Server ports
        self.http_port = find_free_port()
        self.sdp_port = find_free_port()
        self.auth_port = find_free_port()
        
        # Servers
        self.server: Optional[DaydreamServer] = None
        self.sdp_server: Optional[DaydreamServer] = None
        self.auth_server = None
        
        # State
        self.running = False
        self.streaming = False
        self.frame_count = 0
        self.capture_mode = 'test'
        self.capture_window_id = None
        
        # NDI
        self.ndi_receiver = NDIReceiver(ndi_client) if NDI_AVAILABLE else None
        self.ndi_sources = []
    
    def start(self, open_browser: bool = True, use_cli: bool = False):
        """Start the bridge"""
        print("\n" + "="*50)
        print("  Daydream Bridge")
        print("="*50)
        
        # Check login
        if not self.api.is_logged_in:
            print("\n⚠ Not logged in to Daydream")
            self._start_login_flow()
            return
        
        print(f"\n✓ Logged in to Daydream")
        
        # Start servers
        self._start_servers()
        
        # Scan for NDI sources
        if NDI_AVAILABLE:
            self._scan_ndi_sources()
        
        # Open control panel in browser
        if open_browser:
            print(f"\n🌐 Opening control panel in browser...")
            webbrowser.open(f"http://localhost:{self.http_port}")
        
        # Show menu or keep running
        if use_cli:
            self._show_menu()
        else:
            self._run_headless()
    
    def _start_login_flow(self):
        """Start OAuth login flow"""
        print("\nStarting login flow...")
        
        auth_state = self.api.create_auth_state()
        
        from http.server import HTTPServer, BaseHTTPRequestHandler
        from urllib.parse import urlparse, parse_qs
        
        bridge = self
        
        class AuthHandler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            
            def do_GET(self):
                parsed = urlparse(self.path)
                params = parse_qs(parsed.query)
                
                token = params.get('token', [None])[0]
                state = params.get('state', [None])[0]
                
                if not token:
                    self.send_response(400)
                    self.end_headers()
                    self.wfile.write(b"No token received")
                    return
                
                if not bridge.api.consume_auth_state(state):
                    self.send_response(400)
                    self.end_headers()
                    self.wfile.write(b"Invalid state")
                    return
                
                try:
                    bridge.api.create_api_key_from_jwt(token)
                    
                    self.send_response(302)
                    self.send_header('Location', 'https://app.daydream.live/sign-in/local/success')
                    self.end_headers()
                    
                    print("\n✓ Login successful!")
                    threading.Thread(target=bridge._login_complete, daemon=True).start()
                    
                except Exception as e:
                    self.send_response(500)
                    self.end_headers()
                    self.wfile.write(f"Error: {e}".encode())
        
        self.auth_server = HTTPServer(('127.0.0.1', self.auth_port), AuthHandler)
        threading.Thread(target=self.auth_server.serve_forever, daemon=True).start()
        
        auth_url = f"https://app.daydream.live/sign-in/local?port={self.auth_port}&state={auth_state}"
        print(f"\nOpening browser for login...")
        webbrowser.open(auth_url)
        
        print("\nWaiting for login... (Press Ctrl+C to cancel)")
        
        try:
            while not self.api.is_logged_in:
                time.sleep(0.5)
        except KeyboardInterrupt:
            print("\nLogin cancelled.")
    
    def _login_complete(self):
        time.sleep(1)
        if self.auth_server:
            self.auth_server.shutdown()
        self.start()
    
    def _start_servers(self):
        """Start HTTP and SDP proxy servers"""
        print(f"\nStarting servers...")
        
        self.server = DaydreamServer(self.http_port, self.api, self.sdp_port)
        self.server.bridge = self  # Connect server to bridge
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        
        self.sdp_server = DaydreamServer(self.sdp_port, self.api, self.sdp_port)
        self.sdp_server.bridge = self  # Connect server to bridge
        threading.Thread(target=self.sdp_server.serve_forever, daemon=True).start()
        
        print(f"  Control Panel: http://localhost:{self.http_port}")
        print(f"  Relay page: http://localhost:{self.http_port}/relay")
    
    def _scan_ndi_sources(self):
        """Scan for NDI sources"""
        if not self.ndi_receiver:
            return
        
        print("\nScanning for NDI sources...")
        self.ndi_sources = self.ndi_receiver.find_sources(timeout_ms=3000)
        
        if self.ndi_sources:
            print(f"Found {len(self.ndi_sources)} source(s):")
            for i, src in enumerate(self.ndi_sources):
                print(f"  {i+1}. {src['name']}")
        else:
            print("No NDI sources found")
    
    def _run_headless(self):
        """Run without CLI menu (web UI only)"""
        print("\n" + "-"*50)
        print("Control panel is running at:")
        print(f"  → http://localhost:{self.http_port}")
        print("-"*50)
        print("\nPress Ctrl+C to quit\n")
        
        self.running = True
        
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            self._stop_streaming()
            if NDI_AVAILABLE and ndi_client:
                ndi_client.close()
            print("\nGoodbye!")
    
    def _show_menu(self):
        """Show interactive menu"""
        print("\n" + "-"*50)
        print("Commands:")
        print("  1. Start streaming (test pattern)")
        if NDI_AVAILABLE:
            print("  2. Start streaming from NDI")
            print("  3. Rescan NDI sources")
        if SCREEN_CAPTURE_AVAILABLE:
            print("  w. Start streaming from window capture")
        print("  p. Configure prompt")
        print("  o. Open output in browser")
        print("  s. Stop streaming")
        print("  q. Quit")
        print("-"*50)
        
        self.running = True
        
        while self.running:
            try:
                cmd = input("\n> ").strip().lower()
                
                if cmd == '1':
                    self._start_streaming('test')
                elif cmd == '2' and NDI_AVAILABLE:
                    self._select_ndi_and_stream()
                elif cmd == '3' and NDI_AVAILABLE:
                    self._scan_ndi_sources()
                elif cmd == 'w' and SCREEN_CAPTURE_AVAILABLE:
                    self._select_window_and_stream()
                elif cmd == 'p':
                    self._configure_prompt()
                elif cmd == 'o':
                    webbrowser.open(f"http://localhost:{self.http_port}")
                elif cmd == 's':
                    self._stop_streaming()
                elif cmd == 'q':
                    self._stop_streaming()
                    self.running = False
                    if NDI_AVAILABLE and ndi_client:
                        ndi_client.close()
                    print("\nGoodbye!")
                else:
                    print("Unknown command")
            
            except KeyboardInterrupt:
                self._stop_streaming()
                self.running = False
                print("\nGoodbye!")
    
    def _select_ndi_and_stream(self):
        """Let user select an NDI source"""
        if not self.ndi_sources:
            print("\nNo NDI sources found. Rescanning...")
            self._scan_ndi_sources()
            if not self.ndi_sources:
                return
        
        print("\n" + "-"*50)
        print("Select NDI source:")
        print("-"*50)
        
        for i, src in enumerate(self.ndi_sources):
            print(f"  {i+1}. {src['name']}")
        
        print("\nEnter number (or 0 to cancel): ", end="")
        try:
            choice = int(input().strip())
            if choice == 0:
                return
            if 1 <= choice <= len(self.ndi_sources):
                selected = self.ndi_sources[choice - 1]
                if self.ndi_receiver.connect(selected):
                    self._start_streaming('ndi')
            else:
                print("Invalid selection")
        except ValueError:
            print("Invalid input")
    
    def _select_window_and_stream(self):
        """Let user select a window to capture"""
        windows = self._list_windows()
        all_windows = windows[:15]
        
        if not all_windows:
            print("No windows found!")
            return
        
        print("\n" + "-"*50)
        print("Select window:")
        print("-"*50)
        
        for i, w in enumerate(all_windows):
            print(f"  {i+1}. {w['owner']}: {w['name']} ({w['width']}x{w['height']})")
        
        print("\nEnter number (or 0 to cancel): ", end="")
        try:
            choice = int(input().strip())
            if choice == 0:
                return
            if 1 <= choice <= len(all_windows):
                self.capture_window_id = all_windows[choice - 1]['id']
                self._start_streaming('window')
            else:
                print("Invalid selection")
        except ValueError:
            print("Invalid input")
    
    def _list_windows(self) -> List[dict]:
        """List available windows for capture"""
        if not SCREEN_CAPTURE_AVAILABLE:
            return []
        
        try:
            windows = CGWindowListCopyWindowInfo(kCGWindowListOptionOnScreenOnly, kCGNullWindowID)
            
            result = []
            for window in windows:
                name = window.get('kCGWindowName', '')
                owner = window.get('kCGWindowOwnerName', '')
                window_id = window.get('kCGWindowNumber', 0)
                bounds = window.get('kCGWindowBounds', {})
                width = bounds.get('Width', 0)
                height = bounds.get('Height', 0)
                
                if width > 100 and height > 100 and (name or owner):
                    result.append({
                        'id': window_id,
                        'name': name or '(unnamed)',
                        'owner': owner,
                        'width': int(width),
                        'height': int(height)
                    })
            
            return result
        except:
            return []
    
    def _configure_prompt(self):
        """Configure the AI prompt"""
        print(f"\nCurrent prompt: {self.config.prompt}")
        new_prompt = input("New prompt (or Enter to keep): ").strip()
        
        if new_prompt:
            self.config.prompt = new_prompt
            print(f"✓ Prompt updated")
            
            if self.streaming and self.stream:
                self.api.update_stream(self.stream.id, self.config)
                print("✓ Stream parameters updated")
    
    def _start_streaming(self, capture_mode: str = 'test'):
        """Start streaming to Daydream"""
        if self.streaming:
            print("Already streaming. Stop first with 's'")
            return
        
        print("\nCreating stream...")
        
        try:
            self.stream = self.api.create_stream(self.config)
            
            self.server.set_stream_info(self.stream.id, self.stream.whip_url)
            self.sdp_server.set_stream_info(self.stream.id, self.stream.whip_url)
            
            self.streaming = True
            self.capture_mode = capture_mode
            self.frame_count = 0
            
            threading.Thread(target=self._frame_loop, daemon=True).start()
            
            print(f"\n✓ Streaming started!")
            print(f"  Stream ID: {self.stream.id}")
            print(f"  Capture: {capture_mode}")
            print(f"  Press 'o' to open output in browser")
            
        except Exception as e:
            print(f"✗ Failed to start stream: {e}")
    
    def _stop_streaming(self):
        """Stop streaming"""
        if not self.streaming:
            return
        
        print("\nStopping stream...")
        self.streaming = False
        
        if self.ndi_receiver:
            self.ndi_receiver.disconnect()
        
        if self.stream:
            try:
                self.api.delete_stream(self.stream.id)
            except:
                pass
            self.stream = None
        
        self.server.clear_stream_info()
        self.sdp_server.clear_stream_info()
        
        print("✓ Stream stopped")
    
    def _frame_loop(self):
        """Send frames to the relay page"""
        fps = 30
        frame_time = 1.0 / fps
        
        while self.streaming:
            start = time.time()
            
            try:
                # Get frame based on capture mode
                if self.capture_mode == 'ndi' and self.ndi_receiver:
                    frame = self.ndi_receiver.get_frame()
                elif self.capture_mode == 'window':
                    frame = self._capture_window()
                else:
                    frame = self._generate_test_frame()
                
                if frame is not None:
                    # Resize to 512x512 preserving aspect ratio (letterbox)
                    frame = self._resize_with_letterbox(frame, 512, 512)
                    
                    # Convert to JPEG
                    jpeg_data = self._frame_to_jpeg(frame)
                    
                    # Send to WebSocket clients
                    self.server.broadcast_frame(jpeg_data)
                    
                    self.frame_count += 1
                    
                    if self.frame_count % 150 == 0:
                        print(f"  📤 {self.frame_count} frames sent")
            
            except Exception as e:
                if self.streaming:
                    print(f"Frame error: {e}")
            
            elapsed = time.time() - start
            sleep_time = frame_time - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)
    
    def _generate_test_frame(self) -> np.ndarray:
        """Generate animated test pattern"""
        t = self.frame_count * 0.03
        
        # Use numpy broadcasting for speed
        y, x = np.mgrid[0:512, 0:512]
        
        r = (127 + 127 * np.sin(x * 0.02 + t)).astype(np.uint8)
        g = (127 + 127 * np.sin(y * 0.02 + t * 1.3)).astype(np.uint8)
        b = (127 + 127 * np.sin((x + y) * 0.01 + t * 0.7)).astype(np.uint8)
        
        frame = np.stack([r, g, b], axis=-1)
        return frame
    
    def _capture_window(self) -> Optional[np.ndarray]:
        """Capture a window"""
        if not SCREEN_CAPTURE_AVAILABLE or not self.capture_window_id:
            return None
        
        try:
            image = CGWindowListCreateImage(
                CGRectNull,
                kCGWindowListOptionOnScreenOnly,
                self.capture_window_id,
                kCGWindowImageDefault
            )
            
            if not image:
                return None
            
            width = CGImageGetWidth(image)
            height = CGImageGetHeight(image)
            
            provider = CGImageGetDataProvider(image)
            data = CGDataProviderCopyData(provider)
            
            arr = np.frombuffer(data, dtype=np.uint8)
            arr = arr.reshape((height, width, 4))
            
            # BGRA to RGB
            return arr[:, :, [2, 1, 0]]
        except:
            return None
    
    def _resize_with_letterbox(self, frame: np.ndarray, target_w: int, target_h: int) -> np.ndarray:
        """Resize frame to target size while preserving aspect ratio (letterbox/pillarbox)"""
        h, w = frame.shape[:2]
        
        # If already correct size, return as-is
        if w == target_w and h == target_h:
            return frame
        
        # Calculate scaling factor to fit within target
        scale = min(target_w / w, target_h / h)
        new_w = int(w * scale)
        new_h = int(h * scale)
        
        # Resize the image
        img = Image.fromarray(frame)
        img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        
        # Create black canvas and paste resized image centered
        canvas = Image.new('RGB', (target_w, target_h), (0, 0, 0))
        paste_x = (target_w - new_w) // 2
        paste_y = (target_h - new_h) // 2
        canvas.paste(img, (paste_x, paste_y))
        
        return np.array(canvas)
    
    def _frame_to_jpeg(self, frame: np.ndarray, quality: int = 70) -> bytes:
        """Convert frame to JPEG"""
        img = Image.fromarray(frame)
        buffer = BytesIO()
        img.save(buffer, format='JPEG', quality=quality)
        return buffer.getvalue()


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Daydream VDJ Bridge')
    parser.add_argument('--cli', action='store_true', help='Use command-line interface instead of web UI')
    parser.add_argument('--no-browser', action='store_true', help='Do not open browser automatically')
    args = parser.parse_args()
    
    bridge = DaydreamBridge()
    bridge.start(open_browser=not args.no_browser, use_cli=args.cli)


if __name__ == '__main__':
    main()
