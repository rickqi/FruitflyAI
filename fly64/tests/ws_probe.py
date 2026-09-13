import asyncio, json, struct, sys
import websockets

PORT = sys.argv[1] if len(sys.argv) > 1 else "8765"
PATH = sys.argv[2] if len(sys.argv) > 2 else "/ws"

async def main():
    async with websockets.connect(f"ws://127.0.0.1:{PORT}{PATH}") as ws:
        data = await asyncio.wait_for(ws.recv(), 5)
        magic, size = struct.unpack_from("<4sI", data)
        meta = json.loads(data[8:8+size])
        r = meta["rows"][-1]
        print("causal_schema:", meta.get("causal_schema"))
        print("decision_source:", r.get("decision_source"))
        print("cliff_conf:", r.get("cliff_conf"), "stuck_conf:", r.get("stuck_conf"))
        print("gate_forward:", r.get("gate_forward"), "gate_jump:", r.get("gate_jump"))
        print("sector_active:", r.get("sector_active"), "sector_contrast_len:", len(r.get("sector_contrast") or []))

asyncio.run(main())
