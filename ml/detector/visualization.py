"""
VanaDrishti - Wildlife Surveillance & Ranger Decision-Support System
Visualization & UI Rendering Utilities for Video/Webcam Stream Overlays

Keeps UI styling and OpenCV drawing code strictly separated from ML detector logic.
"""

from typing import List, Dict, Any, Optional, Tuple
import numpy as np
import cv2

# Visual theme colors for VanaDrishti surveillance streams (BGR format)
CLASS_COLORS = {
    "animal": (60, 190, 80),     # Forest Green
    "person": (30, 130, 255),    # Tactical Amber / Orange Alert
    "vehicle": (230, 180, 20),   # Golden Yellow
    "unknown": (180, 180, 180)   # Neutral Gray
}


def get_class_color(class_name: str) -> Tuple[int, int, int]:
    """Returns the BGR color for a given detected class."""
    return CLASS_COLORS.get(class_name.lower(), CLASS_COLORS["unknown"])


def draw_bounding_box(
    frame: np.ndarray,
    detection: Dict[str, Any],
    box_thickness: int = 2,
    font_scale: float = 0.55
) -> None:
    """
    Renders an individual detection onto the frame with tactical corner accents
    and a badge displaying class name and confidence percentage.
    """
    height, width = frame.shape[:2]
    bbox = detection.get("bbox", [0.0, 0.0, 0.0, 0.0])
    class_name = detection.get("class", "object")
    confidence = float(detection.get("confidence", 0.0))

    # Convert normalized coords [0.0 - 1.0] to integer pixel coordinates
    x1 = int(round(bbox[0] * width))
    y1 = int(round(bbox[1] * height))
    x2 = int(round(bbox[2] * width))
    y2 = int(round(bbox[3] * height))

    # Ensure coordinates stay within frame bounds
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(width - 1, x2), min(height - 1, y2)

    if x2 <= x1 or y2 <= y1:
        return

    color = get_class_color(class_name)

    # 1. Main bounding box
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, box_thickness, cv2.LINE_AA)

    # 2. Corner accent markers for tactical camera surveillance aesthetic
    corner_len = min(16, max(6, int((x2 - x1) * 0.15)), max(6, int((y2 - y1) * 0.15)))
    accent_thick = box_thickness + 1
    # Top-left
    cv2.line(frame, (x1, y1), (x1 + corner_len, y1), color, accent_thick, cv2.LINE_AA)
    cv2.line(frame, (x1, y1), (x1, y1 + corner_len), color, accent_thick, cv2.LINE_AA)
    # Top-right
    cv2.line(frame, (x2, y1), (x2 - corner_len, y1), color, accent_thick, cv2.LINE_AA)
    cv2.line(frame, (x2, y1), (x2, y1 + corner_len), color, accent_thick, cv2.LINE_AA)
    # Bottom-left
    cv2.line(frame, (x1, y2), (x1 + corner_len, y2), color, accent_thick, cv2.LINE_AA)
    cv2.line(frame, (x1, y2), (x1, y2 - corner_len), color, accent_thick, cv2.LINE_AA)
    # Bottom-right
    cv2.line(frame, (x2, y2), (x2 - corner_len, y2), color, accent_thick, cv2.LINE_AA)
    cv2.line(frame, (x2, y2), (x2, y2 - corner_len), color, accent_thick, cv2.LINE_AA)

    # 3. Label badge
    label_text = f"{class_name.upper()} {int(round(confidence * 100))}%"
    font = cv2.FONT_HERSHEY_SIMPLEX
    (text_w, text_h), baseline = cv2.getTextSize(label_text, font, font_scale, 1)

    badge_y1 = max(0, y1 - text_h - 8)
    badge_y2 = y1
    badge_x1 = x1
    badge_x2 = min(width - 1, x1 + text_w + 12)

    # Badge background filled rectangle
    cv2.rectangle(frame, (badge_x1, badge_y1), (badge_x2, badge_y2), color, -1)

    # Badge text (dark charcoal text on bright badge)
    text_color = (15, 15, 15)
    cv2.putText(
        frame,
        label_text,
        (badge_x1 + 6, badge_y2 - 5),
        font,
        font_scale,
        text_color,
        1,
        cv2.LINE_AA
    )


def draw_hud(
    frame: np.ndarray,
    detections: List[Dict[str, Any]],
    fps: Optional[float] = None,
    source_title: str = "VanaDrishti Surveillance Node"
) -> None:
    """
    Renders an elegant tactical top HUD header showing system status, FPS,
    and detection counts by category.
    """
    height, width = frame.shape[:2]
    hud_h = 42

    # Semi-transparent overlay bar at the top
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (width, hud_h), (20, 24, 28), -1)
    cv2.addWeighted(overlay, 0.78, frame, 0.22, 0, frame)

    # Accent line separating HUD from feed
    cv2.line(frame, (0, hud_h), (width, hud_h), (50, 60, 70), 1, cv2.LINE_AA)

    font = cv2.FONT_HERSHEY_SIMPLEX

    # Left: Project & Location
    cv2.putText(
        frame,
        source_title,
        (14, 26),
        font,
        0.55,
        (240, 240, 240),
        1,
        cv2.LINE_AA
    )

    # Middle: Detection counts
    animal_cnt = sum(1 for d in detections if d.get("class") == "animal")
    person_cnt = sum(1 for d in detections if d.get("class") == "person")
    vehicle_cnt = sum(1 for d in detections if d.get("class") == "vehicle")

    stats_text = f"Animals: {animal_cnt} | Persons: {person_cnt} | Vehicles: {vehicle_cnt}"
    (stat_w, _), _ = cv2.getTextSize(stats_text, font, 0.48, 1)
    stat_x = max(260, (width - stat_w) // 2)
    cv2.putText(
        frame,
        stats_text,
        (stat_x, 26),
        font,
        0.48,
        (190, 215, 230),
        1,
        cv2.LINE_AA
    )

    # Right: FPS and Quit prompt
    right_parts = []
    if fps is not None and fps > 0:
        right_parts.append(f"{fps:.1f} FPS")
    right_parts.append("[Q: Quit]")
    right_text = " | ".join(right_parts)

    (r_w, _), _ = cv2.getTextSize(right_text, font, 0.45, 1)
    cv2.putText(
        frame,
        right_text,
        (width - r_w - 14, 26),
        font,
        0.45,
        (160, 175, 185),
        1,
        cv2.LINE_AA
    )


def draw_detections(
    frame: np.ndarray,
    detections: List[Dict[str, Any]],
    fps: Optional[float] = None,
    source_title: str = "VanaDrishti Surveillance Node"
) -> np.ndarray:
    """
    Annotates a video frame with all detected bounding boxes and the status HUD.
    Returns the annotated frame.
    """
    annotated = frame.copy()

    # Draw all bounding boxes
    for det in detections:
        draw_bounding_box(annotated, det)

    # Draw HUD bar
    draw_hud(annotated, detections, fps=fps, source_title=source_title)

    return annotated
