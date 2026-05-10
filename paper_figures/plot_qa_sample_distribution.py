from __future__ import annotations

import math
from pathlib import Path


DATA = [
    ("文本问题", 115, "#4C7DFF"),
    ("图片相关问题", 12, "#20B486"),
    ("混合模态问题", 11, "#8B5CF6"),
    ("表格问题", 1, "#F59E0B"),
    ("公式问题", 1, "#EF6C73"),
]

OUT = Path(__file__).with_name("qa_sample_distribution_pie.svg")


def polar_to_xy(cx: float, cy: float, radius: float, angle_deg: float) -> tuple[float, float]:
    angle = math.radians(angle_deg - 90)
    return cx + radius * math.cos(angle), cy + radius * math.sin(angle)


def donut_slice_path(
    cx: float,
    cy: float,
    outer_radius: float,
    inner_radius: float,
    start_angle: float,
    end_angle: float,
) -> str:
    outer_start = polar_to_xy(cx, cy, outer_radius, start_angle)
    outer_end = polar_to_xy(cx, cy, outer_radius, end_angle)
    inner_end = polar_to_xy(cx, cy, inner_radius, end_angle)
    inner_start = polar_to_xy(cx, cy, inner_radius, start_angle)
    large_arc = 1 if end_angle - start_angle > 180 else 0

    return (
        f"M {outer_start[0]:.2f} {outer_start[1]:.2f} "
        f"A {outer_radius} {outer_radius} 0 {large_arc} 1 {outer_end[0]:.2f} {outer_end[1]:.2f} "
        f"L {inner_end[0]:.2f} {inner_end[1]:.2f} "
        f"A {inner_radius} {inner_radius} 0 {large_arc} 0 {inner_start[0]:.2f} {inner_start[1]:.2f} "
        "Z"
    )


def text(x: float, y: float, content: str, *, cls: str = "", anchor: str = "start") -> str:
    return f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}" class="{cls}">{content}</text>'


def main() -> None:
    total = sum(value for _, value, _ in DATA)
    cx, cy = 350, 330
    outer_r, inner_r = 170, 92

    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="980" height="680" viewBox="0 0 980 680">',
        "<defs>",
        '<filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">',
        '<feDropShadow dx="0" dy="10" stdDeviation="12" flood-color="#22304A" flood-opacity="0.14"/>',
        "</filter>",
        '<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">',
        '<stop offset="0%" stop-color="#F8FBFF"/>',
        '<stop offset="100%" stop-color="#EEF4FF"/>',
        "</linearGradient>",
        "</defs>",
        """<style>
            .title { font: 700 30px "Noto Sans CJK SC", "Microsoft YaHei", "PingFang SC", sans-serif; fill: #172033; }
            .subtitle { font: 400 15px "Noto Sans CJK SC", "Microsoft YaHei", "PingFang SC", sans-serif; fill: #667085; }
            .center-num { font: 800 42px "Noto Sans CJK SC", "Microsoft YaHei", "PingFang SC", sans-serif; fill: #172033; }
            .center-label { font: 500 15px "Noto Sans CJK SC", "Microsoft YaHei", "PingFang SC", sans-serif; fill: #667085; }
            .legend-label { font: 700 17px "Noto Sans CJK SC", "Microsoft YaHei", "PingFang SC", sans-serif; fill: #263244; }
            .legend-meta { font: 500 14px "Noto Sans CJK SC", "Microsoft YaHei", "PingFang SC", sans-serif; fill: #667085; }
            .callout { font: 700 15px "Noto Sans CJK SC", "Microsoft YaHei", "PingFang SC", sans-serif; fill: #263244; }
            .callout-meta { font: 500 13px "Noto Sans CJK SC", "Microsoft YaHei", "PingFang SC", sans-serif; fill: #667085; }
        </style>""",
        '<rect width="980" height="680" rx="28" fill="url(#bg)"/>',
        '<rect x="36" y="40" width="908" height="594" rx="26" fill="#FFFFFF" filter="url(#shadow)"/>',
        text(78, 96, "140条问答样本模态分布", cls="title"),
        text(78, 125, "数据来源：paper.md 表 5-4；按互斥的问题模态统计", cls="subtitle"),
        f'<circle cx="{cx}" cy="{cy}" r="{outer_r + 18}" fill="#F5F8FF"/>',
    ]

    start = -4.0
    mid_angles: list[tuple[float, str, int, str]] = []
    for label, value, color in DATA:
        sweep = 360 * value / total
        end = start + sweep
        parts.append(
            f'<path d="{donut_slice_path(cx, cy, outer_r, inner_r, start, end)}" '
            f'fill="{color}" stroke="#FFFFFF" stroke-width="4"/>'
        )
        mid_angles.append(((start + end) / 2, label, value, color))
        start = end

    parts.extend(
        [
            f'<circle cx="{cx}" cy="{cy}" r="{inner_r - 6}" fill="#FFFFFF"/>',
            text(cx, cy - 8, str(total), cls="center-num", anchor="middle"),
            text(cx, cy + 26, "条问答样本", cls="center-label", anchor="middle"),
        ]
    )

    for angle, label, value, color in mid_angles:
        pct = value / total * 100
        if value <= 1:
            # Tiny slices share compact labels near the lower-left area to avoid collisions.
            continue
        sx, sy = polar_to_xy(cx, cy, outer_r + 4, angle)
        ex, ey = polar_to_xy(cx, cy, outer_r + 40, angle)
        label_x = ex + (18 if ex >= cx else -18)
        anchor = "start" if ex >= cx else "end"
        parts.append(
            f'<path d="M {sx:.1f} {sy:.1f} L {ex:.1f} {ey:.1f}" '
            f'stroke="{color}" stroke-width="2" fill="none" stroke-linecap="round"/>'
        )
        parts.append(text(label_x, ey - 4, label, cls="callout", anchor=anchor))
        parts.append(text(label_x, ey + 18, f"{value}题 · {pct:.1f}%", cls="callout-meta", anchor=anchor))

    parts.append('<g transform="translate(650 190)">')
    parts.append(text(0, -24, "类别明细", cls="legend-label"))
    for i, (label, value, color) in enumerate(DATA):
        y = i * 66
        pct = value / total * 100
        parts.append(f'<rect x="0" y="{y}" width="40" height="40" rx="10" fill="{color}"/>')
        parts.append(text(56, y + 16, label, cls="legend-label"))
        parts.append(text(56, y + 39, f"{value}题，占比 {pct:.1f}%", cls="legend-meta"))
    parts.append("</g>")

    parts.extend(
        [
            '<line x1="78" y1="585" x2="902" y2="585" stroke="#E6EAF2" stroke-width="1"/>',
            text(78, 614, "说明：图谱关系问题、多跳推理问题、跨文件综合问题属于附加能力标签，可能与上述模态重叠，未纳入该饼图。", cls="subtitle"),
            "</svg>",
        ]
    )

    OUT.write_text("\n".join(parts), encoding="utf-8")
    print(f"saved: {OUT}")


if __name__ == "__main__":
    main()
