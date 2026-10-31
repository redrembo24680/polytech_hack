# Відомі підводні камені

- Сайт-хост з суворим CSP має дозволити `frame-src` для origin платформи.
- Платформа не повинна відправляти `X-Frame-Options: DENY` для `/b/*/support`.
- `localStorage` в iframe партиціонується браузерами (third-party storage): на іншому домені розмова може не відновитись після перезавантаження.
- `document.currentScript` недоступний для скриптів, доданих як module/async-динамічно; є запасний пошук `script[data-tenant][src*="widget.js"]`.
- Невідомий `data-tenant` покаже сторінку помилки/404 усередині iframe.
