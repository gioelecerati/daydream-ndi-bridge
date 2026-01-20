"""
Daydream API Client
Adapted from the official Daydream TouchDesigner plugin
https://github.com/daydreamlive/daydream-touchdesigner
"""

import json
import urllib.request
import urllib.error
import http.client
import ssl
import os
import secrets
import socket
import webbrowser
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass

VERSION = "1.0.0"

API_TIMEOUT_CREATE = 15
API_TIMEOUT_UPDATE = 10
API_TIMEOUT_SDP = 5


def _create_ipv4_socket(host, port, timeout):
    """Force IPv4 connection (avoids IPv6 issues)"""
    sock = None
    for res in socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM):
        af, socktype, proto, canonname, sa = res
        try:
            sock = socket.socket(af, socktype, proto)
            sock.settimeout(timeout)
            sock.connect(sa)
            return sock
        except OSError:
            if sock:
                sock.close()
            sock = None
    raise OSError(f"Failed to connect to {host}:{port} via IPv4")


class IPv4HTTPSConnection(http.client.HTTPSConnection):
    def connect(self):
        sock = _create_ipv4_socket(self.host, self.port, self.timeout)
        if self._tunnel_host:
            self.sock = sock
            self._tunnel()
            server_hostname = self._tunnel_host
        else:
            server_hostname = self.host
        self.sock = self._context.wrap_socket(sock, server_hostname=server_hostname)


class IPv4HTTPSHandler(urllib.request.HTTPSHandler):
    def https_open(self, req):
        return self.do_open(IPv4HTTPSConnection, req, context=self._context)


@dataclass
class StreamConfig:
    """Configuration for a Daydream stream"""
    model_id: str = "stabilityai/sdxl-turbo"
    prompt: str = "anime style, vibrant colors, detailed"
    negative_prompt: str = "blurry, low quality, flat, 2d"
    guidance_scale: float = 1.0
    delta: float = 0.7
    width: int = 512
    height: int = 512
    num_inference_steps: int = 50
    do_add_noise: bool = True
    t_index_list: list = None
    
    # ControlNet scales
    depth_scale: float = 0.45
    canny_scale: float = 0.0
    tile_scale: float = 0.21
    
    def __post_init__(self):
        if self.t_index_list is None:
            self.t_index_list = [11]


@dataclass
class StreamInfo:
    """Information about an active stream"""
    id: str
    whip_url: str = ""
    whep_url: str = ""
    model_id: str = ""


# ControlNet support by model
CONTROLNET_SUPPORT = {
    "stabilityai/sdxl-turbo": {
        "depth": ("xinsir/controlnet-depth-sdxl-1.0", "depth_tensorrt"),
        "canny": ("xinsir/controlnet-canny-sdxl-1.0", "canny"),
        "tile": ("xinsir/controlnet-tile-sdxl-1.0", "feedback"),
    },
    "stabilityai/sd-turbo": {
        "depth": ("thibaud/controlnet-sd21-depth-diffusers", "depth_tensorrt"),
        "canny": ("thibaud/controlnet-sd21-canny-diffusers", "canny"),
    },
    "Lykon/dreamshaper-8": {
        "depth": ("lllyasviel/control_v11f1p_sd15_depth", "depth_tensorrt"),
        "canny": ("lllyasviel/control_v11p_sd15_canny", "canny"),
        "tile": ("lllyasviel/control_v11f1e_sd15_tile", "feedback"),
    },
}


class DaydreamAPI:
    """Client for the Daydream API"""
    
    BASE_URL = "https://api.daydream.live/v1"
    CREDENTIALS_PATH = os.path.expanduser("~/.daydream/credentials")
    AUTH_STATES_PATH = os.path.expanduser("~/.daydream/auth_states.json")
    AUTH_STATE_TTL = 300
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.ssl_ctx = ssl._create_unverified_context()
        self._opener = urllib.request.build_opener(
            IPv4HTTPSHandler(context=self.ssl_ctx)
        )
        
        # Try to load saved credentials if no key provided
        if not self.api_key:
            self._load_credentials()
    
    def _get_headers(self) -> Dict[str, str]:
        if not self.api_key:
            raise ValueError("API key not set. Please login first.")
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "x-client-source": "virtualdj-bridge",
        }
    
    def _load_credentials(self):
        """Load API key from saved credentials"""
        if not os.path.exists(self.CREDENTIALS_PATH):
            return
        try:
            with open(self.CREDENTIALS_PATH, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('DAYDREAM_API_KEY:'):
                        self.api_key = line.split(':', 1)[1].strip()
                        print(f"✓ Loaded credentials from {self.CREDENTIALS_PATH}")
                        return
        except Exception as e:
            print(f"Warning: Could not load credentials: {e}")
    
    def _save_credentials(self, api_key: str):
        """Save API key to credentials file"""
        credentials_dir = os.path.dirname(self.CREDENTIALS_PATH)
        if not os.path.exists(credentials_dir):
            os.makedirs(credentials_dir)
        try:
            with open(self.CREDENTIALS_PATH, 'w') as f:
                f.write(f"DAYDREAM_API_KEY: {api_key}\n")
            print(f"✓ Saved credentials to {self.CREDENTIALS_PATH}")
        except Exception as e:
            print(f"Warning: Could not save credentials: {e}")
    
    @property
    def is_logged_in(self) -> bool:
        return bool(self.api_key)
    
    def set_api_key(self, key: str, save: bool = True):
        """Set API key and optionally save it"""
        self.api_key = key
        if save:
            self._save_credentials(key)
    
    def create_stream(self, config: StreamConfig) -> StreamInfo:
        """Create a new stream"""
        
        # Build controlnets
        controlnets = []
        support = CONTROLNET_SUPPORT.get(config.model_id, {})
        
        if "depth" in support and config.depth_scale > 0:
            model_id, preprocessor = support["depth"]
            controlnets.append({
                "model_id": model_id,
                "conditioning_scale": config.depth_scale,
                "preprocessor": preprocessor,
                "preprocessor_params": {},
                "enabled": True
            })
        
        if "canny" in support and config.canny_scale > 0:
            model_id, preprocessor = support["canny"]
            controlnets.append({
                "model_id": model_id,
                "conditioning_scale": config.canny_scale,
                "preprocessor": preprocessor,
                "preprocessor_params": {},
                "enabled": True
            })
        
        if "tile" in support and config.tile_scale > 0:
            model_id, preprocessor = support["tile"]
            controlnets.append({
                "model_id": model_id,
                "conditioning_scale": config.tile_scale,
                "preprocessor": preprocessor,
                "preprocessor_params": {},
                "enabled": True
            })
        
        # Build params
        params = {
            "model_id": config.model_id,
            "prompt": config.prompt,
            "negative_prompt": config.negative_prompt,
            "guidance_scale": config.guidance_scale,
            "delta": config.delta,
            "width": config.width,
            "height": config.height,
            "num_inference_steps": config.num_inference_steps,
            "do_add_noise": config.do_add_noise,
            "t_index_list": config.t_index_list,
        }
        
        if controlnets:
            params["controlnets"] = controlnets
        
        payload = {
            "pipeline": "streamdiffusion",
            "params": params
        }
        
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(
            f"{self.BASE_URL}/streams",
            data=data,
            headers=self._get_headers(),
            method="POST"
        )
        
        try:
            with self._opener.open(req, timeout=API_TIMEOUT_CREATE) as resp:
                response_data = json.loads(resp.read().decode('utf-8'))
                
                stream = StreamInfo(
                    id=response_data.get("id", ""),
                    whip_url=response_data.get("whip_url", ""),
                    model_id=response_data.get("params", {}).get("model_id", config.model_id)
                )
                
                print(f"✓ Stream created: {stream.id}")
                print(f"  WHIP URL: {stream.whip_url}")
                
                return stream
                
        except urllib.error.HTTPError as e:
            err_body = e.read().decode()
            print(f"✗ API Error {e.code}: {err_body}")
            raise
    
    def update_stream(self, stream_id: str, config: StreamConfig) -> bool:
        """Update stream parameters"""
        
        if not stream_id:
            print("Warning: No stream_id for update")
            return False
        
        params = {
            "model_id": config.model_id,
            "prompt": config.prompt,
            "negative_prompt": config.negative_prompt,
            "guidance_scale": config.guidance_scale,
            "delta": config.delta,
        }
        
        # Build controlnets
        support = CONTROLNET_SUPPORT.get(config.model_id, {})
        controlnets = []
        
        for cn_type, scale in [("depth", config.depth_scale), 
                               ("canny", config.canny_scale), 
                               ("tile", config.tile_scale)]:
            if cn_type in support:
                model_id, preprocessor = support[cn_type]
                controlnets.append({
                    "model_id": model_id,
                    "conditioning_scale": scale,
                    "preprocessor": preprocessor,
                    "preprocessor_params": {},
                    "enabled": True
                })
        
        if controlnets:
            params["controlnets"] = controlnets
        
        payload = {
            "pipeline": "streamdiffusion",
            "params": params
        }
        
        print(f"→ Updating stream {stream_id}: prompt='{config.prompt[:30]}...', delta={config.delta}")
        
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(
            f"{self.BASE_URL}/streams/{stream_id}",
            data=data,
            headers=self._get_headers(),
            method="PATCH"
        )
        
        try:
            with self._opener.open(req, timeout=API_TIMEOUT_UPDATE) as resp:
                print(f"✓ Stream parameters updated")
                return True
        except urllib.error.HTTPError as e:
            err_body = e.read().decode()
            print(f"✗ Update failed {e.code}: {err_body}")
            return False
        except Exception as e:
            print(f"✗ Update failed: {e}")
            return False
    
    def exchange_sdp(self, url: str, offer_sdp: str, timeout: float = API_TIMEOUT_SDP) -> tuple:
        """Exchange SDP for WHIP/WHEP"""
        headers = {
            "Content-Type": "application/sdp",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        data = offer_sdp.encode('utf-8')
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        
        try:
            with self._opener.open(req, timeout=timeout) as resp:
                answer = resp.read().decode('utf-8')
                response_headers = dict(resp.getheaders())
                return answer, response_headers
        except urllib.error.HTTPError as e:
            raise e
    
    def delete_stream(self, stream_id: str) -> bool:
        """Delete/stop a stream"""
        req = urllib.request.Request(
            f"{self.BASE_URL}/streams/{stream_id}",
            headers=self._get_headers(),
            method="DELETE"
        )
        try:
            with self._opener.open(req, timeout=API_TIMEOUT_UPDATE):
                return True
        except:
            return True  # DELETE often returns empty on success
    
    # OAuth Login Flow
    def _load_auth_states(self) -> Dict:
        import time
        if not os.path.exists(self.AUTH_STATES_PATH):
            return {}
        try:
            with open(self.AUTH_STATES_PATH, 'r') as f:
                data = json.load(f)
            states = data.get('states', {})
            now = time.time()
            return {s: t for s, t in states.items() if now - t < self.AUTH_STATE_TTL}
        except:
            return {}
    
    def _save_auth_states(self, states: Dict):
        auth_dir = os.path.dirname(self.AUTH_STATES_PATH)
        if not os.path.exists(auth_dir):
            os.makedirs(auth_dir)
        try:
            with open(self.AUTH_STATES_PATH, 'w') as f:
                json.dump({'states': states}, f)
        except Exception as e:
            print(f"Warning: Could not save auth states: {e}")
    
    def create_auth_state(self) -> str:
        """Create and save an auth state for OAuth flow"""
        import time
        state = secrets.token_urlsafe(16)
        states = self._load_auth_states()
        states[state] = time.time()
        self._save_auth_states(states)
        return state
    
    def consume_auth_state(self, state: str) -> bool:
        """Validate and consume an auth state"""
        if not state:
            return False
        states = self._load_auth_states()
        if state not in states:
            return False
        del states[state]
        self._save_auth_states(states)
        return True
    
    def create_api_key_from_jwt(self, jwt_token: str, name: str = "VirtualDJ Bridge") -> str:
        """Create an API key from a JWT token (OAuth callback)"""
        payload = {"name": name, "user_type": "virtualdj"}
        data = json.dumps(payload).encode('utf-8')
        headers = {
            "Authorization": f"Bearer {jwt_token}",
            "Content-Type": "application/json",
            "x-client-source": "virtualdj-bridge"
        }
        req = urllib.request.Request(
            f"{self.BASE_URL}/api-key",
            data=data,
            headers=headers,
            method="POST"
        )
        try:
            with self._opener.open(req, timeout=API_TIMEOUT_UPDATE) as resp:
                result = json.loads(resp.read().decode('utf-8'))
                api_key = result.get('apiKey')
                if api_key:
                    self.set_api_key(api_key, save=True)
                return api_key
        except urllib.error.HTTPError as e:
            err_body = e.read().decode()
            print(f"Error creating API key: {e.code}: {err_body}")
            raise


# Test
if __name__ == "__main__":
    api = DaydreamAPI()
    
    if not api.is_logged_in:
        print("Not logged in. Run the app to login via browser.")
    else:
        print(f"Logged in with API key: {api.api_key[:20]}...")
        
        config = StreamConfig(
            prompt="cyberpunk city, neon lights, rain",
            model_id="stabilityai/sdxl-turbo"
        )
        
        print("\nCreating test stream...")
        try:
            stream = api.create_stream(config)
            print(f"Stream ID: {stream.id}")
            print(f"WHIP URL: {stream.whip_url}")
            
            input("\nPress Enter to delete stream...")
            api.delete_stream(stream.id)
            print("Stream deleted.")
        except Exception as e:
            print(f"Error: {e}")
