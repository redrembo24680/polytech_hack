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

  // 2. Problem and solution -------------------------------------------------
  pres.addSection({ title: "Проблема і рішення" });
  s = pres.addSlide({ masterName: "Content", sectionTitle: "Проблема і рішення" });
  s.addText("Рутина підтримки → AI, який сам діє в системі", { placeholder: "title" });
  const lw = 5.7;
  s.addText("ПРОБЛЕМА", { x: M, y: 1.4, w: lw, h: 0.3, fontSize: 12, bold: true, color: C.accent2, margin: 0, isTextBox: true, objectName: "problem label" });
  [
    [I.inbox, "«Перенесіть», «поверніть»", "Адміністратор цілий день робить однакові дії вручну"],
    [I.clock, "15–23% записів — неявки", "Передоплати, штрафи й винятки перевіряють вручну"],
    [I.robot, "Боти лише пояснюють", "Розкажуть правила, але не перенесуть і не повернуть гроші"],
  ].forEach(([ic, head, text], i) => {
    const y = 1.85 + i * 1.35;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: M, y, w: lw, h: 1.15, rectRadius: 0.1, fill: { color: C.background2 }, line: { type: "none" }, objectName: `pain ${i + 1}` });
    s.addShape(pres.shapes.OVAL, { x: M + 0.25, y: y + 0.27, w: 0.62, h: 0.62, fill: { color: C.background1 }, line: { type: "none" }, objectName: `pain ${i + 1} icon bg` });
    s.addImage({ data: ic, x: M + 0.39, y: y + 0.41, w: 0.34, h: 0.34, objectName: `pain ${i + 1} icon` });
    s.addText(head, { x: M + 1.1, y: y + 0.15, w: lw - 1.3, h: 0.42, fontSize: 17, bold: true, color: C.text1, margin: 0, valign: "middle", isTextBox: true, objectName: `pain ${i + 1} head` });
    s.addText(text, { x: M + 1.1, y: y + 0.57, w: lw - 1.3, h: 0.45, fontSize: 14, color: C.text2, margin: 0, valign: "top", isTextBox: true, objectName: `pain ${i + 1} text` });
  });
  const rx = M + lw + 0.4;
  const rw = W - M - rx;
  s.addText("РІШЕННЯ", { x: rx, y: 1.4, w: rw, h: 0.3, fontSize: 12, bold: true, color: C.accent1, margin: 0, isTextBox: true, objectName: "solution label" });
  card(s, { x: rx, y: 1.85, w: rw, h: 3.85, ico: I.robot, head: "Bookly + AI-агент підтримки", textSize: 15, text: [
    { text: "Платформа для салонів і клінік: запис, передоплата, адмінка, правила бізнесу", options: { bullet: true, breakLine: true } },
    { text: "Агент розуміє намір і емоцію та діє інструментами: переносить, скасовує, повертає", options: { bullet: true, breakLine: true } },
    { text: "Власник налаштовує, що AI робить сам, а що лише з погодженням", options: { bullet: true, breakLine: true } },
    { text: "Чат на сайті, віджет, телефон — одні правила й одна черга погоджень", options: { bullet: true } },
  ], name: "solution" });
  s.addText([
    { text: "Питання не в тому, як швидше відповісти, ", options: { bold: true, color: C.text1 } },
    { text: "а в тому, як вирішити проблему.", options: { color: C.accent1, bold: true } },
  ], { x: M, y: 6.0, w: W - 2 * M, h: 0.5, fontSize: 18, margin: 0, isTextBox: true, objectName: "key question" });
  s.addText("Частка неявок: SchedulingKit, Appointment No-Show Statistics 2026 (оцінки вендора).", { x: M, y: 6.75, w: 10, h: 0.3, fontSize: 10, color: C.accent5, margin: 0, isTextBox: true, objectName: "source" });
  s.addNotes("Біль реальний: до чверті записів не доходять, а адміністратор вручну перевіряє правила й переносить записи. Боти не допомагають — вони не мають доступу до системи. Ми зробили платформу для бізнесів за записом і агента, який працює поверх неї: читає правила саме цього бізнесу й виконує дії, а ризикові рішення віддає людині.");

  // 3. Market and competitors -----------------------------------------------
  s = pres.addSlide({ masterName: "Content", sectionTitle: "Проблема і рішення" });
  s.addText("Ринок і конкуренти", { placeholder: "title" });
  const mstats = [
    ["≈20%", "записів у салонах — неявки", C.accent2],
    ["$3 600", "втрат салону на місяць через неявки", C.accent2],
    ["−45%", "неявок, коли є передоплата й правила скасування", C.accent3],
    ["$0,99–2", "платить бізнес за одне AI-рішення в Intercom і Zendesk", C.accent1],
  ];
  const msw = (W - 2 * M - 0.9) / 4;
  mstats.forEach(([big, text, color], i) => {
    const x = M + i * (msw + 0.3);
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 1.35, w: msw, h: 1.35, rectRadius: 0.12, fill: { color: C.background2 }, line: { type: "none" }, objectName: `market stat ${i}` });
    s.addText(big, { x: x + 0.25, y: 1.45, w: msw - 0.5, h: 0.62, fontSize: 30, bold: true, color, margin: 0, isTextBox: true, objectName: `market stat ${i} value` });
    s.addText(text, { x: x + 0.25, y: 2.08, w: msw - 0.5, h: 0.55, fontSize: 12, color: C.text2, margin: 0, valign: "top", isTextBox: true, objectName: `market stat ${i} label` });
  });
  const th = (t, hi) => ({ text: t, options: { bold: true, color: C.background1, fill: { color: hi ? C.accent1 : C.text2 }, align: "center" } });
  const tl = (t) => ({ text: t, options: { bold: true, color: C.text1 } });
  const yes = (t = "так") => ({ text: t, options: { color: C.accent3, bold: true, align: "center" } });
  const mid = (t) => ({ text: t, options: { color: C.accent4, align: "center" } });
  const nope = (t) => ({ text: t, options: { color: C.accent5, align: "center" } });
  const us = (t) => ({ text: t, options: { color: C.accent3, bold: true, align: "center", fill: { color: C.background2 } } });
  s.addTable([
    [th("", false), th("Bookly", true), th("Fresha AI Concierge", false), th("Booksy", false), th("Intercom Fin / Zendesk AI", false)],
    [tl("Сам переносить і скасовує записи"), us("так"), yes(), nope("лише сторонні сервіси"), mid("через власні інтеграції")],
    [tl("Правила бізнесу: передоплата, штраф, виняток"), us("так, у кожного свої"), nope("не заявлено"), nope("ні"), mid("треба налаштовувати")],
    [tl("Ризикові дії — з погодженням людини"), us("так, налаштовує власник"), nope("не заявлено"), nope("ні"), mid("частково")],
    [tl("Для салонів і клінік з коробки"), us("так"), yes("салони й спа"), nope("—"), nope("ні, загальний helpdesk")],
    [tl("Ціна AI"), us("за підпискою"), mid("$99,95 / міс за локацію"), nope("—"), mid("$0,99–2 за рішення + місця")],
  ], { x: M, y: 2.95, w: W - 2 * M, colW: [3.5, 2.05, 2.2, 1.9, 2.48], fontSize: 13, rowH: 0.52, border: { type: "solid", color: HEX.lt2, pt: 1 }, fill: { color: HEX.lt1 }, valign: "middle", margin: [0, 0.08, 0, 0.08], objectName: "competitors table" });
  s.addText("Джерела: SchedulingKit і Square (неявки, оцінки вендорів), сайт Fresha та огляди 2026, огляди цін Intercom і Zendesk 2026. «Не заявлено» — у відкритих описах продукту такої функції немає.", { x: M, y: 6.55, w: W - 2 * M - 0.7, h: 0.45, fontSize: 10, color: C.accent5, margin: 0, isTextBox: true, objectName: "market sources" });
  s.addNotes("Ринок: у салонах близько 20% записів — неявки, це в середньому $3 600 втрат на місяць. Передоплата й чіткі правила скасування знижують неявки майже вдвічі — саме їх наш агент і застосовує автоматично. Конкуренти: Fresha вже має AI-консьєржа, але без налаштовуваних правил і погоджень; у Booksy власного AI-агента немає; Intercom Fin і Zendesk — загальні helpdesk-и, де за кожне рішення платять $0,99–2 і все треба інтегрувати самому. Ми — вертикальне рішення для бізнесів за записом, де AI діє за правилами власника. Цифри — оцінки вендорів, джерела внизу слайда.");

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
      file: "scene-A.mp4", poster: "posters/scene-A.png",
      title: "Демо 1. Олена: агент сам рятує передоплату",
      sub: "«Дитина захворіла, не встигаю завтра на 10». Пізнє перенесення — за правилами передоплата згорає.",
      steps: [["Контекст", "12 візитів, 0 неявок, винятків ще не було", null], ["Рішення сам", "Правило салону дозволяє виняток автоматично", "12B886"], ["Дія", "Знаходить слоти, переносить, 500 грн збережено", null]],
      notes: "Агент не просто співчуває — він бачить, що це лояльна клієнтка, а політика салону дозволяє один виняток на пів року без погодження. Тому сам переносить і зберігає передоплату. В copilot видно кожен виклик інструмента.",
    },
    {
      file: "scene-B.mp4", poster: "posters/scene-B.png",
      title: "Демо 2. Максим: ризикове рішення — людині",
      sub: "Той самий запит, але в клієнта 2 неявки. Агент не вирішує сам, а просить адміністратора.",
      steps: [["Контекст", "2 неявки — автоматичний виняток не дозволено", "F59F00"], ["Погодження", "Адміністратор схвалює в copilot одним кліком", "F59F00"], ["Дія", "Агент сам повертається до клієнта й переносить", null]],
      notes: "Однакове звернення — інше рішення, бо інший контекст. Агент чесно пояснює клієнту, що чекає на рішення, а адміністратор отримує готовий розбір і кнопку «схвалити».",
    },
    {
      file: "scene-C.mp4", poster: "posters/scene-C.png",
      title: "Демо 3. Петро в клініці: суворі правила, дві дії",
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

  // 13. Closing --------------------------------------------------------------
  pres.addSection({ title: "Підсумок" });
  s = pres.addSlide({ masterName: "Dark Title", sectionTitle: "Підсумок" });
  s.addText("Дякуємо!", { placeholder: "title" });
  s.addText("Далі: інтеграція з календарями й CRM салонів, SMS-нагадування, прогноз неявок і передоплата для ризикових клієнтів", { placeholder: "body" });
  [["3 з 3", "сценаріїв вирішено діями"], ["1 клік", "на погодження ризикової дії"], ["1 700 грн", "передоплат збережено або повернено"]].forEach(([big, text], i) => {
    const x = M + i * 3.3;
    s.addText(big, { x, y: 5.4, w: 3.0, h: 0.6, fontSize: 30, bold: true, color: C.background1, margin: 0, isTextBox: true, objectName: `closing stat ${i}` });
    s.addText(text, { x, y: 6.0, w: 3.0, h: 0.45, fontSize: 13, color: C.accent6, margin: 0, isTextBox: true, objectName: `closing stat ${i} label` });
  });
  s.addText("github.com/redrembo24680/polytech_hack", { x: M, y: 6.85, w: 9, h: 0.4, fontSize: 16, color: C.accent6, margin: 0, isTextBox: true, objectName: "repo" });
  s.addNotes("Цифри з демо: 500 грн Олени і 400 грн Максима збережено, 800 грн Петру повернено. Критерії: Operational Impact — звернення закриваються діями, людина лише для ризикових рішень; Innovation — permission engine, який налаштовує власник; Use of AI — оркестратор Claude Sonnet, Gemma 4, агент з інструментами; Reasoning & Context — рішення залежить від історії клієнта й правил бізнесу; Demo — працюючий продукт. Підсумок: AI тут не інтерфейс спілкування, а учасник операцій. Наступні кроки — інтеграції й прогнозування неявок на даних, які платформа вже збирає.");

  const out = path.join(__dirname, "Bookly-pitch.pptx");
  await pres.writeFile({ fileName: out });
  await applyTheme(out, THEME);
  console.log("wrote", out);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
