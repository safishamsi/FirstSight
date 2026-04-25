import cv2
import numpy as np


def draw_detection_box(img, bbox, track_id, label, color, line_thickness=2):
    """Draw a bounding box with rounded label background and track ID."""
    x1, y1, x2, y2 = [int(v) for v in bbox]
    tl = line_thickness

    # Draw bounding box
    cv2.rectangle(img, (x1, y1), (x2, y2), color, tl, cv2.LINE_AA)

    # Draw label background with rounded corners
    tf = max(tl - 1, 1)
    t_size = cv2.getTextSize(label, 0, fontScale=tl / 3, thickness=tf)[0]
    _draw_rounded_rect(
        img, (x1, y1 - t_size[1] - 3), (x1 + t_size[0], y1 + 3), color, 1, 8, 2
    )
    cv2.putText(
        img, label, (x1, y1 - 2), 0, tl / 3,
        [225, 255, 255], thickness=tf, lineType=cv2.LINE_AA,
    )

    # Draw track ID
    id_label = str(track_id)
    id_size = cv2.getTextSize(id_label, cv2.FONT_HERSHEY_PLAIN, 2, 2)[0]
    cv2.rectangle(
        img, (x1, y1), (x1 + id_size[0] + 3, y1 + id_size[1] + 4), color, -1
    )
    cv2.putText(
        img, id_label, (x1, y1 + id_size[1] + 4),
        cv2.FONT_HERSHEY_PLAIN, 1, [255, 255, 255], 1,
    )


def draw_fps(img, fps):
    """Draw FPS counter on the image."""
    cv2.line(img, (20, 25), (127, 25), [85, 45, 255], 30)
    cv2.putText(
        img, f"FPS: {int(fps)}", (11, 35), 0, 1,
        [225, 255, 255], thickness=2, lineType=cv2.LINE_AA,
    )


def draw_heart_rate_overlay(img, crop_frame, position, bpm, is_ready):
    """Composite the heart rate crop onto the main frame."""
    x_offset, y_offset = position
    h, w = crop_frame.shape[:2]
    x_end = x_offset + w
    y_end = y_offset + h

    img_h, img_w = img.shape[:2]
    if x_end > img_w or y_end > img_h or x_offset < 0 or y_offset < 0:
        return

    img[y_offset:y_end, x_offset:x_end] = crop_frame


def compute_color_for_label(label_id):
    """Deterministic color for a class label."""
    palette = (2 ** 11 - 1, 2 ** 15 - 1, 2 ** 20 - 1)
    color = [int((p * (label_id ** 2 - label_id + 1)) % 255) for p in palette]
    return tuple(color)


def _draw_rounded_rect(img, pt1, pt2, color, thickness, r, d):
    """Draw a rectangle with rounded corners."""
    x1, y1 = pt1
    x2, y2 = pt2
    cv2.line(img, (x1 + r, y1), (x1 + r + d, y1), color, thickness)
    cv2.line(img, (x1, y1 + r), (x1, y1 + r + d), color, thickness)
    cv2.ellipse(img, (x1 + r, y1 + r), (r, r), 180, 0, 90, color, thickness)
    cv2.line(img, (x2 - r, y1), (x2 - r - d, y1), color, thickness)
    cv2.line(img, (x2, y1 + r), (x2, y1 + r + d), color, thickness)
    cv2.ellipse(img, (x2 - r, y1 + r), (r, r), 270, 0, 90, color, thickness)
    cv2.line(img, (x1 + r, y2), (x1 + r + d, y2), color, thickness)
    cv2.line(img, (x1, y2 - r), (x1, y2 - r - d), color, thickness)
    cv2.ellipse(img, (x1 + r, y2 - r), (r, r), 90, 0, 90, color, thickness)
    cv2.line(img, (x2 - r, y2), (x2 - r - d, y2), color, thickness)
    cv2.line(img, (x2, y2 - r), (x2, y2 - r - d), color, thickness)
    cv2.ellipse(img, (x2 - r, y2 - r), (r, r), 0, 0, 90, color, thickness)
    cv2.rectangle(img, (x1 + r, y1), (x2 - r, y2), color, -1, cv2.LINE_AA)
    cv2.rectangle(img, (x1, y1 + r), (x2, y2 - r - d), color, -1, cv2.LINE_AA)
    cv2.circle(img, (x1 + r, y1 + r), 2, color, 12)
    cv2.circle(img, (x2 - r, y1 + r), 2, color, 12)
    cv2.circle(img, (x1 + r, y2 - r), 2, color, 12)
    cv2.circle(img, (x2 - r, y2 - r), 2, color, 12)
