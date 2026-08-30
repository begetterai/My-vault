/* Инвесторская колода «Ромашки» для ЕБРР.
   Запуск: node scripts/deck_ebrd.js файл.pptx   (нужен npm i pptxgenjs)
   Все цифры — из нашей базы, выдуманных нет. */
const pptx = require('pptxgenjs');
const p = new pptx();
p.layout = 'LAYOUT_16x9';                       // 10 x 5.625
p.author = 'Ромашка';
p.title = 'Ромашка — операционная система сети быстрого питания';

const NAVY = '16294A', NAVY2 = '24406E', ICE = 'E6ECF6', ICE2 = 'AFC1DC';
const ACC = '0E8C79', ACC2 = '0A6C5D', ACCL = '3FB79F';
const INK = '101B2E', INK2 = '55637C', PAPER = 'FFFFFF', LINE = 'D2DAE7';
const F = 'Times New Roman';
const W = 10, H = 5.625;
const PW = 3.35;                                // ширина левой панели
const CX = 3.8, CW = 5.75;                      // колонка контента
const TOP = 0.62, BOT = 5.06;                   // рабочая полоса по высоте

/* Левая панель во всю высоту: заголовок, вывод одной фразой, номер.
   Она же держит вертикаль — контент справа рисуется от TOP до BOT. */
function panel(s, t, lead, n) {
  // «профинансировать» в колонку 2,45 дюйма при 26 кеглях не влезает и рвётся
  // посреди слова. Подбираем размер по самому длинному слову заголовка.
  const long = Math.max(...t.split(' ').map(w => w.length));
  const size = Math.max(18, Math.min(26, Math.floor(172 / (0.53 * long))));
  s.addShape(p.ShapeType.rect, {x: 0, y: 0, w: PW, h: H, fill: {color: NAVY}});
  s.addText(t, {x: 0.45, y: 0.62, w: 2.45, h: 1.75, fontFace: F,
    fontSize: size, bold: true, color: PAPER, valign: 'top', isTextBox: true,
    margin: 0});
  s.addText(lead, {x: 0.45, y: 2.5, w: 2.45, h: 1.9, fontFace: F,
    fontSize: 12.5, color: ICE2, lineSpacing: 17, valign: 'top',
    isTextBox: true, margin: 0});
  s.addText(String(n).padStart(2, '0') + ' / 12',
    {x: 0.45, y: 4.85, w: 2.45, h: 0.3, fontFace: F, fontSize: 10.5,
     color: '6B82A6', valign: 'top', isTextBox: true, margin: 0});
}

/* Заголовок на слайде без панели. */
function wide(s, t, sub, dark) {
  s.addText(t, {x: 0.6, y: 0.5, w: 8.8, h: 0.7, fontFace: F, fontSize: 32,
    bold: true, color: dark ? PAPER : INK, valign: 'top', isTextBox: true, margin: 0});
  if (sub) s.addText(sub, {x: 0.6, y: 1.2, w: 8.8, h: 0.36, fontFace: F,
    fontSize: 14, italic: true, color: dark ? ACCL : INK2, valign: 'top', isTextBox: true,
    margin: 0});
}

/* Мотив колоды: маленький бирюзовый квадрат-маркер. */
function dot(s, x, y, c) {
  s.addShape(p.ShapeType.rect, {x, y, w: 0.13, h: 0.13,
    fill: {color: c || ACC}});
}

/* 1 ── титул ─────────────────────────────────────────────────────── */
let s = p.addSlide();
s.background = {color: NAVY};
s.addShape(p.ShapeType.rect, {x: 6.55, y: 0, w: 3.45, h: H,
  fill: {color: NAVY2}});
s.addText('Р', {x: 6.55, y: 1.15, w: 3.45, h: 2.95, fontFace: F, fontSize: 150,
  bold: true, color: '2F5490', align: 'center', valign: 'middle',
  isTextBox: true, margin: 0});
s.addText('Ромашка', {x: 0.7, y: 1.28, w: 5.5, h: 0.85, fontFace: F,
  fontSize: 46, bold: true, color: PAPER, valign: 'top', isTextBox: true, margin: 0});
s.addText('Операционная система сети быстрого питания',
  {x: 0.7, y: 2.14, w: 5.7, h: 0.5, fontFace: F, fontSize: 20, color: ACCL,
   valign: 'top', isTextBox: true, margin: 0});
s.addShape(p.ShapeType.rect, {x: 0.7, y: 3.2, w: 1.5, h: 0.05,
  fill: {color: ACC}});
s.addText('Стандарт работы, который исполняется и проверяется — '
  + 'а не лежит в папке',
  {x: 0.7, y: 3.45, w: 5.4, h: 0.7, fontFace: F, fontSize: 14, italic: true,
   color: ICE2, valign: 'top', isTextBox: true, margin: 0});
s.addText('Душанбе, Таджикистан · сентябрь 2026\n'
  + 'Заявка на финансирование профессиональной разработки',
  {x: 0.7, y: 4.42, w: 5.4, h: 0.7, fontFace: F, fontSize: 12.5, color: ICE2,
   lineSpacing: 18, valign: 'top', isTextBox: true, margin: 0});
s.addNotes('Мы построили работающий прототип своими силами на собственной '
  + 'сети. Прошу профинансировать превращение его в продукт.');

/* 2 ── кто мы ────────────────────────────────────────────────────── */
s = p.addSlide();
panel(s, 'Кто мы', 'Действующий бизнес, а не идея на бумаге. Уличная еда: '
  + 'шаурма, выпечка, салаты, напитки. Две смены в день, десять рабочих '
  + 'мест, высокий оборот людей — типичная сеть быстрого питания в регионе.',
  2);
const facts = [
  ['2', 'точки в Душанбе', 'Зелёный базар · ОВИР'],
  ['29', 'сотрудников', 'кухня, цех, бар, касса, зал'],
  ['дек. 2025', 'ведём журнал отзывов', 'по обеим точкам, 143 записи'],
  ['24.08.26', 'прототип в работе', 'ежедневно, обе точки'],
];
facts.forEach((f, i) => {
  const x = CX + (i % 2) * (CW / 2 + 0.1);
  const y = TOP + Math.floor(i / 2) * 2.28;
  s.addShape(p.ShapeType.rect, {x, y, w: CW / 2 - 0.1, h: 2.1,
    fill: {color: ICE}});
  dot(s, x + 0.28, y + 0.32);
  s.addText(f[0], {x: x + 0.28, y: y + 0.58, w: CW / 2 - 0.56, h: 0.72,
    fontFace: F, fontSize: f[0].length > 4 ? 26 : 34, bold: true, color: NAVY,
    valign: 'top', isTextBox: true, margin: 0});
  s.addText(f[1], {x: x + 0.28, y: y + 1.3, w: CW / 2 - 0.56, h: 0.34,
    fontFace: F, fontSize: 14.5, bold: true, color: INK, valign: 'top', isTextBox: true,
    margin: 0});
  s.addText(f[2], {x: x + 0.28, y: y + 1.62, w: CW / 2 - 0.56, h: 0.34,
    fontFace: F, fontSize: 11.5, color: INK2, valign: 'top', isTextBox: true, margin: 0});
});
s.addNotes('Мы не стартап без выручки. Мы работающая сеть, которая построила '
  + 'инструмент для себя и увидела, что он нужен всем вокруг.');

/* 3 ── проблема ──────────────────────────────────────────────────── */
s = p.addSlide();
panel(s, 'Проблема', 'Стандарт написан. Его исполнение никто не измеряет — '
  + 'и о нарушении первым узнаёт гость, а не управляющий.', 3);
s.addText('143 отзыва гостя, декабрь 2025 — август 2026',
  {x: CX, y: TOP, w: CW, h: 0.32, fontFace: F, fontSize: 15, bold: true,
   color: INK, valign: 'top', isTextBox: true, margin: 0});
s.addChart(p.ChartType.bar, [{
  name: 'Отзывы',
  labels: ['Ошибка сборки', 'Работа не по чеку', 'Сервис',
           'Недовольство качеством', 'Работа не по ТТК', 'Пищевая безопасность'],
  values: [4, 9, 17, 27, 31, 39],
}], {
  x: CX - 0.12, y: 1.02, w: CW + 0.12, h: 2.62,
  barDir: 'bar', showTitle: false, showLegend: false,
  showValue: true, dataLabelPosition: 'outEnd', dataLabelFontFace: F,
  dataLabelFontSize: 11, dataLabelColor: INK,
  chartColors: [NAVY2, NAVY2, NAVY2, NAVY2, ACC, ACC], varyColors: true,
  catAxisLabelFontFace: F, catAxisLabelFontSize: 11, catAxisLabelColor: INK,
  valAxisHidden: true, valGridLine: {style: 'none'},
  catGridLine: {style: 'none'}, catAxisLineShow: false,
  barGapWidthPct: 40, valAxisMaxVal: 46,
});
s.addShape(p.ShapeType.rect, {x: CX, y: 3.82, w: CW, h: 0.62,
  fill: {color: ICE}});
s.addText([{text: '70 из 143 ', options: {bold: true, color: ACC2}},
  {text: '— пищевая безопасность и работа не по техкарте. '
   + 'Половина всех жалоб.', options: {color: INK}}],
  {x: CX + 0.22, y: 3.82, w: CW - 0.44, h: 0.62, fontFace: F, fontSize: 13,
   valign: 'middle', isTextBox: true, margin: 0});
s.addShape(p.ShapeType.rect, {x: CX, y: 4.54, w: CW, h: 0.62,
  fill: {color: ICE}});
s.addText([{text: '53 отзыва ', options: {bold: true, color: ACC2}},
  {text: '— пришли публично, в Instagram. Треть жалоб видит рынок, '
   + 'а не управляющий.', options: {color: INK}}],
  {x: CX + 0.22, y: 4.54, w: CW - 0.44, h: 0.62, fontFace: F, fontSize: 13,
   valign: 'middle', isTextBox: true, margin: 0});
s.addNotes('Это наши собственные данные, не отраслевая оценка. Половина жалоб '
  + 'не про вкус и не про сервис, а про отход смены от стандарта.');

/* 4 ── почему ────────────────────────────────────────────────────── */
s = p.addSlide();
panel(s, 'Почему так происходит', 'Четыре разрыва между написанным '
  + 'стандартом и тем, что делает смена. Ни один из них не лечится '
  + 'ещё одним регламентом.', 4);
const why = [
  ['Стандарт лежит отдельно от работы',
   'Регламенты и техкарты написаны. Смена работает по памяти: открыть '
   + 'папку посреди часа пик невозможно.'],
  ['Исполнение не оставляет следа',
   'Была ли проверена температура фритюра в девять утра? Ответа нет ни '
   + 'у кого — ни «да», ни «нет».'],
  ['Ответственность теряется на пересменке',
   'Вторая смена находит грязную станцию. Чья это работа — выяснить '
   + 'нечем, и не отвечает никто.'],
  ['О нарушении сообщает гость',
   'Управляющий узнаёт о проблеме из отзыва в Instagram — когда '
   + 'исправлять уже поздно.'],
];
why.forEach((w, i) => {
  const y = TOP + i * 1.14;
  s.addText(String(i + 1), {x: CX, y: y - 0.04, w: 0.42, h: 0.44, fontFace: F,
    fontSize: 24, bold: true, color: ICE2, valign: 'top', isTextBox: true, margin: 0});
  s.addText(w[0], {x: CX + 0.5, y: y, w: CW - 0.5, h: 0.32, fontFace: F,
    fontSize: 15.5, bold: true, color: NAVY, valign: 'top', isTextBox: true, margin: 0});
  s.addText(w[1], {x: CX + 0.5, y: y + 0.34, w: CW - 0.5, h: 0.6, fontFace: F,
    fontSize: 12.5, color: INK2, valign: 'top', isTextBox: true, margin: 0});
  if (i < 3) s.addShape(p.ShapeType.line, {x: CX, y: y + 1.02, w: CW, h: 0,
    line: {color: LINE, width: 1}});
});
s.addNotes('Ни один из четырёх разрывов не лечится ещё одним документом. '
  + 'Их лечит инструмент в руках смены.');

/* 5 ── решение (тёмный, без панели) ──────────────────────────────── */
s = p.addSlide();
s.background = {color: NAVY};
wide(s, 'Что мы построили', 'Telegram-бот и мини-приложение внутри телефона, '
  + 'который уже есть у каждого сотрудника', true);
const four = [
  ['Явка', 'Приход и уход только с подтверждённой геометкой. Часы '
   + 'считаются по факту, а не по памяти.'],
  ['Чек-листы', 'Стандарт разложен по рабочим местам и этапам смены: '
   + 'пункт, срок, фото по требованию.'],
  ['Обучение', 'Регламент открывается прямо из пункта, знание проверяется '
   + 'вопросами, ознакомление подписывается.'],
  ['Проверка', 'Сданный лист уходит руководителю. Расхождение становится '
   + 'задачей, а не разговором.'],
];
four.forEach((f, i) => {
  const x = 0.6 + (i % 2) * 4.5;
  const y = 1.92 + Math.floor(i / 2) * 1.66;
  s.addShape(p.ShapeType.rect, {x, y, w: 4.2, h: 1.44, fill: {color: NAVY2}});
  dot(s, x + 0.3, y + 0.28);
  s.addText(f[0], {x: x + 0.55, y: y + 0.2, w: 3.4, h: 0.32, fontFace: F,
    fontSize: 17, bold: true, color: PAPER, valign: 'top', isTextBox: true, margin: 0});
  s.addText(f[1], {x: x + 0.3, y: y + 0.6, w: 3.65, h: 0.75, fontFace: F,
    fontSize: 12.5, color: ICE2, valign: 'top', isTextBox: true, margin: 0});
});
s.addNotes('Ни одного нового устройства и ни одной установки: Telegram уже '
  + 'стоит у всех, приложение открывается внутри него.');

/* 6 ── объём ─────────────────────────────────────────────────────── */
s = p.addSlide();
panel(s, 'Что уже оцифровано', 'Прототип работает в ежедневной эксплуатации '
  + 'на обеих точках. Стандарт описан данными, а не кодом: чек-лист меняет '
  + 'управляющий, новая точка добавляется без программиста.', 6);
const nums = [
  ['54', 'чек-листа'], ['896', 'пунктов стандарта'], ['10', 'рабочих мест'],
  ['46', 'регламентов'], ['16', 'тренингов с проверкой'],
  ['28', 'журналов событий'],
];
nums.forEach((n, i) => {
  const x = CX + (i % 3) * (CW / 3);
  const y = TOP + 0.24 + Math.floor(i / 3) * 1.5;
  s.addText(n[0], {x, y, w: CW / 3 - 0.18, h: 0.72, fontFace: F, fontSize: 40,
    bold: true, color: NAVY, valign: 'top', isTextBox: true, margin: 0});
  s.addText(n[1], {x, y: y + 0.74, w: CW / 3 - 0.18, h: 0.5, fontFace: F,
    fontSize: 12.5, color: INK2, valign: 'top', isTextBox: true, margin: 0});
});
s.addShape(p.ShapeType.line, {x: CX, y: TOP + 1.66, w: CW - 0.18, h: 0,
  line: {color: LINE, width: 1}});
s.addShape(p.ShapeType.rect, {x: CX, y: 4.12, w: CW, h: 0.94,
  fill: {color: ICE}});
dot(s, CX + 0.24, 4.38);
s.addText('Каждое рабочее место закрывает за день четыре листа: открытие · '
  + 'передача · приём · закрытие. Раньше это была папка документов, '
  + 'которую в смене никто не открывал.',
  {x: CX + 0.5, y: 4.12, w: CW - 0.74, h: 0.94, fontFace: F, fontSize: 12.5,
   color: INK, valign: 'middle', isTextBox: true, margin: 0});
s.addNotes('896 пунктов — это разложенный на конкретные действия стандарт, '
  + 'который раньше существовал только как текст.');

/* 7 ── передача смены (во всю ширину) ────────────────────────────── */
s = p.addSlide();
wide(s, 'Ключевой узел: передача смены',
  'Место, где обычно теряется ответственность');
const step = [
  ['Открытие', 'Первая смена принимает точку и подтверждает готовность'],
  ['Передача', 'Сдающий проходит лист и фиксирует состояние станции'],
  ['Приём', 'Принимающий проверяет то же самое своими глазами'],
  ['Закрытие', 'Вторая смена закрывает точку и сдаёт лист'],
];
step.forEach((t, i) => {
  const x = 0.6 + i * 2.26;
  s.addShape(p.ShapeType.rect, {x, y: 1.76, w: 2.0, h: 1.62,
    fill: {color: ICE}});
  s.addText(String(i + 1), {x: x + 0.22, y: 1.9, w: 0.4, h: 0.4, fontFace: F,
    fontSize: 22, bold: true, color: ACC, valign: 'top', isTextBox: true, margin: 0});
  s.addText(t[0], {x: x + 0.22, y: 2.36, w: 1.6, h: 0.3, fontFace: F,
    fontSize: 15, bold: true, color: NAVY, valign: 'top', isTextBox: true, margin: 0});
  s.addText(t[1], {x: x + 0.22, y: 2.68, w: 1.62, h: 0.62, fontFace: F,
    fontSize: 10.5, color: INK2, valign: 'top', isTextBox: true, margin: 0});
  if (i < 3) s.addText('→', {x: x + 2.02, y: 2.4, w: 0.24, h: 0.3, fontFace: F,
    fontSize: 17, color: ACC, align: 'center', valign: 'top', isTextBox: true, margin: 0});
});
s.addShape(p.ShapeType.rect, {x: 0.6, y: 3.66, w: 8.8, h: 1.4,
  fill: {color: NAVY}});
dot(s, 0.9, 3.98);
s.addText('Расхождение нельзя оставить без разбора',
  {x: 1.15, y: 3.88, w: 8.0, h: 0.32, fontFace: F, fontSize: 16, bold: true,
   color: ACCL, valign: 'top', isTextBox: true, margin: 0});
s.addText('Если принимающий отметил пункт как невыполненный, система не даст '
  + 'закрыть лист, пока не сказано, чья это вина: первой смены, второй или '
  + 'внешняя причина. Из внешней причины автоматически рождается задача '
  + 'на починку. Так «не сошлось» перестаёт быть разговором и становится '
  + 'записью с адресатом.',
  {x: 0.9, y: 4.28, w: 8.2, h: 0.72, fontFace: F, fontSize: 12.5,
   color: ICE2, valign: 'top', isTextBox: true, margin: 0});
s.addNotes('Это главное отличие от чек-листа в тетради: тетрадь фиксирует '
  + 'галочку, а система заставляет назвать ответственного.');

/* 8 ── доказательство ────────────────────────────────────────────── */
s = p.addSlide();
panel(s, 'Полевые тесты', '29–30 августа 2026. Шесть сотрудников, две точки, '
  + 'обычные рабочие дни — не демонстрация.', 8);
const proof = [
  ['15', 'листов сдано'], ['728', 'из 729 пунктов'], ['0', 'сбоев системы'],
];
proof.forEach((f, i) => {
  const x = CX + i * (CW / 3);
  s.addText(f[0], {x, y: TOP, w: CW / 3 - 0.18, h: 0.72, fontFace: F,
    fontSize: 38, bold: true, color: NAVY, valign: 'top', isTextBox: true, margin: 0});
  s.addText(f[1], {x, y: TOP + 0.72, w: CW / 3 - 0.18, h: 0.34, fontFace: F,
    fontSize: 12.5, color: INK2, valign: 'top', isTextBox: true, margin: 0});
});
s.addShape(p.ShapeType.line, {x: CX, y: 1.86, w: CW - 0.18, h: 0,
  line: {color: LINE, width: 1}});
s.addText('Но ценность не в этих цифрах, а в том, что система увидела:',
  {x: CX, y: 2.04, w: CW, h: 0.3, fontFace: F, fontSize: 14.5, bold: true,
   color: INK, valign: 'top', isTextBox: true, margin: 0});
const saw = [
  ['Опоздания на 92 и на 17 минут',
   'Раньше их никто не считал: приход отмечали на словах.'],
  ['Шесть листов сданы позже срока',
   'Открытие точки в 10:13–12:25 при нормативе 09:30.'],
  ['Лист из 12 пунктов заполнен за 0,2 минуты',
   'Пройти станцию за это время физически нельзя — это формальная галочка.'],
];
saw.forEach((t, i) => {
  const y = 2.5 + i * 0.85;
  dot(s, CX, y + 0.07);
  s.addText(t[0], {x: CX + 0.28, y, w: CW - 0.28, h: 0.3, fontFace: F,
    fontSize: 13.5, bold: true, color: NAVY, valign: 'top', isTextBox: true, margin: 0});
  s.addText(t[1], {x: CX + 0.28, y: y + 0.3, w: CW - 0.28, h: 0.44,
    fontFace: F, fontSize: 12, color: INK2, valign: 'top', isTextBox: true, margin: 0});
});
s.addNotes('Мы показываем и то, что нашли против себя. Ровно ради этого '
  + 'инструмент и строится.');

/* 9 ── соответствие ──────────────────────────────────────────────── */
s = p.addSlide();
panel(s, 'Прозрачность и соответствие', 'Что перестаёт быть декларацией '
  + 'и становится выгружаемыми данными — по каждому сотруднику, дню '
  + 'и рабочему месту.', 9);
const comp = [
  ['Пищевая безопасность',
   'Температуры, сроки, маркировка и чистота оборудования — пункты '
   + 'с фотографией и временем. Основа для внедрения ХАССП.'],
  ['Трудовые отношения',
   'Часы считаются по фактическому приходу и уходу с подтверждением '
   + 'места. Честная база для табеля и оплаты.'],
  ['Обучение персонала',
   'Регламент открывается из рабочего пункта, знание проверяется '
   + 'вопросами, ознакомление подписывается в системе.'],
  ['Аудиторский след',
   'Кто, когда и что отметил, кто подтвердил. Своё заполнение '
   + 'подтвердить нельзя — проверяет тот, кто выше.'],
];
comp.forEach((c, i) => {
  const x = CX + (i % 2) * (CW / 2 + 0.1);
  const y = TOP + Math.floor(i / 2) * 2.28;
  s.addShape(p.ShapeType.rect, {x, y, w: CW / 2 - 0.1, h: 2.1,
    fill: {color: ICE}});
  dot(s, x + 0.28, y + 0.3);
  s.addText(c[0], {x: x + 0.28, y: y + 0.58, w: CW / 2 - 0.56, h: 0.34,
    fontFace: F, fontSize: 15, bold: true, color: NAVY, valign: 'top', isTextBox: true,
    margin: 0});
  s.addText(c[1], {x: x + 0.28, y: y + 0.98, w: CW / 2 - 0.56, h: 1.0,
    fontFace: F, fontSize: 12, color: INK2, valign: 'top', isTextBox: true, margin: 0});
});
s.addNotes('Для банка развития это ключевое: соответствие перестаёт быть '
  + 'обещанием и становится данными, которые можно проверить.');

/* 10 ── масштаб ──────────────────────────────────────────────────── */
s = p.addSlide();
panel(s, 'Почему это масштабируется', 'Продукт с первого дня отделён '
  + 'от конкретной точки: роли и права разделены, стандарт лежит '
  + 'в данных, работа идёт на телефоне сотрудника.', 10);
const way = [
  ['Сегодня', '2 точки, 29 человек — собственная сеть как полигон'],
  ['Шаг 1', 'Вся сеть «Ромашки», включая цех и доставку'],
  ['Шаг 2', 'Продукт для сетей общепита Таджикистана и Центральной Азии'],
  ['Шаг 3', 'Франшиза: стандарт передаётся вместе с инструментом'],
];
way.forEach((w, i) => {
  const y = TOP + 0.1 + i * 1.14;
  s.addShape(p.ShapeType.ellipse, {x: CX, y: y + 0.04, w: 0.24, h: 0.24,
    fill: {color: i ? ACC : NAVY}});
  if (i < 3) s.addShape(p.ShapeType.line, {x: CX + 0.12, y: y + 0.28, w: 0,
    h: 0.9, line: {color: LINE, width: 1.5}});
  s.addText(w[0], {x: CX + 0.5, y, w: CW - 0.5, h: 0.32, fontFace: F,
    fontSize: 15.5, bold: true, color: NAVY, valign: 'top', isTextBox: true, margin: 0});
  s.addText(w[1], {x: CX + 0.5, y: y + 0.34, w: CW - 0.5, h: 0.5, fontFace: F,
    fontSize: 12.5, color: INK2, valign: 'top', isTextBox: true, margin: 0});
});
s.addNotes('Мы строили не «приложение для Ромашки», а систему, в которой '
  + 'Ромашка — первый клиент.');

/* 11 ── просим ───────────────────────────────────────────────────── */
s = p.addSlide();
panel(s, 'Что просим профинансировать', 'Прототип написан одним человеком '
  + 'и работает. Мы просим не на проверку идеи — она проверена на своей '
  + 'сети. Мы просим на инженерию.', 11);
const need = [
  ['Промышленная база данных',
   'Сейчас данные в таблицах: это дало скорость, но упирается в предел '
   + 'запросов и не выдержит десятки точек.'],
  ['Мобильное приложение',
   'Работа без сети и синхронизация: связь на точке пропадает, '
   + 'а смена не должна останавливаться.'],
  ['Контроль качества по фото',
   'Автоматическая сверка снимка с эталоном, чтобы «чисто» подтверждала '
   + 'не только галочка.'],
  ['Интеграции',
   'Касса, складской учёт, зарплатный контур: списания и остатки '
   + 'должны приходить сами.'],
  ['Безопасность и аудит',
   'Профессиональный разбор прав доступа, шифрование, независимый '
   + 'аудит персональных данных.'],
  ['Локализация',
   'Русский, таджикский, английский — без этого продукт не выходит '
   + 'за пределы одной сети.'],
];
need.forEach((n, i) => {
  const y = TOP + i * 0.755;
  dot(s, CX, y + 0.07);
  s.addText(n[0], {x: CX + 0.28, y, w: CW - 0.28, h: 0.3, fontFace: F,
    fontSize: 13.5, bold: true, color: NAVY, valign: 'top', isTextBox: true, margin: 0});
  s.addText(n[1], {x: CX + 0.28, y: y + 0.29, w: CW - 0.28, h: 0.42,
    fontFace: F, fontSize: 11.5, color: INK2, valign: 'top', isTextBox: true, margin: 0});
});
s.addNotes('Шесть направлений. Первые два — обязательные, остальные '
  + 'определяют, станет ли это продуктом для рынка.');

/* 12 ── итог ─────────────────────────────────────────────────────── */
s = p.addSlide();
s.background = {color: NAVY};
wide(s, 'Статус и просьба', null, true);
const st = [
  ['Сделано', 'Работающий прототип в ежедневной эксплуатации на двух точках. '
   + 'Полевые тесты пройдены, стандарт оцифрован полностью: 54 чек-листа, '
   + '896 пунктов, 46 регламентов.'],
  ['Вложено', 'Собственные силы и время. Инфраструктура — облачный хостинг '
   + 'и таблицы, денежные расходы минимальны.'],
  ['Нужно', 'Инженерная команда на 12 месяцев: разработка, мобильное '
   + 'приложение, безопасность, интеграции, локализация.'],
];
st.forEach((x, i) => {
  const y = 1.62 + i * 1.22;
  s.addShape(p.ShapeType.rect, {x: 0.6, y: y + 0.06, w: 0.13, h: 0.13,
    fill: {color: ACC}});
  s.addText(x[0], {x: 0.88, y, w: 1.5, h: 0.3, fontFace: F, fontSize: 15.5,
    bold: true, color: ACCL, valign: 'top', isTextBox: true, margin: 0});
  s.addText(x[1], {x: 2.5, y, w: 6.9, h: 0.62, fontFace: F,
    fontSize: 13, color: ICE2, valign: 'top', isTextBox: true, margin: 0});
});
s.addShape(p.ShapeType.rect, {x: 0.6, y: 4.72, w: 8.8, h: 0.6,
  fill: {color: ACC}});
s.addText('Запрашиваем ____________ на 12 месяцев   ·   контакт: '
  + '____________________',
  {x: 0.85, y: 4.72, w: 8.3, h: 0.6, fontFace: F, fontSize: 14, bold: true,
   color: PAPER, valign: 'middle', isTextBox: true, margin: 0});
s.addNotes('Сумму и контакт вписать перед показом.');

p.writeFile({fileName: process.argv[2] || 'deck.pptx'})
  .then(f => console.log('готово:', f));
