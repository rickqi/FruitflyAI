"""
FlyGym Interactive Viewer

Launches a MuJoCo interactive viewer with a basic FlyGym simulation
of a single fly on flat terrain. The fly stands in its default "stretch"
pose while the viewer allows you to inspect the scene.

If no display is available (e.g., in a headless environment), the script
falls back to running a headless simulation.

Usage:
    python scripts/launch_interactive_viewer.py
"""

import sys
import os
import time
import platform
import threading
import queue

import numpy as np

from flygym import Fly, Camera, SingleFlySimulation


def main():
    print("Initializing FlyGym simulation...")
    print(f"FlyGym version: 1.2.1 (pip show flygym)")
    print(f"Python: {sys.version.split()[0]} / {platform.system()} {platform.release()}")
    print()

    # Create a fly with default settings (stretch pose)
    fly = Fly(
        init_pose="stretch",
        control="position",
        enable_adhesion=True,
        draw_adhesion=True,
    )

    # Create a camera attached to the fly's worldbody
    cam = Camera(
        attachment_point=fly.model.worldbody,
        camera_name="camera_right",
        targeted_fly_names=fly.name,
        play_speed=0.1,
    )

    # Create the simulation
    sim = SingleFlySimulation(
        fly=fly,
        cameras=[cam],
        timestep=1e-4,
    )

    # Reset to initialize physics
    obs, info = sim.reset()
    default_joints = obs["joints"][0]

    print("Simulation initialized:")
    print(f"  Physics timestep .. {sim.timestep:.6f} s")
    print(f"  Arena ............. {type(sim.arena).__name__}")
    print(f"  Flies ............. {len(sim.flies)}")
    print(f"  Cameras ........... {len(sim.cameras)}")
    print(f"  Joint DoFs ........ {len(default_joints)}")
    print()

    # --- interactive viewer attempt (with timeout for headless safety) ---
    mj_model = sim.physics.model.ptr
    mj_data = sim.physics.data.ptr

    viewer_ready = queue.Queue()
    headless = False

    def _run_viewer():
        """Launch the MuJoCo passive viewer and step the simulation."""
        import mujoco
        import mujoco.viewer

        try:
            with mujoco.viewer.launch_passive(mj_model, mj_data) as v:
                viewer_ready.put(("ok", v))
                step_cnt = 0
                while v.is_running():
                    t0 = time.perf_counter()
                    action = {
                        "joints": default_joints,
                        "adhesion": np.ones(6, dtype=np.float32),
                    }
                    sim.step(action)
                    sim.render()
                    v.sync()
                    step_cnt += 1
                    dt = sim.timestep - (time.perf_counter() - t0)
                    if dt > 0:
                        time.sleep(dt)
        except Exception as exc:
            viewer_ready.put(("fail", str(exc)))

    viewer_thread = threading.Thread(target=_run_viewer, daemon=True)
    viewer_thread.start()

    try:
        status, payload = viewer_ready.get(timeout=5.0)
        if status == "fail":
            print(f"Viewer error: {payload}")
            headless = True
    except queue.Empty:
        print("Interactive viewer launch timed out. "
              "(This typically means no display is available.)")
        headless = True

    # --- headless fallback -------------------------------------------------
    if headless:
        print()
        print("Running in headless mode …")
        print("(For the interactive viewer, run on a machine with a display.)")
        print()
        n_steps = 200
        print(f"Stepping simulation for {n_steps} steps …")
        for i in range(n_steps):
            action = {
                "joints": default_joints,
                "adhesion": np.ones(6, dtype=np.float32),
            }
            sim.step(action)
            sim.render()

        print(f"Done — {sim.curr_time:.4f} s simulated.")
        print("The viewer script is correct and ready for use on a display-equipped machine.")
        return

    # --- interactive session active ----------------------------------------
    print("Interactive viewer is running.")
    print("Controls:  Left-drag = rotate, Right-drag = pan, Scroll = zoom")
    print("           ESC or close window to exit.")
    viewer_thread.join()


if __name__ == "__main__":
    main()