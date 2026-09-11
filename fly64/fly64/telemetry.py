"""Read-only instruments. Never feed dashboard values back into the model."""
import json
import struct

import numpy as np

HEADER = struct.Struct("<4sI")
WINDOW = 13


class Observatory:
    def __init__(self, model):
        self.model = model
        self.ring = np.zeros((WINDOW, model.n), np.uint8)
        self.counts = np.zeros(model.n, np.uint8)
        self.ticks = 0
        self.rows = []
        self.previous_preview = None
        self.preview = np.zeros((128, 256, 3), np.uint8)
        self.change = self.preview.copy()
        self.frame_seq = None
        self.frame_time = 0.
        self.contrast = [0., 0.]
        self.has_comparison = False
        self.groups = dict(visual=model.visual, forward=model.forward,
                           left=model.turn_left, right=model.turn_right, jump=model.jump_nodes)

    def observe(self, frame, seq, control, spikes, game):
        m = self.model
        t = (m.step_count - 1) * m.dt
        if seq != self.frame_seq:
            self.preview = m.retina.preview(frame)
            self.has_comparison = self.previous_preview is not None
            if self.has_comparison:
                weights = np.array([.2126, .7152, .0722])
                delta = np.abs(self.preview @ weights - self.previous_preview @ weights)
                delta[~m.retina.mask] = 0
                self.change = np.repeat(np.rint(delta)[..., None], 3, axis=2).astype(np.uint8)
                self.contrast = [float(delta[:, s:s+128][m.retina.mask[:, s:s+128]].mean()/255)
                                 for s in (0, 128)]
            self.previous_preview = self.preview.copy()
            self.frame_seq, self.frame_time = seq, t
        slot = self.ticks % WINDOW
        self.counts -= self.ring[slot]
        self.ring[slot].fill(0)
        self.ring[slot, spikes] = 1
        self.counts += self.ring[slot]
        self.ticks += 1
        denom = min(self.ticks, WINDOW) * m.dt
        rates = {key: float(self.counts[ids].mean()/denom) if len(ids) else None
                 for key, ids in self.groups.items()}
        row = dict(t=t, **rates, contrast_left=self.contrast[0], contrast_right=self.contrast[1],
                   temporal=m.temporal_energy, x=control.x, y=control.y,
                   jump_event=bool(control.jump), cooldown=max(0., .8-(t-m.last_jump)),
                   game_x=game["x"], game_y=game["y"], game_a=game["jump"],
                   game_state=game["state"], game_age=game["age_ms"],
                   frame_age=t-self.frame_time)
        self.rows.append(row)
        return row

    def packet(self, seq, **performance):
        denom = min(self.ticks, WINDOW)
        activity = np.rint(self.counts.astype(np.float32)/max(denom, 1)*255).astype(np.uint8)
        meta = dict(schema=3, seq=seq, n=self.model.n, width=256, height=128,
                    dt=self.model.dt, window_ticks=denom, rate_max=1/self.model.dt,
                    has_comparison=self.has_comparison, visual_connected=self.model.visual_connected,
                    rows=self.rows, **performance)
        encoded = json.dumps(meta, separators=(",", ":"), allow_nan=False).encode()
        packet = HEADER.pack(b"F643", len(encoded)) + encoded + activity.tobytes() + self.preview.tobytes() + self.change.tobytes()
        self.rows = []
        return packet
