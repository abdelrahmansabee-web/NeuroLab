import os
import sys
import platform
import numpy as np
import trimesh
import pyrender
import cv2
from typing import List, Tuple


_PLATFORM = platform.system()
if _PLATFORM == "Linux":
    os.environ["PYOPENGL_PLATFORM"] = "egl"


def _make_offscreen_renderer(width: int, height: int):
    """Create a pyrender OffscreenRenderer with the best available backend."""
    last_exc = None
    if _PLATFORM == "Linux":
        for backend in ["egl", "osmesa"]:
            os.environ["PYOPENGL_PLATFORM"] = backend
            try:
                import importlib
                if "OpenGL" in sys.modules:
                    importlib.reload(sys.modules["OpenGL"])
                renderer = pyrender.OffscreenRenderer(width, height)
                print(f"[skeleton3d] using {backend} backend")
                return renderer
            except Exception as exc:
                last_exc = exc
                print(f"[skeleton3d] {backend} failed: {exc}")
        raise RuntimeError(f"No headless OpenGL backend available: {last_exc}")
    else:
        # Windows/macOS: use pyglet/GLFW display backend
        renderer = pyrender.OffscreenRenderer(width, height)
        print("[skeleton3d] using platform default backend")
        return renderer


class Skeleton3DRenderer:
    """Render a 3-D articulated skeleton from MediaPipe-style landmarks."""

    BONE_RADIUS = 0.028
    JOINT_RADIUS = 0.035
    HEAD_RADIUS = 0.06

    def __init__(self, width: int = 1920, height: int = 1080):
        self.width = width
        self.height = height
        self.scene = pyrender.Scene(
            bg_color=(0.0, 0.0, 0.0, 0.0),
            ambient_light=(0.85, 0.84, 0.82, 1.0),
        )
        self.camera = pyrender.camera.OrthographicCamera(
            xmag=1.0,
            ymag=1.0,
            znear=0.05,
            zfar=5.0,
        )
        # Position camera on -Z looking toward origin
        camera_pose = self._look_at(np.array([0.0, 0.0, 1.5]), np.array([0.0, 0.0, 0.0]))
        self.camera_node = self.scene.add(self.camera, pose=camera_pose)
        self.light = pyrender.DirectionalLight(color=(1.0, 0.98, 0.95), intensity=2.5)
        self.scene.add(self.light, pose=camera_pose)
        self.renderer = None

    def _look_at(self, eye: np.ndarray, target: np.ndarray) -> np.ndarray:
        eye = eye.astype(np.float64)
        target = target.astype(np.float64)
        forward = eye - target
        forward = forward / np.linalg.norm(forward)
        right = np.cross(np.array([0.0, 1.0, 0.0]), forward)
        if np.linalg.norm(right) < 1e-6:
            right = np.array([1.0, 0.0, 0.0])
        right = right / np.linalg.norm(right)
        up = np.cross(forward, right)
        pose = np.eye(4, dtype=np.float64)
        pose[:3, 0] = right
        pose[:3, 1] = up
        pose[:3, 2] = forward
        pose[:3, 3] = eye
        return pose

    def _cylinder(self, a: np.ndarray, b: np.ndarray, radius: float, color: Tuple[float, float, float, float]) -> pyrender.Mesh:
        vec = b - a
        length = np.linalg.norm(vec)
        if length < 1e-6:
            length = 1e-6
        cyl = trimesh.creation.cylinder(radius=radius, height=length, sections=24)
        axis = np.array([0.0, 1.0, 0.0])
        rot = trimesh.geometry.align_vectors(axis, vec / length)
        if rot is not None:
            cyl.apply_transform(rot)
        cyl.apply_translation((a + b) / 2)
        mesh = pyrender.Mesh.from_trimesh(
            cyl,
            material=pyrender.MetallicRoughnessMaterial(
                baseColorFactor=color,
                metallicFactor=0.1,
                roughnessFactor=0.6,
            ),
            smooth=True,
        )
        return mesh

    def _sphere(self, center: np.ndarray, radius: float, color: Tuple[float, float, float, float]) -> pyrender.Mesh:
        sph = trimesh.creation.icosphere(subdivisions=2, radius=radius)
        sph.apply_translation(center)
        return pyrender.Mesh.from_trimesh(
            sph,
            material=pyrender.MetallicRoughnessMaterial(
                baseColorFactor=color,
                metallicFactor=0.1,
                roughnessFactor=0.5,
            ),
            smooth=True,
        )

    def render(
        self,
        landmarks_3d: dict,
        active_side: str = "right",
    ) -> np.ndarray:
        """
        landmarks_3d: dict mapping joint name -> (x, y, z) in normalized screen coords.
        Returns BGRA image of shape (height, width, 4).
        """
        active = active_side.lower() == "left" and "LEFT" or "RIGHT"
        active_color = (0.15, 0.75, 1.0, 1.0)
        inactive_color = (0.88, 0.84, 0.78, 1.0)
        joint_color = (0.92, 0.90, 0.86, 1.0)

        # Map 2D normalized coords to camera-view 3D plane z=0.
        # Use orthographic projection so 1 unit in X/Y maps to a known screen fraction.
        # We want (x,y) in [0,1] to span the video frame exactly.
        # Orthographic xmag=1 => NDC x in [-1,1] maps to clip; we scale so the
        # skeleton fills the frame naturally.
        pts = {}
        for name, (x, y, z) in landmarks_3d.items():
            pts[name] = np.array([
                (x - 0.5) * 2.0 * (self.width / self.height),
                -(y - 0.5) * 2.0,
                0.0,
            ])

        meshes: List[trimesh.Trimesh] = []

        def add_bone(n1: str, n2: str):
            if n1 not in pts or n2 not in pts:
                return
            is_active = active in n1 and active in n2
            color = active_color if is_active else inactive_color
            meshes.append(self._cylinder(pts[n1], pts[n2], self.BONE_RADIUS, color))
            meshes.append(self._sphere(pts[n1], self.JOINT_RADIUS, joint_color))
            meshes.append(self._sphere(pts[n2], self.JOINT_RADIUS, joint_color))

        # Torso
        add_bone("LEFT_SHOULDER", "RIGHT_SHOULDER")
        add_bone("LEFT_SHOULDER", "LEFT_HIP")
        add_bone("RIGHT_SHOULDER", "RIGHT_HIP")
        add_bone("LEFT_HIP", "RIGHT_HIP")
        if "LEFT_SHOULDER" in pts and "RIGHT_SHOULDER" in pts:
            neck = (pts["LEFT_SHOULDER"] + pts["RIGHT_SHOULDER"]) / 2
            if "LEFT_HIP" in pts and "RIGHT_HIP" in pts:
                pelvis = (pts["LEFT_HIP"] + pts["RIGHT_HIP"]) / 2
                meshes.append(self._cylinder(neck, pelvis, self.BONE_RADIUS * 0.8, inactive_color))

        # Arms
        add_bone("LEFT_SHOULDER", "LEFT_ELBOW")
        add_bone("LEFT_ELBOW", "LEFT_WRIST")
        add_bone("RIGHT_SHOULDER", "RIGHT_ELBOW")
        add_bone("RIGHT_ELBOW", "RIGHT_WRIST")

        # Head sphere at nose
        if "NOSE" in pts:
            meshes.append(self._sphere(pts["NOSE"], self.HEAD_RADIUS, inactive_color))

        if not meshes:
            return np.zeros((self.height, self.width, 4), dtype=np.uint8)

        # Combine all meshes into one node
        for m in meshes:
            self.scene.add(m)

        if self.renderer is None:
            self.renderer = _make_offscreen_renderer(self.width, self.height)

        flags = pyrender.RenderFlags.RGBA
        color, depth = self.renderer.render(self.scene, flags=flags)

        # Clear dynamic meshes from scene
        for node in list(self.scene.mesh_nodes):
            self.scene.remove_node(node)

        # Convert RGBA -> BGRA for OpenCV
        return cv2.cvtColor(color, cv2.COLOR_RGBA2BGRA)

    def close(self):
        if self.renderer is not None:
            self.renderer.delete()
            self.renderer = None
