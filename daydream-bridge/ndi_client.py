"""
Pure Python NDI client using ctypes
Directly interfaces with the NDI SDK library without needing ndi-python package
"""

import ctypes
import ctypes.util
import time
import platform
from dataclasses import dataclass
from typing import Optional, List
import numpy as np

# Load the NDI library
def _load_ndi_library():
    """Load the NDI runtime library"""
    system = platform.system()
    
    if system == "Darwin":
        # macOS - look in NDI SDK locations (varies by SDK version)
        lib_paths = [
            # NDI 5+ SDK
            "/Library/NDI SDK for Apple/lib/macOS/libndi.dylib",
            # NDI 4.x SDK (older)
            "/Library/NDI SDK for Apple/lib/x64/libndi.4.dylib",
            "/Library/NDI SDK for Apple/lib/x64/libndi.dylib",
            # Alternative locations
            "/usr/local/lib/libndi.dylib",
            "/usr/local/lib/libndi.5.dylib",
            ctypes.util.find_library("ndi"),
        ]
    elif system == "Windows":
        import os
        lib_paths = [
            "Processing.NDI.Lib.x64.dll",
            ctypes.util.find_library("Processing.NDI.Lib.x64"),
        ]
        # Check NDI runtime environment variables (set by NDI Tools installer)
        for v in ['NDI_RUNTIME_DIR_V6', 'NDI_RUNTIME_DIR_V5', 'NDI_RUNTIME_DIR_V4', 'NDI_RUNTIME_DIR_V3']:
            env_path = os.environ.get(v)
            if env_path:
                lib_paths.append(os.path.join(env_path, "Processing.NDI.Lib.x64.dll"))
    else:  # Linux
        lib_paths = [
            "/usr/lib/libndi.so",
            "/usr/local/lib/libndi.so",
            ctypes.util.find_library("ndi"),
        ]
    
    for path in lib_paths:
        if path:
            try:
                return ctypes.CDLL(path)
            except OSError:
                continue
    
    raise RuntimeError(
        "NDI library not found. Please install NDI Tools from https://ndi.video/tools/\n"
        "On macOS, install 'NDI SDK for Apple' from the NDI website."
    )


# NDI data structures
class NDIlib_source_t(ctypes.Structure):
    _fields_ = [
        ("p_ndi_name", ctypes.c_char_p),
        ("p_url_address", ctypes.c_char_p),
    ]


class NDIlib_find_create_t(ctypes.Structure):
    _fields_ = [
        ("show_local_sources", ctypes.c_bool),
        ("p_groups", ctypes.c_char_p),
        ("p_extra_ips", ctypes.c_char_p),
    ]


class NDIlib_recv_create_v3_t(ctypes.Structure):
    _fields_ = [
        ("source_to_connect_to", NDIlib_source_t),
        ("color_format", ctypes.c_int),
        ("bandwidth", ctypes.c_int),
        ("allow_video_fields", ctypes.c_bool),
        ("p_ndi_recv_name", ctypes.c_char_p),
    ]


class NDIlib_video_frame_v2_t(ctypes.Structure):
    _fields_ = [
        ("xres", ctypes.c_int),
        ("yres", ctypes.c_int),
        ("FourCC", ctypes.c_int),
        ("frame_rate_N", ctypes.c_int),
        ("frame_rate_D", ctypes.c_int),
        ("picture_aspect_ratio", ctypes.c_float),
        ("frame_format_type", ctypes.c_int),
        ("timecode", ctypes.c_int64),
        ("p_data", ctypes.c_void_p),
        ("line_stride_in_bytes", ctypes.c_int),
        ("p_metadata", ctypes.c_char_p),
        ("timestamp", ctypes.c_int64),
    ]


class NDIlib_audio_frame_v2_t(ctypes.Structure):
    _fields_ = [
        ("sample_rate", ctypes.c_int),
        ("no_channels", ctypes.c_int),
        ("no_samples", ctypes.c_int),
        ("timecode", ctypes.c_int64),
        ("p_data", ctypes.c_void_p),
        ("channel_stride_in_bytes", ctypes.c_int),
        ("p_metadata", ctypes.c_char_p),
        ("timestamp", ctypes.c_int64),
    ]


class NDIlib_metadata_frame_t(ctypes.Structure):
    _fields_ = [
        ("length", ctypes.c_int),
        ("timecode", ctypes.c_int64),
        ("p_data", ctypes.c_char_p),
    ]


# Color format constants
NDIlib_recv_color_format_BGRX_BGRA = 0
NDIlib_recv_color_format_UYVY_BGRA = 1
NDIlib_recv_color_format_RGBX_RGBA = 2
NDIlib_recv_color_format_UYVY_RGBA = 3
NDIlib_recv_color_format_fastest = 100
NDIlib_recv_color_format_best = 101

# Bandwidth constants
NDIlib_recv_bandwidth_metadata_only = -10
NDIlib_recv_bandwidth_audio_only = 10
NDIlib_recv_bandwidth_lowest = 0
NDIlib_recv_bandwidth_highest = 100

# Frame type constants
NDIlib_frame_type_none = 0
NDIlib_frame_type_video = 1
NDIlib_frame_type_audio = 2
NDIlib_frame_type_metadata = 3
NDIlib_frame_type_error = 4
NDIlib_frame_type_status_change = 100

# FourCC constants (as integers)
NDIlib_FourCC_type_UYVY = 0x59565955  # 'YVYU' reversed
NDIlib_FourCC_type_BGRA = 0x41524742  # 'ARGB' reversed
NDIlib_FourCC_type_BGRX = 0x58524742
NDIlib_FourCC_type_RGBA = 0x41424752
NDIlib_FourCC_type_RGBX = 0x58424752


@dataclass
class NDISource:
    """Represents a discovered NDI source"""
    name: str
    url: str


class NDIClient:
    """Simple NDI client for receiving video frames"""
    
    def __init__(self):
        self._lib = _load_ndi_library()
        self._setup_functions()
        
        # Initialize NDI
        if not self._lib.NDIlib_initialize():
            raise RuntimeError("Failed to initialize NDI library")
        
        self._find_instance = None
        self._recv_instance = None
        self._current_source: Optional[NDISource] = None
    
    def _setup_functions(self):
        """Set up ctypes function signatures"""
        lib = self._lib
        
        # NDIlib_initialize
        lib.NDIlib_initialize.restype = ctypes.c_bool
        lib.NDIlib_initialize.argtypes = []
        
        # NDIlib_destroy
        lib.NDIlib_destroy.restype = None
        lib.NDIlib_destroy.argtypes = []
        
        # NDIlib_find_create_v2
        lib.NDIlib_find_create_v2.restype = ctypes.c_void_p
        lib.NDIlib_find_create_v2.argtypes = [ctypes.POINTER(NDIlib_find_create_t)]
        
        # NDIlib_find_destroy
        lib.NDIlib_find_destroy.restype = None
        lib.NDIlib_find_destroy.argtypes = [ctypes.c_void_p]
        
        # NDIlib_find_wait_for_sources
        lib.NDIlib_find_wait_for_sources.restype = ctypes.c_bool
        lib.NDIlib_find_wait_for_sources.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        
        # NDIlib_find_get_current_sources
        lib.NDIlib_find_get_current_sources.restype = ctypes.POINTER(NDIlib_source_t)
        lib.NDIlib_find_get_current_sources.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)]
        
        # NDIlib_recv_create_v3
        lib.NDIlib_recv_create_v3.restype = ctypes.c_void_p
        lib.NDIlib_recv_create_v3.argtypes = [ctypes.POINTER(NDIlib_recv_create_v3_t)]
        
        # NDIlib_recv_destroy
        lib.NDIlib_recv_destroy.restype = None
        lib.NDIlib_recv_destroy.argtypes = [ctypes.c_void_p]
        
        # NDIlib_recv_capture_v2
        lib.NDIlib_recv_capture_v2.restype = ctypes.c_int
        lib.NDIlib_recv_capture_v2.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(NDIlib_video_frame_v2_t),
            ctypes.POINTER(NDIlib_audio_frame_v2_t),
            ctypes.POINTER(NDIlib_metadata_frame_t),
            ctypes.c_uint32,
        ]
        
        # NDIlib_recv_free_video_v2
        lib.NDIlib_recv_free_video_v2.restype = None
        lib.NDIlib_recv_free_video_v2.argtypes = [ctypes.c_void_p, ctypes.POINTER(NDIlib_video_frame_v2_t)]
    
    def find_sources(self, timeout_ms: int = 5000) -> List[NDISource]:
        """Find available NDI sources on the network"""
        # Create find instance if needed
        if self._find_instance is None:
            create_settings = NDIlib_find_create_t()
            create_settings.show_local_sources = True
            create_settings.p_groups = None
            create_settings.p_extra_ips = None
            
            self._find_instance = self._lib.NDIlib_find_create_v2(ctypes.byref(create_settings))
            if not self._find_instance:
                raise RuntimeError("Failed to create NDI find instance")
        
        # Wait for sources
        self._lib.NDIlib_find_wait_for_sources(self._find_instance, timeout_ms)
        
        # Get sources
        num_sources = ctypes.c_uint32(0)
        sources_ptr = self._lib.NDIlib_find_get_current_sources(
            self._find_instance, ctypes.byref(num_sources)
        )
        
        sources = []
        for i in range(num_sources.value):
            source = sources_ptr[i]
            name = source.p_ndi_name.decode('utf-8') if source.p_ndi_name else ""
            url = source.p_url_address.decode('utf-8') if source.p_url_address else ""
            sources.append(NDISource(name=name, url=url))
        
        return sources
    
    def connect(self, source: NDISource) -> bool:
        """Connect to an NDI source"""
        # Disconnect existing
        if self._recv_instance:
            self._lib.NDIlib_recv_destroy(self._recv_instance)
            self._recv_instance = None
        
        # Create source struct
        ndi_source = NDIlib_source_t()
        ndi_source.p_ndi_name = source.name.encode('utf-8')
        ndi_source.p_url_address = source.url.encode('utf-8') if source.url else None
        
        # Create receiver
        recv_create = NDIlib_recv_create_v3_t()
        recv_create.source_to_connect_to = ndi_source
        recv_create.color_format = NDIlib_recv_color_format_RGBX_RGBA
        recv_create.bandwidth = NDIlib_recv_bandwidth_highest
        recv_create.allow_video_fields = False
        recv_create.p_ndi_recv_name = b"Daydream Bridge"
        
        self._recv_instance = self._lib.NDIlib_recv_create_v3(ctypes.byref(recv_create))
        if not self._recv_instance:
            return False
        
        self._current_source = source
        return True
    
    def capture_video_frame(self, timeout_ms: int = 100) -> Optional[np.ndarray]:
        """
        Capture a video frame from the connected source.
        Returns RGBA numpy array or None if no frame available.
        """
        if not self._recv_instance:
            return None
        
        video_frame = NDIlib_video_frame_v2_t()
        audio_frame = NDIlib_audio_frame_v2_t()
        metadata_frame = NDIlib_metadata_frame_t()
        
        frame_type = self._lib.NDIlib_recv_capture_v2(
            self._recv_instance,
            ctypes.byref(video_frame),
            ctypes.byref(audio_frame),
            ctypes.byref(metadata_frame),
            timeout_ms,
        )
        
        if frame_type != NDIlib_frame_type_video:
            return None
        
        try:
            # Get frame dimensions
            width = video_frame.xres
            height = video_frame.yres
            stride = video_frame.line_stride_in_bytes
            fourcc = video_frame.FourCC
            
            # Calculate bytes per pixel based on FourCC
            if fourcc in (NDIlib_FourCC_type_RGBA, NDIlib_FourCC_type_RGBX,
                         NDIlib_FourCC_type_BGRA, NDIlib_FourCC_type_BGRX):
                bpp = 4
            else:
                # UYVY or other format - need conversion
                bpp = 2
            
            # Copy frame data to numpy array
            if stride == width * bpp:
                # No padding, direct copy
                buffer_size = height * stride
                buffer = (ctypes.c_uint8 * buffer_size).from_address(video_frame.p_data)
                frame_data = np.frombuffer(buffer, dtype=np.uint8).reshape((height, width, bpp if bpp == 4 else -1))
            else:
                # Handle stride/padding
                frame_data = np.zeros((height, width, 4), dtype=np.uint8)
                for y in range(height):
                    row_start = video_frame.p_data + y * stride
                    row_buffer = (ctypes.c_uint8 * (width * 4)).from_address(row_start)
                    frame_data[y] = np.frombuffer(row_buffer, dtype=np.uint8).reshape((width, 4))
            
            # Convert BGRA to RGBA if needed
            if fourcc in (NDIlib_FourCC_type_BGRA, NDIlib_FourCC_type_BGRX):
                frame_data = frame_data[:, :, [2, 1, 0, 3]]  # BGR(A) -> RGB(A)
            
            return frame_data.copy()  # Copy before freeing the NDI frame
        
        finally:
            # Free the video frame
            self._lib.NDIlib_recv_free_video_v2(self._recv_instance, ctypes.byref(video_frame))
    
    def disconnect(self):
        """Disconnect from the current source"""
        if self._recv_instance:
            self._lib.NDIlib_recv_destroy(self._recv_instance)
            self._recv_instance = None
        self._current_source = None
    
    def close(self):
        """Clean up NDI resources"""
        self.disconnect()
        
        if self._find_instance:
            self._lib.NDIlib_find_destroy(self._find_instance)
            self._find_instance = None
        
        self._lib.NDIlib_destroy()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False


# Test function
if __name__ == "__main__":
    print("Testing NDI Client...")
    
    try:
        with NDIClient() as client:
            print("Searching for NDI sources (5 seconds)...")
            sources = client.find_sources(timeout_ms=5000)
            
            if not sources:
                print("No NDI sources found.")
            else:
                print(f"Found {len(sources)} NDI source(s):")
                for i, src in enumerate(sources):
                    print(f"  {i+1}. {src.name}")
                
                # Try to connect to first source
                print(f"\nConnecting to: {sources[0].name}")
                if client.connect(sources[0]):
                    print("Connected! Capturing frames...")
                    
                    for _ in range(30):  # Try for 3 seconds
                        frame = client.capture_video_frame(timeout_ms=100)
                        if frame is not None:
                            print(f"Got frame: {frame.shape}")
                            break
                    else:
                        print("No frames received in 3 seconds")
                else:
                    print("Failed to connect")
    
    except Exception as e:
        print(f"Error: {e}")

