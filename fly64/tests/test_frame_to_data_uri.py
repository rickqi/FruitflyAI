"""Test frame_to_data_uri PNG conversion for all frame sizes."""
import json, base64, struct, zlib, os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "plugin"))
from llm_consult import frame_to_data_uri

SCREEN_B64_307200 = "A" * 307200  # 320×240 placeholder
FORWARD_B64_65536 = "A" * 65536   # 128×128 placeholder

def test_screen_320x240():
    uri = frame_to_data_uri(SCREEN_B64_307200)
    assert uri and uri.startswith("data:image/png;base64,"), "screen PNG prefix missing"
    png_b64 = uri[len("data:image/png;base64,"):]
    png = base64.b64decode(png_b64)
    assert png.startswith(b"\x89PNG"), "not a valid PNG"
    # Check IHDR for 320×240
    ihdr = png[16:24]
    w, h = struct.unpack(">II", ihdr)
    assert (w, h) == (320, 240), f"expected 320×240, got {w}×{h}"
    print("✅ 320×240: valid PNG with correct dimensions")

def test_forward_128x128():
    uri = frame_to_data_uri(FORWARD_B64_65536)
    assert uri and uri.startswith("data:image/png;base64,"), "forward PNG prefix missing"
    png_b64 = uri[len("data:image/png;base64,"):]
    png = base64.b64decode(png_b64)
    assert png.startswith(b"\x89PNG"), "not a valid PNG"
    ihdr = png[16:24]
    w, h = struct.unpack(">II", ihdr)
    assert (w, h) == (128, 128), f"expected 128×128, got {w}×{h}"
    print("✅ 128×128: valid PNG with correct dimensions")

def test_none_returns_none():
    assert frame_to_data_uri(None) is None
    print("✅ None input returns None")

def test_data_uri_passthrough():
    uri = "data:image/png;base64,AAAA"
    assert frame_to_data_uri(uri) == uri
    print("✅ data: URI passthrough works")

if __name__ == "__main__":
    test_screen_320x240()
    test_forward_128x128()
    test_none_returns_none()
    test_data_uri_passthrough()
    print("\n🎉 All tests passed")