import csv

rows = list(csv.DictReader(open("/root/fly64/runtime/mbon_eval.csv")))
ev = [r for r in rows if r["event"] == "complete" and r["primitive"] == "longjump"]
print("longjump completions:", len(ev))
for label, part in (("first third", ev[:len(ev)//3]),
                    ("middle third", ev[len(ev)//3:2*len(ev)//3]),
                    ("last third", ev[2*len(ev)//3:])):
    ws = [float(r["mb_w_longjump"]) for r in part if r["mb_w_longjump"]]
    ds = [float(r["dopamine"]) for r in part if r["dopamine"] not in ("", None)]
    disp = [float(r["disp_60s"] or 0) for r in part]
    print(f"{label:12s} w_mean={sum(ws)/len(ws):+.5f} dop_mean={sum(ds)/len(ds):+.3f} "
          f"disp_mean={sum(disp)/len(disp):.0f}u")
