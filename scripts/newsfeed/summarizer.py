"""Краткий русский пересказ новости через LLM (ProxyAPI) + fallback без LLM.

OpenAI-совместимый клиент; модель по умолчанию gpt-4o-mini.
Любая ошибка -> fallback: очищенный RSS-дескрипшн, summarized=false
(прогон не падает; до-пересказ в следующий раз).
"""

import json
import os
import re

SYSTEM_PROMPT = (
    "Ты — редактор новостей по таможенному законодательству РФ и ЕАЭС "
    "для ленты на сайте customstech.ru. Русский язык, профессиональный тон, "
    "без хайпа, эмодзи и оценок. Только факты из источника; "
    "если данных не хватает — опусти это, не выдумывай."
)

USER_PROMPT = """Новость. Источник: {source_name}. Дата: {date}.
Заголовок: {title}
Описание: {description}

Перескажи для ленты сайта: ровно 2–3 предложения, суммарно 250–450 символов.
1-е предложение — суть (что принято/что изменено и на кого влияет).
2–3-е — конкретика: реквизиты акта, даты вступления в силу, ставки/сроки/списки.
Не придумывай реквизиты, номера, даты и цифры, которых нет в описании.
Верни только JSON: {{"summary": "...", "topic": "Декларирование|Пошлины|Контроль|Экспорт|НПА"}}"""


def _clean_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    # RSS-хвост вида «Сообщение ... появились сначала на Вэдофон .»
    text = re.sub(r"Сообщение\s+[^.]*появились\s+сначала\s+на\s+[^.]*\.?\s*$", "", text)
    return re.sub(r"\s+", " ", text).strip()


def fallback_summary(description: str, max_chars: int = 450) -> str:
    """Очищенный дескрипшн, обрезанный по границе предложения до 450 символов."""
    text = _clean_html(description)
    while len(text) > max_chars:
        parts = text.rstrip(".!? ")
        last = parts.rfind(". ")
        if last <= 0:
            break
        text = parts[: last + 1]
    return text


def summarize(client, model: str, item, timeout: int) -> dict:
    """Вернуть {'summary', 'topic', 'summarized'} для новости."""
    desc = item.summary or item.title
    if client is None:
        return {"summary": fallback_summary(desc), "topic": None, "summarized": False}

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": USER_PROMPT.format(
                    source_name=item.source_name,
                    date=item.published_at.strftime("%Y-%m-%d") if item.published_at else "неизвестна",
                    title=item.title,
                    description=_clean_html(desc)[:1500],
                )},
            ],
            temperature=0.3,
            max_tokens=400,
            timeout=timeout,
        )
        data = json.loads(response.choices[0].message.content)
        summary = _clean_html(data.get("summary") or "")
        if not summary:
            raise ValueError("empty summary")
        return {"summary": summary, "topic": data.get("topic"), "summarized": True}
    except Exception as exc:
        print(f"[summarizer] fallback ({item.source_name}): {exc}")
        return {"summary": fallback_summary(desc), "topic": None, "summarized": False}


def make_client():
    """OpenAI-совместимый клиент ProxyAPI; None без ключа (--no-llm)."""
    api_key = os.getenv("PROXYAPI_API_KEY", "")
    if not api_key:
        return None
    from openai import OpenAI
    return OpenAI(
        api_key=api_key,
        base_url=os.getenv("PROXYAPI_BASE_URL", "https://api.proxyapi.ru/openai/v1"),
        timeout=float(os.getenv("PROXYAPI_TIMEOUT", "60")),
    )


def default_model() -> str:
    return os.getenv("PROXYAPI_MODEL", "gpt-4o-mini")