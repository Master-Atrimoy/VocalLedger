from faster_whisper import WhisperModel
from omegaconf import DictConfig
import tempfile, os, logging
from typing import Optional

logger = logging.getLogger(__name__)


class STTService:
    def __init__(self, cfg: DictConfig):
        self.cfg = cfg
        logger.info(f"Loading Whisper '{cfg.model_size}' on {cfg.device} ...")
        self.model = WhisperModel(cfg.model_size, device=cfg.device, compute_type=cfg.compute_type)
        logger.info("Whisper ready.")

    def transcribe_bytes(self, audio_bytes: bytes, language: Optional[str] = None) -> dict:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name
        try:
            return self._run(tmp_path, language)
        finally:
            os.unlink(tmp_path)

    def transcribe_file(self, file_path: str, language: Optional[str] = None) -> dict:
        return self._run(file_path, language)

    def _run(self, path: str, language: Optional[str] = None) -> dict:
        lang = language or self.cfg.get("language") or None
        segments, info = self.model.transcribe(path, language=lang, beam_size=self.cfg.beam_size)
        transcript = " ".join(seg.text for seg in segments).strip()
        logger.info(f"Transcribed: '{transcript}' (lang={info.language}, p={info.language_probability:.2f})")
        return {
            "transcript": transcript,
            "language": info.language,
            "language_probability": round(info.language_probability, 3),
            "duration_seconds": round(info.duration, 2),
        }
