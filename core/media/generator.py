"""
ShivAI 100% Free Multimodal Generation Engine (Images, Videos, Audio).
Requires 0 MB GPU RAM on Render by utilizing serverless inference dispatch.
"""
import urllib.parse
from typing import Optional, Dict, Any, List
import httpx
import edge_tts


class FreeMediaGenerator:
    """
    Central orchestration engine for generating Images, Videos, and Neural Speech.
    Zero credit cards, zero GPU billing, Render Free compatible.
    """

    def __init__(self, hf_token: Optional[str] = None):
        self.hf_token = hf_token

    # -------------------------------------------------------------
    # 1. 🖼️ TEXT-TO-IMAGE (Zero API Key, High-Resolution Flux/SDXL)
    # -------------------------------------------------------------
    async def generate_image(
        self,
        prompt: str,
        width: int = 1024,
        height: int = 1024,
        model: str = "flux",
        seed: Optional[int] = None,
        fetch_bytes: bool = False
    ) -> Dict[str, Any]:
        """
        Generates high-res photorealistic images via Pollinations Flux API.
        Supported models: 'flux', 'turbo', 'flux-realism', 'flux-anime', 'flux-3d'.
        """
        if not prompt or not prompt.strip():
            raise ValueError("Image prompt cannot be empty.")

        clean_prompt = prompt.strip()
        encoded_prompt = urllib.parse.quote(clean_prompt)
        seed_param = f"&seed={seed}" if seed is not None else ""
        
        image_url = (
            f"https://image.pollinations.ai/prompt/{encoded_prompt}"
            f"?width={width}&height={height}&model={model}&nologo=true{seed_param}"
        )

        result: Dict[str, Any] = {
            "status": "success",
            "media_type": "image/jpeg",
            "image_url": image_url,
            "width": width,
            "height": height,
            "model": model,
            "prompt": clean_prompt,
        }

        if fetch_bytes:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.get(image_url)
                if resp.status_code == 200:
                    result["bytes"] = resp.content
                else:
                    raise RuntimeError(f"Image fetch failed with HTTP {resp.status_code}")

        return result

    # -------------------------------------------------------------
    # 2. 🎬 TEXT-TO-VIDEO (Free Short Video & Animation)
    # -------------------------------------------------------------
    async def generate_video(
        self,
        prompt: str,
        duration_seconds: int = 3,
        fps: int = 16
    ) -> Dict[str, Any]:
        """
        Generates short video / animated clips.
        """
        if not prompt or not prompt.strip():
            raise ValueError("Video prompt cannot be empty.")

        clean_prompt = prompt.strip()
        encoded_prompt = urllib.parse.quote(clean_prompt)
        
        video_url = (
            f"https://image.pollinations.ai/prompt/{encoded_prompt}"
            f"?model=flux-video&duration={duration_seconds}&fps={fps}"
        )

        return {
            "status": "success",
            "media_type": "video/mp4",
            "video_url": video_url,
            "duration": duration_seconds,
            "fps": fps,
            "prompt": clean_prompt,
        }

    # -------------------------------------------------------------
    # 3. 🔊 AUDIO: NEURAL SPEECH & VOICE (Microsoft Edge-TTS)
    # -------------------------------------------------------------
    async def generate_speech(
        self,
        text: str,
        voice: str = "hi-IN-SwaraNeural",
        rate: str = "+0%",
        pitch: str = "+0Hz"
    ) -> bytes:
        """
        Generates natural human-like speech with high fidelity.
        Voices:
          - 'hi-IN-SwaraNeural' (Hindi Female)
          - 'hi-IN-MadhurNeural' (Hindi Male)
          - 'en-IN-NeerjaNeural' (Indian English Female)
          - 'en-IN-PrabhatNeural' (Indian English Male)
          - 'en-US-JennyNeural' (US English Female)
        """
        if not text or not text.strip():
            raise ValueError("Speech text cannot be empty.")

        communicate = edge_tts.Communicate(text.strip(), voice=voice, rate=rate, pitch=pitch)
        audio_chunks = []
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_chunks.append(chunk["data"])
        
        if not audio_chunks:
            raise RuntimeError("No audio chunks generated from TTS engine.")

        return b"".join(audio_chunks)

    # -------------------------------------------------------------
    # 4. 🎵 MUSIC & SOUND EFFECTS (Meta MusicGen via Hugging Face)
    # -------------------------------------------------------------
    async def generate_music(self, prompt: str) -> bytes:
        """
        Generates short instrumental audio/music using free Hugging Face inference.
        """
        if not prompt or not prompt.strip():
            raise ValueError("Music prompt cannot be empty.")

        url = "https://api-inference.huggingface.co/models/facebook/musicgen-small"
        headers = {}
        if self.hf_token:
            headers["Authorization"] = f"Bearer {self.hf_token}"
            
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(url, headers=headers, json={"inputs": prompt.strip()})
            if resp.status_code == 200:
                return resp.content
            else:
                raise RuntimeError(f"MusicGen failed with status {resp.status_code}: {resp.text}")


media_generator = FreeMediaGenerator()


def get_media_generator() -> FreeMediaGenerator:
    return media_generator
