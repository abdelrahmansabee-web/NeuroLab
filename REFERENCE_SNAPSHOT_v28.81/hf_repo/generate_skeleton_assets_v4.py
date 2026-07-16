# -*- coding: utf-8 -*-
"""Generate high-quality anatomical bone PNG assets for NeuroLab skeleton overlay."""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


def bone_gradient(size: tuple[int, int], base: tuple[int, int, int], light_dir: tuple[float, float] = (-0.35, -0.25)) -> Image.Image:
    w, h = size
    arr = np.full((h, w, 4), (0, 0, 0, 0), dtype=np.uint8)
    cx, cy = w / 2.0, h / 2.0
    for y in range(h):
        for x in range(w):
            dx = (x - cx) / (w / 2.0 + 1e-6)
            dy = (y - cy) / (h / 2.0 + 1e-6)
            dist = math.sqrt(dx * dx + dy * dy)
            shadow = dist ** 1.4 * 0.5
            highlight = max(0.0, 1.0 - ((dx - light_dir[0]) ** 2 + (dy - light_dir[1]) ** 2) * 1.8)
            r = int(np.clip(base[0] + highlight * 45 - shadow * 25, 0, 255))
            g = int(np.clip(base[1] + highlight * 40 - shadow * 22, 0, 255))
            b = int(np.clip(base[2] + highlight * 30 - shadow * 18, 0, 255))
            arr[y, x] = [r, g, b, 255]
    return Image.fromarray(arr)


def add_surface_noise(img: Image.Image, scale: float = 0.10, seed: int = 42, strength: float = 0.08) -> Image.Image:
    w, h = img.size
    rng = np.random.default_rng(seed)
    gy = max(2, int(h * scale))
    gx = max(2, int(w * scale))
    grid = rng.random((gy, gx))
    noise = np.array(Image.fromarray((grid * 255).astype(np.uint8)).resize((w, h), Image.BILINEAR))
    fine = rng.random((max(4, h // 8), max(4, w // 8)))
    fine = np.array(Image.fromarray((fine * 255).astype(np.uint8)).resize((w, h), Image.BILINEAR))
    noise = (noise * 0.6 + fine * 0.4).astype(np.uint8)
    noise_img = Image.fromarray(noise).convert("L")
    rgb = img.convert("RGB")
    noise_rgb = Image.merge("RGB", [noise_img, noise_img, noise_img])
    blended = Image.blend(rgb, noise_rgb, strength)
    alpha = img.split()[3]
    return Image.merge("RGBA", (*blended.split(), alpha))


def save_with_outline(path: Path, mask: Image.Image, base: tuple[int, int, int], seed: int,
                      light_dir: tuple[float, float] = (-0.35, -0.25)) -> None:
    w, h = mask.size
    grad = bone_gradient((w, h), base, light_dir)
    out = Image.composite(grad, Image.new("RGBA", (w, h), (0, 0, 0, 0)), mask)
    out = add_surface_noise(out, seed=seed)
    out.save(path)
    print("saved", path)


def make_humerus(path: Path) -> None:
    w, h = 320, 1500
    mask = Image.new("L", (w, h), 0)
    md = ImageDraw.Draw(mask)
    cx = w // 2
    head_r = 95
    head_y = head_r + 15
    condyle_r = 80
    condyle_y = h - condyle_r - 15
    md.ellipse([cx - head_r, head_y - head_r, cx + head_r, head_y + head_r], fill=255)
    md.ellipse([cx - condyle_r, condyle_y - condyle_r, cx + condyle_r, condyle_y + condyle_r], fill=255)
    tw, bw = head_r * 0.72, condyle_r * 0.9
    md.polygon(
        [
            (cx - tw, head_y + head_r * 0.25),
            (cx + tw, head_y + head_r * 0.25),
            (cx + bw, condyle_y - condyle_r * 0.25),
            (cx - bw, condyle_y - condyle_r * 0.25),
        ],
        fill=255,
    )
    save_with_outline(path, mask, (245, 235, 220), seed=1)


def make_forearm(path: Path) -> None:
    w, h = 380, 1300
    mask = Image.new("L", (w, h), 0)
    md = ImageDraw.Draw(mask)

    def bone(cx: int, top_r: int, bot_r: int, lean: int) -> None:
        top_y = top_r + 10
        bot_y = h - bot_r - 10
        md.ellipse([cx - top_r, top_y - top_r, cx + top_r, top_y + top_r], fill=255)
        md.ellipse([cx - top_r + lean, bot_y - top_r, cx + top_r + lean, bot_y + top_r], fill=255)
        tw, bw = top_r * 0.65, bot_r * 0.8
        md.polygon(
            [
                (cx - tw, top_y + top_r * 0.3),
                (cx + tw, top_y + top_r * 0.3),
                (cx + bw + lean, bot_y - bot_r * 0.3),
                (cx - bw + lean, bot_y - bot_r * 0.3),
            ],
            fill=255,
        )

    bone(w // 3, 60, 75, 0)
    bone(2 * w // 3, 50, 90, 0)
    save_with_outline(path, mask, (240, 230, 215), seed=2)


def make_hand(path: Path) -> None:
    w, h = 400, 520
    mask = Image.new("L", (w, h), 0)
    md = ImageDraw.Draw(mask)
    px, py = w // 2, h - 90
    palm_w, palm_h = 130, 130
    md.rounded_rectangle([px - palm_w // 2, py - palm_h, px + palm_w // 2, py], radius=35, fill=255)
    finger_w = 28
    for gx in [-48, -16, 16, 48]:
        fx = px + gx
        fy = py - palm_h
        md.rounded_rectangle([fx - finger_w // 2, fy - 110, fx + finger_w // 2, fy], radius=finger_w // 2, fill=255)
        md.ellipse([fx - finger_w * 0.45, fy - 140, fx + finger_w * 0.45, fy - 100], fill=255)
    # thumb
    tx, ty = px + palm_w // 2 + 15, py - palm_h // 2
    md.rounded_rectangle([tx, ty - 25, tx + 70, ty + 25], radius=20, fill=255)
    md.ellipse([tx + 55, ty - 45, tx + 95, ty - 5], fill=255)
    save_with_outline(path, mask, (240, 230, 215), seed=3)


def make_clavicle(path: Path) -> None:
    w, h = 900, 220
    mask = Image.new("L", (w, h), 0)
    md = ImageDraw.Draw(mask)
    pts = [(50, h // 2), (w // 3, h // 2 + 28), (2 * w // 3, h // 2 - 18), (w - 50, h // 2)]
    for i in range(len(pts) - 1):
        md.line([pts[i], pts[i + 1]], fill=255, width=50)
    md.ellipse([20, h // 2 - 35, 80, h // 2 + 35], fill=255)
    md.ellipse([w - 80, h // 2 - 35, w - 20, h // 2 + 35], fill=255)
    save_with_outline(path, mask, (240, 230, 215), seed=4)


def make_torso(path: Path) -> None:
    w, h = 520, 1100
    mask = Image.new("L", (w, h), 0)
    md = ImageDraw.Draw(mask)
    cx = w // 2
    md.rounded_rectangle([cx - 16, 30, cx + 16, h - 30], radius=8, fill=255)
    for i, y in enumerate(range(100, h - 100, 75)):
        rw = 180 + (i % 3) * 25
        md.ellipse([cx - rw, y - 12, cx, y + 12], fill=255)
        md.ellipse([cx, y - 12, cx + rw, y + 12], fill=255)
    md.polygon([(cx - 70, h - 40), (cx + 70, h - 40), (cx + 40, h - 10), (cx - 40, h - 10)], fill=255)
    save_with_outline(path, mask, (235, 225, 210), seed=5)


def make_skull(path: Path) -> None:
    w, h = 300, 400
    mask = Image.new("L", (w, h), 0)
    md = ImageDraw.Draw(mask)
    cx = w // 2
    cranium_r = 95
    md.ellipse([cx - cranium_r, 30, cx + cranium_r, 30 + 2 * cranium_r], fill=255)
    md.polygon(
        [
            (cx - 70, 30 + cranium_r),
            (cx + 70, 30 + cranium_r),
            (cx + 45, 30 + cranium_r + 90),
            (cx - 45, 30 + cranium_r + 90),
        ],
        fill=255,
    )
    md.ellipse([cx - 55, 30 + cranium_r + 75, cx + 55, 30 + cranium_r + 115], fill=255)
    save_with_outline(path, mask, (245, 235, 220), seed=6)


def make_joint(path: Path) -> None:
    w, h = 140, 140
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx, cy = w // 2, h // 2
    r = w // 2 - 6
    for i in range(r, 0, -1):
        t = i / r
        col = int(235 - t * 45)
        d.ellipse([cx - i, cy - i, cx + i, cy + i], fill=(col, col - 8, col - 16, 255))
    d.ellipse([cx - r // 2 - 5, cy - r // 2 - 5, cx - r // 4 + 5, cy - r // 4 + 5], fill=(255, 255, 255, 200))
    img.save(path)
    print("saved", path)


def main() -> None:
    out_dir = Path(__file__).parent / "assets" / "skeleton_v4"
    out_dir.mkdir(parents=True, exist_ok=True)
    np.random.seed(42)

    make_humerus(out_dir / "humerus.png")
    make_forearm(out_dir / "forearm.png")
    make_hand(out_dir / "hand.png")
    make_clavicle(out_dir / "clavicle.png")
    make_torso(out_dir / "torso.png")
    make_skull(out_dir / "skull.png")
    make_joint(out_dir / "joint.png")

    print(f"\nAll high-quality assets saved to {out_dir}")


if __name__ == "__main__":
    main()
