"""Headless previews: a small numpy z-buffer rasteriser (no OpenGL needed).

Smooth shading inside each CAD face, crisp edges between faces, outlines from depth and
normal discontinuities. Good enough to judge shapes and to make listing images.
"""

from pathlib import Path

import numpy as np
from PIL import Image

COLORS = {
    "black": (0.10, 0.09, 0.11),
    "orange": (0.95, 0.42, 0.06),
    "white": (0.92, 0.90, 0.84),
    "grey": (0.45, 0.44, 0.47),
    "blue": (0.23, 0.45, 0.70),
    "card": (0.80, 0.86, 0.93),
}


def _rgb(color) -> np.ndarray:
    return np.array(COLORS[color] if isinstance(color, str) else color, dtype=float)


def _mesh(shape, tolerance: float):
    """Triangles plus per-vertex normals averaged within each CAD face."""
    tris, norms = [], []
    shapes = shape if isinstance(shape, (list, tuple)) else [shape]
    for face in (f for sh in shapes for f in sh.faces()):
        verts, idx = face.tessellate(tolerance, 0.2)
        if not idx:
            continue
        v = np.array([[p.X, p.Y, p.Z] for p in verts])
        t = np.array(idx)
        fn = np.cross(v[t[:, 1]] - v[t[:, 0]], v[t[:, 2]] - v[t[:, 0]])
        vn = np.zeros_like(v)
        for k in range(3):
            np.add.at(vn, t[:, k], fn)
        vn /= np.linalg.norm(vn, axis=1, keepdims=True) + 1e-12
        tris.append(v[t])
        norms.append(vn[t])
    if not tris:
        return np.zeros((0, 3, 3)), np.zeros((0, 3, 3))
    return np.concatenate(tris), np.concatenate(norms)


def _look_at(eye, target, up=(0, 0, 1)):
    f = np.asarray(target, float) - eye
    f /= np.linalg.norm(f)
    r = np.cross(f, up)
    r /= np.linalg.norm(r)
    u = np.cross(r, f)
    return np.stack([r, u, -f])  # rows: camera x, y, z (camera looks along -z)


def render(items, path, elev=28.0, azim=-60.0, zoom=1.0, size=(900, 700), ss=2,
           target=None, distance=None, tolerance=0.08, background=((0.93, 0.92, 0.95),
                                                                (0.72, 0.70, 0.76))):
    """Render [(shape, colour), ...] to `path`. Angles in degrees, azim around +z."""
    meshes = [(*_mesh(s, tolerance), _rgb(c)) for s, c in items]
    pts = np.concatenate([m[0].reshape(-1, 3) for m in meshes if len(m[0])])
    lo, hi = pts.min(0), pts.max(0)
    center = (lo + hi) / 2 if target is None else np.asarray(target, float)
    radius = np.linalg.norm(hi - lo) / 2
    el, az = np.radians(elev), np.radians(azim)
    direction = np.array([np.cos(el) * np.cos(az), np.cos(el) * np.sin(az), np.sin(el)])
    dist = distance or radius * 3.2
    eye = center + direction * dist
    rot = _look_at(eye, center)
    w, h = size[0] * ss, size[1] * ss
    focal = 0.5 * h * dist / (radius * 1.15) * zoom

    zbuf = np.full((h, w), np.inf)
    nbuf = np.zeros((h, w, 3))
    cbuf = np.zeros((h, w, 3))
    light = rot.T @ np.array([-0.45, 0.65, 0.62])
    light /= np.linalg.norm(light)
    fill = rot.T @ np.array([0.6, -0.2, 0.75])
    fill /= np.linalg.norm(fill)

    for tri, nrm, base in meshes:
        if not len(tri):
            continue
        cam = (tri - eye) @ rot.T  # (n, 3, 3) camera space
        z = -cam[..., 2]
        ok = (z > 1e-3).all(1)
        cam, z, nrm = cam[ok], z[ok], nrm[ok]
        sx = w / 2 + focal * cam[..., 0] / z
        sy = h / 2 - focal * cam[..., 1] / z
        for i in range(len(sx)):
            x0, x1 = int(max(sx[i].min(), 0)), int(min(np.ceil(sx[i].max()), w - 1))
            y0, y1 = int(max(sy[i].min(), 0)), int(min(np.ceil(sy[i].max()), h - 1))
            if x1 < x0 or y1 < y0:
                continue
            gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
            (ax_, bx, cx), (ay, by, cy) = sx[i], sy[i]
            den = (by - cy) * (ax_ - cx) + (cx - bx) * (ay - cy)
            if abs(den) < 1e-9:
                continue
            l0 = ((by - cy) * (gx - cx) + (cx - bx) * (gy - cy)) / den
            l1 = ((cy - ay) * (gx - cx) + (ax_ - cx) * (gy - cy)) / den
            l2 = 1 - l0 - l1
            inside = (l0 >= -1e-6) & (l1 >= -1e-6) & (l2 >= -1e-6)
            if not inside.any():
                continue
            iz = l0 / z[i, 0] + l1 / z[i, 1] + l2 / z[i, 2]  # perspective-correct
            depth = 1 / np.where(inside, iz, 1e-12)
            sub = zbuf[y0:y1 + 1, x0:x1 + 1]
            win = inside & (depth < sub)
            if not win.any():
                continue
            sub[win] = depth[win]
            n = (l0[..., None] * nrm[i, 0] / z[i, 0] + l1[..., None] * nrm[i, 1] / z[i, 1]
                 + l2[..., None] * nrm[i, 2] / z[i, 2]) / iz[..., None]
            nbuf[y0:y1 + 1, x0:x1 + 1][win] = n[win]
            cbuf[y0:y1 + 1, x0:x1 + 1][win] = base

    hit = np.isfinite(zbuf)
    n = nbuf / (np.linalg.norm(nbuf, axis=2, keepdims=True) + 1e-12)
    view = direction  # towards the camera
    flip = (n @ view) < 0
    n[flip] *= -1
    diff = np.clip(n @ light, 0, 1)
    diff2 = np.clip(n @ fill, 0, 1)
    half = light + view
    half /= np.linalg.norm(half)
    spec = np.clip(n @ half, 0, 1) ** 40
    shade = 0.28 + 0.62 * diff + 0.18 * diff2
    img = cbuf * shade[..., None] + 0.22 * spec[..., None]

    # outlines from depth / normal discontinuities
    zf = np.where(hit, zbuf, zbuf[hit].max() * 1.5 if hit.any() else 1)
    edge = np.zeros_like(zf, dtype=bool)
    for axis in (0, 1):  # compare each pixel with its next neighbour (no wrap-around)
        a = [slice(None)] * 2
        b = [slice(None)] * 2
        a[axis], b[axis] = slice(None, -1), slice(1, None)
        a, b = tuple(a), tuple(b)
        dz = np.abs(zf[a] - zf[b])
        dn = 1 - np.sum(n[a] * n[b], axis=2)
        edge[a] |= (dz > 0.004 * zf[a]) | ((dn > 0.35) & hit[a])
    img[edge & hit] *= 0.35

    top, bottom = (np.array(c) for c in background)
    t = np.linspace(0, 1, h)[:, None, None]
    bg = top * (1 - t) + bottom * t
    out = np.where(hit[..., None], img, np.broadcast_to(bg, img.shape))
    out = (np.clip(out, 0, 1) * 255).astype(np.uint8)
    Image.fromarray(out).resize(size, Image.LANCZOS).save(path)


def gif(frames_items, path, duration=80, **kw):
    """Render an iterable of item lists into an animated GIF that plays forth and back."""
    frames = list(frames_items)
    if not frames:
        raise ValueError("gif() needs at least one frame")
    path = Path(path)
    tmp_paths = [path.with_suffix(f".{k:03d}.png") for k in range(len(frames))]
    try:
        images = []
        for items, tmp in zip(frames, tmp_paths):
            render(items, tmp, **kw)
            images.append(Image.open(tmp).convert("P", palette=Image.ADAPTIVE))
        seq = images + images[-2:0:-1]
        seq[0].save(path, save_all=True, append_images=seq[1:], duration=duration, loop=0)
    finally:
        for tmp in tmp_paths:
            tmp.unlink(missing_ok=True)
