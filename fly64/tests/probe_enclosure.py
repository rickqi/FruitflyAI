import asyncio, json, struct, urllib.request
import websockets

async def main():
    async with websockets.connect("ws://127.0.0.1:8766/") as ws:
        for _ in range(3):
            data = await asyncio.wait_for(ws.recv(), 8)
    size = struct.unpack_from("<4sI", data)[1]
    meta = json.loads(data[8:8+size])
    r = meta["rows"][-1]
    print("enclosure_score:", r.get("enclosure_score"))
    print("hrc_asymmetry:", r.get("hrc_asymmetry"))
    print("decision_source:", r.get("decision_source"))

asyncio.run(main())

f = json.load(urllib.request.urlopen("http://127.0.0.1:8765/flow.json", timeout=5))
print("flow terrain:", f.get("terrain"), "| enclosure:", f.get("enclosure_score"), "| scene:", f.get("scene_name"))
