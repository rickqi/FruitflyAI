"""Exercise the real browser packet decoder in Node, without browser automation."""
from pathlib import Path
import shutil
import subprocess

import numpy as np
import pytest

from fly64.model import FlyModel
from fly64.telemetry import Observatory


@pytest.mark.skipif(shutil.which("node") is None, reason="Node not installed")
def test_javascript_reads_python_packet_and_rejects_corruption():
    model = FlyModel(demo=True)
    obs = Observatory(model)
    frame = np.zeros((256, 384, 3), np.uint8)
    control, spikes = model.step(frame)
    obs.observe(frame, 1, control, spikes, dict(x=0, y=0, jump=False, state=4, age_ms=300.))
    result = subprocess.run(["node", "--input-type=module", "-e", """
import assert from 'node:assert/strict';
import {decodePacket} from './web/dashboard.js';
const chunks=[];for await(const c of process.stdin)chunks.push(c);
const b=Buffer.concat(chunks);const packet=b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength);
const parsed=decodePacket(packet);
assert.equal(parsed.data.n,4096);assert.equal(parsed.data.rows[0].t,0);
assert.equal(parsed.activity.length,4096);assert.equal(parsed.eyes.length,98304);
assert.equal(parsed.change.length,98304);
assert.throws(()=>decodePacket(packet.slice(0,-1)),/Incomplete/);
assert.throws(()=>decodePacket(packet.slice(0,5)),/Incomplete/);
const corrupt=packet.slice(0);new Uint8Array(corrupt)[0]=0;
assert.throws(()=>decodePacket(corrupt),/mismatch/);
"""], input=obs.packet(1), capture_output=True, cwd=Path(__file__).resolve().parents[1])
    assert result.returncode == 0, result.stderr.decode()
