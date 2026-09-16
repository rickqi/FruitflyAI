import json, urllib.request
f = json.load(urllib.request.urlopen("http://127.0.0.1:8765/flow.json"))
print("mb_mbon_longjump =", f.get("mb_mbon_longjump"), "(>0 => M3.2 bonus gate ACTIVE)")
print("mb_w_longjump    =", f.get("mb_w_longjump"))
print("cpg_status       =", f.get("cpg_status"))
print("decision_source  =", f.get("decision_source"))
print("primitive_disp   =", f.get("primitive_disp"))
