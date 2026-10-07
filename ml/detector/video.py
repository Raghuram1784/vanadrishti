"""
VanaDrishti - Wildlife Surveillance & Ranger Decision-Support System
Phase 1: Prerecorded Video Processing & Surveillance Detection

Processes prerecorded camera-trap or patrol drone footage, performs
wildlife, human, and vehicle detection using MegaDetector V6, displays
live annotated detections preserving original playback speed, and optionally
exports the annotated video to an output file.
"""

import os
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
    format="[%(asctime)s] [%(levelname)s] [vanadrishti.video]: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("vanadrishti.video")


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments for video processing."""
    parser = argparse.ArgumentParser(
        description="VanaDrishti Phase 1 - Prerecorded Video Surveillance Analysis"
    )
    parser.add_argument(
        "--input", "-i",
        type=str,
        required=True,
        help="Path to input video file (e.g. data/demo/trail_camera.mp4)"
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default=None,
        help="Optional path to save annotated output video (e.g. data/demo/output_annotated.mp4)"
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
        "--no-display",
        action="store_true",
        help="Disable interactive OpenCV window (recommended for headless or batch exports)"
    )
    parser.add_argument(
        "--max-frames",
        type=int,
        default=None,
        help="Maximum frames to process before terminating"
    )
    return parser.parse_args()


def process_video(
    input_path: str,
    output_path: Optional[str] = None,
    conf_threshold: float = DEFAULT_CONF_THRESHOLD,
    model_version: str = DEFAULT_MODEL_VERSION,
    device: Optional[str] = None,
    no_display: bool = False,
    max_frames: Optional[int] = None
) -> int:
    """
    Process a prerecorded video file and annotate animal, person, and vehicle detections.
    """
    if not os.path.exists(input_path):
        logger.error("Input video file does not exist: %s", input_path)
        return 1

    logger.info("Opening input video: %s", input_path)
    cap = cv2.VideoCapture(input_path)

    if not cap.isOpened():
        logger.error("Failed to open video file: %s. Verify video format and codecs.", input_path)
        return 1

    # Extract video properties
    src_fps = cap.get(cv2.CAP_PROP_FPS)
    if src_fps <= 0 or src_fps != src_fps:  # check <= 0 or NaN
        src_fps = 25.0
        logger.warning("Could not read original FPS. Defaulting to %.1f FPS.", src_fps)

    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    logger.info(
        "Video metadata: %dx%d resolution, %.2f FPS, %s frames total",
        frame_width, frame_height, src_fps, total_frames if total_frames > 0 else "unknown"
    )

    # Initialize model (singleton ensures one-time load)
    try:
        detector = WildlifeDetector.get_instance(
            model_version=model_version,
            device=device,
            conf_threshold=conf_threshold
        )
    except Exception as exc:
        logger.error("Failed to initialize detector: %s", exc)
        cap.release()
        return 1

    # Initialize video writer if requested
    writer = None
    if output_path:
        out_dir = os.path.dirname(output_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(output_path, fourcc, src_fps, (frame_width, frame_height))
        if not writer.isOpened():
            logger.warning("Failed to open VideoWriter with 'mp4v' codec. Trying 'XVID'...")
            fourcc = cv2.VideoWriter_fourcc(*"XVID")
            writer = cv2.VideoWriter(output_path, fourcc, src_fps, (frame_width, frame_height))

        if writer.isOpened():
            logger.info("Exporting annotated video to: %s", output_path)
        else:
            logger.error("Could not initialize VideoWriter for %s. Video saving disabled.", output_path)
            writer = None

    window_name = f"VanaDrishti - {os.path.basename(input_path)}"
    if not no_display:
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        logger.info("Display window active. Press 'q' to quit early.")

    target_frame_duration_ms = 1000.0 / src_fps
    frame_idx = 0
    start_time = time.time()
    total_detections_count = 0
    class_counts = {"animal": 0, "person": 0, "vehicle": 0}

    try:
        while True:
            t_frame_start = time.time()
            ret, frame = cap.read()

            if not ret or frame is None:
                logger.info("Reached end of video stream.")
                break

            frame_idx += 1

            # Run detection
            t_infer_start = time.time()
            detections = detector.detect(frame, conf_threshold=conf_threshold)
            t_infer_duration_ms = (time.time() - t_infer_start) * 1000.0

            if detections:
                total_detections_count += len(detections)
                for d in detections:
                    cls_name = d.get("class", "animal")
                    class_counts[cls_name] = class_counts.get(cls_name, 0) + 1

                summary = ", ".join([f"{d['class']} ({int(d['confidence'] * 100)}%)" for d in detections])
                logger.info("Frame %d/%s | Detections (%d): %s", frame_idx, total_frames, len(detections), summary)

            # Rolling FPS for HUD display
            current_fps = 1000.0 / max(1.0, t_infer_duration_ms)

            # Draw tactical bounding boxes and HUD
            annotated_frame = draw_detections(
                frame,
                detections,
                fps=current_fps,
                source_title=f"TATR Footage: {os.path.basename(input_path)}"
            )

            # Write to output file if configured
            if writer is not None:
                writer.write(annotated_frame)

            # Display with approximate original FPS playback pacing
            if not no_display:
                cv2.imshow(window_name, annotated_frame)
                elapsed_ms = (time.time() - t_frame_start) * 1000.0
                delay_ms = max(1, int(round(target_frame_duration_ms - elapsed_ms)))
                key = cv2.waitKey(delay_ms) & 0xFF
                if key == ord("q") or key == ord("Q") or key == 27:
                    logger.info("User requested early termination.")
                    break

            if max_frames is not None and frame_idx >= max_frames:
                logger.info("Reached frame processing limit (%d frames).", max_frames)
                break

    except KeyboardInterrupt:
        logger.info("Processing interrupted by user (Ctrl+C).")
    finally:
        cap.release()
        if writer is not None:
            writer.release()
            logger.info("Successfully finalized output video: %s", output_path)
        if not no_display:
            cv2.destroyAllWindows()

    total_time = time.time() - start_time
    avg_fps = frame_idx / total_time if total_time > 0 else 0.0
    logger.info("==================================================")
    logger.info("Video Processing Summary:")
    logger.info("Frames processed: %d | Time: %.2fs | Avg Speed: %.1f FPS", frame_idx, total_time, avg_fps)
    logger.info("Total detections: %d", total_detections_count)
    logger.info("  - Animals:  %d", class_counts.get("animal", 0))
    logger.info("  - Persons:  %d", class_counts.get("person", 0))
    logger.info("  - Vehicles: %d", class_counts.get("vehicle", 0))
    logger.info("==================================================")

    return 0


def main() -> None:
    args = parse_arguments()
    exit_code = process_video(
        input_path=args.input,
        output_path=args.output,
        conf_threshold=args.conf_threshold,
        model_version=args.model_version,
        device=args.device,
        no_display=args.no_display,
        max_frames=args.max_frames
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
