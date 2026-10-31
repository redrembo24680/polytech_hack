# support-widget

Вбудовуваний віджет підтримки для власного сайту бізнесу: один `<script>`, що додає плаваючу кнопку чату з AI-підтримкою (iframe на `/b/<tenant>/support?embed=1`).

Підключення (один рядок):

```html
<script src="https://<host>/widget.js" data-tenant="lumen"></script>
```

Атрибути:
- `data-tenant` (обов'язковий) — id бізнесу.
- `data-color` — акцентний колір кнопки (за замовчуванням `#4f46e5`).
- `data-label` — короткий текстовий підпис поруч із кнопкою.

JS API: `window.BooklyWidget.open()` / `.close()`. Демо: `/demo-salon-site.html` («власний сайт» Lumen Beauty).
