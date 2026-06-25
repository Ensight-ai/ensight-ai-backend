"""Language detection + mapping helpers for multilingual conversations.

A conversation's language is detected once (from the first turn) and stored on
the conversation row, so the whole session stays in that language.

* ``detect_language`` -> ISO 639-1 code (e.g. "es") from text.
* ``language_name`` -> human name ("Spanish") for instructing the LLM.
* ``to_locale`` -> BCP-47 locale ("es-ES") for Google STT/TTS.
"""

# ISO 639-1 code -> human-readable language name.
LANGUAGE_NAMES = {
    "ar": "Arabic",
    "bn": "Bengali",
    "cs": "Czech",
    "da": "Danish",
    "de": "German",
    "el": "Greek",
    "en": "English",
    "es": "Spanish",
    "fi": "Finnish",
    "fr": "French",
    "he": "Hebrew",
    "hi": "Hindi",
    "hu": "Hungarian",
    "id": "Indonesian",
    "it": "Italian",
    "ja": "Japanese",
    "ko": "Korean",
    "nl": "Dutch",
    "no": "Norwegian",
    "pl": "Polish",
    "pt": "Portuguese",
    "ro": "Romanian",
    "ru": "Russian",
    "sv": "Swedish",
    "th": "Thai",
    "tr": "Turkish",
    "uk": "Ukrainian",
    "vi": "Vietnamese",
    "zh-cn": "Chinese",
    "zh-tw": "Chinese (Traditional)",
    "zh": "Chinese",
}

# ISO code -> default BCP-47 locale for Google Speech APIs.
_DEFAULT_LOCALES = {
    "ar": "ar-XA",
    "cs": "cs-CZ",
    "da": "da-DK",
    "de": "de-DE",
    "el": "el-GR",
    "en": "en-US",
    "es": "es-ES",
    "fi": "fi-FI",
    "fr": "fr-FR",
    "he": "he-IL",
    "hi": "hi-IN",
    "hu": "hu-HU",
    "id": "id-ID",
    "it": "it-IT",
    "ja": "ja-JP",
    "ko": "ko-KR",
    "nl": "nl-NL",
    "no": "nb-NO",
    "pl": "pl-PL",
    "pt": "pt-BR",
    "ro": "ro-RO",
    "ru": "ru-RU",
    "sv": "sv-SE",
    "th": "th-TH",
    "tr": "tr-TR",
    "uk": "uk-UA",
    "vi": "vi-VN",
    "zh-cn": "cmn-CN",
    "zh-tw": "cmn-TW",
    "zh": "cmn-CN",
}

# Candidate locales for Google STT auto-detection on voice-first sessions.
# (Google STT v1 allows the primary language plus up to 3 alternatives.)
STT_CANDIDATE_LOCALES = ["es-ES", "fr-FR", "de-DE"]


# Detection on very short text (e.g. "Hello") is unreliable, so we don't lock
# a conversation's language until there's enough text, detected confidently.
_MIN_DETECT_CHARS = 15
_MIN_DETECT_CONFIDENCE = 0.90


def detect_language(text: str | None) -> str | None:
    """Best-effort ISO 639-1 code for ``text``, or None if not confident.

    Returns None for short/ambiguous input so the caller doesn't lock the
    conversation to a wrong guess (the agent then just mirrors the user's
    language for that turn). ``langdetect`` is imported lazily.
    """
    if not text:
        return None
    cleaned = text.strip()
    if len(cleaned) < _MIN_DETECT_CHARS:
        return None
    try:
        from langdetect import DetectorFactory, detect_langs

        DetectorFactory.seed = 0  # make detection deterministic
        candidates = detect_langs(cleaned)
        if candidates and candidates[0].prob >= _MIN_DETECT_CONFIDENCE:
            return candidates[0].lang
        return None
    except Exception:
        return None


def language_name(code: str | None) -> str | None:
    if not code:
        return None
    return LANGUAGE_NAMES.get(
        code.lower(), LANGUAGE_NAMES.get(code.split("-")[0].lower(), code)
    )


def to_locale(code: str | None) -> str | None:
    if not code:
        return None
    return _DEFAULT_LOCALES.get(
        code.lower(), _DEFAULT_LOCALES.get(code.split("-")[0].lower())
    )


def code_from_locale(locale: str | None) -> str | None:
    """BCP-47 locale ('es-ES') -> ISO code ('es')."""
    if not locale:
        return None
    return locale.split("-")[0].lower()
