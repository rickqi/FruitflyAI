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
        self.sector_contrast = None
        self.sector_active = None
        self.sector_loom = None
        self.groups = dict(visual=model.visual, forward=model.forward,
                           left=model.turn_left, right=model.turn_right, jump=model.jump_nodes)
        # ---- t4 B6/B7: telemetry heartbeat ----
        self._seq_counter = 0       # monotonic sequence number per observe()
        self._watchdog_counter = 0  # increments every 100 observe()

    def observe(self, frame, seq, control, spikes, game, causal=None):
        m = self.model
        causal = causal or {}
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
                # Sector aggregation reuses the same delta array (frame edge only).
                # Geometry: preview grid (128x256) split into 8 azimuth bands
                # x upper/lower halves — display space of the eye preview, so the
                # frontend overlay bands align exactly with the rendered image.
                self.sector_contrast = None
                self.sector_active = None
                h, w = delta.shape
                bw = w // 8
                vals = [float(delta[r*h//2:(r+1)*h//2, c*bw:(c+1)*bw].mean())
                        for c in range(8) for r in range(2)]
                self.sector_contrast = [min(100, int(round(v / 255 * 100))) for v in vals]
                active = 0
                for i, v in enumerate(vals):
                    if v > 2.0:
                        active |= 1 << i
                self.sector_active = active
                # LC4-style HRC looming population (16 azimuth sectors x
                # upper/lower x L/R).  Frame-edge only, additive field.
                loom = getattr(m, "hrc_sector_looming", None)
                self.sector_loom = dict(loom) if loom else None
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
        # ---- t4 B6/B7: monotonic seq + watchdog heartbeat ----
        self._seq_counter += 1
        if self._seq_counter % 100 == 0:
            self._watchdog_counter += 1
        watchdog_seq = self._watchdog_counter  # increments every 100 observe()
        row = dict(t=t, **rates, contrast_left=self.contrast[0], contrast_right=self.contrast[1],
                   temporal=m.temporal_energy, x=control.x, y=control.y,
                   jump_event=bool(control.jump), cooldown=max(0., .8-(t-m.last_jump)),
                   game_x=game["x"], game_y=game["y"], game_a=game["jump"],
                   game_state=game["state"], game_age=game["age_ms"],
                   frame_age=t-self.frame_time,
                   flow_asymmetry=m.flow_asymmetry,
                   hrc_asymmetry=getattr(m, "hrc_asymmetry", 0.0),
                   flow_looming=m.flow_looming,
                   flow_cliff=m.flow_cliff,
                   cliff_conf=causal.get("cliff_conf"),
                   stuck_conf=causal.get("stuck_conf"),
                   cliff_confirmed=bool(causal.get("cliff_confirmed", False)),
                   gate_forward=bool(rates["forward"] is not None and rates["forward"] > .4),
                   gate_jump=bool(rates["jump"] is not None and rates["jump"] > 2.),
                   enclosure_score=float(getattr(m, "enclosure_score", 0.0)),
                   decision_source=causal.get("decision_source", "steering"),
                   seq=self._seq_counter, watchdog_seq=watchdog_seq)
        if self.sector_active is not None:
            row["sector_contrast"] = self.sector_contrast
            row["sector_active"] = self.sector_active
        if self.sector_loom:
            row["sector_loom"] = self.sector_loom
        self.rows.append(row)
        return row

    def packet(self, seq, **performance):
        denom = min(self.ticks, WINDOW)
        activity = np.rint(self.counts.astype(np.float32)/max(denom, 1)*255).astype(np.uint8)
        meta = dict(schema=3, causal_schema=1, seq=seq, n=self.model.n, width=256, height=128,
                    dt=self.model.dt, window_ticks=denom, rate_max=1/self.model.dt,
                    has_comparison=self.has_comparison, visual_connected=self.model.visual_connected,
                    rows=self.rows, **performance)
        encoded = json.dumps(meta, separators=(",", ":"), allow_nan=False, default=str).encode()
        packet = HEADER.pack(b"F643", len(encoded)) + encoded + activity.tobytes() + self.preview.tobytes() + self.change.tobytes()
        self.rows = []
        return packet
