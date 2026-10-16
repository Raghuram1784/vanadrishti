"""Backward-compatible backend adapter to the shared ML pipeline."""
from functools import lru_cache
from ml.pipeline.service import FrameAnalyzer, box_iou


class VisionService(FrameAnalyzer):
    pass


@lru_cache(maxsize=1)
def get_vision_service():
    return VisionService()
