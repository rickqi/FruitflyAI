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
        bridge.mm[HEADER_SIZE:] = bytes([99])*FRAME_BYTES
        assert bridge.read_frame() == good
        assert bridge.frame_metadata == metadata
