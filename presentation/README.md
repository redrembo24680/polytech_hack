# Презентація для журі

- `Bookly-pitch.pptx` — 10 слайдів, структура під критерії з ТЗ (Operational Impact, Innovation, Use of AI, Reasoning & Context, Presentation & Demo). Нотатки доповідача є на кожному слайді.
- `videos/` — відео під слайди: `scene-Q/A/B/C.mp4` (чат клієнта і copilot поруч, синхронно), `product-tour.mp4`.

## Як вставити відео в Google Slides (≈2 хв)
Google Slides не імпортує відео з .pptx, тому на слайдах стоять кадри-обкладинки з написом «▶ вставити …».

1. Завантажте папку `videos/` на Google Drive.
2. Google Slides → File → Import slides (або просто відкрийте `Bookly-pitch.pptx` з Drive і збережіть як Google Slides).
3. На кожному слайді з обкладинкою: Insert → Video → Google Drive → файл з напису на обкладинці. Розтягніть відео точно по обкладинці (вона того ж розміру й пропорцій) і видаліть обкладинку з написом.
4. Format options → Video playback → **Play (automatically)**, щоб відео стартувало при переході на слайд, і за бажанням **Mute audio**.

| Слайд | Відео |
|---|---|
| 4. Демо 1. Олена | `scene-A.mp4` |
| 5. Демо 2. Максим | `scene-B.mp4` |
| 6. Демо 3. Петро | `scene-C.mp4` |
| 8. Справжній продукт | `product-tour.mp4` |

`scene-Q.mp4` (просте питання → відповідає Gemma 4) у слайди не увійшло, лишається як запасне.

Порада: завантажте `videos/` ще й на ноутбук для показу — якщо на сцені не буде інтернету, Google Slides відео з Drive не програє.

## Перезібрати
```bash
cd presentation && npm install && ./render.sh   # build.js → Bookly-pitch.pptx, прев'ю в render/
```
Відео сцен зібрано з `docs/demo-videos/*-customer.mp4` + `*-copilot.mp4` (ffmpeg hstack).
