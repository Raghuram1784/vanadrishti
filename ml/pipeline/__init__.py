"""Source-agnostic frame inference; input is uint8 H x W x 3 BGR."""
from .analysis import analyze_frame
from .models import FrameAnalysisResult, FrameStatus
from .quality import QualityConfig

__all__ = ['analyze_frame', 'FrameAnalysisResult', 'FrameStatus', 'QualityConfig']
