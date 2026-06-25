"""Voice agent: Google Speech-to-Text -> RAG engine -> Text-to-Speech.

The voice agent is the RAG engine with audio on both ends:

1. Speech-to-Text transcribes the visitor's audio to a question.
2. The existing :class:`RagEngine` answers it (scoped to user_id + agent_id).
3. Text-to-Speech turns the answer back into audio (MP3).

Both Speech APIs are Google Cloud products and authenticate the same way as
Vertex AI (Application Default Credentials), so no extra setup beyond what the
RAG engine already needs.
"""

from dataclasses import dataclass

from dotenv import load_dotenv
from google.cloud import speech, texttospeech

from app.core.config import settings
from app.core.language import code_from_locale, language_name
from rag_bot.rag_engine import get_engine

load_dotenv()

# Audio encodings we accept for incoming speech. Browser MediaRecorder
# typically produces WEBM_OPUS.
_STT_ENCODINGS = {
    "WEBM_OPUS": speech.RecognitionConfig.AudioEncoding.WEBM_OPUS,
    "OGG_OPUS": speech.RecognitionConfig.AudioEncoding.OGG_OPUS,
    "LINEAR16": speech.RecognitionConfig.AudioEncoding.LINEAR16,
    "MP3": speech.RecognitionConfig.AudioEncoding.MP3,
    "FLAC": speech.RecognitionConfig.AudioEncoding.FLAC,
}


@dataclass
class VoiceResult:
    transcript: str  # what the visitor said
    answer: str  # the agent's text answer
    audio: bytes  # the answer spoken, as MP3
    language: str | None = None  # BCP-47 locale used for the turn


class VoiceEngine:
    """Wraps Google STT + TTS around the shared RAG engine."""

    def __init__(
        self,
        *,
        language_code: str | None = None,
        voice_name: str | None = None,
        speaking_rate: float = 1.0,
    ) -> None:
        self.language_code = language_code or settings.voice_language_code
        self.voice_name = voice_name if voice_name is not None else settings.voice_name
        self.speaking_rate = speaking_rate
        self.stt_client = speech.SpeechClient()
        self.tts_client = texttospeech.TextToSpeechClient()

    def transcribe(
        self,
        audio_bytes: bytes,
        *,
        encoding: str = "WEBM_OPUS",
        sample_rate_hertz: int | None = None,
        language_code: str | None = None,
        alternative_language_codes: list[str] | None = None,
    ) -> tuple[str, str | None]:
        """Speech-to-Text: audio -> ``(transcript, detected_locale)``.

        Pass ``alternative_language_codes`` to let Google auto-detect the
        spoken language; the detected BCP-47 locale is returned alongside the
        transcript.
        """
        stt_encoding = _STT_ENCODINGS.get(encoding.upper())
        if stt_encoding is None:
            supported = ", ".join(sorted(_STT_ENCODINGS))
            raise ValueError(
                f"Unsupported audio encoding {encoding!r}. Supported: {supported}"
            )

        config_kwargs = {
            "encoding": stt_encoding,
            "language_code": language_code or self.language_code,
            "enable_automatic_punctuation": True,
        }
        # For container formats (WEBM/OGG) the sample rate is read from the
        # header, so only pass it when the caller provides one.
        if sample_rate_hertz:
            config_kwargs["sample_rate_hertz"] = sample_rate_hertz
        if alternative_language_codes:
            config_kwargs["alternative_language_codes"] = alternative_language_codes

        config = speech.RecognitionConfig(**config_kwargs)
        audio = speech.RecognitionAudio(content=audio_bytes)
        response = self.stt_client.recognize(config=config, audio=audio)

        transcript = " ".join(
            result.alternatives[0].transcript
            for result in response.results
            if result.alternatives
        ).strip()

        detected_locale = None
        for result in response.results:
            if getattr(result, "language_code", ""):
                detected_locale = result.language_code
                break

        return transcript, detected_locale

    def synthesize(self, text: str, *, language_code: str | None = None) -> bytes:
        """Text-to-Speech: text -> MP3 bytes."""
        synthesis_input = texttospeech.SynthesisInput(text=text)

        voice_kwargs = {"language_code": language_code or self.language_code}
        if self.voice_name:
            voice_kwargs["name"] = self.voice_name
        else:
            voice_kwargs["ssml_gender"] = texttospeech.SsmlVoiceGender.NEUTRAL
        voice = texttospeech.VoiceSelectionParams(**voice_kwargs)

        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=self.speaking_rate,
        )
        response = self.tts_client.synthesize_speech(
            input=synthesis_input, voice=voice, audio_config=audio_config
        )
        return response.audio_content

    def respond(
        self,
        audio_bytes: bytes,
        *,
        user_id: str,
        agent_id: str,
        chat_history=None,
        encoding: str = "WEBM_OPUS",
        sample_rate_hertz: int | None = None,
        language_code: str | None = None,
        alternative_language_codes: list[str] | None = None,
    ) -> VoiceResult:
        """Full turn: transcribe -> RAG answer -> synthesize, all in one language.

        If ``language_code`` is known (the session already has a language) it is
        used for STT and TTS. Otherwise ``alternative_language_codes`` enables
        auto-detection, and the detected locale drives the answer + speech.
        """
        transcript, detected_locale = self.transcribe(
            audio_bytes,
            encoding=encoding,
            sample_rate_hertz=sample_rate_hertz,
            language_code=language_code,
            alternative_language_codes=alternative_language_codes,
        )
        effective_locale = language_code or detected_locale or self.language_code
        if not transcript:
            return VoiceResult(
                transcript="", answer="", audio=b"", language=effective_locale
            )

        spoken_language = language_name(code_from_locale(effective_locale))
        answer = get_engine().chat(
            transcript,
            user_id=user_id,
            agent_id=agent_id,
            chat_history=chat_history,
            language=spoken_language,
        )
        audio = self.synthesize(answer, language_code=effective_locale)
        return VoiceResult(
            transcript=transcript,
            answer=answer,
            audio=audio,
            language=effective_locale,
        )


_voice_engine: VoiceEngine | None = None


def get_voice_engine() -> VoiceEngine:
    global _voice_engine
    if _voice_engine is None:
        _voice_engine = VoiceEngine()
    return _voice_engine
