"""
Scope WebRTC Client
Connects to a Daydream Scope instance (local or RunPod) via WebRTC
"""

import json
import logging
import ssl
from typing import Optional, Callable, Dict, Any
from dataclasses import dataclass, field

import urllib.request
import urllib.error

logger = logging.getLogger(__name__)


@dataclass
class ScopeConfig:
    """Configuration for Scope connection"""
    prompts: list = field(default_factory=lambda: [{"text": "anime style, vibrant colors", "weight": 1.0}])
    negative_prompt: str = "blurry, low quality"
    denoising_step_list: list = field(default_factory=lambda: [1000, 750])  # Default for video mode
    guidance_scale: float = 1.0
    input_mode: str = "video"  # "video" for v2v, "text" for t2v
    pipeline_id: str = "streamdiffusionv2"  # "streamdiffusionv2", "longlive", "krea-realtime-video"
    
    # Resolution (defaults for Krea: 256x256 for video mode)
    width: int = 512
    height: int = 512


class ScopeClient:
    """
    Client for connecting to Daydream Scope via WebRTC.
    
    Scope uses standard WebRTC (not WHIP/WHEP), so we need to:
    1. Get ICE servers from Scope
    2. Create offer with our video track
    3. Send offer to Scope's /api/v1/webrtc/offer
    4. Get answer and connect
    5. Send/receive video bidirectionally
    """
    
    def __init__(self, scope_url: str):
        """
        Initialize Scope client.
        
        Args:
            scope_url: Base URL of Scope instance (e.g., https://xxx-8000.proxy.runpod.net)
        """
        self.scope_url = scope_url.rstrip('/')
        self.config = ScopeConfig()
        self.session_id: Optional[str] = None
        self.connected = False
        self._on_frame_callback: Optional[Callable] = None
        
    def get_api_url(self, endpoint: str) -> str:
        """Get full API URL for an endpoint"""
        return f"{self.scope_url}/api/v1{endpoint}"
    
    def _get_ssl_context(self):
        """Get SSL context that skips verification (for RunPod proxies)"""
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE
        return ssl_ctx
    
    def _get_headers(self) -> dict:
        """Get headers required for RunPod proxy (needs Referer header)"""
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Referer": f"{self.scope_url}/",
            "Origin": self.scope_url,
            "User-Agent": "DaydreamBridge/1.0",
        }
    
    def get_ice_servers(self) -> list:
        """Get ICE server configuration from Scope"""
        try:
            url = self.get_api_url("/webrtc/ice-servers")
            req = urllib.request.Request(url, headers=self._get_headers())
            
            with urllib.request.urlopen(req, timeout=10, context=self._get_ssl_context()) as resp:
                data = json.loads(resp.read().decode())
                return data.get("iceServers", [])
        except Exception as e:
            logger.warning(f"Failed to get ICE servers: {e}")
            # Return default STUN server
            return [{"urls": ["stun:stun.l.google.com:19302"]}]
    
    def send_offer(self, sdp: str, sdp_type: str = "offer", initial_params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Send WebRTC offer to Scope and get answer.
        
        Args:
            sdp: SDP offer string
            sdp_type: SDP type (usually "offer")
            initial_params: Optional dict to override default parameters
            
        Returns:
            Dict with answer SDP, type, and sessionId
        """
        url = self.get_api_url("/webrtc/offer")
        
        # Build initial parameters from config
        # Convert prompts to PromptItem format: [{"text": "...", "weight": 1.0}]
        prompts = self.config.prompts
        if initial_params and "prompts" in initial_params:
            prompts = initial_params["prompts"]
        
        # Convert string prompts to PromptItem format
        formatted_prompts = []
        if isinstance(prompts, list):
            for p in prompts:
                if isinstance(p, str):
                    formatted_prompts.append({"text": p, "weight": 1.0})
                elif isinstance(p, dict):
                    formatted_prompts.append(p)
        elif isinstance(prompts, str):
            formatted_prompts.append({"text": prompts, "weight": 1.0})
        
        # Get pipeline_id from params or config
        pipeline_id = self.config.pipeline_id
        if initial_params and "pipeline_id" in initial_params:
            pipeline_id = initial_params["pipeline_id"]
        
        params = {
            "input_mode": self.config.input_mode,
            "prompts": formatted_prompts,
            "negative_prompt": initial_params.get("negative_prompt", self.config.negative_prompt) if initial_params else self.config.negative_prompt,
            "denoising_step_list": self.config.denoising_step_list,
            "guidance_scale": initial_params.get("guidance_scale", self.config.guidance_scale) if initial_params else self.config.guidance_scale,
            "noise_scale": 0.7,  # Required for video mode
            "noise_controller": True,  # Enable automatic noise adjustment
            "width": self.config.width,
            "height": self.config.height,
            "pipeline_ids": [pipeline_id],  # Specify which pipeline to use
        }
        
        payload = {
            "sdp": sdp,
            "type": sdp_type,
            "initialParameters": params
        }
        
        data = json.dumps(payload).encode('utf-8')
        headers = self._get_headers()
        req = urllib.request.Request(
            url,
            data=data,
            headers=headers,
            method="POST"
        )
        
        ssl_ctx = self._get_ssl_context()
        try:
            with urllib.request.urlopen(req, timeout=30, context=ssl_ctx) as resp:
                answer = json.loads(resp.read().decode())
                self.session_id = answer.get("sessionId")
                self.connected = True
                logger.info(f"Connected to Scope, session: {self.session_id}")
                return answer
        except urllib.error.HTTPError as e:
            err_body = e.read().decode()
            logger.error(f"Scope offer failed ({e.code}): {err_body}")
            raise
        except Exception as e:
            logger.error(f"Scope offer failed: {e}")
            raise
    
    def send_ice_candidate(self, candidate: str, sdp_mid: str, sdp_mline_index: int):
        """Send ICE candidate to Scope"""
        if not self.session_id:
            logger.warning("No session ID, cannot send ICE candidate")
            return
        
        url = self.get_api_url(f"/webrtc/offer/{self.session_id}")
        
        payload = {
            "candidates": [{
                "candidate": candidate,
                "sdpMid": sdp_mid,
                "sdpMLineIndex": sdp_mline_index
            }]
        }
        
        data = json.dumps(payload).encode('utf-8')
        headers = self._get_headers()
        req = urllib.request.Request(
            url,
            data=data,
            headers=headers,
            method="PATCH"
        )
        
        ssl_ctx = self._get_ssl_context()
        try:
            with urllib.request.urlopen(req, timeout=10, context=ssl_ctx) as resp:
                pass
        except Exception as e:
            logger.warning(f"Failed to send ICE candidate: {e}")
    
    def update_parameters(self, params: Dict[str, Any]):
        """
        Update parameters on an active session.
        Note: In Scope, this is done via WebRTC data channel, not REST API.
        This method is for reference - actual updates go through the data channel.
        """
        self.config.prompts = params.get("prompts", self.config.prompts)
        self.config.negative_prompt = params.get("negative_prompt", self.config.negative_prompt)
        self.config.guidance_scale = params.get("guidance_scale", self.config.guidance_scale)
        self.config.denoising_step_list = params.get("denoising_step_list", self.config.denoising_step_list)
    
    def check_connection(self) -> bool:
        """Check if Scope is reachable"""
        ssl_ctx = self._get_ssl_context()
        headers = self._get_headers()
        
        # Try the health endpoint first (Scope uses /health, not /api/v1/health)
        try:
            url = f"{self.scope_url}/health"
            req = urllib.request.Request(url, headers=headers, method="GET")
            with urllib.request.urlopen(req, timeout=10, context=ssl_ctx) as resp:
                return resp.status == 200
        except Exception as e:
            logger.warning(f"Health check failed: {e}")
        
        # Try the ICE servers endpoint
        try:
            url = self.get_api_url("/webrtc/ice-servers")
            req = urllib.request.Request(url, headers=headers, method="GET")
            with urllib.request.urlopen(req, timeout=10, context=ssl_ctx) as resp:
                return resp.status == 200
        except Exception as e:
            logger.warning(f"ICE servers check failed: {e}")
        
        # Try pipeline status endpoint
        try:
            url = self.get_api_url("/pipeline/status")
            req = urllib.request.Request(url, headers=headers, method="GET")
            with urllib.request.urlopen(req, timeout=10, context=ssl_ctx) as resp:
                return resp.status == 200
        except Exception as e:
            logger.warning(f"Pipeline status check failed: {e}")
        
        # Try the main page as last resort
        try:
            req = urllib.request.Request(self.scope_url, headers=headers, method="GET")
            with urllib.request.urlopen(req, timeout=10, context=ssl_ctx) as resp:
                return resp.status == 200
        except Exception as e:
            logger.warning(f"Main page check failed: {e}")
            return False
    
    def get_pipelines(self) -> list:
        """Get available pipelines from Scope"""
        try:
            url = self.get_api_url("/pipelines/schemas")
            req = urllib.request.Request(url, headers=self._get_headers())
            with urllib.request.urlopen(req, timeout=10, context=self._get_ssl_context()) as resp:
                data = json.loads(resp.read().decode())
                # Returns dict with pipeline_id as keys
                pipelines = data.get("pipelines", {})
                return list(pipelines.keys())
        except Exception as e:
            logger.warning(f"Failed to get pipelines: {e}")
            return []
    
    def load_pipeline(self, pipeline_id: str) -> bool:
        """Load a pipeline on Scope (must be called before streaming)"""
        try:
            url = self.get_api_url("/pipeline/load")
            payload = {
                "pipeline_ids": [pipeline_id]
            }
            data = json.dumps(payload).encode('utf-8')
            headers = self._get_headers()
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            
            ssl_ctx = self._get_ssl_context()
            with urllib.request.urlopen(req, timeout=30, context=ssl_ctx) as resp:
                result = json.loads(resp.read().decode())
                logger.info(f"Pipeline load initiated: {result}")
                return True
        except urllib.error.HTTPError as e:
            err_body = e.read().decode()
            logger.error(f"Failed to load pipeline ({e.code}): {err_body}")
            return False
        except Exception as e:
            logger.error(f"Failed to load pipeline: {e}")
            return False
    
    def get_pipeline_status(self) -> dict:
        """Get current pipeline status from Scope"""
        try:
            url = self.get_api_url("/pipeline/status")
            req = urllib.request.Request(url, headers=self._get_headers())
            
            ssl_ctx = self._get_ssl_context()
            with urllib.request.urlopen(req, timeout=10, context=ssl_ctx) as resp:
                return json.loads(resp.read().decode())
        except Exception as e:
            logger.warning(f"Failed to get pipeline status: {e}")
            return {"status": "unknown"}
    
    def wait_for_pipeline_loaded(self, timeout: int = 120) -> bool:
        """Wait for pipeline to be loaded"""
        import time
        start = time.time()
        while time.time() - start < timeout:
            status = self.get_pipeline_status()
            if status.get("status") == "loaded":
                logger.info("Pipeline loaded successfully")
                return True
            elif status.get("status") == "error":
                logger.error(f"Pipeline loading failed: {status}")
                return False
            logger.info(f"Waiting for pipeline... status: {status.get('status')}")
            time.sleep(2)
        logger.error("Timeout waiting for pipeline to load")
        return False
    
    def disconnect(self):
        """Disconnect from Scope"""
        self.connected = False
        self.session_id = None


def test_scope_connection(url: str) -> Dict[str, Any]:
    """
    Test connection to a Scope instance.
    
    Returns:
        Dict with connection status and info
    """
    client = ScopeClient(url)
    
    result = {
        "reachable": False,
        "url": url,
        "pipelines": [],
        "ice_servers": [],
        "error": None
    }
    
    try:
        # First, try to reach the URL at all
        ssl_ctx = client._get_ssl_context()
        headers = client._get_headers()
        
        # Test basic connectivity with proper headers (RunPod needs Referer)
        try:
            req = urllib.request.Request(url, headers=headers, method="GET")
            with urllib.request.urlopen(req, timeout=15, context=ssl_ctx) as resp:
                if resp.status == 200:
                    result["reachable"] = True
        except urllib.error.HTTPError as e:
            # HTTP errors mean we reached the server
            if e.code in [200, 404, 500]:
                result["reachable"] = True
            else:
                result["error"] = f"HTTP {e.code}: {e.reason}"
                return result
        except urllib.error.URLError as e:
            result["error"] = f"Cannot reach URL: {e.reason}"
            return result
        except Exception as e:
            result["error"] = f"Connection error: {str(e)}"
            return result
        
        # If reachable, try to get more info
        if result["reachable"]:
            try:
                result["pipelines"] = client.get_pipelines()
            except Exception as e:
                logger.warning(f"Could not get pipelines: {e}")
            
            try:
                result["ice_servers"] = client.get_ice_servers()
            except Exception as e:
                logger.warning(f"Could not get ICE servers: {e}")
    except Exception as e:
        result["error"] = str(e)
    
    return result


if __name__ == "__main__":
    # Test connection
    import sys
    
    if len(sys.argv) > 1:
        url = sys.argv[1]
    else:
        url = "http://localhost:8000"
    
    print(f"Testing connection to: {url}")
    result = test_scope_connection(url)
    
    if result["reachable"]:
        print("✓ Scope is reachable!")
        print(f"  Pipelines: {len(result['pipelines'])}")
        print(f"  ICE servers: {len(result['ice_servers'])}")
    else:
        print(f"✗ Connection failed: {result['error']}")

