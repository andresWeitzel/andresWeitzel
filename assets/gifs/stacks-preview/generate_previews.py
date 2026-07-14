"""
Preview-only 3D neon sci-fi GIFs for README section titles.
Does NOT overwrite assets/gifs/stacks/*.gif
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

OUT_DIR = Path(__file__).resolve().parent
SIZE = 200
FRAMES = 64
DURATION_MS = 70
BG = (4, 9, 20)
CYAN = (0, 200, 255)
CYAN_SOFT = (140, 235, 255)
CYAN_MID = (0, 140, 210)
CYAN_DEEP = (0, 55, 110)
WHITE = (235, 248, 255)


def clamp(v, a=0, b=255):
    return max(a, min(b, int(v)))


def mix(c1, c2, t):
    t = max(0.0, min(1.0, t))
    return tuple(clamp(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def with_alpha(rgb, a):
    return (*rgb, clamp(a))


def rot_y(x, y, z, ang):
    ca, sa = math.cos(ang), math.sin(ang)
    return x * ca + z * sa, y, -x * sa + z * ca


def rot_x(x, y, z, ang):
    ca, sa = math.cos(ang), math.sin(ang)
    return x, y * ca - z * sa, y * sa + z * ca


def project(x, y, z, cx=None, cy=None, scale=2.15):
    if cx is None:
        cx = SIZE / 2
    if cy is None:
        cy = SIZE / 2 + 6
    # soft isometric
    px = cx + (x - z) * scale * 0.86
    py = cy + (x + z) * scale * 0.48 - y * scale
    depth = x + z + y * 0.2
    return px, py, depth


def transform(points, yaw, pitch, lift=0.0):
    out = []
    for x, y, z in points:
        x, y, z = rot_y(x, y + lift, z, yaw)
        x, y, z = rot_x(x, y, z, pitch)
        out.append((x, y, z))
    return out


def face_normal(pts3):
    ax, ay, az = pts3[1][0] - pts3[0][0], pts3[1][1] - pts3[0][1], pts3[1][2] - pts3[0][2]
    bx, by, bz = pts3[2][0] - pts3[0][0], pts3[2][1] - pts3[0][1], pts3[2][2] - pts3[0][2]
    nx = ay * bz - az * by
    ny = az * bx - ax * bz
    nz = ax * by - ay * bx
    length = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
    return nx / length, ny / length, nz / length


def shade(normal, lit=(0.45, 0.85, -0.35)):
    lx, ly, lz = lit
    l = math.sqrt(lx * lx + ly * ly + lz * lz)
    lx, ly, lz = lx / l, ly / l, lz / l
    ndot = max(0.0, normal[0] * lx + normal[1] * ly + normal[2] * lz)
    return 0.28 + 0.72 * ndot


class Scene:
    def __init__(self):
        self.faces = []  # (depth, poly2d, fill_rgba, edge_rgba)

    def add_face(self, pts3, fill, edge=None, edge_w=1):
        if len(pts3) < 3:
            return
        n = face_normal(pts3)
        # backface-ish cull soft
        if n[1] < -0.85 and n[0] + n[2] < -0.2:
            return
        s = shade(n)
        col = mix(CYAN_DEEP, fill, s)
        hi = mix(col, WHITE, 0.18 * s)
        projected = [project(*p) for p in pts3]
        depth = sum(p[2] for p in projected) / len(projected)
        poly = [(p[0], p[1]) for p in projected]
        self.faces.append((depth, poly, with_alpha(hi, 195), with_alpha(edge or CYAN_SOFT, 220), edge_w))

    def add_edge(self, a3, b3, color=CYAN_SOFT, width=2, alpha=210):
        a = project(*a3)
        b = project(*b3)
        depth = (a[2] + b[2]) / 2
        self.faces.append((depth, [(a[0], a[1]), (b[0], b[1])], None, with_alpha(color, alpha), width))

    def add_disc(self, center, rx, ry, rz, yaw, pitch, lift, fill, segments=28):
        pts = []
        for i in range(segments):
            a = i * 2 * math.pi / segments
            pts.append((center[0] + rx * math.cos(a), center[1], center[2] + rz * math.sin(a)))
        pts = transform(pts, yaw, pitch, lift)
        self.add_face(pts, fill, CYAN)

    def render(self, t):
        img = Image.new("RGB", (SIZE, SIZE), BG)
        # ambient vignette glow under object
        glow = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow)
        pulse = 0.55 + 0.45 * (0.5 + 0.5 * math.sin(t * 2 * math.pi))
        cx = SIZE / 2
        cy = SIZE / 2 + 70
        gd.ellipse([cx - 70, cy - 18, cx + 70, cy + 18], fill=with_alpha(CYAN_MID, int(55 * pulse)))
        glow = glow.filter(ImageFilter.GaussianBlur(12))
        img = Image.alpha_composite(img.convert("RGBA"), glow).convert("RGB")

        # pedestal rings
        ped = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
        pd = ImageDraw.Draw(ped)
        for i, (rx, ry, a) in enumerate([(58, 15, 110), (44, 11, 160), (30, 8, 200)]):
            col = mix(CYAN_DEEP, CYAN, 0.45 + 0.2 * pulse)
            pd.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], outline=with_alpha(col, a), width=2)
        # orbiting pedestal spark
        a = t * 2 * math.pi
        sx = cx + 58 * math.cos(a)
        sy = cy + 15 * math.sin(a) * 0.35
        pd.ellipse([sx - 2.5, sy - 2.5, sx + 2.5, sy + 2.5], fill=with_alpha(CYAN_SOFT, 240))
        ped = ped.filter(ImageFilter.GaussianBlur(0.4))
        img = Image.alpha_composite(img.convert("RGBA"), ped)

        # draw faces back-to-front
        layer = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        for depth, poly, fill, edge, width in sorted(self.faces, key=lambda f: f[0]):
            if fill is not None and len(poly) >= 3:
                d.polygon(poly, fill=fill, outline=edge)
            elif len(poly) == 2:
                d.line(poly, fill=edge, width=width)
            if fill is not None and edge is not None and len(poly) >= 3:
                d.line(poly + [poly[0]], fill=edge, width=width)

        # soft outer glow of geometry
        glow2 = layer.filter(ImageFilter.GaussianBlur(3))
        glow2 = ImageEnhance.Brightness(glow2).enhance(1.35)
        out = Image.alpha_composite(img, glow2)
        out = Image.alpha_composite(out, layer)
        return ImageEnhance.Contrast(out.convert("RGB")).enhance(1.08)


def hover(t):
    return 2.0 * math.sin(t * 2 * math.pi)


def spin(t):
    return t * 2 * math.pi


def rock(t, amp=0.22):
    return amp * math.sin(t * 2 * math.pi)


def icon_motion(t):
    """
    Giro completo 360° (1 vuelta por loop), diagonal hacia la izquierda.
    yaw da la vuelta entera; pitch mantiene la inclinación isométrica.
    """
    yaw = -0.55 + t * 2 * math.pi  # 360° cerrados al reiniciar el GIF
    pitch = 0.34
    lift = hover(t)
    return yaw, pitch, lift


# ---------- models ----------

def box_faces(x0, x1, y0, y1, z0, z1):
    return [
        [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0)],  # front-ish
        [(x0, y0, z1), (x0, y1, z1), (x1, y1, z1), (x1, y0, z1)],
        [(x0, y0, z0), (x0, y0, z1), (x1, y0, z1), (x1, y0, z0)],  # bottom
        [(x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1)],  # top
        [(x0, y0, z0), (x0, y1, z0), (x0, y1, z1), (x0, y0, z1)],
        [(x1, y0, z0), (x1, y0, z1), (x1, y1, z1), (x1, y1, z0)],
    ]


def cylinder_faces(radius, y0, y1, segs=16):
    faces = []
    top, bot = [], []
    for i in range(segs):
        a0 = i * 2 * math.pi / segs
        a1 = (i + 1) * 2 * math.pi / segs
        x0, z0 = radius * math.cos(a0), radius * math.sin(a0)
        x1, z1 = radius * math.cos(a1), radius * math.sin(a1)
        faces.append([(x0, y0, z0), (x1, y0, z1), (x1, y1, z1), (x0, y1, z0)])
        top.append((x0, y1, z0))
        bot.append((x0, y0, z0))
    faces.append(list(reversed(top)))
    faces.append(bot)
    return faces


def add_transformed(scene: Scene, faces, yaw, pitch, lift, fill):
    for face in faces:
        scene.add_face(transform(face, yaw, pitch, lift), fill)


def translate_faces(faces, dx=0, dy=0, dz=0):
    return [[(x + dx, y + dy, z + dz) for x, y, z in face] for face in faces]


def sphere_faces(r, cx=0, cy=0, cz=0, stacks=7, slices=12):
    faces = []
    for i in range(stacks):
        v0 = i / stacks * math.pi
        v1 = (i + 1) / stacks * math.pi
        for j in range(slices):
            u0 = j / slices * 2 * math.pi
            u1 = (j + 1) / slices * 2 * math.pi

            def pt(v, u):
                return (
                    cx + r * math.sin(v) * math.cos(u),
                    cy + r * math.cos(v),
                    cz + r * math.sin(v) * math.sin(u),
                )

            p00, p01, p10, p11 = pt(v0, u0), pt(v0, u1), pt(v1, u0), pt(v1, u1)
            if i > 0:
                faces.append([p00, p01, p11])
            if i < stacks - 1:
                faces.append([p00, p11, p10])
    return faces


def extrude_poly(poly_xy, z0, z1):
    """poly_xy list of (x,y), extruded along Z for a standing plate (then we remap)."""
    faces = []
    n = len(poly_xy)
    # front / back in Z
    front = [(x, y, z1) for x, y in poly_xy]
    back = [(x, y, z0) for x, y in reversed(poly_xy)]
    faces.append(front)
    faces.append(back)
    for i in range(n):
        j = (i + 1) % n
        x0, y0 = poly_xy[i]
        x1, y1 = poly_xy[j]
        faces.append([(x0, y0, z0), (x1, y1, z0), (x1, y1, z1), (x0, y0, z1)])
    return faces


def hexagon_xy(r):
    return [(r * math.cos(i * math.pi / 3 - math.pi / 6), r * math.sin(i * math.pi / 3 - math.pi / 6)) for i in range(6)]


def frame_database(t):
    """Classic stacked DB cylinders (like the banner center)."""
    s = Scene()
    yaw, pitch, lift = icon_motion(t)
    # thin pancake discs stacked with visible ellipses
    for i, y0 in enumerate((-12, -1, 10)):
        add_transformed(
            s,
            cylinder_faces(15, y0, y0 + 6, 20),
            yaw,
            pitch,
            lift,
            mix(CYAN_MID, CYAN_SOFT, 0.15 + 0.2 * i),
        )
    # small shield badge in front
    shield = [(-1, 2, 16), (6, 5, 17), (6, -2, 17), (-1, -7, 16), (-8, -2, 15), (-8, 5, 15)]
    s.add_face(transform(shield, yaw, pitch, lift), mix(CYAN, WHITE, 0.2))
    return s.render(t)


def frame_api_rest(t):
    """Hex badge with {} — reads as API/REST hub."""
    s = Scene()
    yaw, pitch, lift = icon_motion(t)
    # flat hex coin (thin), readable as API badge
    add_transformed(s, extrude_poly(hexagon_xy(18), -4, 4), yaw, pitch, lift, CYAN_MID)
    add_transformed(s, extrude_poly(hexagon_xy(13), 4, 5.5), yaw, pitch, lift, mix(CYAN, WHITE, 0.15))
    # curly braces as extruded strokes
    left = [(-8, 8), (-11, 4), (-11, -4), (-8, -8), (-9, -4), (-9, 4)]
    right = [(8, 8), (11, 4), (11, -4), (8, -8), (9, -4), (9, 4)]
    add_transformed(s, extrude_poly(left, 5.5, 7), yaw, pitch, lift, WHITE)
    add_transformed(s, extrude_poly(right, 5.5, 7), yaw, pitch, lift, WHITE)
    # tiny code window above (as in banner)
    add_transformed(s, box_faces(-7, 7, 22, 28, -3, 3), yaw, pitch, lift, CYAN_SOFT)
    return s.render(t)


def frame_aws(t):
    """Cloud + smile arrow (AWS)."""
    s = Scene()
    yaw, pitch, lift = icon_motion(t)
    # overlapping spheres = cloud silhouette
    blobs = [(-9, 0, 0, 9), (8, 1, -1, 9), (0, 7, 1, 8), (-2, -3, 3, 10), (4, -2, 4, 7)]
    for cx, cy, cz, r in blobs:
        add_transformed(s, sphere_faces(r, cx, cy, cz, 6, 10), yaw, pitch, lift, mix(CYAN_MID, CYAN, 0.35))
    # AWS smile
    tip = [(12, -12, 8), (18, -15, 9), (17, -9, 9)]
    s.add_face(transform(tip, yaw, pitch, lift), mix(CYAN_SOFT, WHITE, 0.3))
    for i in range(8):
        a0 = math.radians(25 + i * 16)
        a1 = math.radians(25 + (i + 1) * 16)
        p0 = (14 * math.cos(a0), -10 + 6 * math.sin(a0), 7)
        p1 = (14 * math.cos(a1), -10 + 6 * math.sin(a1), 7)
        s.add_edge(transform([p0], yaw, pitch, lift)[0], transform([p1], yaw, pitch, lift)[0], CYAN_SOFT, 3, 230)
    return s.render(t)


def frame_web_app(t):
    """Browser window with UI chrome + globe — matches banner."""
    s = Scene()
    yaw, pitch, lift = icon_motion(t)
    # thin browser frame
    add_transformed(s, box_faces(-20, 20, -14, 14, -2, 2), yaw, pitch, lift, CYAN_MID)
    # screen
    add_transformed(s, box_faces(-17, 17, -11, 9, 2, 3.2), yaw, pitch, lift, mix(BG, CYAN_DEEP, 0.55))
    # title bar
    add_transformed(s, box_faces(-17, 17, 9, 14, 2, 3.5), yaw, pitch, lift, mix(CYAN, WHITE, 0.08))
    # traffic lights
    for dx in (-13, -8, -3):
        add_transformed(s, sphere_faces(1.6, dx, 11.5, 4, 4, 6), yaw, pitch, lift, CYAN_SOFT)
    # content blocks
    add_transformed(s, box_faces(-13, -2, -7, 5, 3.2, 4.2), yaw, pitch, lift, CYAN)
    add_transformed(s, box_faces(1, 13, -7, -2, 3.2, 4.2), yaw, pitch, lift, CYAN_SOFT)
    add_transformed(s, box_faces(1, 13, 0, 5, 3.2, 4.2), yaw, pitch, lift, CYAN_SOFT)
    # globe under window
    add_transformed(s, sphere_faces(6, 8, -18, 4, 6, 10), yaw, pitch, lift, CYAN)
    return s.render(t)


def frame_websites(t):
    """Folder + globe + floating site windows."""
    s = Scene()
    yaw, pitch, lift = icon_motion(t)
    # folder body (wider, flatter)
    add_transformed(s, box_faces(-18, 18, -12, 6, -8, 4), yaw, pitch, lift, CYAN_MID)
    # tab
    add_transformed(s, box_faces(-18, -2, 6, 12, -8, 4), yaw, pitch, lift, mix(CYAN, CYAN_MID, 0.55))
    # front pocket lip
    add_transformed(s, box_faces(-18, 18, -12, -8, 4, 6), yaw, pitch, lift, mix(CYAN_DEEP, CYAN, 0.4))
    # globe on folder
    add_transformed(s, sphere_faces(8, 0, -1, 8, 7, 12), yaw, pitch, lift, CYAN_SOFT)
    # meridian hints
    for a in (0, math.pi / 2):
        ring = []
        for i in range(16):
            u = i / 16 * 2 * math.pi
            ring.append((8 * math.sin(u) * math.cos(a), -1 + 8 * math.cos(u), 8 + 8 * math.sin(u) * math.sin(a)))
        pts = transform(ring, yaw, pitch, lift)
        for i in range(len(pts)):
            s.add_edge(pts[i], pts[(i + 1) % len(pts)], CYAN, 1, 160)
    # browser windows popping out
    for i, dx in enumerate((-16, 0, 16)):
        y = 16 + 2.2 * math.sin(spin(t) + i)
        add_transformed(s, box_faces(dx - 6, dx + 6, y - 4, y + 4, -12, -9), yaw, pitch, lift, CYAN_SOFT)
        add_transformed(s, box_faces(dx - 5, dx + 5, y + 1, y + 3.5, -9, -8.2), yaw, pitch, lift, CYAN)
    return s.render(t)


def frame_desktop(t):
    """Monitor with code lines + stand."""
    s = Scene()
    yaw, pitch, lift = icon_motion(t)
    add_transformed(s, box_faces(-20, 20, -12, 12, -3, 3), yaw, pitch, lift, CYAN_MID)
    add_transformed(s, box_faces(-17, 17, -9, 8, 3, 4), yaw, pitch, lift, mix(BG, CYAN_DEEP, 0.7))
    # code lines
    for i, w in enumerate((12, 9, 11, 7, 10)):
        y = 4 - i * 2.8
        add_transformed(s, box_faces(-12, -12 + w, y - 0.5, y + 0.5, 4, 4.6), yaw, pitch, lift, CYAN_SOFT)
    add_transformed(s, box_faces(-3, 3, -18, -12, -2, 2), yaw, pitch, lift, CYAN)
    add_transformed(s, box_faces(-12, 12, -20, -18, -3, 3), yaw, pitch, lift, CYAN_MID)
    return s.render(t)


def frame_notification(t):
    """Bell + envelope — processing / messaging / notification."""
    s = Scene()
    yaw, pitch, lift = icon_motion(t)
    # bell body (sphere + flared cylinder)
    add_transformed(s, sphere_faces(9, 0, 2, 0, 7, 12), yaw, pitch, lift, mix(CYAN_MID, CYAN, 0.4))
    add_transformed(s, cylinder_faces(11, -8, -3, 16), yaw, pitch, lift, CYAN_MID)
    add_transformed(s, sphere_faces(2.5, 0, 12, 0, 4, 8), yaw, pitch, lift, CYAN_SOFT)
    # clapper
    add_transformed(s, sphere_faces(2.2, 0, -10, 0, 4, 8), yaw, pitch, lift, WHITE)
    # tiny envelope badge
    add_transformed(s, box_faces(10, 20, -4, 4, 6, 9), yaw, pitch, lift, CYAN_SOFT)
    s.add_face(transform([(10, 4, 9), (15, 0, 11), (20, 4, 9)], yaw, pitch, lift), WHITE)
    return s.render(t)


def frame_ia(t):
    """Circuit brain silhouette (matches IA banner center)."""
    s = Scene()
    yaw, pitch, lift = icon_motion(t)
    # brain outline (top view-ish lobes)
    brain = [
        (-2, 14), (-8, 13), (-13, 9), (-15, 3), (-14, -3), (-11, -8), (-7, -11),
        (-3, -12), (0, -10), (3, -12), (7, -11), (11, -8), (14, -3), (15, 3),
        (13, 9), (8, 13), (2, 14), (0, 12),
    ]
    add_transformed(s, extrude_poly(brain, -5, 5), yaw, pitch, lift, mix(CYAN_MID, CYAN, 0.45))
    # center crease
    add_transformed(s, box_faces(-1, 1, -10, 12, 5, 6.5), yaw, pitch, lift, CYAN_DEEP)
    # circuit nodes on surface
    nodes = [(-8, 6, 6), (8, 6, 6), (-6, -2, 6), (6, -2, 6), (0, 4, 6), (-3, -6, 6), (3, -6, 6)]
    for i, (nx, ny, nz) in enumerate(nodes):
        add_transformed(s, sphere_faces(1.8, nx, ny, nz, 4, 6), yaw, pitch, lift, CYAN_SOFT)
        if i > 0:
            p0 = transform([nodes[0]], yaw, pitch, lift)[0]
            p1 = transform([(nx, ny, nz)], yaw, pitch, lift)[0]
            if i % 2 == 0:
                s.add_edge(p0, p1, CYAN, 1, 150)
    # outer ring
    ring = []
    for i in range(28):
        a = i / 28 * 2 * math.pi
        ring.append((20 * math.cos(a), 20 * math.sin(a) * 0.85, 0))
    pts = transform([(x, y, z) for x, y, z in ring], yaw, pitch, lift)
    for i in range(len(pts)):
        s.add_edge(pts[i], pts[(i + 1) % len(pts)], CYAN, 2, 140)
    return s.render(t)


def frame_graphql_rpc(t):
    """GraphQL hexagon/rhombus logo + small server stack."""
    s = Scene()
    yaw, pitch, lift = icon_motion(t)
    # GraphQL: hexagon rhombus with internal triangle
    r = 16
    verts = [(r * math.cos(i * math.pi / 3 - math.pi / 6), r * math.sin(i * math.pi / 3 - math.pi / 6)) for i in range(6)]
    add_transformed(s, extrude_poly(verts, -3, 3), yaw, pitch, lift, CYAN_MID)
    # inner connections: midpoints -> form classic logo lines as thin boxes via edges in 3D
    mids = []
    for i in range(6):
        x0, y0 = verts[i]
        x1, y1 = verts[(i + 1) % 6]
        mids.append(((x0 + x1) / 2, (y0 + y1) / 2))
    # triangle through alternate vertices
    tri = [verts[0], verts[2], verts[4]]
    add_transformed(s, extrude_poly(tri, 3, 4.5), yaw, pitch, lift, mix(CYAN, WHITE, 0.2))
    for i in range(6):
        p0 = transform([(verts[i][0], verts[i][1], 4.5)], yaw, pitch, lift)[0]
        p1 = transform([(mids[i][0], mids[i][1], 4.5)], yaw, pitch, lift)[0]
        s.add_edge(p0, p1, CYAN_SOFT, 2, 220)
        # node dots
        add_transformed(s, sphere_faces(1.6, verts[i][0], verts[i][1], 5, 4, 6), yaw, pitch, lift, WHITE)
    # tiny RPC server stack beside/below
    for i, y0 in enumerate((-18, -13, -8)):
        add_transformed(s, box_faces(-5, 5, y0, y0 + 3.5, 10, 15), yaw, pitch, lift, mix(CYAN_DEEP, CYAN, 0.3 + 0.1 * i))
    return s.render(t)


def frame_embedded(t):
    """Microcontroller IC with pins — clear chip."""
    s = Scene()
    yaw, pitch, lift = icon_motion(t)
    add_transformed(s, box_faces(-13, 13, -13, 13, -4, 4), yaw, pitch, lift, CYAN_MID)
    add_transformed(s, box_faces(-7, 7, -7, 7, 4, 6.5), yaw, pitch, lift, mix(CYAN, WHITE, 0.12))
    # die mark
    add_transformed(s, sphere_faces(1.8, -9, 9, 5, 4, 6), yaw, pitch, lift, CYAN_SOFT)
    for i in range(-3, 4):
        x = i * 3.4
        add_transformed(s, box_faces(x - 0.8, x + 0.8, 13, 18, -1.2, 1.2), yaw, pitch, lift, CYAN_SOFT)
        add_transformed(s, box_faces(x - 0.8, x + 0.8, -18, -13, -1.2, 1.2), yaw, pitch, lift, CYAN_SOFT)
        add_transformed(s, box_faces(-18, -13, x - 0.8, x + 0.8, -1.2, 1.2), yaw, pitch, lift, CYAN_SOFT)
        add_transformed(s, box_faces(13, 18, x - 0.8, x + 0.8, -1.2, 1.2), yaw, pitch, lift, CYAN_SOFT)
    return s.render(t)


FRAMES_FN = {
    "aws": frame_aws,
    "api-rest": frame_api_rest,
    "notification": frame_notification,
    "web-app": frame_web_app,
    "ia-brain": frame_ia,
    "websites": frame_websites,
    "desktop-app": frame_desktop,
    "database": frame_database,
    "graphql-rpc": frame_graphql_rpc,
    "embedded-system": frame_embedded,
}


def make_gif(name: str, frame_fn) -> Path:
    frames_rgb = [frame_fn(i / FRAMES) for i in range(FRAMES)]
    sample = Image.new("RGB", (SIZE * 2, SIZE * 2), BG)
    sample.paste(frames_rgb[0], (0, 0))
    sample.paste(frames_rgb[FRAMES // 3], (SIZE, 0))
    sample.paste(frames_rgb[2 * FRAMES // 3], (0, SIZE))
    sample.paste(frames_rgb[-1], (SIZE, SIZE))
    palette = sample.convert("P", palette=Image.ADAPTIVE, colors=160)
    frames = [f.quantize(palette=palette, dither=Image.Dither.NONE) for f in frames_rgb]
    out = OUT_DIR / f"{name}-preview.gif"
    frames[0].save(
        out,
        save_all=True,
        append_images=frames[1:],
        duration=DURATION_MS,
        loop=0,
        optimize=False,
        disposal=2,
    )
    return out


def main():
    paths = []
    for name, fn in FRAMES_FN.items():
        path = make_gif(name, fn)
        paths.append(path)
        print(f"wrote {path.name}")

    cards = "\n".join(
        f"""
        <figure>
          <img src="{p.name}" width="150" height="150" alt="{p.stem}" />
          <figcaption>{p.stem.replace('-preview', '')}</figcaption>
        </figure>"""
        for p in paths
    )
    html = f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8" />
  <title>Preview GIFs 3D polished</title>
  <style>
    body {{ margin:0; padding:32px; background:#070b16; color:#d8f0ff; font-family:Segoe UI,system-ui,sans-serif; }}
    h1 {{ font-weight:600; }}
    p {{ color:#8eb6d8; max-width:760px; line-height:1.45; }}
    .grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(170px,1fr)); gap:20px; margin-top:28px; }}
    figure {{ margin:0; text-align:center; background:#0c1428; border:1px solid #1d3a5c; border-radius:12px; padding:18px 10px 12px; }}
    figcaption {{ margin-top:10px; font-size:13px; color:#9ec9ea; }}
    img {{ background:#060c1c; border-radius:8px; }}
  </style>
</head>
<body>
  <h1>Preview GIFs — 3D pulido</h1>
  <p>Solo muestras. Caras sólidas con sombreado, pedestal glow, hover y giro lento sin salto. No reemplazan <code>assets/gifs/stacks/</code>.</p>
  <div class="grid">{cards}</div>
</body>
</html>
"""
    (OUT_DIR / "preview.html").write_text(html, encoding="utf-8")
    print(f"gallery: {OUT_DIR / 'preview.html'}")


if __name__ == "__main__":
    main()
