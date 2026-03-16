import logging
from pathlib import Path

from fluent.runtime import FluentBundle, FluentResource

logger = logging.getLogger(__name__)

LOCALES_DIR = Path(__file__).parent.parent / "locales"
SUPPORTED_LOCALES = ("en", "ru", "ko")
DEFAULT_LOCALE = "en"

_bundles: dict[str, FluentBundle] = {}


def init_localization() -> None:
    for locale in SUPPORTED_LOCALES:
        locale_dir = LOCALES_DIR / locale
        bundle = FluentBundle([locale])
        for ftl_file in locale_dir.glob("*.ftl"):
            resource = FluentResource(ftl_file.read_text(encoding="utf-8"))
            bundle.add_resource(resource)
        _bundles[locale] = bundle
    logger.info("Loaded locales: %s", list(_bundles.keys()))


def _resolve_locale(language_code: str | None) -> str:
    if not language_code:
        return DEFAULT_LOCALE
    code = language_code.lower().split("-")[0]
    if code in SUPPORTED_LOCALES:
        return code
    return DEFAULT_LOCALE


def t(key: str, language_code: str | None = None, **kwargs) -> str:
    locale = _resolve_locale(language_code)
    bundle = _bundles.get(locale) or _bundles[DEFAULT_LOCALE]
    msg = bundle.get_message(key)
    if msg and msg.value:
        val, _ = bundle.format_pattern(msg.value, kwargs)
        return val
    # Fallback to English
    if locale != DEFAULT_LOCALE:
        fb = _bundles[DEFAULT_LOCALE]
        msg = fb.get_message(key)
        if msg and msg.value:
            val, _ = fb.format_pattern(msg.value, kwargs)
            return val
    return key


def get_disclaimer(language_code: str | None) -> tuple[str, bool]:
    """Return (disclaimer_text, from_locale).

    If the user's language is in supported locales, returns the pre-translated
    disclaimer. Otherwise returns the English version and ``from_locale=False``
    so the caller knows it should be translated via AI.
    """
    locale = _resolve_locale(language_code)
    text = t("translation-disclaimer", locale)
    from_locale = locale in SUPPORTED_LOCALES and (language_code or "").lower().split("-")[0] in SUPPORTED_LOCALES
    return text, from_locale
