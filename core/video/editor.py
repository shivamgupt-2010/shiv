from pathlib import Path
"""
ShivAI Video Studio: Video Processing and Timeline Render Engine.
Provides deterministic media inspection, trimming, concatenation, subtitles,
and export pipeline integration.
"""
import os
import shutil
import json
import logging
import subprocess
from typing import Dict, Any, List, Optional
import uuid

from core.video.timeline import VideoTimelineProject, Track, VideoClip, TextOverlay, AudioTrackItem
from core.execution.artifacts import artifact_manager, StoredArtifact

logger = logging.getLogger("shivai.video.editor")


class VideoEditor:
    """Manages video timeline manipulation, media inspection, and rendering jobs."""

    def __init__(self):
        self._projects: Dict[str, VideoTimelineProject] = {}
        self._ffmpeg_bin = self._resolve_ffmpeg()
        self._has_ffmpeg = self._ffmpeg_bin is not None

    def _resolve_ffmpeg(self) -> Optional[str]:
        # 1. Check local project .tools
        local_tool = Path("F:/SHIV/shivai/.tools/ffmpeg/bin/ffmpeg.exe")
        if local_tool.exists():
            return str(local_tool)
        # 2. Check imageio_ffmpeg
        try:
            import imageio_ffmpeg
            return imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            pass
        # 3. Check PATH
        return shutil.which("ffmpeg")

    def create_timeline(
        self,
        name: str,
        aspect_ratio: str = "16:9",
        fps: int = 30,
    ) -> VideoTimelineProject:
        """Initializes a new video timeline with selected aspect ratio."""
        dim_map = {
            "16:9": (1920, 1080),
            "9:16": (1080, 1920),
            "1:1": (1080, 1080),
            "4:5": (1080, 1350),
        }
        w, h = dim_map.get(aspect_ratio, (1920, 1080))
        project_id = f"vid_{uuid.uuid4().hex[:10]}"

        base_video_track = Track(
            track_id="track_v1",
            name="Main Video Track",
            track_type="video",
            clips=[],
        )

        project = VideoTimelineProject(
            project_id=project_id,
            name=name,
            width=w,
            height=h,
            fps=fps,
            aspect_ratio=aspect_ratio,
            tracks=[base_video_track],
            text_overlays=[],
            audio_tracks=[],
            total_duration=0.0,
        )
        self._projects[project_id] = project
        logger.info(f"Created video timeline project '{name}' ({project_id}) - {aspect_ratio}")
        return project

    def get_timeline(self, project_id: str) -> Optional[VideoTimelineProject]:
        return self._projects.get(project_id)

    def add_clip(
        self,
        project_id: str,
        source_url: str,
        name: str = "Clip",
        start_time: float = 0.0,
        end_time: Optional[float] = None,
        duration: Optional[float] = None,
        volume: float = 1.0,
        speed: float = 1.0,
    ) -> Optional[VideoClip]:
        """Appends or inserts a video clip into the timeline."""
        project = self.get_timeline(project_id)
        if not project:
            return None

        if duration is not None:
            actual_duration = max(0.1, duration)
            actual_end_time = start_time + actual_duration
        else:
            actual_end_time = end_time if end_time is not None else start_time + 5.0
            actual_duration = max(0.1, actual_end_time - start_time)

        clip_id = f"clip_{uuid.uuid4().hex[:8]}"

        # Calculate placement after existing clips on main track
        main_track = project.tracks[0]
        timeline_start = sum(c.duration for c in main_track.clips)

        clip = VideoClip(
            clip_id=clip_id,
            source_url=source_url,
            name=name,
            start_time=start_time,
            end_time=actual_end_time,
            duration=actual_duration,
            timeline_start=timeline_start,
            volume=volume,
            speed=speed,
        )
        main_track.clips.append(clip)
        self._recalculate_duration(project)
        return clip

    def add_text_overlay(
        self,
        project_id: str,
        text: str,
        start_time: float = 0.0,
        end_time: float = 5.0,
        x: int = 100,
        y: int = 100,
        font_size: int = 36,
        font_color: str = "#FFFFFF",
    ) -> Optional[TextOverlay]:
        """Adds a subtitle or text banner overlay."""
        project = self.get_timeline(project_id)
        if not project:
            return None

        text_id = f"txt_{uuid.uuid4().hex[:8]}"
        overlay = TextOverlay(
            text_id=text_id,
            text=text,
            start_time=start_time,
            end_time=end_time,
            x=x,
            y=y,
            font_size=font_size,
            font_color=font_color,
        )
        project.text_overlays.append(overlay)
        self._recalculate_duration(project)
        return overlay

    def add_audio_track(
        self,
        project_id: str,
        source_url: str,
        duration: float,
        timeline_start: float = 0.0,
        volume: float = 0.8,
    ) -> Optional[AudioTrackItem]:
        """Adds a background music or voice track."""
        project = self.get_timeline(project_id)
        if not project:
            return None

        audio_id = f"aud_{uuid.uuid4().hex[:8]}"
        audio = AudioTrackItem(
            audio_id=audio_id,
            source_url=source_url,
            timeline_start=timeline_start,
            duration=duration,
            volume=volume,
        )
        project.audio_tracks.append(audio)
        self._recalculate_duration(project)
        return audio

    def _recalculate_duration(self, project: VideoTimelineProject) -> None:
        """Computes total project duration from clips and overlays."""
        max_clip = 0.0
        for track in project.tracks:
            for c in track.clips:
                max_clip = max(max_clip, c.timeline_start + c.duration)
        max_overlay = max((o.end_time for o in project.text_overlays), default=0.0)
        max_audio = max((a.timeline_start + a.duration for a in project.audio_tracks), default=0.0)
        project.total_duration = max(max_clip, max_overlay, max_audio)

    def render_manifest(self, project_id: str) -> Dict[str, Any]:
        """
        Generates a portable render specification and HTML5 web player manifest.
        Enables seamless playback in browser canvas players or native FFmpeg pipelines.
        """
        project = self.get_timeline(project_id)
        if not project:
            raise FileNotFoundError(f"Video project '{project_id}' not found.")

        return {
            "project_id": project.project_id,
            "name": project.name,
            "resolution": {"width": project.width, "height": project.height},
            "fps": project.fps,
            "aspect_ratio": project.aspect_ratio,
            "total_duration": project.total_duration,
            "tracks": [t.model_dump() for t in project.tracks],
            "text_overlays": [o.model_dump() for o in project.text_overlays],
            "audio_tracks": [a.model_dump() for a in project.audio_tracks],
            "ffmpeg_available": self._has_ffmpeg,
        }

    def export_video_project(self, project_id: str, job_id: str) -> StoredArtifact:
        """Stores the rendered timeline project specification as a permanent downloadable artifact."""
        manifest = self.render_manifest(project_id)
        raw_json = json.dumps(manifest, indent=2).encode("utf-8")
        return artifact_manager.store_bytes(
            job_id=job_id,
            name=f"{project_id}_timeline.json",
            data=raw_json,
            mime_type="application/json",
            metadata={"type": "video_timeline_manifest", "duration": manifest["total_duration"]},
        )



    async def render_binary_video(
        self,
        input_video_path: str,
        output_video_path: str,
        remove_background: bool = True,
        bg_color_hex: str = "0x994972",
        target_bg_hex: str = "0x070b14",
        voiceover_text: Optional[str] = None,
        voice_model: str = "en-US-ChristopherNeural",
        text_overlay: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Executes binary video processing with FFmpeg:
        - Removes/replaces video background
        - Synthesizes and synchronizes neural voiceover
        - Adds subtitle/caption overlay
        - Encodes production-ready MP4 (H.264 + AAC)
        """
        ffmpeg = self._resolve_ffmpeg()
        if not ffmpeg:
            raise RuntimeError("FFmpeg executable not available for binary video rendering.")

        if not os.path.exists(input_video_path):
            raise FileNotFoundError(f"Source video not found: {input_video_path}")

        # 1. Probe input duration and resolution
        probe_cmd = [ffmpeg, "-i", input_video_path]
        probe_res = subprocess.run(probe_cmd, stderr=subprocess.PIPE, text=True)
        dur = 10.0
        w, h = 1920, 1080
        for l in probe_res.stderr.splitlines():
            if "Duration:" in l:
                try:
                    parts = l.split("Duration:")[1].split(",")[0].strip().split(":")
                    dur = float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
                except Exception:
                    pass
            if "Video:" in l:
                import re
                m = re.search(r"(\d{3,4})x(\d{3,4})", l)
                if m:
                    w, h = int(m.group(1)), int(m.group(2))

        # 2. Generate voiceover if requested
        temp_audio = None
        timed_audio = None
        if voiceover_text:
            import edge_tts
            import uuid
            t_id = uuid.uuid4().hex[:8]
            temp_audio = f"F:/SHIV/shivai/storage/temp_voice_{t_id}.mp3"
            timed_audio = f"F:/SHIV/shivai/storage/temp_voice_{t_id}_timed.m4a"
            communicate = edge_tts.Communicate(voiceover_text, voice_model, rate="-10%", pitch="-5Hz")
            await communicate.save(temp_audio)

            # Pad audio with delay and echo to match video duration
            audio_pad_cmd = [
                ffmpeg, "-y", "-i", temp_audio,
                "-af", f"adelay=1200|1200,aecho=0.8:0.85:60:0.35,apad=whole_dur={dur:.2f}",
                "-c:a", "aac", "-b:a", "192k",
                timed_audio,
            ]
            subprocess.run(audio_pad_cmd, check=True, capture_output=True)

        # 3. Assemble Filtergraph
        filters = []
        if remove_background:
            # Key out background color and composite over target dark background
            filters.append(f"[0:v]colorkey={bg_color_hex}:0.32:0.18[keyed]")
            filters.append(f"color=s={w}x{h}:c={target_bg_hex}:d={dur:.2f}[bg]")
            filters.append("[bg][keyed]overlay=shortest=1[keyed_out]")
            current_v = "[keyed_out]"
        else:
            current_v = "[0:v]"

        if text_overlay:
            filters.append(
                f"{current_v}drawtext=text='{text_overlay}':fontcolor=white@0.9:fontsize=72:"
                f"x=(w-text_w)/2:y=h-240:enable='between(t,1.2,{dur-1.5:.1f})'[outv]"
            )
            final_v = "[outv]"
        else:
            final_v = current_v

        # 4. Construct command
        cmd = [ffmpeg, "-y", "-i", input_video_path]
        if timed_audio:
            cmd.extend(["-i", timed_audio])

        if filters:
            cmd.extend(["-filter_complex", ";".join(filters), "-map", final_v])
        else:
            cmd.extend(["-map", "0:v"])

        if timed_audio:
            cmd.extend(["-map", "1:a"])

        cmd.extend([
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "20",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            output_video_path,
        ])

        # Execute render
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(f"FFmpeg render failed: {proc.stderr[-500:]}")

        # Cleanup temp audio
        if temp_audio and os.path.exists(temp_audio):
            os.remove(temp_audio)
        if timed_audio and os.path.exists(timed_audio):
            os.remove(timed_audio)

        out_size = os.path.getsize(output_video_path)
        return {
            "success": True,
            "output_path": output_video_path,
            "duration": dur,
            "resolution": f"{w}x{h}",
            "size_bytes": out_size,
            "size_mb": round(out_size / (1024 * 1024), 2),
            "voiceover": voiceover_text,
            "background_removed": remove_background,
        }

video_editor = VideoEditor()
