import json, time, urllib.request, base64
import numpy as np

def snap():
    f = json.load(urllib.request.urlopen("http://127.0.0.1:8765/screen.json"))
    b = base64.b64decode(f["screen_b64"])[:320*240*3]
    return np.frombuffer(b, dtype=np.uint8).reshape(240, 320, 3).astype(int)

st = json.load(urllib.request.urlopen("http://127.0.0.1:8765/bridge-status.json"))
print("game_frame =", st.get("game_frame"), "seq =", st.get("seq"))
a = snap(); time.sleep(6); b = snap()
st2 = json.load(urllib.request.urlopen("http://127.0.0.1:8765/bridge-status.json"))
print("game_frame'=", st2.get("game_frame"))
print("pixel delta =", float(np.abs(a-b).mean()))
# also compare against the frame 6s earlier via hist
print("histL1 =", float(np.abs(np.histogram(a[...,0],bins=16,range=(0,255),density=True)[0]
                            - np.histogram(b[...,0],bins=16,range=(0,255),density=True)[0]).sum()))
