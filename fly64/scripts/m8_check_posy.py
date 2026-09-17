import json, urllib.request
d = json.load(urllib.request.urlopen("http://127.0.0.1:8765/memory.json", timeout=5))
print("pos_y key in memory.json:", d.get("pos_y"))
print("position:", d.get("position"))
print("bridge-status pos_y:", end=" ")
st = json.load(urllib.request.urlopen("http://127.0.0.1:8765/bridge-status.json", timeout=5))
print(st.get("pose", [None])[1] if st.get("pose") else "N/A")