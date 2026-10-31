# Точки інтеграції

- `support-chat`: сторінка `/b/[tenant]/support?embed=1` та її API.
- `admin-panel`: перегляд розмов у `/admin/<tenant>/support`.
- `proxy.ts`: статичні файли з `public/` проходять без редіректів; для `?embed=1` ставиться заголовок `x-embed`.
- Origin платформи береться з `src` скрипта, тож віджет працює з будь-якого хоста/порту.
