#!/usr/bin/env python3
"""Build and validate per-actor dashboard sprite sheets.

The generated contact sheets are QA sources, not runtime geometry. This script
normalizes every frame around two stable measurements: the idle body's visible
width and the feet contact point. Raw source canvas height never affects actor
placement in the office world.
"""

from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "docs/dashboard/characters/source"
RUNTIME_DIR = ROOT / "docs/dashboard/characters/runtime"
QA_DIR = ROOT / "docs/dashboard/qa/character-art/runtime"

STATES = ("idle", "walk", "work", "talk", "blocked", "complete")
CELL_WIDTH = 96
CELL_HEIGHT = 128
FOOT_ANCHOR = (48, 120)
VISIBLE_IDLE_WIDTH = 48
ALPHA_THRESHOLD = 128


@dataclass(frozen=True)
class ActorSource:
    actor_id: str
    display_name: str
    sheet: str
    row: int
    rows: int


ACTORS = (
    ActorSource("planning-lead", "Planning Lead", "contact-sheet-a.png", 0, 6),
    ActorSource("planning-member", "Planning Member", "contact-sheet-a.png", 1, 6),
    ActorSource("research-lead", "Research Lead", "contact-sheet-a.png", 2, 6),
    ActorSource("research-member", "Research Member", "contact-sheet-a.png", 3, 6),
    ActorSource("design-lead", "Design Lead", "contact-sheet-a.png", 4, 6),
    ActorSource("design-member", "Design Member", "contact-sheet-a.png", 5, 6),
    ActorSource("engineering-lead", "Engineering Lead", "contact-sheet-b.png", 0, 5),
    ActorSource("engineer-a", "Engineer A", "contact-sheet-b.png", 1, 5),
    ActorSource("engineer-b", "Engineer B", "contact-sheet-b.png", 2, 5),
    ActorSource("verification-lead", "Verification Lead", "contact-sheet-b.png", 3, 5),
    ActorSource("verification-member", "Verification Member", "contact-sheet-b.png", 4, 5),
)


def source_frame_bounds(image: Image.Image, expected_rows: int) -> list[list[tuple[int, int, int, int]]]:
    """Find the actual person bounds instead of assuming equal row spacing."""
    alpha = image.getchannel("A")
    width, height = image.size
    opaque = {
        (x, y)
        for y in range(height)
        for x in range(width)
        if alpha.getpixel((x, y)) >= ALPHA_THRESHOLD
    }
    components: list[tuple[int, int, int, int, int]] = []
    while opaque:
        start = opaque.pop()
        queue = deque((start,))
        points: list[tuple[int, int]] = []
        while queue:
            x, y = queue.popleft()
            points.append((x, y))
            for neighbor in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if neighbor in opaque:
                    opaque.remove(neighbor)
                    queue.append(neighbor)
        if len(points) >= 100:
            xs = [point[0] for point in points]
            ys = [point[1] for point in points]
            components.append((len(points), min(xs), min(ys), max(xs) + 1, max(ys) + 1))
    expected = expected_rows * len(STATES)
    if len(components) != expected:
        raise ValueError(f"Expected {expected} source frames, found {len(components)}")

    row_height = height / expected_rows
    rows: list[list[tuple[int, int, int, int]]] = [[] for _ in range(expected_rows)]
    for _, left, top, right, bottom in components:
        row = min(expected_rows - 1, int(((top + bottom) / 2) / row_height))
        rows[row].append((left, top, right, bottom))
    for row in rows:
        row.sort(key=lambda bounds: bounds[0])
        if len(row) != len(STATES):
            raise ValueError(f"Expected {len(STATES)} frames in source row, found {len(row)}")
    return rows


def crop_source_frame(image: Image.Image, bounds: tuple[int, int, int, int]) -> Image.Image:
    padding = 4
    left, top, right, bottom = bounds
    return image.crop(
        (
            max(0, left - padding),
            max(0, top - padding),
            min(image.width, right + padding),
            min(image.height, bottom + padding),
        )
    )


def alpha_bbox(image: Image.Image) -> tuple[int, int, int, int]:
    alpha = image.getchannel("A")
    mask = alpha.point(lambda value: 255 if value >= ALPHA_THRESHOLD else 0)
    bbox = mask.getbbox()
    if bbox is None:
        raise ValueError("Frame has no visible pixels")
    return bbox


def foot_point(image: Image.Image, bbox: tuple[int, int, int, int]) -> tuple[float, int]:
    """Estimate the ground contact center from the lowest opaque rows."""
    left, top, right, bottom = bbox
    alpha = image.getchannel("A")
    scan_top = max(top, bottom - max(5, round((bottom - top) * 0.09)))
    xs: list[int] = []
    lowest = top
    for y in range(scan_top, bottom):
        row_xs = [x for x in range(left, right) if alpha.getpixel((x, y)) >= ALPHA_THRESHOLD]
        if row_xs:
            lowest = y
            xs.extend(row_xs)
    if not xs:
        raise ValueError("Frame has no detectable feet")
    return sum(xs) / len(xs), lowest


def connected_components(image: Image.Image) -> list[int]:
    """Return opaque component sizes for detached-pixel QA."""
    alpha = image.getchannel("A")
    width, height = image.size
    opaque = {
        (x, y)
        for y in range(height)
        for x in range(width)
        if alpha.getpixel((x, y)) >= ALPHA_THRESHOLD
    }
    sizes: list[int] = []
    while opaque:
        start = opaque.pop()
        queue = deque((start,))
        size = 0
        while queue:
            x, y = queue.popleft()
            size += 1
            for neighbor in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if neighbor in opaque:
                    opaque.remove(neighbor)
                    queue.append(neighbor)
        sizes.append(size)
    return sorted(sizes, reverse=True)


def remove_tiny_components(image: Image.Image, maximum_size: int = 8) -> Image.Image:
    """Remove isolated loose pixels while preserving connected props and limbs."""
    cleaned = image.copy()
    alpha = cleaned.getchannel("A")
    opaque = {
        (x, y)
        for y in range(cleaned.height)
        for x in range(cleaned.width)
        if alpha.getpixel((x, y)) >= ALPHA_THRESHOLD
    }
    components: list[list[tuple[int, int]]] = []
    while opaque:
        start = opaque.pop()
        queue = deque((start,))
        points: list[tuple[int, int]] = []
        while queue:
            point = queue.popleft()
            points.append(point)
            x, y = point
            for neighbor in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if neighbor in opaque:
                    opaque.remove(neighbor)
                    queue.append(neighbor)
        components.append(points)
    pixels = cleaned.load()
    for component in components:
        if len(component) <= maximum_size:
            for x, y in component:
                pixels[x, y] = (0, 0, 0, 0)
    return cleaned


def normalize_frame(frame: Image.Image, scale: float) -> Image.Image:
    """Place a source frame in a stable runtime cell using its foot anchor."""
    frame = frame.copy()
    alpha = frame.getchannel("A").point(lambda value: 255 if value >= ALPHA_THRESHOLD else 0)
    frame.putalpha(alpha)
    bbox = alpha_bbox(frame)
    visible = frame.crop(bbox)
    resized = visible.resize(
        (max(1, round(visible.width * scale)), max(1, round(visible.height * scale))),
        Image.Resampling.NEAREST,
    )
    resized_bbox = alpha_bbox(resized)
    foot_x, foot_y = foot_point(resized, resized_bbox)
    x = round(FOOT_ANCHOR[0] - foot_x)
    y = round(FOOT_ANCHOR[1] - foot_y)
    canvas = Image.new("RGBA", (CELL_WIDTH, CELL_HEIGHT), (0, 0, 0, 0))
    canvas.alpha_composite(resized, (x, y))
    return remove_tiny_components(canvas)


def frame_report(frame: Image.Image) -> dict[str, object]:
    bbox = alpha_bbox(frame)
    _, foot_y = foot_point(frame, bbox)
    components = connected_components(frame)
    alpha = frame.getchannel("A")
    border_pixels = 0
    for x in range(frame.width):
        border_pixels += int(alpha.getpixel((x, 0)) >= ALPHA_THRESHOLD)
        border_pixels += int(alpha.getpixel((x, frame.height - 1)) >= ALPHA_THRESHOLD)
    for y in range(1, frame.height - 1):
        border_pixels += int(alpha.getpixel((0, y)) >= ALPHA_THRESHOLD)
        border_pixels += int(alpha.getpixel((frame.width - 1, y)) >= ALPHA_THRESHOLD)
    tiny_components = [size for size in components[1:] if size <= 8]
    return {
        "visibleBounds": list(bbox),
        "visibleWidth": bbox[2] - bbox[0],
        "visibleHeight": bbox[3] - bbox[1],
        "footY": foot_y,
        "borderPixels": border_pixels,
        "componentCount": len(components),
        "tinyDetachedComponents": tiny_components,
        "artifactPass": border_pixels == 0 and not tiny_components,
        "footAnchorPass": abs(foot_y - FOOT_ANCHOR[1]) <= 1,
        "frameBleedPass": border_pixels == 0,
    }


def load_font(size: int) -> ImageFont.ImageFont:
    candidates = (
        Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
        Path("/System/Library/Fonts/SFNS.ttf"),
    )
    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def build_contact_sheet(frames_by_actor: dict[str, list[Image.Image]]) -> None:
    label_width = 170
    header_height = 44
    row_height = CELL_HEIGHT + 18
    sheet = Image.new(
        "RGBA",
        (label_width + CELL_WIDTH * len(STATES), header_height + row_height * len(ACTORS)),
        (247, 245, 239, 255),
    )
    draw = ImageDraw.Draw(sheet)
    title_font = load_font(16)
    label_font = load_font(13)
    for column, state in enumerate(STATES):
        draw.text((label_width + column * CELL_WIDTH + 8, 14), state.upper(), fill=(41, 48, 46), font=label_font)
    for row, actor in enumerate(ACTORS):
        y = header_height + row * row_height
        draw.text((12, y + 42), actor.display_name, fill=(41, 48, 46), font=label_font)
        for column, frame in enumerate(frames_by_actor[actor.actor_id]):
            sheet.alpha_composite(frame, (label_width + column * CELL_WIDTH, y))
        draw.line((0, y + row_height - 1, sheet.width, y + row_height - 1), fill=(221, 218, 208, 255))
    draw.text((12, 12), "48 px visible body / common foot anchor", fill=(41, 48, 46), font=title_font)
    sheet.save(QA_DIR / "character-contact-sheet-6-state.png")


def main() -> None:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    QA_DIR.mkdir(parents=True, exist_ok=True)
    loaded = {
        name: Image.open(SOURCE_DIR / name).convert("RGBA")
        for name in {actor.sheet for actor in ACTORS}
    }
    bounds_by_sheet = {
        "contact-sheet-a.png": source_frame_bounds(loaded["contact-sheet-a.png"], 6),
        "contact-sheet-b.png": source_frame_bounds(loaded["contact-sheet-b.png"], 5),
    }
    frames_by_actor: dict[str, list[Image.Image]] = {}
    report: dict[str, object] = {
        "contract": {
            "states": list(STATES),
            "cell": {"width": CELL_WIDTH, "height": CELL_HEIGHT},
            "visibleIdleWidth": VISIBLE_IDLE_WIDTH,
            "footAnchor": {"x": FOOT_ANCHOR[0], "y": FOOT_ANCHOR[1]},
            "placementBasis": "visible-body-bounds-and-foot-anchor",
        },
        "actors": {},
    }
    manifest_actors: dict[str, object] = {}

    for actor in ACTORS:
        source = loaded[actor.sheet]
        raw_frames = [
            crop_source_frame(source, bounds_by_sheet[actor.sheet][actor.row][column])
            for column in range(len(STATES))
        ]
        idle_width = alpha_bbox(raw_frames[0])[2] - alpha_bbox(raw_frames[0])[0]
        scale = VISIBLE_IDLE_WIDTH / idle_width
        frames = [normalize_frame(frame, scale) for frame in raw_frames]
        frames_by_actor[actor.actor_id] = frames

        actor_dir = RUNTIME_DIR / actor.actor_id
        actor_dir.mkdir(parents=True, exist_ok=True)
        sheet = Image.new("RGBA", (CELL_WIDTH * len(STATES), CELL_HEIGHT), (0, 0, 0, 0))
        actor_report: dict[str, object] = {}
        for index, (state, frame) in enumerate(zip(STATES, frames, strict=True)):
            frame.save(actor_dir / f"{state}.png")
            sheet.alpha_composite(frame, (index * CELL_WIDTH, 0))
            actor_report[state] = frame_report(frame)
        sheet.save(actor_dir / "sheet.png")
        report["actors"][actor.actor_id] = actor_report
        manifest_actors[actor.actor_id] = {
            "displayName": actor.display_name,
            "sheet": f"./characters/runtime/{actor.actor_id}/sheet.png",
            "frames": {state: index for index, state in enumerate(STATES)},
        }

    build_contact_sheet(frames_by_actor)

    failures: list[str] = []
    for actor_id, states in report["actors"].items():
        for state, checks in states.items():
            if not checks["artifactPass"]:
                failures.append(f"{actor_id}/{state}: sprite artifact")
            if not checks["footAnchorPass"]:
                failures.append(f"{actor_id}/{state}: foot anchor")
            if not checks["frameBleedPass"]:
                failures.append(f"{actor_id}/{state}: frame bleed")
    report["summary"] = {
        "actorCount": len(ACTORS),
        "frameCount": len(ACTORS) * len(STATES),
        "failureCount": len(failures),
        "failures": failures,
        "pass": not failures,
    }
    (QA_DIR / "character-sprite-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    manifest = {
        "version": 2,
        "states": list(STATES),
        "cell": {"width": CELL_WIDTH, "height": CELL_HEIGHT},
        "visibleBodyWidth": VISIBLE_IDLE_WIDTH,
        "footAnchor": {"x": FOOT_ANCHOR[0], "y": FOOT_ANCHOR[1]},
        "actors": manifest_actors,
    }
    (RUNTIME_DIR / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
