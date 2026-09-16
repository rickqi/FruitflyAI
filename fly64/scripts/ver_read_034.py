import json
d = json.load(open("skills/evolution_history.json"))
recs = d["records"] if isinstance(d, dict) else d
for r in recs:
    if r.get("id") == "EVO-034":
        print(json.dumps(r, ensure_ascii=False)[:800])
        break
print("canonical:", d.get("canonical_versions"))
print("total:", len(recs))
