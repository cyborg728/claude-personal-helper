import logging

from google import genai

logger = logging.getLogger(__name__)

_client: genai.Client | None = None
_model: str = ""


def init_gemini(api_key: str, model: str) -> None:
    global _client, _model
    _client = genai.Client(api_key=api_key)
    _model = model
    logger.info("Gemini client initialized with model: %s", model)


async def translate_text(text: str, target_language: str) -> str:
    assert _client is not None, "Gemini not initialized"
    prompt = (
        f"Translate the following text to {target_language}. "
        "Return ONLY the translated text without any explanation, "
        "preamble, or formatting.\n\n"
        f"{text}"
    )
    response = await _client.aio.models.generate_content(
        model=_model,
        contents=prompt,
    )
    return response.text.strip()


async def transcribe_and_translate(audio_bytes: bytes, target_language: str) -> str:
    """Transcribe voice audio and translate to target language."""
    assert _client is not None, "Gemini not initialized"

    upload = await _client.aio.files.upload(
        file=audio_bytes,
        config={"mime_type": "audio/ogg"},
    )

    prompt = (
        f"First transcribe this audio message, then translate the transcription to {target_language}. "
        "Return the result in the following format:\n"
        "TRANSCRIPTION: <original text>\n"
        "TRANSLATION: <translated text>"
    )
    response = await _client.aio.models.generate_content(
        model=_model,
        contents=[prompt, upload],
    )
    return response.text.strip()


async def translate_disclaimer(disclaimer: str, target_language: str) -> str:
    """Translate the AI disclaimer to an unsupported locale language."""
    assert _client is not None, "Gemini not initialized"
    prompt = (
        f"Translate the following disclaimer to {target_language}. "
        "Return ONLY the translated text.\n\n"
        f"{disclaimer}"
    )
    response = await _client.aio.models.generate_content(
        model=_model,
        contents=prompt,
    )
    return response.text.strip()
