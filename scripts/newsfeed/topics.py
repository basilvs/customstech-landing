"""Маппинг направлений (sources.yaml) в темы ленты лендинга.

Темы карточек customstech: Декларирование | Пошлины | Контроль | Экспорт | НПА.
LLM-topic используется только как тайбрейк, когда правило не решило.
"""

TOPICS = ["Декларирование", "Пошлины", "Контроль", "Экспорт", "НПА"]
DEFAULT_TOPIC = "НПА"

# Тарифные слова: наличие в тексте перекидывает в Пошлины (кроме декларирования)
_TARIFF_WORDS = ("пошлин", "ставк", "тариф", "этт", "пошлина")
_DIRECTIONS_WORDS = ("экспорт", "вывоз")
_DECLARATION_WORDS = ("декларир", "деклараци")

DIRECTION_MAP = {
    "декларирование": "Декларирование",
    "тн вэд и етт": "Пошлины",
    "таможенные операции и таможенный контроль": "Контроль",
    "запреты и ограничения": "Контроль",
    "безопасность товаров": "Контроль",
    "маркировка": "Контроль",
}


def resolve_topic(direction: str | None, is_act: bool, llm_topic: str | None,
                  text: str) -> str:
    """Тема карточки: правило из направления, LLM — тайбрейк, дефолт — НПА/Контроль."""
    low = text.lower()

    if direction == "запреты и ограничения" and any(w in low for w in _DIRECTIONS_WORDS):
        return "Экспорт"

    base = DIRECTION_MAP.get(
        (direction or "").strip().lower(),
        DEFAULT_TOPIC if is_act else "Контроль",
    )

    if base != "Декларирование" and any(w in low for w in _TARIFF_WORDS):
        return "Пошлины"
    if base == DEFAULT_TOPIC and any(w in low for w in _DECLARATION_WORDS):
        return "Декларирование"

    # LLM-тайбрейк строго из известного списка
    if llm_topic and llm_topic.strip() in TOPICS:
        return llm_topic.strip()
    return base