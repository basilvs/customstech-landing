# Lighthouse-отчёт — CustomsTech landing

**Дата:** 2026-08-11
**URL проверки:** http://127.0.0.1:8000/ (локальная копия `index.html`)
**Инструмент:** Google Lighthouse через DevTools → Lighthouse → Mobile/Desktop

---

## Как запустить

1. Поднять локальный сервер:

```bash
py -m http.server 8000
```

2. Открыть `http://127.0.0.1:8000/` в Chromium/Chrome.
3. DevTools → Lighthouse → выбрать Mode: Navigation, Device: Mobile, Categories: all → Analyze page load.

---

## Что проверяли

| Категория | Ожидаемый минимум | Примечание |
|---|---|---|
| Performance | ≥ 90 | Статичный HTML/CSS/JS, lazy loading изображений, нет тяжёлых скриптов |
| Accessibility | ≥ 95 | ARIA-метки на кнопке меню, контрастные цвета, семантические теги |
| Best Practices | ≥ 90 | HTTPS-линки на внешние источники, отсутствие устаревших API |
| SEO | ≥ 90 | Мета-теги, Open Graph, Schema.org, `<html lang="ru">` |

---

## Наблюдения

- Сайт загружается без ошибок в консоли.
- Изображения в ленте используют `loading="lazy"`.
- Все внешние ссылки (`url` новостей) ведут на HTTPS-источники и открываются с `rel="noopener"`.
- Мобильное меню работает через `aria-label` на кнопке-гамбургере.

---

## Рекомендации по дальнейшему росту метрик

1. **Performance:** прирост даст конвертация PNG в WebP/AVIF и включение CDN для статики.
2. **Accessibility:** добавить `aria-expanded` на кнопку меню и `aria-current` для активного фильтра.
3. **SEO:** добавить `canonical` и XML/JSON Sitemap после размещения на постоянном домене.

---

## Статус

Проверка проведена локально. Проект готов к запуску полного Lighthouse на продакшене.
