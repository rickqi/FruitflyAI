import asyncio, json, struct
import websockets

async def main():
    async with websockets.connect("ws://127.0.0.1:8766/") as ws:
        data = await asyncio.wait_for(ws.recv(), 8)
        magic, size = struct.unpack_from("<4sI", data)
        meta = json.loads(data[8:8+size])
        off = 8 + size
        n = meta["n"]; w, h = meta["width"], meta["height"]
        px = w * h * 3
        eyes = data[off+n: off+n+px]
        rows = meta["rows"][-1]
        print("visual_connected:", meta.get("visual_connected"), "| has_comparison:", meta.get("has_comparison"))
        print("frame_age_ms:", round(rows.get("frame_age", 0)*1000), "| temporal:", round(rows.get("temporal",0),4))
        print("hrc_asymmetry:", rows.get("hrc_asymmetry"), "| decision_source:", rows.get("decision_source"))
        with open("/mnt/d/codes/flygym/fly64/docs/screenshots/live_eyes.ppm", "wb") as f:
            f.write(f"P6\n{w} {h}\n255\n".encode() + bytes(eyes))
        print("eyes dumped", w, h)

asyncio.run(main())
