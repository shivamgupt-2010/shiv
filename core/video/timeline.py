"""
ShivAI Video Studio: Timeline and Track Data Models.
Defines a non-destructive, multi-track timeline project representation for video editing.
"""
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class VideoClip(BaseModel):
    clip_id: str
    source_url: str
    name: str = "Clip"
    start_time: float = 0.0  # seconds into source
    end_time: float = 5.0    # seconds into source
    duration: float = 5.0
    timeline_start: float = 0.0  # placement on timeline
    volume: float = 1.0
    speed: float = 1.0
    crop_x: Optional[int] = None
    crop_y: Optional[int] = None
    crop_w: Optional[int] = None
    crop_h: Optional[int] = None


class TextOverlay(BaseModel):
    text_id: str
    text: str
    start_time: float = 0.0
    end_time: float = 5.0
    x: int = 100
    y: int = 100
    font_size: int = 36
    font_color: str = "#FFFFFF"
    background_color: Optional[str] = "rgba(0,0,0,0.5)"
    animation: str = "fade"  # "none", "fade", "slide"


class AudioTrackItem(BaseModel):
    audio_id: str
    source_url: str
    name: str = "Audio"
    timeline_start: float = 0.0
    duration: float = 10.0
    volume: float = 0.8
    fade_in: float = 0.5
    fade_out: float = 0.5


class Track(BaseModel):
    track_id: str
    name: str
    track_type: str = "video"  # "video", "audio", "overlay"
    muted: bool = False
    locked: bool = False
    clips: List[VideoClip] = Field(default_factory=list)


class VideoTimelineProject(BaseModel):
    project_id: str
    name: str
    width: int = 1920
    height: int = 1080
    fps: int = 30
    aspect_ratio: str = "16:9"  # "16:9", "9:16", "1:1", "4:5"
    tracks: List[Track] = Field(default_factory=list)
    text_overlays: List[TextOverlay] = Field(default_factory=list)
    audio_tracks: List[AudioTrackItem] = Field(default_factory=list)
    total_duration: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)
