# Фронтенд

- `app/web/public/widget.js` — ES5 IIFE без залежностей і глобалів (крім `window.BooklyWidget`). Усі елементи мають id з префіксом `bookly-` та inline-стилі, `z-index: 2147483000`.
- Кнопка: кругла, SVG-іконка, `aria-label="Підтримка"`. Панель: `role="dialog"`, кнопка закриття, iframe створюється при першому відкритті.
- `app/web/public/demo-salon-site.html` — статичний демо-сайт Lumen Beauty зі скриптом `<script src="/widget.js" data-tenant="lumen">`.
- `?embed=1` ховає шапку застосунку (`proxy.ts` ставить `x-embed`, `SiteChrome`).
