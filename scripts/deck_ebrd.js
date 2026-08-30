const pptx = require('pptxgenjs');
const p = new pptx();
p.layout = 'LAYOUT_16x9';           // 10 x 5.625
p.author = 'Ромашка';
p.title = 'Ромашка — операционная система сети быстрого питания';

const INK = '1F2124', INK2 = '5E6165', AMB = 'E8A317', AMB2 = 'C88700';
const PAPER = 'FFFFFF', WASH = 'F4F2EE', LINE = 'DCD8D1', SNOW = 'F0EEEA';
const F = 'Times New Roman';
const M = 0.55, W = 10, H = 5.625, CW = W - 2 * M;

function title(s, t, sub, dark) {
  s.addText(t, {x: M, y: 0.42, w: CW, h: 0.72, fontFace: F, fontSize: 32,
    bold: true, color: dark ? PAPER : INK, isTextBox: true, margin: 0});
  if (sub) s.addText(sub, {x: M, y: 1.14, w: CW, h: 0.34, fontFace: F,
    fontSize: 14, italic: true, color: dark ? AMB : INK2, isTextBox: true,
    margin: 0});
}

function num(s, n, x, y, d) {
  s.addShape(p.ShapeType.ellipse, {x, y, w: 0.42, h: 0.42,
    fill: {color: d ? AMB : INK}});
  s.addText(String(n), {x, y, w: 0.42, h: 0.42, fontFace: F, fontSize: 15,
    bold: true, color: d ? INK : PAPER, align: 'center', valign: 'middle',
    isTextBox: true, margin: 0});
}

function foot(s, txt, dark) {
  s.addText(txt, {x: M, y: H - 0.52, w: CW, h: 0.3, fontFace: F, fontSize: 10,
    color: dark ? '8A8D91' : INK2, isTextBox: true, margin: 0});
}

/* 1 ── титул ─────────────────────────────────────────────────────── */
let s = p.addSlide();
s.background = {color: INK};
s.addShape(p.ShapeType.ellipse, {x: 7.4, y: 1.15, w: 2.1, h: 2.1,
  fill: {color: AMB}});
s.addText('Р', {x: 7.4, y: 1.15, w: 2.1, h: 2.1, fontFace: F, fontSize: 84,
  bold: true, color: INK, align: 'center', valign: 'middle', isTextBox: true,
  margin: 0});
s.addText('Ромашка', {x: M, y: 1.32, w: 6.6, h: 0.8, fontFace: F, fontSize: 44,
  bold: true, color: PAPER, isTextBox: true, margin: 0});
s.addText('Операционная система сети быстрого питания',
  {x: M, y: 2.12, w: 6.6, h: 0.9, fontFace: F, fontSize: 21, color: AMB,
   isTextBox: true, margin: 0});
s.addText('Стандарт работы, который исполняется и проверяется — а не лежит '
  + 'в папке', {x: M, y: 3.02, w: 6.6, h: 0.6, fontFace: F, fontSize: 13.5,
  italic: true, color: 'B9BCC0', isTextBox: true, margin: 0});
s.addShape(p.ShapeType.line, {x: M, y: 3.86, w: 2.2, h: 0,
  line: {color: AMB, width: 2}});
s.addText('Душанбе, Таджикистан · сентябрь 2026\n'
  + 'Заявка на финансирование профессиональной разработки',
  {x: M, y: 4.02, w: 6.6, h: 0.7, fontFace: F, fontSize: 12.5, color: 'D8DADD',
   lineSpacing: 18, isTextBox: true, margin: 0});
s.addNotes('Мы построили работающий прототип на свои силы и на собственной '
  + 'сети. Сегодня прошу профинансировать превращение его в продукт.');

/* 2 ── кто мы ────────────────────────────────────────────────────── */
s = p.addSlide();
title(s, 'Кто мы', 'Действующий бизнес, а не идея на бумаге');
const facts = [
  ['2', 'точки в Душанбе', 'Зелёный базар · ОВИР'],
  ['29', 'сотрудников', 'кухня, цех, бар, касса, зал'],
  ['9 мес.', 'журналу отзывов', 'ведётся с декабря 2025'],
  ['24.08', 'прототип в работе', 'ежедневно, обе точки'],
];
facts.forEach((f, i) => {
  const x = M + i * (CW / 4);
  s.addShape(p.ShapeType.roundRect, {x: x + 0.04, y: 1.72, w: CW / 4 - 0.16,
    h: 1.72, fill: {color: WASH}, line: {color: LINE, width: 0.75},
    rectRadius: 0.08});
  s.addText(f[0], {x: x + 0.04, y: 1.88, w: CW / 4 - 0.16, h: 0.62,
    fontFace: F, fontSize: 34, bold: true, color: AMB2, align: 'center',
    isTextBox: true, margin: 0});
  s.addText(f[1], {x: x + 0.04, y: 2.52, w: CW / 4 - 0.16, h: 0.3, fontFace: F,
    fontSize: 13.5, bold: true, color: INK, align: 'center', isTextBox: true,
    margin: 0});
  s.addText(f[2], {x: x + 0.12, y: 2.84, w: CW / 4 - 0.32, h: 0.5, fontFace: F,
    fontSize: 11, color: INK2, align: 'center', isTextBox: true, margin: 0});
});
s.addText('Уличная еда: шаурма, выпечка, салаты, напитки. Две смены в день, '
  + 'десять рабочих мест, оборот людей высокий — типичная сеть быстрого '
  + 'питания в регионе.',
  {x: M, y: 3.72, w: CW, h: 0.6, fontFace: F, fontSize: 14, color: INK,
   isTextBox: true, margin: 0});
s.addNotes('Мы не стартап без выручки. Мы работающая сеть, которая построила '
  + 'инструмент для себя и увидела, что он нужен всем вокруг.');

/* 3 ── проблема ──────────────────────────────────────────────────── */
s = p.addSlide();
title(s, 'Проблема', 'Стандарт есть. Исполнение — не измеряется');
s.addChart(p.ChartType.bar, [{
  name: 'Отзывы',
  labels: ['Ошибка сборки', 'Работа не по чеку', 'Сервис',
           'Качество', 'Работа не по ТТК', 'Пищевая безопасность'],
  values: [4, 9, 17, 27, 31, 39],
}], {
  x: M, y: 1.6, w: 5.5, h: 3.4,
  barDir: 'bar', showTitle: false, showLegend: false,
  showValue: true, dataLabelPosition: 'outEnd', dataLabelFontFace: F,
  dataLabelFontSize: 11, dataLabelColor: INK,
  chartColors: [AMB2],
  catAxisLabelFontFace: F, catAxisLabelFontSize: 11, catAxisLabelColor: INK,
  valAxisHidden: true, valGridLine: {style: 'none'},
  catGridLine: {style: 'none'}, catAxisLineShow: false,
  barGapWidthPct: 45, valAxisMaxVal: 46,
});
s.addText('143', {x: 6.35, y: 1.62, w: 3.1, h: 0.72, fontFace: F,
  fontSize: 44, bold: true, color: INK, isTextBox: true, margin: 0});
s.addText('отзыва гостя с декабря 2025 по двум точкам',
  {x: 6.35, y: 2.3, w: 3.1, h: 0.5, fontFace: F, fontSize: 12, color: INK2,
   isTextBox: true, margin: 0});
s.addShape(p.ShapeType.roundRect, {x: 6.35, y: 2.92, w: 3.1, h: 1.0,
  fill: {color: INK}, rectRadius: 0.08});
s.addText([{text: '70 из 143 — ', options: {bold: true, color: AMB}},
  {text: 'это пищевая безопасность и работа не по техкарте. Половина всех '
   + 'жалоб.', options: {color: PAPER}}],
  {x: 6.5, y: 3.02, w: 2.8, h: 0.8, fontFace: F, fontSize: 12.5,
   valign: 'middle', isTextBox: true, margin: 0});
s.addText([{text: '53 отзыва пришли публично, в Instagram. ',
  options: {bold: true}},
  {text: 'Треть жалоб видит не управляющий, а рынок.', options: {}}],
  {x: 6.35, y: 4.02, w: 3.1, h: 0.8, fontFace: F, fontSize: 12.5, color: INK,
   isTextBox: true, margin: 0});
foot(s, 'Источник: собственный журнал отзывов «Ромашки», 143 записи, '
  + 'декабрь 2025 — август 2026');
s.addNotes('Это наши собственные данные, не отраслевая оценка. Половина всех '
  + 'жалоб — не про вкус и не про сервис, а про то, что смена отошла '
  + 'от стандарта.');

/* 4 ── почему ────────────────────────────────────────────────────── */
s = p.addSlide();
title(s, 'Почему так происходит', 'Четыре разрыва между стандартом и сменой');
const why = [
  ['Стандарт лежит отдельно от работы',
   'Регламенты и техкарты написаны. Смена работает по памяти: открыть папку '
   + 'посреди часа пик невозможно.'],
  ['Исполнение не оставляет следа',
   'Была ли проверена температура фритюра в 9 утра? Ответа нет ни у кого — '
   + 'ни «да», ни «нет».'],
  ['Ответственность теряется на пересменке',
   'Вторая смена находит грязную станцию. Кто виноват — выяснить нечем, '
   + 'и никто не отвечает.'],
  ['О нарушении сообщает гость',
   'Управляющий узнаёт о проблеме из отзыва в Instagram — когда исправлять '
   + 'уже поздно.'],
];
why.forEach((w, i) => {
  const y = 1.62 + i * 0.92;
  num(s, i + 1, M, y + 0.06);
  s.addText(w[0], {x: M + 0.62, y: y, w: CW - 0.62, h: 0.3, fontFace: F,
    fontSize: 15, bold: true, color: INK, isTextBox: true, margin: 0});
  s.addText(w[1], {x: M + 0.62, y: y + 0.31, w: CW - 0.62, h: 0.5, fontFace: F,
    fontSize: 12.5, color: INK2, isTextBox: true, margin: 0});
});
s.addNotes('Ни один из четырёх разрывов не лечится ещё одним регламентом. '
  + 'Их лечит инструмент в руках смены.');

/* 5 ── решение ───────────────────────────────────────────────────── */
s = p.addSlide();
s.background = {color: INK};
title(s, 'Что мы построили', 'Telegram-бот и мини-приложение на телефоне, '
  + 'который уже есть у каждого сотрудника', true);
const four = [
  ['Явка', 'Приход и уход только с подтверждённой геометкой. Часы считаются '
   + 'по факту, а не по памяти.'],
  ['Чек-листы', 'Стандарт разложен по рабочим местам и этапам смены. Пункт, '
   + 'срок, фото по требованию.'],
  ['Обучение', 'Регламент открывается прямо из пункта, знание проверяется '
   + 'вопросами, подпись фиксируется.'],
  ['Проверка', 'Сданный лист уходит руководителю. Расхождение превращается '
   + 'в задачу, а не в разговор.'],
];
four.forEach((f, i) => {
  const x = M + (i % 2) * (CW / 2), y = 1.78 + Math.floor(i / 2) * 1.42;
  s.addShape(p.ShapeType.ellipse, {x: x, y: y + 0.02, w: 0.34, h: 0.34,
    fill: {color: AMB}});
  s.addText(f[0], {x: x + 0.48, y: y, w: CW / 2 - 0.7, h: 0.34, fontFace: F,
    fontSize: 17, bold: true, color: PAPER, isTextBox: true, margin: 0});
  s.addText(f[1], {x: x + 0.48, y: y + 0.38, w: CW / 2 - 0.7, h: 0.85,
    fontFace: F, fontSize: 12.5, color: 'BFC2C6', isTextBox: true, margin: 0});
});
s.addNotes('Ни одного нового устройства и ни одной установки: Telegram уже '
  + 'стоит у всех, приложение открывается внутри него.');

/* 6 ── объём ─────────────────────────────────────────────────────── */
s = p.addSlide();
title(s, 'Что уже оцифровано', 'Прототип работает в ежедневной эксплуатации');
const nums = [
  ['54', 'чек-листа'], ['896', 'пунктов стандарта'], ['10', 'рабочих мест'],
  ['46', 'регламентов'], ['16', 'тренингов с проверкой'], ['28', 'журналов событий'],
];
nums.forEach((n, i) => {
  const x = M + (i % 3) * (CW / 3), y = 1.72 + Math.floor(i / 3) * 1.14;
  s.addText(n[0], {x: x, y: y, w: CW / 3 - 0.2, h: 0.66, fontFace: F,
    fontSize: 40, bold: true, color: AMB2, isTextBox: true, margin: 0});
  s.addText(n[1], {x: x, y: y + 0.66, w: CW / 3 - 0.2, h: 0.32, fontFace: F,
    fontSize: 13.5, color: INK, isTextBox: true, margin: 0});
});
s.addShape(p.ShapeType.roundRect, {x: M, y: 4.18, w: CW, h: 0.82,
  fill: {color: WASH}, line: {color: LINE, width: 0.75}, rectRadius: 0.08});
s.addText('Каждое рабочее место закрывает четыре листа за день: открытие · '
  + 'передача · приём · закрытие. Стандарт описан данными, а не кодом — '
  + 'новая точка добавляется без программиста.',
  {x: M + 0.2, y: 4.24, w: CW - 0.4, h: 0.7, fontFace: F, fontSize: 12.5,
   color: INK, valign: 'middle', isTextBox: true, margin: 0});
s.addNotes('896 пунктов — это разложенный на действия стандарт, который '
  + 'раньше существовал как папка документов.');

/* 7 ── передача смены ────────────────────────────────────────────── */
s = p.addSlide();
title(s, 'Ключевой узел: передача смены',
  'Место, где обычно теряется ответственность');
const step = [
  ['Открытие', 'Первая смена принимает точку'],
  ['Передача', 'Сдающий фиксирует состояние станции'],
  ['Приём', 'Принимающий проверяет то же самое'],
  ['Закрытие', 'Вторая смена закрывает точку'],
];
step.forEach((t, i) => {
  const x = M + i * (CW / 4);
  s.addShape(p.ShapeType.roundRect, {x: x + 0.03, y: 1.66, w: CW / 4 - 0.24,
    h: 1.40, fill: {color: i % 2 ? SNOW : WASH},
    line: {color: LINE, width: 0.75}, rectRadius: 0.08});
  num(s, i + 1, x + 0.19, 1.80, true);
  s.addText(t[0], {x: x + 0.17, y: 2.24, w: CW / 4 - 0.5, h: 0.28, fontFace: F,
    fontSize: 14.5, bold: true, color: INK, isTextBox: true, margin: 0});
  s.addText(t[1], {x: x + 0.17, y: 2.52, w: CW / 4 - 0.5, h: 0.48, fontFace: F,
    fontSize: 10.5, color: INK2, isTextBox: true, margin: 0});
  if (i < 3) s.addText('→', {x: x + CW / 4 - 0.24, y: 2.12, w: 0.24, h: 0.3,
    fontFace: F, fontSize: 16, color: AMB2, align: 'center', isTextBox: true,
    margin: 0});
});
s.addShape(p.ShapeType.roundRect, {x: M, y: 3.2, w: CW, h: 1.34,
  fill: {color: INK}, rectRadius: 0.08});
s.addText('Расхождение нельзя оставить без разбора',
  {x: M + 0.24, y: 3.34, w: CW - 0.48, h: 0.32, fontFace: F, fontSize: 15,
   bold: true, color: AMB, isTextBox: true, margin: 0});
s.addText('Если принимающий отметил пункт как невыполненный, система не даст '
  + 'закрыть лист, пока не сказано, чья это вина: первой смены, второй или '
  + 'внешняя причина. Из внешней причины автоматически рождается задача '
  + 'на починку. Так «не сошлось» перестаёт быть разговором и становится '
  + 'записью с адресатом.',
  {x: M + 0.24, y: 3.68, w: CW - 0.48, h: 0.76, fontFace: F, fontSize: 12.5,
   color: 'C7CACE', isTextBox: true, margin: 0});
s.addNotes('Это главное отличие от чек-листа в тетради: тетрадь фиксирует '
  + 'галочку, а система заставляет назвать ответственного.');

/* 8 ── доказательство ────────────────────────────────────────────── */
s = p.addSlide();
title(s, 'Полевые тесты', '29–30 августа 2026 · шесть сотрудников · две точки');
const proof = [
  ['15', 'листов сдано за два дня'],
  ['728', 'из 729 пунктов отмечено'],
  ['0', 'сбоев системы'],
];
proof.forEach((f, i) => {
  const x = M + i * (CW / 3);
  s.addText(f[0], {x: x, y: 1.62, w: CW / 3 - 0.2, h: 0.66, fontFace: F,
    fontSize: 40, bold: true, color: AMB2, isTextBox: true, margin: 0});
  s.addText(f[1], {x: x, y: 2.26, w: CW / 3 - 0.24, h: 0.44, fontFace: F,
    fontSize: 13, color: INK, isTextBox: true, margin: 0});
});
s.addText('Но главное — не эти цифры, а то, что система увидела:',
  {x: M, y: 2.86, w: CW, h: 0.3, fontFace: F, fontSize: 14, bold: true,
   color: INK, isTextBox: true, margin: 0});
const saw = [
  'Опоздания на 92 и на 17 минут — раньше их никто не считал',
  'Шесть листов сданы позже срока: открытие в 10:13–12:25 при норме 09:30',
  'Лист из 12 пунктов заполнен за 0,2 минуты — пройти станцию за это время '
  + 'физически нельзя',
];
saw.forEach((t, i) => {
  s.addShape(p.ShapeType.ellipse, {x: M + 0.02, y: 3.3 + i * 0.5, w: 0.14,
    h: 0.14, fill: {color: AMB}});
  s.addText(t, {x: M + 0.34, y: 3.22 + i * 0.5, w: CW - 0.34, h: 0.42,
    fontFace: F, fontSize: 12.5, color: INK, isTextBox: true, margin: 0});
});
foot(s, 'Последняя строка — не сбой, а находка: система показала формальное '
  + 'заполнение, которого без неё не видно.');
s.addNotes('Мы честно показываем и то, что нашли против себя. Именно ради '
  + 'этого инструмент и строится.');

/* 9 ── соответствие ──────────────────────────────────────────────── */
s = p.addSlide();
title(s, 'Прозрачность и соответствие',
  'Что становится проверяемым, а не декларируемым');
const comp = [
  ['Пищевая безопасность',
   'Температуры, сроки, маркировка и чистота оборудования — пункты с фото '
   + 'и временем. Основа для внедрения ХАССП.'],
  ['Трудовые отношения',
   'Часы считаются по фактическому приходу и уходу с подтверждением места. '
   + 'Честная база для оплаты и для табеля.'],
  ['Обучение персонала',
   'Регламент открывается из рабочего пункта, знание проверяется вопросами, '
   + 'ознакомление подписывается в системе.'],
  ['Аудиторский след',
   'Кто, когда, что отметил и кто подтвердил. Своё заполнение подтвердить '
   + 'нельзя — проверяет тот, кто выше.'],
];
comp.forEach((c, i) => {
  const x = M + (i % 2) * (CW / 2 + 0.1);
  const y = 1.68 + Math.floor(i / 2) * 1.6;
  s.addShape(p.ShapeType.roundRect, {x: x, y: y, w: CW / 2 - 0.1, h: 1.42,
    fill: {color: WASH}, line: {color: LINE, width: 0.75}, rectRadius: 0.08});
  s.addText(c[0], {x: x + 0.2, y: y + 0.16, w: CW / 2 - 0.5, h: 0.3,
    fontFace: F, fontSize: 14.5, bold: true, color: INK, isTextBox: true,
    margin: 0});
  s.addText(c[1], {x: x + 0.2, y: y + 0.5, w: CW / 2 - 0.5, h: 0.82,
    fontFace: F, fontSize: 12, color: INK2, isTextBox: true, margin: 0});
});
s.addNotes('Для банка развития это ключевое: соответствие перестаёт быть '
  + 'обещанием и становится выгружаемыми данными.');

/* 10 ── масштаб ──────────────────────────────────────────────────── */
s = p.addSlide();
title(s, 'Почему это масштабируется',
  'Продукт отделён от конкретной точки с первого дня');
s.addShape(p.ShapeType.roundRect, {x: M, y: 1.66, w: 4.5, h: 3.0,
  fill: {color: WASH}, line: {color: LINE, width: 0.75}, rectRadius: 0.08});
s.addText('Устройство', {x: M + 0.24, y: 1.82, w: 4.0, h: 0.3, fontFace: F,
  fontSize: 15, bold: true, color: INK, isTextBox: true, margin: 0});
s.addText([
  {text: 'Стандарт описан данными, а не кодом — чек-лист меняет управляющий, '
   + 'не программист', options: {bullet: true, breakLine: true}},
  {text: 'Новая точка — строка в таблице: свои сроки, свои координаты, '
   + 'свои люди', options: {bullet: true, breakLine: true}},
  {text: 'Роли и права уже разделены: сотрудник, управляющий, директор',
   options: {bullet: true, breakLine: true}},
  {text: 'Работает на телефоне сотрудника, без закупки оборудования',
   options: {bullet: true}},
], {x: M + 0.24, y: 2.18, w: 4.0, h: 2.3, fontFace: F, fontSize: 12.5,
    color: INK2, paraSpaceAfter: 8, isTextBox: true, margin: 0});
const way = [
  ['Сегодня', '2 точки, 29 человек — собственная сеть как полигон'],
  ['Шаг 1', 'Вся сеть «Ромашки», включая цех и доставку'],
  ['Шаг 2', 'Продукт для сетей общепита Таджикистана и Центральной Азии'],
  ['Шаг 3', 'Франшизная модель: стандарт передаётся вместе с инструментом'],
];
way.forEach((w, i) => {
  const y = 1.72 + i * 0.76;
  s.addShape(p.ShapeType.ellipse, {x: 5.42, y: y + 0.08, w: 0.16, h: 0.16,
    fill: {color: i ? AMB : INK}});
  if (i < 3) s.addShape(p.ShapeType.line, {x: 5.50, y: y + 0.26, w: 0, h: 0.5,
    line: {color: LINE, width: 1.25}});
  s.addText(w[0], {x: 5.94, y: y, w: 3.5, h: 0.28, fontFace: F, fontSize: 14,
    bold: true, color: INK, isTextBox: true, margin: 0});
  s.addText(w[1], {x: 5.94, y: y + 0.28, w: 3.55, h: 0.44, fontFace: F,
    fontSize: 11.5, color: INK2, isTextBox: true, margin: 0});
});
s.addNotes('Мы строили не «приложение для Ромашки», а систему, в которой '
  + 'Ромашка — первый клиент.');

/* 11 ── просим ───────────────────────────────────────────────────── */
s = p.addSlide();
title(s, 'Что просим профинансировать',
  'Прототип написан одним человеком и работает. Дальше нужна инженерная '
  + 'команда');
const need = [
  ['Промышленная база данных',
   'Сегодня данные живут в Google Sheets: это дало скорость, но упирается '
   + 'в предел запросов и не выдержит десятки точек.'],
  ['Мобильное приложение',
   'Работа без сети и синхронизация: на точке связь пропадает, а смена '
   + 'не должна останавливаться.'],
  ['Контроль качества по фото',
   'Автоматическая сверка снимка с эталоном — чтобы «чисто» подтверждалось '
   + 'не только галочкой.'],
  ['Интеграции',
   'Касса, складской учёт, зарплатный контур: списания и остатки должны '
   + 'приходить сами.'],
  ['Безопасность и аудит',
   'Профессиональный разбор прав доступа, шифрование, независимый аудит '
   + 'персональных данных.'],
  ['Локализация',
   'Русский, таджикский, английский — без этого продукт не выходит за '
   + 'пределы одной сети.'],
];
need.forEach((n, i) => {
  const x = M + (i % 2) * (CW / 2 + 0.1);
  const y = 1.78 + Math.floor(i / 2) * 1.06;
  s.addShape(p.ShapeType.ellipse, {x: x, y: y + 0.04, w: 0.14, h: 0.14,
    fill: {color: AMB}});
  s.addText(n[0], {x: x + 0.3, y: y - 0.04, w: CW / 2 - 0.42, h: 0.28,
    fontFace: F, fontSize: 13.5, bold: true, color: INK, isTextBox: true,
    margin: 0});
  s.addText(n[1], {x: x + 0.3, y: y + 0.24, w: CW / 2 - 0.42, h: 0.7,
    fontFace: F, fontSize: 11, color: INK2, isTextBox: true, margin: 0});
});
foot(s, 'Запрашиваемая сумма и срок — на следующем слайде');
s.addNotes('Важно проговорить: мы просим не на проверку идеи. Идея проверена '
  + 'на своей сети. Мы просим на инженерию.');

/* 12 ── итог ─────────────────────────────────────────────────────── */
s = p.addSlide();
s.background = {color: INK};
title(s, 'Статус и просьба', null, true);
const st = [
  ['Сделано', 'Работающий прототип в ежедневной эксплуатации на двух точках. '
   + 'Полевые тесты пройдены, стандарт оцифрован полностью.'],
  ['Вложено', 'Собственные силы и время. Инфраструктура — облачный хостинг '
   + 'и таблицы, расходы минимальны.'],
  ['Нужно', 'Инженерная команда на 12 месяцев: разработка, мобильное '
   + 'приложение, безопасность, интеграции.'],
];
st.forEach((x, i) => {
  const y = 1.5 + i * 1.02;
  s.addText(x[0], {x: M, y: y, w: 1.5, h: 0.3, fontFace: F, fontSize: 15,
    bold: true, color: AMB, isTextBox: true, margin: 0});
  s.addText(x[1], {x: M + 1.6, y: y - 0.02, w: CW - 1.6, h: 0.8, fontFace: F,
    fontSize: 13, color: 'C7CACE', isTextBox: true, margin: 0});
});
s.addShape(p.ShapeType.roundRect, {x: M, y: 4.5, w: CW, h: 0.62,
  fill: {color: AMB}, rectRadius: 0.08});
s.addText('Запрашиваем ____________ на 12 месяцев · контакт: '
  + '____________________',
  {x: M + 0.24, y: 4.5, w: CW - 0.48, h: 0.62, fontFace: F, fontSize: 14,
   bold: true, color: INK, valign: 'middle', isTextBox: true, margin: 0});
s.addNotes('Сумму и контакт вписать перед показом.');

p.writeFile({fileName: process.argv[2]}).then(f => console.log('готово:', f));
