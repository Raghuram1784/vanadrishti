"""Bounded-cost image heuristics. Flags describe appearance, never physical cause."""
import cv2
import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator
from .models import ImageQuality, QualityFlag as Flag, QualityStatus as Status


class QualityConfig(BaseModel):
    model_config = ConfigDict(frozen=True, allow_inf_nan=False)
    max_dimension: int = Field(default=640, ge=32, le=4096)
    dark_brightness: float = Field(default=25, ge=0, le=255)
    bright_brightness: float = Field(default=235, ge=0, le=255)
    low_contrast: float = Field(default=12, ge=0, le=128)
    blur_threshold: float = Field(default=35, ge=0)
    near_black: int = Field(default=10, ge=0, le=255)
    near_white: int = Field(default=245, ge=0, le=255)
    unusable_extreme_ratio: float = Field(default=.98, gt=0, le=1)

    @model_validator(mode='after')
    def ordered(self):
        if self.dark_brightness >= self.bright_brightness or self.near_black >= self.near_white:
            raise ValueError('Dark thresholds must be below bright thresholds')
        return self


def valid_frame(frame):
    return (isinstance(frame, np.ndarray) and frame.dtype == np.uint8
            and frame.ndim == 3 and frame.shape[2] == 3
            and frame.shape[0] > 0 and frame.shape[1] > 0)


def assess_quality(frame, config=None):
    if not valid_frame(frame):
        raise ValueError('Expected a nonempty uint8 H x W x 3 BGR frame')
    config = config or QualityConfig()
    h, w = frame.shape[:2]
    scale = min(1., config.max_dimension / max(h, w))
    sample = frame if scale == 1 else cv2.resize(
        frame, (max(1, round(w * scale)), max(1, round(h * scale))), interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(sample, cv2.COLOR_BGR2GRAY)
    brightness, contrast = float(gray.mean()), float(gray.std())
    blur = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    black = float(np.mean(gray <= config.near_black))
    white = float(np.mean(gray >= config.near_white))
    flags, reasons = [], []
    for condition, flag, reason in (
        (brightness < config.dark_brightness, Flag.TOO_DARK, 'Very low image brightness.'),
        (brightness > config.bright_brightness, Flag.OVEREXPOSED, 'Very high image brightness.'),
        (blur < config.blur_threshold, Flag.BLURRED, 'Low sharpness; image may be blurred.'),
        (contrast < config.low_contrast, Flag.LOW_CONTRAST, 'Low image contrast.'),
    ):
        if condition:
            flags.append(flag)
            reasons.append(reason)
    obstruction = Flag.BLURRED in flags and Flag.LOW_CONTRAST in flags
    if obstruction:
        flags.append(Flag.POSSIBLE_OBSTRUCTION)
        reasons.append('Possible obstruction or low-detail scene; lens inspection may be useful if persistent.')
    unusable = max(black, white) >= config.unusable_extreme_ratio
    status = Status.UNUSABLE if unusable else Status.DEGRADED if flags else Status.GOOD
    return ImageQuality(status=status, brightness=brightness, contrast=contrast, blur_score=blur,
                        near_black_ratio=black, near_white_ratio=white,
                        possible_obstruction=obstruction, flags=flags, reasons=reasons)
