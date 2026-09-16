import json
d = json.load(open("skills/evolution_history.json"))
recs = d["records"] if isinstance(d, dict) else d
for r in recs:
    if r.get("id") == "EVO-033":
        print(json.dumps(r, ensure_ascii=False, indent=1)[:1500])
        break
print("---keys:", list(recs[-1].keys()))
