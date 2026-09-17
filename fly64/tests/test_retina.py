import numpy as np
import pytest
from fly64.retina import BASES, SphericalRetina, angular_rays, atlas_indices
from fly64.bridge import SharedBridge, HEADER_SIZE, FRAME_BYTES


def direction_atlas():
    yy, xx = np.mgrid[:128,:128]
    u, v = (xx+.5)/64-1, 1-(yy+.5)/64
    atlas = np.zeros((256,384,3), np.uint8)
    for face, (right, up, forward) in enumerate(BASES):
        rays = forward + u[...,None]*right + v[...,None]*up
        rays /= np.linalg.norm(rays,axis=-1,keepdims=True)
        atlas[face//3*128:(face//3+1)*128,face%3*128:(face%3+1)*128] = ((rays+1)*127.5).astype(np.uint8)
    return atlas


def test_cube_centers_and_orientation():
    atlas = direction_atlas().reshape(-1,3)
    # Front/right/back/left/up/down must pick the corresponding face centers.
    indices = atlas_indices(BASES[:,2])
    faces = (indices//384//128)*3 + (indices%384)//128
    np.testing.assert_array_equal(faces, np.arange(6))
    rays = angular_rays(np.array([-120,-60,0,60,120]),np.array([40,-40,0,40,-40]))
    np.testing.assert_allclose(atlas[atlas_indices(rays)]/127.5-1, rays, atol=.02)


def test_spherical_cones_cross_cube_seams_without_discontinuity():
    pixels = np.array([[23.5,31*(a+135)/143.5] for a in (-45.1,-45,-44.9)])
    retina = SphericalRetina(pixels)
    values = retina.sample(direction_atlas())
    assert np.max(np.abs(np.diff(values,axis=0))) < .01
    np.testing.assert_allclose(np.linalg.norm(retina.rays,axis=1),1,atol=1e-6)


def test_eye_sides_and_fisheye_preview():
    retina = SphericalRetina(np.array([[23.5,0],[23.5,31],[23.5,32],[23.5,63]]))
    az = np.rad2deg(np.arctan2(retina.rays[:,0],retina.rays[:,2]))
    np.testing.assert_allclose(az,[-135,8.5,-8.5,135],atol=1e-4)
    image = retina.preview(direction_atlas())
    assert image.shape == (128,256,3)
    assert np.all(image[~retina.mask] == 0)
    assert image[retina.mask].mean() > 20


def test_clean_break_rejects_old_images_and_protocol(tmp_path):
    retina = SphericalRetina(np.array([[24,16]]))
    with pytest.raises(ValueError): retina.sample(np.zeros((48,64,3),np.uint8))
    with SharedBridge(tmp_path/'bridge') as bridge:
        assert HEADER_SIZE == 128 and FRAME_BYTES == 6*128*128*3
        bridge.mm[:8] = b'FLY64V1\0'
        with pytest.raises(ValueError): SharedBridge(bridge.path,create=False)


def test_replay_keeps_each_tick_and_camera_but_deduplicates_images(tmp_path):
    from fly64.main import Replay
    from fly64.model import Control
    import json
    r = Replay(tmp_path/'run.npz', fixture=True)
    frame = direction_atlas()
    for i in range(8):
        r.add(i*.02,frame,Control(0,0,False,0,0,0),np.array([],np.uint32),
              dict(pose=[1,2,3,.5], game_frame=30))
    r.close()
    index = json.loads((tmp_path/'run.index.json').read_text())
    with np.load(tmp_path/index['chunks'][0]) as chunk:
        assert len(chunk['frames']) == 1 and len(chunk['timestamps']) == 8
        np.testing.assert_array_equal(chunk['frame_indices'], np.zeros(8))
        np.testing.assert_array_equal(chunk['camera'], np.tile([1,2,3,.5,30],(8,1)))
    assert not list(tmp_path.glob('*.partial'))


def test_pose_and_pixels_share_the_frame_seqlock(tmp_path):
    import struct
    with SharedBridge(tmp_path/'bridge') as bridge:
        struct.pack_into('<4fIf',bridge.mm,64,1,2,3,.5,123,4.5)
        bridge.write_frame(bytes([17])*FRAME_BYTES)
        good = bridge.read_frame()
        metadata = bridge.frame_metadata.copy()
        assert metadata == dict(pose=[1,2,3,.5],game_frame=123,render_ms=4.5)
        struct.pack_into('<I',bridge.mm,12,good[0]+1)
        struct.pack_into('<4fIf',bridge.mm,64,9,9,9,9,999,9)
        # Corrupt ONLY the frame region: the mmap also holds a 320x240 SCREEN
        # buffer after FRAME_BYTES, so `bridge.mm[HEADER_SIZE:]` is longer than
        # one frame and raises IndexError (test-drift, EVO-068).
        bridge.mm[HEADER_SIZE:HEADER_SIZE+FRAME_BYTES] = bytes([99])*FRAME_BYTES
        assert bridge.read_frame() == good
        assert bridge.frame_metadata == metadata


# ---- T4/T5-style HRC direction-selective motion detection (EVO Round 7) ----

def hrc_retina(rows=range(10, 20), cols=range(4, 29)):
    """Retina on a small left-eye grid (all cells in left eye, col < 32)."""
    pixels = np.array([(r, c) for r in rows for c in cols], float)
    return SphericalRetina(pixels), len(pixels), list(cols)


def hrc_lum(n_rows, cols, bright_cols, value=1.0):
    """Per-cell luminance with a bright vertical bar at the given columns."""
    lum = np.zeros(n_rows * len(cols), np.float32)
    for i, c in enumerate(cols):
        if c in bright_cols:
            lum[np.arange(n_rows) * len(cols) + i] = value
    return lum


def test_hrc_first_frame_primes_without_signal():
    retina, n, cols = hrc_retina()
    lum = hrc_lum(10, cols, {10, 11})
    out = retina.compute_hrc(lum)
    assert out["hrc_right"] == 0.0 and out["hrc_left"] == 0.0
    assert out["hrc_asymmetry"] == 0.0
    # Prime frame is stored; second identical (static) frame gives no signal.
    out2 = retina.compute_hrc(lum)
    assert out2["hrc_right"] == 0.0 and out2["hrc_left"] == 0.0
    assert abs(out2["hrc_asymmetry"]) < 1e-6


def test_hrc_right_moving_bar_detects_rightward():
    retina, n, cols = hrc_retina()
    retina.compute_hrc(hrc_lum(10, cols, {10, 11}))          # prime
    out = retina.compute_hrc(hrc_lum(10, cols, {12, 13}))    # bar moved right
    assert out["hrc_right"] > 0.0
    assert out["hrc_right"] > out["hrc_left"]
    assert out["hrc_asymmetry"] < 0.0   # positive asymmetry = leftward motion
    assert out["hrc_translation_x"] > 0.0


def test_hrc_left_moving_bar_detects_leftward():
    retina, n, cols = hrc_retina()
    retina.compute_hrc(hrc_lum(10, cols, {12, 13}))          # prime
    out = retina.compute_hrc(hrc_lum(10, cols, {10, 11}))    # bar moved left
    assert out["hrc_left"] > 0.0
    assert out["hrc_left"] > out["hrc_right"]
    assert out["hrc_asymmetry"] > 0.0


def test_hrc_static_texture_gives_no_directional_signal():
    retina, n, cols = hrc_retina()
    rng = np.random.default_rng(7)
    lum = rng.random(n).astype(np.float32)
    retina.compute_hrc(lum)
    out = retina.compute_hrc(lum.copy())   # same frame = static texture
    assert out["hrc_right"] == 0.0 and out["hrc_left"] == 0.0
    assert out["hrc_up"] == 0.0 and out["hrc_down"] == 0.0
    assert abs(out["hrc_asymmetry"]) < 1e-6
    assert abs(out["hrc_translation_x"]) < 1e-6


def test_hrc_looming_population_channels_present():
    retina, n, cols = hrc_retina()
    retina.compute_hrc(hrc_lum(10, cols, {10, 11}))
    out = retina.compute_hrc(hrc_lum(10, cols, {12, 13}))
    looming = out["_looming"]
    assert len(looming) == 32   # 16 sectors x L/R visual hemifield
    # All cells are left-eye, lower-field rows (elevation derived from row>32
    # is not guaranteed on this synthetic grid), so at least one channel is
    # non-zero where the moving bar lives.
    assert max(looming.values()) > 0.0


def test_compute_flow_hrc_keys_are_purely_additive():
    retina = SphericalRetina(np.array([(r, c) for r in range(10, 20)
                                       for c in range(4, 29)], float))
    atlas = direction_atlas()
    old_keys = {
        "tau", "sectors", "sectors_16", "left_right_asymmetry",
        "center_expansion", "lower_field_green", "terrain",
        "wall_score", "ramp_score", "opening_score", "sky_score",
        "ground_angle", "door_frame_score", "opening_width",
        "on_raw", "off_raw", "sustained_raw",
        "edge_0", "edge_45", "edge_90", "edge_135",
        "emd_on_right", "emd_on_left", "emd_on_down", "emd_on_up",
        "emd_off_right", "emd_off_left", "emd_off_down", "emd_off_up",
        "emd_on_total", "emd_off_total",
    }
    new_keys = {
        "hrc_right", "hrc_left", "hrc_up", "hrc_down", "hrc_asymmetry",
        "hrc_translation_x", "hrc_translation_y", "hrc_rotation",
        "hrc_looming_az0_upper_L", "hrc_looming_az7_lower_R",
    }
    atlas_copy = atlas.copy()
    result = retina.compute_flow(atlas)
    result2 = retina.compute_flow(atlas)
    assert old_keys <= set(result)
    assert new_keys <= set(result)
    np.testing.assert_array_equal(atlas, atlas_copy)   # read-only observation


def test_hrc_reset_temporal_state_clears_hrc_buffer():
    retina, n, cols = hrc_retina()
    retina.compute_hrc(hrc_lum(10, cols, {10, 11}))
    retina.reset_temporal_state()
    out = retina.compute_hrc(hrc_lum(10, cols, {12, 13}))
    assert out["hrc_right"] == 0.0   # buffer cleared -> prime frame again


# ---- Indoor enclosure detection (EVO Round 9) ----

def _scene_atlas(indoor: bool):
    """Outdoor: blue sky above horizon, green ground, smooth.
    Indoor: dark textured (striped) ceiling, blue carpet, vertical wall edges."""
    atlas = np.zeros((256, 384, 3), np.uint8)
    if indoor:
        top = (80, 80, 90)         # dark gray ceiling (non-blue)
        bottom = (60, 40, 180)     # blue carpet
    else:
        top = (60, 120, 220)       # blue sky (B >> R,G)
        bottom = (60, 180, 60)     # green grass
    for face_row in range(2):
        for face_col in range(3):
            tile = atlas[face_row*128:(face_row+1)*128, face_col*128:(face_col+1)*128]
            tile[:64] = top
            tile[64:] = bottom
            if indoor:
                # vertical structural stripes on the "ceiling" area + wall seams
                for x in range(0, 128, 16):
                    tile[:64, x:x+4] = (200, 200, 210)
                    tile[64:, x:x+2] = (40, 40, 50)
    return atlas


def _full_retina():
    return SphericalRetina(np.array([(r, c) for r in range(0, 48, 2)
                                     for c in range(0, 64, 2)], float))


def test_indoor_scene_scores_higher_enclosure_than_outdoor():
    retina = _full_retina()
    indoor = _scene_atlas(indoor=True)
    outdoor = _scene_atlas(indoor=False)
    r_in = retina.compute_flow(indoor)
    r_out = retina.compute_flow(outdoor)
    assert r_in["enclosure_score"] > r_out["enclosure_score"]
    assert r_in["enclosure_score"] > 0.35


def test_indoor_terrain_label_and_sky_suppression():
    retina = _full_retina()
    r_in = retina.compute_flow(_scene_atlas(indoor=True))
    assert r_in["terrain"] == "indoor"
    # Blue-dominance gate suppresses indoor "sky": raw (upper_mean-0.1)*2 would
    # clip to 1.0 on the bright striped ceiling; gate must pull it well below.
    assert r_in["sky_score"] < 0.5
    assert r_in["upper_blue"] < 0.2


def test_enclosure_keys_are_additive():
    retina = _full_retina()
    out = retina.compute_flow(_scene_atlas(indoor=False))
    assert "enclosure_score" in out and "upper_blue" in out
    # old keys still present
    for k in ("tau", "terrain", "sky_score", "hrc_asymmetry", "left_right_asymmetry"):
        assert k in out
