// Builds deck.pptx for the PolyTech Code Fest pitch.
// Videos are not embedded: Google Slides drops embedded media, so each video slide
// carries a poster frame where the matching file from videos/ is inserted from Drive.
const path = require("path");
const pptxgen = require("pptxgenjs");
const React = require("react");
const ReactDOMServer = require("react-dom/server");
const sharp = require("sharp");
const fa = require("react-icons/fa6");
const { applyTheme } = require(
  "/Users/admin/.claude/skills/synced/833a518a-8268-4d79-868d-d1533ff88917_b3fb4a3c-98ec-43e1-af9e-26d47c5f82a9/pptx/scripts/apply_theme.js",
);

const THEME = {
  name: "Bookly Pitch",
  headFontFace: "Arial",
  bodyFontFace: "Arial",
  colors: {
    dk1: "16163A", // ink
    lt1: "FFFFFF",
    dk2: "4B4E6D", // muted text
    lt2: "F1F2FB", // tint background
    accent1: "4F46E5", // product indigo
    accent2: "F2665C", // coral highlight
    accent3: "12B886", // success green
    accent4: "F59F00", // approval amber
    accent5: "868AA8",
    accent6: "C7C9F5",
    hlink: "4F46E5",
    folHlink: "6D28D9",
  },
};
const HEX = THEME.colors;

const W = 13.333;
const H = 7.5;
const M = 0.6; // outer margin

async function icon(Comp, color, size = 256) {
  const svg = ReactDOMServer.renderToStaticMarkup(React.createElement(Comp, { color: "#" + color, size }));
  const buf = await sharp(Buffer.from(svg)).png().toBuffer();
  return "image/png;base64," + buf.toString("base64");
}

async function main() {
  const pres = new pptxgen();
  pres.layout = "LAYOUT_WIDE";
  pres.title = "Bookly — AI-підтримка, яка діє";
  pres.author = "redrembo24680";
  pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
  const C = pres.SchemeColor;

  // --- layouts -------------------------------------------------------------
  pres.defineSlideMaster({
    title: "Dark Title",
    background: { color: HEX.dk1 },
    objects: [
      { placeholder: { options: { name: "title", type: "title", x: M, y: 2.2, w: 9.5, h: 1.6, fontSize: 48, bold: true, color: C.background1, valign: "bottom", align: "left", margin: 0 }, text: "" } },
      { placeholder: { options: { name: "body", type: "body", x: M, y: 4.1, w: 9.5, h: 1.2, fontSize: 22, color: C.accent6, valign: "top", margin: 0 }, text: "" } },
    ],
  });
  pres.defineSlideMaster({
    title: "Content",
    background: { color: HEX.lt1 },
    objects: [
      { placeholder: { options: { name: "title", type: "title", x: M, y: 0.4, w: W - 2 * M, h: 0.8, fontSize: 32, bold: true, color: C.text1, valign: "middle", align: "left", margin: 0 }, text: "" } },
    ],
    slideNumber: { x: W - M - 0.5, y: H - 0.45, w: 0.5, h: 0.3, fontSize: 10, color: C.accent5, align: "right" },
  });
  pres.defineSlideMaster({
    title: "Demo",
    background: { color: HEX.lt2 },
    objects: [
      { placeholder: { options: { name: "title", type: "title", x: M, y: 0.35, w: W - 2 * M, h: 0.7, fontSize: 30, bold: true, color: C.text1, valign: "middle", align: "left", margin: 0 }, text: "" } },
      { placeholder: { options: { name: "body", type: "body", x: M, y: 1.05, w: W - 2 * M, h: 0.45, fontSize: 16, color: C.text2, valign: "top", margin: 0 }, text: "" } },
    ],
    slideNumber: { x: W - M - 0.5, y: H - 0.45, w: 0.5, h: 0.3, fontSize: 10, color: C.accent5, align: "right" },
  });

  const shadow = () => ({ type: "outer", color: "16163A", opacity: 0.12, blur: 8, offset: 2, angle: 90 });

  // Rounded white card with optional icon, heading and text.
  function card(slide, { x, y, w, h, ico, head, text, headColor, fill, name, headH = 0.5, headSize = 18, textSize = 14 }) {
    slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
      x, y, w, h, rectRadius: 0.12, fill: { color: fill || C.background1 }, line: { color: C.background2, width: 0.75 }, shadow: shadow(), objectName: name + " card",
    });
    let ty = y + 0.3;
    if (ico) {
      slide.addShape(pres.shapes.OVAL, { x: x + 0.3, y: ty, w: 0.62, h: 0.62, fill: { color: C.background2 }, line: { type: "none" }, objectName: name + " icon bg" });
      slide.addImage({ data: ico, x: x + 0.44, y: ty + 0.14, w: 0.34, h: 0.34, objectName: name + " icon" });
      ty += 0.82;
    }
    if (head) {
      slide.addText(head, { x: x + 0.3, y: ty, w: w - 0.6, h: headH, fontSize: headSize, bold: true, color: headColor || C.text1, margin: 0, valign: "top", isTextBox: true, objectName: name + " head" });
      ty += headH + 0.1;
    }
    if (text) {
      slide.addText(text, { x: x + 0.3, y: ty, w: w - 0.6, h: y + h - ty - 0.2, fontSize: textSize, color: C.text2, margin: 0, valign: "top", isTextBox: true, objectName: name + " text" });
    }
  }

  // Poster frame where the real video goes after import into Google Slides.
  function videoSlot(slide, { x, y, w, h, poster, file, labels }) {
    slide.addImage({ path: path.join(__dirname, poster), x, y, w, h, objectName: `video ${file}`, altText: `Кадр з відео ${file}` });
    slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
      x: x + w / 2 - 1.6, y: y + h / 2 - 0.3, w: 3.2, h: 0.6, rectRadius: 0.3, fill: { color: C.text1, transparency: 15 }, line: { type: "none" }, objectName: "insert video badge",
    });
    slide.addText(`▶  вставити ${file}`, {
      x: x + w / 2 - 1.6, y: y + h / 2 - 0.3, w: 3.2, h: 0.6, fontSize: 14, bold: true, color: C.background1, align: "center", valign: "middle", margin: 0, isTextBox: true, objectName: "insert video label",
    });
    if (labels) {
      labels.forEach((t, i) => {
        slide.addText(t, { x: x + (w / labels.length) * i, y: y - 0.32, w: w / labels.length, h: 0.28, fontSize: 12, bold: true, color: C.accent5, align: "center", margin: 0, isTextBox: true, objectName: `video label ${i}` });
      });
    }
  }

  // Three "what you see" steps under a demo video.
  function steps(slide, items, y) {
    const gap = 0.3;
    const w = (W - 2 * M - gap * (items.length - 1)) / items.length;
    items.forEach(([head, text, color], i) => {
      const x = M + i * (w + gap);
      slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h: 1.1, rectRadius: 0.1, fill: { color: C.background1 }, line: { type: "none" }, shadow: shadow(), objectName: `step ${i + 1}` });
      slide.addShape(pres.shapes.OVAL, { x: x + 0.22, y: y + 0.22, w: 0.4, h: 0.4, fill: { color: color || C.accent1 }, line: { type: "none" }, objectName: `step ${i + 1} dot` });
      slide.addText(String(i + 1), { x: x + 0.22, y: y + 0.22, w: 0.4, h: 0.4, fontSize: 14, bold: true, color: C.background1, align: "center", valign: "middle", margin: 0, isTextBox: true, objectName: `step ${i + 1} number` });
      slide.addText(head, { x: x + 0.75, y: y + 0.18, w: w - 0.95, h: 0.45, fontSize: 15, bold: true, color: C.text1, margin: 0, valign: "middle", isTextBox: true, objectName: `step ${i + 1} head` });
      slide.addText(text, { x: x + 0.75, y: y + 0.62, w: w - 0.95, h: 0.55, fontSize: 12, color: C.text2, margin: 0, valign: "top", isTextBox: true, objectName: `step ${i + 1} text` });
    });
  }

  const I = {
    clock: await icon(fa.FaRegClock, HEX.accent1),
    inbox: await icon(fa.FaInbox, HEX.accent1),
    robot: await icon(fa.FaRobot, HEX.accent1),
    store: await icon(fa.FaStore, HEX.accent1),
    bolt: await icon(fa.FaBolt, HEX.accent1),
    shield: await icon(fa.FaShieldHalved, HEX.accent1),
    chart: await icon(fa.FaChartLine, HEX.accent1),
    brain: await icon(fa.FaBrain, HEX.accent1),
    plug: await icon(fa.FaPlug, HEX.accent1),
    comments: await icon(fa.FaComments, HEX.accent1),
    phone: await icon(fa.FaPhone, HEX.accent1),
    code: await icon(fa.FaCode, HEX.accent1),
  };

  // 1. Title ----------------------------------------------------------------
  pres.addSection({ title: "Вступ" });
  let s = pres.addSlide({ masterName: "Dark Title", sectionTitle: "Вступ" });
  s.addText("PolyTech Code Fest · AI Customer Support Automation", { x: M, y: 0.6, w: 9, h: 0.4, fontSize: 14, color: C.accent5, margin: 0, isTextBox: true, objectName: "event" });
  s.addText("AI-підтримка, яка не пояснює, а вирішує", { placeholder: "title" });
  s.addText("Bookly — платформа для бізнесів за записом і AI-агент, що сам переносить, скасовує та повертає гроші за правилами кожного бізнесу", { placeholder: "body" });
  s.addShape(pres.shapes.OVAL, { x: 10.6, y: 2.15, w: 2.2, h: 2.2, fill: { color: C.accent1 }, line: { type: "none" }, objectName: "hero circle" });
  s.addImage({ data: await icon(fa.FaRobot, "FFFFFF"), x: 11.15, y: 2.7, w: 1.1, h: 1.1, objectName: "hero icon" });
  s.addNotes("Ми зробили не чат-бот, а операційного асистента для підтримки. Клієнт пише як людині — агент сам розбирається, що сталося, і виконує дію в системі бізнесу, а ризикові рішення віддає адміністратору.");

  // 2. Problem ---------------------------------------------------------------
  pres.addSection({ title: "Проблема і рішення" });
  s = pres.addSlide({ masterName: "Content", sectionTitle: "Проблема і рішення" });
  s.addText("Підтримка салонів і клінік тоне в рутині", { placeholder: "title" });
  const pw = (W - 2 * M - 0.6) / 3;
  card(s, { x: M, y: 1.6, w: pw, h: 3.55, ico: I.inbox, head: "«Перенесіть», «поверніть»", headH: 0.8, text: "Адміністратор цілий день відповідає в директі й телефоні на однакові запити, які потребують лише кількох дій у системі.", name: "pain 1" });
  card(s, { x: M + pw + 0.3, y: 1.6, w: pw, h: 3.55, ico: I.clock, head: "Неявки й пізні скасування", headH: 0.8, text: "15–23% записаних клієнтів у сервісних бізнесах не приходять. Кожне правило (передоплата, штраф, виняток) перевіряють вручну.", name: "pain 2" });
  card(s, { x: M + 2 * (pw + 0.3), y: 1.6, w: pw, h: 3.55, ico: I.robot, head: "Боти лише пояснюють", headH: 0.8, text: "Звичайний чат-бот розповість про правила скасування, але не перенесе запис і не поверне передоплату.", name: "pain 3" });
  s.addText([
    { text: "Питання не в тому, як швидше відповісти. ", options: { bold: true, color: C.text1 } },
    { text: "Питання в тому, як зробити так, щоб проблема була вирішена.", options: { color: C.accent1, bold: true } },
  ], { x: M, y: 5.5, w: W - 2 * M, h: 0.6, fontSize: 18, margin: 0, isTextBox: true, objectName: "key question" });
  s.addText("Джерело частки неявок: SchedulingKit, Appointment No-Show Statistics 2026 (оцінки вендора).", { x: M, y: 6.75, w: 10, h: 0.3, fontSize: 10, color: C.accent5, margin: 0, isTextBox: true, objectName: "source" });
  s.addNotes("Біль реальний: у сервісних бізнесах до чверті записів не доходять, а адміністратор вручну перевіряє правила й переносить записи. Боти тут не допомагають — вони не мають доступу до системи.");

  // 3. Solution --------------------------------------------------------------
  s = pres.addSlide({ masterName: "Content", sectionTitle: "Проблема і рішення" });
  s.addText("Наше рішення: агент, який має руки в системі бізнесу", { placeholder: "title" });
  const sw = (W - 2 * M - 0.3) / 2;
  card(s, { x: M, y: 1.6, w: sw, h: 4.2, ico: I.store, head: "Bookly — платформа для бізнесів за записом", headH: 0.8, textSize: 15, text: [
    { text: "Сторінка бізнесу, онлайн-запис із передоплатою", options: { bullet: true, breakLine: true } },
    { text: "Адмінка: бронювання, клієнти, майстри, послуги", options: { bullet: true, breakLine: true } },
    { text: "Правила кожного бізнесу: вікно скасування, штраф, передоплата", options: { bullet: true, breakLine: true } },
    { text: "Чат підтримки на сайті та віджет для будь-якого сайту", options: { bullet: true, breakLine: true } },
    { text: "Один салон чи клініка підключається без коду", options: { bullet: true } },
  ], name: "platform" });
  card(s, { x: M + sw + 0.3, y: 1.6, w: sw, h: 4.2, ico: I.robot, head: "AI-агент підтримки", headH: 0.8, textSize: 15, text: [
    { text: "Розуміє намір, емоцію і терміновість звернення", options: { bullet: true, breakLine: true } },
    { text: "Діє через інструменти: переносить, скасовує, повертає, знімає штраф", options: { bullet: true, breakLine: true } },
    { text: "Permission engine: сам / з погодженням / заборонено — налаштовує власник", options: { bullet: true, breakLine: true } },
    { text: "Copilot: адміністратор бачить хід думок, дії й погоджує ризикові", options: { bullet: true, breakLine: true } },
    { text: "Канали: чат на сайті, віджет, телефон (Vapi)", options: { bullet: true } },
  ], name: "agent" });
  s.addText("Дві частини з'єднані HTTP API та MCP: агент бачить і змінює ті самі дані, що й адміністратор", { x: M, y: 6.1, w: W - 2 * M, h: 0.5, fontSize: 16, bold: true, color: C.accent1, margin: 0, isTextBox: true, objectName: "link line" });
  s.addNotes("Дві частини, з'єднані API та MCP. Платформа — реальний продукт з даними і правилами. Агент працює поверх неї: читає правила саме цього бізнесу і виконує дії через інструменти.");

  // 4. How it works ----------------------------------------------------------
  pres.addSection({ title: "Як це працює" });
  s = pres.addSlide({ masterName: "Content", sectionTitle: "Як це працює" });
  s.addText("Як агент приймає рішення", { placeholder: "title" });
  const flow = [
    [I.comments, "Клієнт пише", "Чат на сайті, віджет або дзвінок"],
    [I.brain, "Оркестратор", "Claude Sonnet: намір, емоція, терміновість, маршрут"],
    [I.bolt, "Агент-виконавець", "Читає профіль і правила, викликає інструменти"],
    [I.shield, "Permission engine", "Сам · з погодженням · заборонено"],
    [I.plug, "Платформа", "API / MCP: зміни в реальних даних"],
  ];
  const fw = 2.15;
  const fgap = (W - 2 * M - fw * flow.length) / (flow.length - 1);
  flow.forEach(([ic, head, text], i) => {
    const x = M + i * (fw + fgap);
    card(s, { x, y: 1.7, w: fw, h: 2.9, ico: ic, head, text, headH: 0.65, headSize: 14, textSize: 13, name: `flow ${i + 1}` });
    if (i < flow.length - 1) {
      s.addText("→", { x: x + fw, y: 2.9, w: fgap, h: 0.5, fontSize: 20, bold: true, color: C.accent1, align: "center", valign: "middle", margin: 0, isTextBox: true, objectName: `flow arrow ${i + 1}` });
    }
  });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: M, y: 5.0, w: W - 2 * M, h: 1.45, rectRadius: 0.12, fill: { color: C.background2 }, line: { type: "none" }, objectName: "routing box" });
  s.addText([
    { text: "Просте питання ", options: { bold: true, color: C.text1 } },
    { text: "(ціна, адреса) → відповідає Gemma 4, без дій.   ", options: { color: C.text2 } },
    { text: "Дія із записом ", options: { bold: true, color: C.text1 } },
    { text: "→ завжди через агента й permission engine.   ", options: { color: C.text2 } },
    { text: "Гнів чи терміновість ", options: { bold: true, color: C.text1 } },
    { text: "→ ескалація людині.", options: { color: C.text2 } },
  ], { x: M + 0.3, y: 5.0, w: W - 2 * M - 0.6, h: 1.45, fontSize: 16, valign: "middle", margin: 0, isTextBox: true, objectName: "routing text" });
  s.addNotes("Кожне повідомлення спершу проходить тріаж: що людина хоче, у якому вона стані, чи це терміново. Прості питання дешево закриває Gemma 4. Усе, що змінює дані, йде через агента, а кожна дія перевіряється правилами бізнесу — модель не може обійти permission engine.");

  // 5–8. Demo scenes ---------------------------------------------------------
  pres.addSection({ title: "Демо" });
  const demos = [
    {
      file: "scene-Q.mp4", poster: "posters/scene-Q.png",
      title: "Демо 1. Просте питання — миттєва відповідь",
      sub: "Клієнт питає ціну й адресу. Оркестратор бачить просте питання, відповідає Gemma 4 без жодних дій.",
      steps: [["Тріаж", "Намір «питання», терміновість низька", null], ["Gemma 4", "Відповідь з фактів бізнесу: послуги, ціни, контакти", null], ["Нуль ризику", "Дані не змінюються, адміністратор не потрібен", "12B886"]],
      notes: "Найчастіші звернення — довідкові. Їх закриває легка модель за секунди, не витрачаючи дорогий цикл агента.",
    },
    {
      file: "scene-A.mp4", poster: "posters/scene-A.png",
      title: "Демо 2. Олена: агент сам рятує передоплату",
      sub: "«Дитина захворіла, не встигаю завтра на 10». Пізнє перенесення — за правилами передоплата згорає.",
      steps: [["Контекст", "12 візитів, 0 неявок, винятків ще не було", null], ["Рішення сам", "Правило салону дозволяє виняток автоматично", "12B886"], ["Дія", "Знаходить слоти, переносить, 500 грн збережено", null]],
      notes: "Агент не просто співчуває — він бачить, що це лояльна клієнтка, а політика салону дозволяє один виняток на пів року без погодження. Тому сам переносить і зберігає передоплату. В copilot видно кожен виклик інструмента.",
    },
    {
      file: "scene-B.mp4", poster: "posters/scene-B.png",
      title: "Демо 3. Максим: ризикове рішення — людині",
      sub: "Той самий запит, але в клієнта 2 неявки. Агент не вирішує сам, а просить адміністратора.",
      steps: [["Контекст", "2 неявки — автоматичний виняток не дозволено", "F59F00"], ["Погодження", "Адміністратор схвалює в copilot одним кліком", "F59F00"], ["Дія", "Агент сам повертається до клієнта й переносить", null]],
      notes: "Однакове звернення — інше рішення, бо інший контекст. Агент чесно пояснює клієнту, що чекає на рішення, а адміністратор отримує готовий розбір і кнопку «схвалити».",
    },
    {
      file: "scene-C.mp4", poster: "posters/scene-C.png",
      title: "Демо 4. Петро в клініці: суворі правила, дві дії",
      sub: "«Хочу скасувати запис і повернути гроші». У клініці правила суворіші: усе через погодження.",
      steps: [["Правила клініки", "Пізніше 48 год — передоплата 800 грн згорає", null], ["Два погодження", "Спершу повернення, потім скасування", "F59F00"], ["Результат", "Запис скасовано, 800 грн повернено", "12B886"]],
      notes: "Той самий агент у іншому бізнесі поводиться обережніше, бо правила інші. Він розбиває задачу на дві дії, кожну погоджує людина, і тримає клієнта в курсі.",
    },
  ];
  for (const d of demos) {
    s = pres.addSlide({ masterName: "Demo", sectionTitle: "Демо" });
    s.addText(d.title, { placeholder: "title" });
    s.addText(d.sub, { placeholder: "body" });
    videoSlot(s, { x: M, y: 1.9, w: W - 2 * M, h: (W - 2 * M) * (600 / 1920), poster: d.poster, file: d.file, labels: ["Клієнт на сайті Bookly", "Чат і copilot адміністратора"] });
    steps(s, d.steps, 5.8);
    s.addNotes(d.notes + "\n\nВідео: presentation/videos/" + d.file);
  }

  // 9. Same agent, different rules -------------------------------------------
  pres.addSection({ title: "Чому це працює" });
  s = pres.addSlide({ masterName: "Content", sectionTitle: "Чому це працює" });
  s.addText("Один агент — різні правила кожного бізнесу", { placeholder: "title" });
  const hdr = (t) => ({ text: t, options: { bold: true, color: C.background1, fill: { color: C.accent1 } } });
  const cell = (t, opt = {}) => ({ text: t, options: { color: C.text1, ...opt } });
  const ok = { color: C.accent3, bold: true };
  const ap = { color: C.accent4, bold: true };
  const no = { color: C.accent2, bold: true };
  s.addTable([
    [hdr("Правило"), hdr("Lumen Beauty (салон)"), hdr("DentaPlus (клініка)")],
    [cell("Безкоштовне скасування"), cell("за 24 год"), cell("за 48 год")],
    [cell("Штраф за неявку"), cell("300 грн"), cell("500 грн")],
    [cell("Перенесення"), cell("сам", ok), cell("сам", ok)],
    [cell("Скасування"), cell("сам", ok), cell("з погодженням", ap)],
    [cell("Повернення передоплати"), cell("сам до 500 грн", ok), cell("з погодженням", ap)],
    [cell("Виняток з доброї волі"), cell("сам (1 раз / 180 днів, без неявок)", ok), cell("з погодженням", ap)],
    [cell("Зняти штраф за неявку"), cell("з погодженням", ap), cell("заборонено", no)],
  ], { x: M, y: 1.55, w: 8.2, colW: [2.9, 2.9, 2.4], fontSize: 14, rowH: 0.52, border: { type: "solid", color: HEX.lt2, pt: 1 }, fill: { color: HEX.lt1 }, valign: "middle", margin: [0, 0.1, 0, 0.1], objectName: "policy table" });
  card(s, { x: M + 8.5, y: 1.55, w: W - 2 * M - 8.5, h: 4.16, ico: I.shield, head: "Власник керує ризиком", text: "Правила й дозволи агента змінюються в адмінці без коду. Агент читає їх на кожному кроці, а платформа перевіряє цілісність даних: вільний слот, сума, стан запису.", name: "control" });
  s.addNotes("Це головна ідея повторного використання: агент не захардкожений під салон. Власник у налаштуваннях вирішує, що AI робить сам, а що лише з погодженням. Тому однакове звернення в салоні й клініці закінчується по-різному.");

  // 10. Product tour ---------------------------------------------------------
  s = pres.addSlide({ masterName: "Content", sectionTitle: "Чому це працює" });
  s.addText("Справжній продукт, а не макет", { placeholder: "title" });
  videoSlot(s, { x: M, y: 1.55, w: 7.6, h: 4.75, poster: "posters/product-tour.png", file: "product-tour.mp4" });
  const tx = M + 7.6 + 0.4;
  const tw = W - M - tx;
  [
    [I.store, "Сторінка бізнесу і запис", "Послуги, майстри, правила, вільні слоти, передоплата"],
    [I.chart, "Адмінка", "Тиждень бронювань, дії агента з міткою «AI», клієнти, майстри, послуги"],
    [I.code, "Відкриті інтеграції", "HTTP API, MCP-сервер для агента, віджет одним рядком коду"],
  ].forEach(([ic, head, text], i) => {
    const y = 1.55 + i * 1.6;
    s.addShape(pres.shapes.OVAL, { x: tx, y, w: 0.62, h: 0.62, fill: { color: C.background2 }, line: { type: "none" }, objectName: `tour icon bg ${i}` });
    s.addImage({ data: ic, x: tx + 0.14, y: y + 0.14, w: 0.34, h: 0.34, objectName: `tour icon ${i}` });
    s.addText(head, { x: tx + 0.85, y, w: tw - 0.85, h: 0.4, fontSize: 17, bold: true, color: C.text1, margin: 0, isTextBox: true, objectName: `tour head ${i}` });
    s.addText(text, { x: tx + 0.85, y: y + 0.42, w: tw - 0.85, h: 0.9, fontSize: 14, color: C.text2, margin: 0, valign: "top", isTextBox: true, objectName: `tour text ${i}` });
  });
  s.addNotes("Під агентом — працююча платформа: мульти-тенант, PostgreSQL, Docker, 119 тестів бекенду. Будь-який салон чи клініка реєструється, налаштовує правила — і AI-підтримка працює одразу. Відео: presentation/videos/product-tour.mp4");

  // 11. Operational impact ---------------------------------------------------
  s = pres.addSlide({ masterName: "Content", sectionTitle: "Чому це працює" });
  s.addText("Що отримує команда підтримки", { placeholder: "title" });
  const stats = [
    ["4 з 4", "демо-звернення вирішено до кінця, а не лише відповіддю", C.accent1],
    ["1 клік", "щоб адміністратор погодив ризикову дію з готовим розбором", C.accent4],
    ["1 700 грн", "передоплат збережено або повернено клієнтам у демо", C.accent3],
  ];
  const stw = (W - 2 * M - 0.6) / 3;
  stats.forEach(([big, text, color], i) => {
    const x = M + i * (stw + 0.3);
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 1.6, w: stw, h: 2.3, rectRadius: 0.12, fill: { color: C.background2 }, line: { type: "none" }, objectName: `stat ${i}` });
    s.addText(big, { x: x + 0.3, y: 1.8, w: stw - 0.6, h: 1.0, fontSize: 48, bold: true, color, margin: 0, isTextBox: true, objectName: `stat ${i} value` });
    s.addText(text, { x: x + 0.3, y: 2.85, w: stw - 0.6, h: 0.9, fontSize: 14, color: C.text2, margin: 0, valign: "top", isTextBox: true, objectName: `stat ${i} label` });
  });
  card(s, { x: M, y: 4.2, w: (W - 2 * M - 0.3) / 2, h: 2.6, ico: I.chart, head: "Аналітика взаємодій", text: "Copilot рахує наміри, емоції, авто-дії, погодження, ескалації та збережені гроші — видно, де AI закриває звернення сам.", name: "analytics" });
  card(s, { x: M + (W - 2 * M - 0.3) / 2 + 0.3, y: 4.2, w: (W - 2 * M - 0.3) / 2, h: 2.6, ico: I.phone, head: "Будь-який канал", text: "Чат на сайті, віджет на сайті бізнесу, телефон через Vapi — однакові інструменти й правила, одна черга погоджень.", name: "channels" });
  s.addNotes("Цифри з наших демо-сценаріїв: 500 грн Олени і 400 грн Максима збережено, 800 грн Петру повернено. Головне — адміністратор більше не робить рутинних дій руками, а лише погоджує те, що справді потребує людини.");

  // 12. Criteria -------------------------------------------------------------
  s = pres.addSlide({ masterName: "Content", sectionTitle: "Чому це працює" });
  s.addText("Як ми закриваємо критерії оцінювання", { placeholder: "title" });
  const crit = [
    ["Operational Impact", "Звернення закриваються діями в системі; людина — лише для ризикових рішень"],
    ["Innovation", "Permission engine, який налаштовує власник, і один агент для будь-якого бізнесу"],
    ["Use of AI", "Оркестратор Claude Sonnet, Gemma 4 для простих питань, агент з інструментами"],
    ["Reasoning & Context", "Рішення залежить від історії клієнта, правил бізнесу та емоції звернення"],
    ["Presentation & Demo", "Працюючий продукт: сайт, адмінка, API, MCP, телефон — усе на відео"],
  ];
  crit.forEach(([head, text], i) => {
    const y = 1.5 + i * 1.0;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: M, y, w: W - 2 * M, h: 0.82, rectRadius: 0.1, fill: { color: i % 2 ? C.background1 : C.background2 }, line: { type: "none" }, objectName: `criterion ${i}` });
    s.addText(head, { x: M + 0.3, y, w: 3.4, h: 0.82, fontSize: 17, bold: true, color: C.accent1, valign: "middle", margin: 0, isTextBox: true, objectName: `criterion ${i} name` });
    s.addText(text, { x: M + 3.8, y, w: W - 2 * M - 4.1, h: 0.82, fontSize: 15, color: C.text1, valign: "middle", margin: 0, isTextBox: true, objectName: `criterion ${i} text` });
  });
  s.addNotes("Пройтися по п'яти критеріях з ТЗ і коротко показати, де кожен закритий.");

  // 13. Closing --------------------------------------------------------------
  pres.addSection({ title: "Підсумок" });
  s = pres.addSlide({ masterName: "Dark Title", sectionTitle: "Підсумок" });
  s.addText("Дякуємо!", { placeholder: "title" });
  s.addText("Далі: інтеграція з календарями й CRM салонів, SMS-нагадування, прогноз неявок і передоплата для ризикових клієнтів", { placeholder: "body" });
  s.addText("github.com/redrembo24680/polytech_hack", { x: M, y: 6.3, w: 9, h: 0.4, fontSize: 16, color: C.accent6, margin: 0, isTextBox: true, objectName: "repo" });
  s.addNotes("Підсумок: AI тут не інтерфейс спілкування, а учасник операцій. Наступні кроки — інтеграції й прогнозування неявок на даних, які платформа вже збирає.");

  const out = path.join(__dirname, "Bookly-pitch.pptx");
  await pres.writeFile({ fileName: out });
  await applyTheme(out, THEME);
  console.log("wrote", out);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
