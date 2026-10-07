"""
VanaDrishti - Wildlife Surveillance & Ranger Decision-Support System
Phase 1: Real-Time Live Webcam Detection Stream

Captures live camera frames, performs real-time detection of animals, persons,
and vehicles using MegaDetector V6, and renders surveillance HUD overlays.
"""

import sys
import time
import argparse
import logging
from typing import Optional

import cv2

from ml.detector.detector import WildlifeDetector, DEFAULT_MODEL_VERSION, DEFAULT_CONF_THRESHOLD
from ml.detector.visualization import draw_detections

# Setup structured logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [vanadrishti.webcam]: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("vanadrishti.webcam")


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments for live webcam stream."""
    parser = argparse.ArgumentParser(
        description="VanaDrishti Phase 1 - Live Webcam Surveillance Detection"
    )
    parser.add_argument(
        "--camera-id", "-c",
        type=int,
        default=0,
        help="Index of camera device (default: 0 for integrated/laptop webcam)"
    )
    parser.add_argument(
        "--conf-threshold", "-t",
        type=float,
        default=DEFAULT_CONF_THRESHOLD,
        help=f"Detection confidence threshold between 0.0 and 1.0 (default: {DEFAULT_CONF_THRESHOLD})"
    )
    parser.add_argument(
        "--model-version",
        type=str,
        default=DEFAULT_MODEL_VERSION,
        help=f"MegaDetector V6 version identifier (default: {DEFAULT_MODEL_VERSION})"
    )
    parser.add_argument(
        "--device",
        type=str,
        default=None,
        help="Compute device ('cuda', 'cpu', or None for automatic selection)"
    )
    parser.add_argument(
        "--width",
        type=int,
        default=None,
        help="Requested capture width in pixels"
    )
    parser.add_argument(
        "--height",
        type=int,
        default=None,
        help="Requested capture height in pixels"
    )
    parser.add_argument(
        "--max-frames",
        type=int,
        default=None,
        help="Maximum frames to process before exiting (useful for testing)"
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run without displaying GUI window (for remote/headless test environments)"
    )
    return parser.parse_args()


def run_webcam_detection(
    camera_id: int = 0,
    conf_threshold: float = DEFAULT_CONF_THRESHOLD,
    model_version: str = DEFAULT_MODEL_VERSION,
    device: Optional[str] = None,
    width: Optional[int] = None,
    height: Optional[int] = None,
    max_frames: Optional[int] = None,
    headless: bool = False
) -> int:
    """
    Main loop for live webcam detection stream.
    """
    logger.info("Initializing VanaDrishti Wildlife Surveillance Stream...")
    logger.info("Camera Device: %d | Confidence Threshold: %.2f", camera_id, conf_threshold)

    # 1. Initialize detector model (loaded only once)
    try:
        detector = WildlifeDetector.get_instance(
            model_version=model_version,
            device=device,
            conf_threshold=conf_threshold
        )
    except Exception as exc:
        logger.error("Failed to initialize detector: %s", exc)
        return 1

    # 2. Open webcam device
    logger.info("Connecting to camera device #%d...", camera_id)
    cap = cv2.VideoCapture(camera_id)

    if not cap.isOpened():
        logger.error(
            "Failed to open camera device %d. "
            "Please ensure your webcam is connected, not in use by another application, "
            "and permissions are granted.",
            camera_id
        )
        return 1

    # Optional resolution setting
    if width is not None:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    if height is not None:
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

    actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    logger.info("Camera stream ready. Resolution: %dx%d px", actual_w, actual_h)
    logger.info("Press 'q' in the video window to stop.")

    window_name = "VanaDrishti - TATR Live Surveillance Stream"
    if not headless:
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)

    frame_count = 0
    start_time = time.time()
    last_fps_time = time.time()
    current_fps = 0.0
    total_detections_count = 0

    try:
        while True:
            t0 = time.time()
            ret, frame = cap.read()

            if not ret or frame is None:
                logger.warning("Failed to read frame from camera %d. Stream may have terminated.", camera_id)
                break

            frame_count += 1

            # Perform detection on the current frame
            detections = detector.detect(frame, conf_threshold=conf_threshold)

            if detections:
                total_detections_count += len(detections)
                summary_classes = [f"{d['class']} ({int(d['confidence'] * 100)}%)" for d in detections]
                logger.info("Frame %d | Detected %d object(s): %s", frame_count, len(detections), ", ".join(summary_classes))

            # Calculate rolling FPS
            dt = time.time() - t0
            instant_fps = 1.0 / dt if dt > 0 else 30.0
            current_fps = 0.85 * current_fps + 0.15 * instant_fps if current_fps > 0 else instant_fps

            # Render overlay annotations
            annotated_frame = draw_detections(
                frame,
                detections,
                fps=current_fps,
                source_title=f"VanaDrishti TATR Camera #{camera_id}"
            )

            if not headless:
                cv2.imshow(window_name, annotated_frame)
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q") or key == ord("Q") or key == 27:  # 'q' or ESC
                    logger.info("Exit requested by user.")
                    break

            if max_frames is not None and frame_count >= max_frames:
                logger.info("Reached maximum requested frames (%d). Stopping.", max_frames)
                break

    except KeyboardInterrupt:
        logger.info("Interrupted by user (Ctrl+C).")
    finally:
        cap.release()
        if not headless:
            cv2.destroyAllWindows()

    elapsed = time.time() - start_time
    avg_fps = frame_count / elapsed if elapsed > 0 else 0.0
    logger.info(
        "Surveillance session finished. Processed %d frames in %.2fs (Avg: %.1f FPS). Total detections: %d",
        frame_count, elapsed, avg_fps, total_detections_count
    )
    return 0


def main() -> None:
    args = parse_arguments()
    exit_code = run_webcam_detection(
        camera_id=args.camera_id,
        conf_threshold=args.conf_threshold,
        model_version=args.model_version,
        device=args.device,
        width=args.width,
        height=args.height,
        max_frames=args.max_frames,
        headless=args.headless
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
