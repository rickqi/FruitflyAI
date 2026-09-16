import json, urllib.request
f = json.load(urllib.request.urlopen("http://127.0.0.1:8765/flow.json"))
print("brain_version =", f.get("brain_version"))
print("decision_source =", f.get("decision_source"))
print("cpg_status =", f.get("cpg_status"))
