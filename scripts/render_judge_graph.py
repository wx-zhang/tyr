from __future__ import annotations

import math
import sys
import tempfile
from pathlib import Path

from gamr_engine.judges.registry import get_judge_pipeline
from PIL import Image, ImageDraw, ImageFont


def _draw_arrow(
    draw: ImageDraw.ImageDraw,
    pt1: tuple[int, int],
    pt2: tuple[int, int],
    color: str = "#374151",
    width: int = 2,
    arrow_size: int = 8,
) -> None:
    draw.line([pt1, pt2], fill=color, width=width)
    dx = pt2[0] - pt1[0]
    dy = pt2[1] - pt1[1]
    angle = math.atan2(dy, dx)
    x, y = pt2
    p1 = (
        x - arrow_size * math.cos(angle - math.pi / 6),
        y - arrow_size * math.sin(angle - math.pi / 6),
    )
    p2 = (
        x - arrow_size * math.cos(angle + math.pi / 6),
        y - arrow_size * math.sin(angle + math.pi / 6),
    )
    draw.polygon([pt2, p1, p2], fill=color)


def resolve_pipeline_id_from_path(judge_path: Path, repo_root: Path) -> str:
    real_path = judge_path.resolve()
    judge_root = (repo_root / "packages" / "engine" / "src" / "gamr_engine" / "judges").resolve()

    if not real_path.exists() or not real_path.is_dir():
        raise ValueError(f"Judge directory does not exist or is not a directory: {judge_path}")

    # Check that real_path is a direct child of judge_root
    if real_path.parent != judge_root:
        raise ValueError(
            f"Judge directory must be a direct child of {judge_root}, got: {real_path}"
        )

    dir_name = real_path.name
    pipeline_id = dir_name.replace("_", "-")
    return pipeline_id


def render_judge_graph(
    judge_dir: Path,
    destination: Path | None = None,
    repo_root: Path | None = None,
) -> Path:
    root = repo_root or Path(__file__).resolve().parent.parent
    pipeline_id = resolve_pipeline_id_from_path(judge_dir, root)

    pipeline = get_judge_pipeline(pipeline_id)
    drawable_graph = pipeline.graph.get_graph()

    target_path = destination or (root / "docs" / "assets" / "judges" / f"{pipeline_id}.png")
    target_path.parent.mkdir(parents=True, exist_ok=True)

    # Extract nodes and edges
    nodes = sorted(list(drawable_graph.nodes.keys()))
    edges = sorted([(e.source, e.target) for e in drawable_graph.edges])

    # Deterministic layout: longest path (topological depth) from start
    # Compute in-degree and adjacency
    adj: dict[str, list[str]] = {n: [] for n in nodes}
    for src, tgt in edges:
        if src in adj:
            adj[src].append(tgt)

    levels: dict[str, int] = {n: 0 for n in nodes}
    # Relax distances along edges (DAG longest path)
    changed = True
    iterations = 0
    max_iter = len(nodes) + 5
    while changed and iterations < max_iter:
        changed = False
        iterations += 1
        for src, tgt in edges:
            if src in levels and tgt in levels:
                if levels[tgt] < levels[src] + 1:
                    levels[tgt] = levels[src] + 1
                    changed = True

    # Group nodes by level
    level_groups: dict[int, list[str]] = {}
    for node, lvl in sorted(levels.items()):
        level_groups.setdefault(lvl, []).append(node)

    # Drawing settings
    box_w = 260
    box_h = 50
    margin_x = 60
    margin_y = 60
    spacing_x = 60
    spacing_y = 60

    max_nodes_in_level = max(len(grp) for grp in level_groups.values()) if level_groups else 1
    total_levels = len(level_groups) if level_groups else 1

    img_w = margin_x * 2 + max_nodes_in_level * box_w + (max_nodes_in_level - 1) * spacing_x
    img_h = margin_y * 2 + total_levels * box_h + (total_levels - 1) * spacing_y

    img = Image.new("RGB", (img_w, img_h), color="white")
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.load_default()
    except Exception:
        font = None

    # Calculate coordinates for each node
    node_coords: dict[str, tuple[int, int, int, int]] = {}
    for lvl, grp in sorted(level_groups.items()):
        row_w = len(grp) * box_w + (len(grp) - 1) * spacing_x
        start_x = (img_w - row_w) // 2
        y = margin_y + lvl * (box_h + spacing_y)
        for i, node in enumerate(sorted(grp)):
            x = start_x + i * (box_w + spacing_x)
            node_coords[node] = (x, y, x + box_w, y + box_h)

    # Draw directed edges
    for src, tgt in edges:
        if src in node_coords and tgt in node_coords:
            x1, y1, x2, y2 = node_coords[src]
            tx1, ty1, tx2, ty2 = node_coords[tgt]
            src_lvl = levels.get(src, 0)
            tgt_lvl = levels.get(tgt, 0)

            # If connecting vertically across multiple levels (e.g. bypass route to end)
            if tgt_lvl > src_lvl + 1:
                # Route from right side of source to right side of target
                src_pt = (x2, (y1 + y2) // 2)
                tgt_pt = (tx2, (ty1 + ty2) // 2)
                mid_x = max(x2, tx2) + 30
                draw.line([src_pt, (mid_x, src_pt[1]), (mid_x, tgt_pt[1])], fill="#374151", width=2)
                _draw_arrow(draw, (mid_x, tgt_pt[1]), tgt_pt)
            else:
                src_pt = ((x1 + x2) // 2, y2)
                tgt_pt = ((tx1 + tx2) // 2, ty1)
                _draw_arrow(draw, src_pt, tgt_pt)

    # Draw node boxes and labels
    for node, (x1, y1, x2, y2) in sorted(node_coords.items()):
        draw.rectangle([x1, y1, x2, y2], outline="black", fill="#f4f4f5", width=2)
        label = node.replace("_", " ").replace("__", "")
        if font:
            bbox = draw.textbbox((0, 0), label, font=font)
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]
            tx = x1 + (box_w - text_w) // 2
            ty = y1 + (box_h - text_h) // 2
            draw.text((tx, ty), label, fill="black", font=font)
        else:
            draw.text((x1 + 10, y1 + 15), label, fill="black")

    # Atomic write via temporary file
    temp_fd, temp_path = tempfile.mkstemp(suffix=".png", dir=target_path.parent)
    try:
        with open(temp_fd, "wb") as f:
            img.save(f, format="PNG")
        Path(temp_path).replace(target_path)
    finally:
        if Path(temp_path).exists():
            Path(temp_path).unlink(missing_ok=True)

    return target_path


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: uv run poe judge-graph <judge-directory>", file=sys.stderr)
        sys.exit(1)

    judge_dir = Path(sys.argv[1])
    try:
        output_path = render_judge_graph(judge_dir)
        repo_root = Path(__file__).resolve().parent.parent
        rel_path = (
            output_path.relative_to(repo_root)
            if output_path.is_relative_to(repo_root)
            else output_path
        )
        print(f"Rendered judge graph to: {rel_path}")
    except Exception as exc:
        print(f"Error rendering judge graph: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
