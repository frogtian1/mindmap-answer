#!/usr/bin/env python3
import argparse
import json
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path

try:
    import cairo
except ImportError:
    print("缺少 pycairo。请安装：python -m pip install pycairo", file=sys.stderr)
    raise SystemExit(3)
try:
    from PIL import Image
except ImportError:
    print("缺少 Pillow。请安装：python -m pip install Pillow", file=sys.stderr)
    raise SystemExit(3)

from validate_tree import load_tree, validate

ROOT_R, RING_GAP, SCALE = 176, 78, 2
BG, INK = "#F7F4EE", "#2E3338"
PALETTE = [
    ("#1B7C79", "#E5F3F1"), ("#C4841C", "#FBF1DD"),
    ("#2E6FD4", "#E6F0FD"), ("#3C8A46", "#E4F3E3"),
    ("#C45B66", "#FDECEE"), ("#6D59A1", "#EFEAF7"),
    ("#4C6880", "#E6EDF2"),
]
FONT_REGULAR = "Noto Sans CJK SC"
FONT_BOLD = "Noto Sans CJK SC"
FONT_FILES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    str(Path.home() / "Library/Fonts/NotoSansCJKsc-Regular.otf"),
    str(Path.home() / "Library/Fonts/NotoSansCJKsc-Bold.otf"),
]
STYLE = {1: (29, 25, 14, 21), 2: (23, 18, 10, 15), 3: (18, 12, 6, 11), 4: (15, 10, 4, 8), 5: (15, 10, 4, 8)}
COL_GAP = {1: 18, 2: 14, 3: 12, 4: 10, 5: 10}
CHILD_GAP = {1: 11, 2: 10, 3: 8, 4: 7, 5: 7}


def rgb(value, alpha=1.0):
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) / 255 for i in (0, 2, 4)) + (alpha,)


@dataclass
class Node:
    label: str
    depth: int
    branch: int
    children: list = field(default_factory=list)
    w: float = 0
    h: float = 0
    subtree_h: float = 0
    x: float = 0
    y: float = 0
    side: int = 1

    @property
    def cy(self): return self.y + self.h / 2
    @property
    def outer(self): return self.x + self.w if self.side > 0 else self.x
    @property
    def inner(self): return self.x if self.side > 0 else self.x + self.w


def make_node(raw, depth, branch):
    node = Node(raw["label"], depth, branch)
    node.children = [make_node(child, depth + 1, branch) for child in raw.get("children", [])]
    return node


def font(ctx, size, bold=False):
    ctx.select_font_face(FONT_BOLD if bold else FONT_REGULAR, cairo.FONT_SLANT_NORMAL,
                         cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL)
    ctx.set_font_size(size)


def measure(nodes, ctx):
    for node in nodes:
        size, px, py, _ = STYLE[min(node.depth, 5)]
        font(ctx, size, node.depth == 1)
        ext = ctx.text_extents(node.label)
        node.w, node.h = ext.width + px * 2, ext.height + py * 2
        measure(node.children, ctx)
        if node.children and node.depth < 3:
            widest = max(child.w for child in node.children)
            for child in node.children:
                child.w = widest
        total = sum(child.subtree_h for child in node.children)
        if node.children:
            total += CHILD_GAP[min(node.depth, 5)] * (len(node.children) - 1)
        node.subtree_h = max(node.h, total)


def place_descendants(node):
    if not node.children:
        return
    gap = CHILD_GAP[min(node.depth, 5)]
    total = sum(c.subtree_h for c in node.children) + gap * (len(node.children) - 1)
    top = node.cy - total / 2
    for child in node.children:
        child.side = node.side
        child.x = node.outer + COL_GAP[node.depth] if node.side > 0 else node.outer - COL_GAP[node.depth] - child.w
        child.y = top + (child.subtree_h - child.h) / 2
        place_descendants(child)
        top += child.subtree_h + gap


def all_nodes(node):
    yield node
    for child in node.children:
        yield from all_nodes(child)


def shift(node, dy):
    for item in all_nodes(node):
        item.y += dy


def bounds(node):
    items = list(all_nodes(node))
    return min(n.x for n in items), min(n.y for n in items), max(n.x + n.w for n in items), max(n.y + n.h for n in items)


def pack_side(nodes, side, cx, cy, height):
    if not nodes:
        return
    gap = 29
    total = sum(n.subtree_h for n in nodes) + gap * (len(nodes) - 1)
    top = max(36, min(cy - total / 2, height - 36 - total))
    for node in nodes:
        node.side = side
        cluster_cy = top + node.subtree_h / 2
        stagger = min(48, 28 * (abs(cluster_cy - cy) / cy) ** 1.15)
        node.x = cx + ROOT_R + RING_GAP + stagger if side > 0 else cx - ROOT_R - RING_GAP - node.w - stagger
        node.y = cluster_cy - node.h / 2
        place_descendants(node)
        top += node.subtree_h + gap
    previous_bottom = 20
    for node in nodes:
        box = bounds(node)
        if box[1] < previous_bottom:
            shift(node, previous_bottom - box[1])
            box = bounds(node)
        previous_bottom = box[3] + 26
    overflow = bounds(nodes[-1])[3] - (height - 20)
    if overflow > 0:
        for node in nodes:
            shift(node, -overflow)


def rounded(ctx, x, y, w, h, r):
    r = min(r, w / 2, h / 2)
    ctx.new_sub_path(); ctx.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    ctx.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    ctx.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    ctx.arc(x + r, y + r, r, math.pi, math.pi * 1.5); ctx.close_path()


def draw_routes(ctx, branches, cx, cy):
    ctx.set_line_cap(cairo.LINE_CAP_ROUND); ctx.set_line_join(cairo.LINE_JOIN_ROUND)
    for node in branches:
        main, _ = PALETTE[node.branch % len(PALETTE)]
        angle = math.atan2(node.cy - cy, node.inner - cx)
        sx, sy = cx + ROOT_R * math.cos(angle), cy + ROOT_R * math.sin(angle)
        ctx.move_to(sx, sy)
        ctx.curve_to(sx + node.side * 64, sy, node.inner - node.side * 50, node.cy, node.inner, node.cy)
        ctx.set_source_rgba(*rgb(main, .78)); ctx.set_line_width(3); ctx.stroke()
        draw_child_routes(ctx, node, main)


def draw_child_routes(ctx, parent, main):
    if not parent.children:
        return
    start = parent.outer
    spine = start + parent.side * 11
    ys = [child.cy for child in parent.children]
    ctx.set_source_rgba(*rgb(main, max(.35, .64 - parent.depth * .07)))
    ctx.set_line_width({1: 1.7, 2: 1.35, 3: 1.15}.get(parent.depth, 1.0))
    ctx.move_to(start, parent.cy); ctx.line_to(spine, parent.cy)
    ctx.move_to(spine, min(ys + [parent.cy])); ctx.line_to(spine, max(ys + [parent.cy]))
    for child in parent.children:
        ctx.move_to(spine, child.cy); ctx.line_to(child.inner, child.cy)
    ctx.stroke()
    for child in parent.children:
        draw_child_routes(ctx, child, main)


def draw_node(ctx, node):
    main, light = PALETTE[node.branch % len(PALETTE)]
    size, _, _, radius = STYLE[min(node.depth, 5)]
    rounded(ctx, node.x, node.y, node.w, node.h, radius)
    if node.depth == 1:
        ctx.set_source_rgb(*rgb(main)[:3]); ctx.fill()
    else:
        ctx.set_source_rgb(*rgb(light)[:3] if node.depth == 2 else rgb(BG)[:3]); ctx.fill_preserve()
        ctx.set_source_rgba(*rgb(main, {2: .55, 3: .42}.get(node.depth, .35)))
        ctx.set_line_width(1.4 if node.depth == 2 else 1.0); ctx.stroke()
    font(ctx, size, node.depth == 1)
    ext = ctx.text_extents(node.label)
    tx = node.x + (node.w - ext.width) / 2 - ext.x_bearing
    ty = node.y + (node.h - ext.height) / 2 - ext.y_bearing
    ctx.move_to(tx, ty)
    ctx.set_source_rgb(*(rgb("#FFFFFF")[:3] if node.depth == 1 else rgb(INK)[:3])); ctx.show_text(node.label)
    for child in node.children: draw_node(ctx, child)


def draw_root(ctx, root, cx, cy):
    grad = cairo.RadialGradient(cx - 55, cy - 65, 15, cx, cy, ROOT_R)
    grad.add_color_stop_rgb(0, *rgb("#167A80")[:3]); grad.add_color_stop_rgb(1, *rgb("#0B4E56")[:3])
    ctx.new_path(); ctx.arc(cx, cy, ROOT_R, 0, math.tau); ctx.set_source(grad); ctx.fill_preserve()
    ctx.set_source_rgba(1, 1, 1, .14); ctx.set_line_width(2.2); ctx.stroke()
    lines = root.splitlines()[:2]
    font(ctx, 39 if len(lines) == 1 else 37, True)
    line_h = 54
    start_y = cy - (len(lines) - 1) * line_h / 2
    ctx.set_source_rgb(1, 1, 1)
    for i, line in enumerate(lines):
        ext = ctx.text_extents(line); ctx.move_to(cx - ext.width / 2 - ext.x_bearing, start_y + i * line_h - ext.y_bearing / 2); ctx.show_text(line)


def render(data, out):
    if not any(Path(path).exists() for path in FONT_FILES):
        raise ValueError("缺少 Noto Sans CJK SC 字体；请安装 NotoSansCJK-Regular.ttc 与 Bold.ttc")
    raw_nodes = [make_node(branch, 1, i) for i, branch in enumerate(data["branches"])]
    max_depth = max(n.depth for root in raw_nodes for n in all_nodes(root))
    width, height = (2480, 1480) if max_depth > 3 else (1920, 1180)
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width * SCALE, height * SCALE)
    ctx = cairo.Context(surface); ctx.scale(SCALE, SCALE)
    ctx.set_source_rgb(*rgb(BG)[:3]); ctx.paint()
    cx, cy = width / 2, height / 2 + 8
    glow = cairo.RadialGradient(cx, cy, ROOT_R * .4, cx, cy, ROOT_R * 2.1)
    glow.add_color_stop_rgba(0, 1, 1, 1, .28); glow.add_color_stop_rgba(1, 1, 1, 1, 0)
    ctx.set_source(glow); ctx.new_path(); ctx.arc(cx, cy, ROOT_R * 2.1, 0, math.tau); ctx.fill()
    measure(raw_nodes, ctx)
    pack_side([n for i, n in enumerate(raw_nodes) if i % 2 == 0], 1, cx, cy, height)
    pack_side([n for i, n in enumerate(raw_nodes) if i % 2 == 1], -1, cx, cy, height)
    for node in raw_nodes:
        x1, y1, x2, y2 = bounds(node)
        if min(x1, y1) < 20 or x2 > width - 20 or y2 > height - 20:
            raise ValueError(f"布局超出画布：第 {node.branch + 1} 枝，请缩短标签或拆子图")
    draw_routes(ctx, raw_nodes, cx, cy)
    for node in raw_nodes: draw_node(ctx, node)
    draw_root(ctx, data["root"], cx, cy)
    temp = out.with_suffix(".2x.png")
    surface.write_to_png(str(temp)); surface.finish()
    with Image.open(temp) as image:
        image.resize((width, height), Image.Resampling.LANCZOS).save(out, "PNG", optimize=True)
    temp.unlink()


def main():
    parser = argparse.ArgumentParser(description="Render mindmap-answer JSON to PNG/JPG")
    parser.add_argument("--input", required=True); parser.add_argument("--out", required=True)
    parser.add_argument("--also-jpg", action="store_true")
    args = parser.parse_args(); out = Path(args.out)
    if out.suffix.lower() != ".png":
        print("错误：--out 必须使用 .png 后缀", file=sys.stderr); return 2
    try:
        data = load_tree(args.input); errors, warnings = validate(data)
        for warning in warnings: print(f"警告：{warning}", file=sys.stderr)
        if errors: raise ValueError("；".join(errors))
        out.parent.mkdir(parents=True, exist_ok=True); render(data, out)
        if args.also_jpg:
            with Image.open(out) as image:
                image.convert("RGB").save(out.with_suffix(".jpg"), "JPEG", quality=92, optimize=True)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"错误：{exc}", file=sys.stderr); return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
