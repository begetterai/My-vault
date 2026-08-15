#!/usr/bin/env python3
"""Навигатор операционного отдела «Ромашка Стрит Фуд».
Статусы, ссылки на живые документы, фильтры. Times New Roman (правило Азиза)."""
import io, html as H

OUT = "/tmp/claude-0/-home-user-My-vault/606dd1b1-a624-5ef2-a06e-c6a894e680ba/scratchpad/ops-navigator.html"
D = "https://docs.google.com/document/d/"

# статус: yes = есть · wip = в очереди/частично · no = нет · ask = уточнить
BLOCKS = [
 (1, "Роли и управление", "Влияет на все KPI", [
   ("Оргструктура операций", "yes", D+"1AgGban4JJ-io6V64O4_nJmdpyxYvqkCWXgYcVeCC31E", "", 0),
   ("SOP — Управляющий (V.1)", "yes", D+"10vfIchEJ0Qklc7QYq7o-q7HaYtrHNNaWJA6Wxdwf854", "", 0),
   ("SOP — Управляющий ЗБ, Владимир", "yes", D+"1MCU_lKa_lpCPh5CdLWmZcMU6EAGzU8pxiQm6Z2aLfXc", "", 0),
   ("SOP — Управляющий ОВИР, Дилчу", "yes", D+"1hmVutQPQHuVbvxPX9EUlQsVSwKw900puEUaIPHxZjOo", "", 0),
   ("Брифинг с управляющими", "yes", D+"1wr7hBGHmboSezdsYeNHDkzIEMm_juzfOfinNKMB6Efs", "май 2026", 0),
   ("Должностные карты — 6 шт.", "no", "", "шаг 2 каркаса: управляющий, старший смены, повар, кассир, курьер, уборщик", 0),
   ("SOP — Старший смены", "no", "", "", 0),
   ("SOP — Старший повар", "wip", "", "в очереди по шагу 8", 0),
   ("KPI и премирование по ролям", "no", "", "шаг 5 — KPI без бонуса не работает", 0),
   ("Ритмы: планёрка · 1-to-1 · отчёты", "wip", "", "планёрка пн есть, 1-to-1 нет", 0),
 ]),
 (2, "Смена — ежедневная операционка", "Время обслуживания · Выручка на точку", [
   ("Чек-лист открытия смены", "wip", "", "в задачах #p1 с июля, не сделан", 1),
   ("Чек-лист закрытия смены", "wip", "", "в задачах #p1 с июля, не сделан", 1),
   ("Кассовая дисциплина и инкассация", "wip", "", "ЗБ ушёл в минус по кассе на 127 567 — дыра уже стоила денег", 1),
   ("Регламент кассира — касса и Poster", "yes", D+"1AsQ9xAaiR6oRHdCleG6RvxzF3qFBxYjsvFhmWtVz9xE", "V.1", 0),
   ("Передача смены", "no", "", "", 0),
   ("Стандарт обслуживания гостя", "no", "", "скрипт + норматив времени выдачи", 0),
   ("Работа с жалобой гостя", "no", "", "", 0),
   ("Журнал происшествий", "no", "", "", 0),
 ]),
 (3, "Люди", "Влияет на все KPI через текучку", [
   ("Дисциплинарная сетка", "yes", "", "в Vault", 0),
   ("Правило телефонов", "yes", "", "в Vault", 0),
   ("Онбординг — день 1, правила под подпись", "wip", "", "в очереди по шагу 8", 1),
   ("Профиль должности + чек-лист собеседования", "no", "", "шаг 4", 0),
   ("Стажировка 3 дня + наставник", "no", "", "шаг 4", 0),
   ("Испытательный срок и светофор", "no", "", "шаг 9", 0),
   ("Аттестация раз в квартал", "no", "", "шаг 9", 0),
   ("Трудовые: договор · матответственность · табель · медкнижки", "ask", "", "не нашёл ни в Vault, ни в Drive — уточнить", 0),
 ]),
 (4, "Кухня и продукт", "Фуд-кост · Качество блюд", [
   ("ТТК — блюда и полуфабрикаты, ~68 шт.", "yes", "", "41 на блюда + 27 на полуфабрикаты", 0),
   ("Аудит меню 2026", "yes", D+"1weeXMF9ETFzLh7sQNRHoIamL3rpe4brpaX2ObtjM03k", "", 0),
   ("Стандарт фритюра — замена масла", "no", "", "прямо бьёт по фуд-косту и вкусу", 1),
   ("Санитария: график уборки + температурный журнал", "no", "", "", 0),
   ("Фото-эталон сборки блюда", "no", "", "без него ТТК не соблюдается", 0),
   ("План заготовок на день", "no", "", "", 0),
   ("Маркировка и сроки годности", "no", "", "", 0),
   ("Товарное соседство и хранение", "no", "", "", 0),
 ]),
 (5, "Товародвижение", "Фуд-кост", [
   ("Тренинг по инвентаризации", "yes", D+"1T5tnXq-j8D6axpd4tu5VsK8pPbN3bkRxSloGFSOsg-U", "V.1", 0),
   ("Тренинг по списаниям", "yes", D+"1dcUP_-Tlzq11yUgGrJ_uzz33ZjpH_grAFQVHiux9GfA", "V.1", 0),
   ("Приём поставки", "wip", "", "в очереди по шагу 8", 0),
   ("Регламент инвентаризации", "no", "", "тренинг есть, регламента нет", 0),
   ("Регламент списаний", "no", "", "тренинг есть, регламента нет", 0),
   ("Закупка на базаре", "no", "", "шаг 3", 0),
   ("Реестр поставщиков и цен", "no", "", "", 0),
   ("Претензия поставщику", "no", "", "", 0),
 ]),
 (6, "Качество и контроль", "Оценки тайных покупателей · Нарушения", [
   ("Реестр нарушений и разбор", "yes", "", "в Vault — анализ КП", 0),
   ("Анкета тайного гостя", "no", "", "это твой KPI, а инструмента нет", 1),
   ("Чек-лист визита собственника", "no", "", "шаг 7 — визит 1×/нед без предупреждения", 0),
   ("Регламент просмотра камер", "no", "", "шаг 7 — 3×/нед по 15 мин", 0),
 ]),
 (7, "Безопасность и соответствие", "Риск остановки точки", [
   ("Охрана труда — фритюр, ножи, газ, электро", "no", "", "дешевле всего закрыть, дороже всего игнорировать", 1),
   ("Пожарная безопасность", "no", "", "", 1),
   ("Контроль медкнижек", "no", "", "", 0),
   ("Действия при проверке органов", "no", "", "", 0),
   ("Действия при ЧП — травма, свет, отравление", "no", "", "", 0),
 ]),
 (8, "Оборудование и запуск точки", "Масштабирование до 6 точек", [
   ("Реестр оборудования", "yes", "", "в реестре активов отчёта AP", 0),
   ("Чек-лист открытия новой точки", "no", "", "ОВИР: 1,1 млн вложений и 22 мес окупаемости против 6,4 мес у Ромашки", 1),
   ("Комплектация точки — оборудование и инвентарь", "no", "", "", 0),
   ("График ТО и действия при поломке", "no", "", "", 0),
 ]),
 (9, "Учёт и Poster", "Фуд-кост · Выручка на точку", [
   ("Категории расходов в Poster", "yes", D+"1pFqgbDmThuQF2qvtG_oqMY7BrNd81rt-bKynycv7g4s", "V.1", 0),
   ("Протокол проверки транзакций", "yes", D+"1UBMAN45H4vxwMTV9i-m8g4bx7scIej_b89sONWr1Ch0", "V.1", 0),
   ("Архитектура Poster и логика P&L", "yes", D+"1w98KIgsHP3twOB5xS_2HeL9RW2tttaElRJtyRnf-m68", "", 0),
   ("Правила — Super P&L", "yes", D+"1ybEYLMeC43z0g7WD38xI4RR2ENAoY8HQGQGjcqGGmN0", "", 0),
   ("Правила — Дневной трекер", "yes", D+"11VuNq-xUKU3E16l2OHNiPPGPvnpooPOo_XQgvDcU22I", "", 0),
   ("Расходы вносить в день оплаты", "wip", "", "шаг 3 — иначе P&L слепой", 0),
   ("SOP по вводу транзакций Alif / DC", "no", "", "из открытых задач", 0),
 ]),
]

LABEL = {"yes":"есть", "wip":"в работе", "no":"нет", "ask":"уточнить"}

def build():
    all_items = [(b[0], it) for b in BLOCKS for it in b[3]]
    n_all = len(all_items)
    n_yes = sum(1 for _, i in all_items if i[1] == "yes")
    n_wip = sum(1 for _, i in all_items if i[1] == "wip")
    n_no  = sum(1 for _, i in all_items if i[1] == "no")
    n_ask = sum(1 for _, i in all_items if i[1] == "ask")
    n_cri = sum(1 for _, i in all_items if i[4])
    pct = round(n_yes / n_all * 100)

    w = io.StringIO().write
    o = io.StringIO()
    w = o.write

    w('''<title>Операционный отдел — навигатор</title>
<style>
:root{
 --ground:#FAF7F1; --surface:#FFFFFF; --surface-2:#F4EFE5;
 --ink:#1F2A37; --body:#3D444E; --muted:#7A736A; --hair:#DED6C7;
 --accent:#B08D3E; --accent-deep:#8C6D28; --accent-soft:#EFE3C7;
 --crit:#A33B2C; --crit-soft:#F5E2DD;
 --pos:#3D6B50; --pos-soft:#DFEAE2;
 --wip:#8C6D28; --wip-soft:#F2E7CC;
 --ask:#4A6076; --ask-soft:#E1E8ED;
 --navy:#1F2A37;--on-navy:#F3EEE0;--on-navy-dim:#A9B0BA;
 --shadow:0 1px 2px rgba(31,42,55,.05),0 8px 22px -14px rgba(31,42,55,.16);
 --f:"Times New Roman",Times,serif;
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
 --ground:#12161C; --surface:#191F27; --surface-2:#222932;
 --ink:#F1ECE1; --body:#C7C2B8; --muted:#8D877D; --hair:#2E3742;
 --accent:#D0A94F; --accent-deep:#E0BC6A; --accent-soft:#3A3222;
 --crit:#D4705E; --crit-soft:#3A2420;
 --pos:#79AE8D; --pos-soft:#1E2E25;
 --wip:#D0A94F; --wip-soft:#332C1B;
 --ask:#8FA6BC; --ask-soft:#222B33;
 --navy:#0D1117;--on-navy:#F1ECE1;--on-navy-dim:#8D949E;
 --shadow:0 1px 2px rgba(0,0,0,.4),0 8px 22px -14px rgba(0,0,0,.6);
}}
:root[data-theme="dark"]{
 --ground:#12161C; --surface:#191F27; --surface-2:#222932;
 --ink:#F1ECE1; --body:#C7C2B8; --muted:#8D877D; --hair:#2E3742;
 --accent:#D0A94F; --accent-deep:#E0BC6A; --accent-soft:#3A3222;
 --crit:#D4705E; --crit-soft:#3A2420;
 --pos:#79AE8D; --pos-soft:#1E2E25;
 --wip:#D0A94F; --wip-soft:#332C1B;
 --ask:#8FA6BC; --ask-soft:#222B33;
 --navy:#0D1117;--on-navy:#F1ECE1;--on-navy-dim:#8D949E;
 --shadow:0 1px 2px rgba(0,0,0,.4),0 8px 22px -14px rgba(0,0,0,.6);
}
*{box-sizing:border-box}
[hidden]{display:none !important}   /* иначе display:flex у li перебивает атрибут hidden */
body{margin:0;background:var(--ground);color:var(--body);font-family:var(--f);
 font-size:17px;line-height:1.55;-webkit-font-smoothing:antialiased}
.wrap{max-width:1020px;margin:0 auto;padding:0 22px}
h1,h2,h3{font-family:var(--f);color:var(--ink);margin:0;font-weight:700;text-wrap:balance}

/* шапка */
header{background:var(--navy);color:var(--on-navy);padding:34px 0 26px;border-bottom:3px solid var(--accent)}
.eyebrow{font-size:11.5px;letter-spacing:.16em;text-transform:uppercase;color:var(--accent);
 font-weight:700;margin-bottom:10px}
header h1{color:var(--on-navy);font-size:clamp(25px,4vw,36px);line-height:1.12;margin-bottom:8px}
header p{margin:0;color:var(--on-navy-dim);font-size:15.5px;max-width:64ch}
.bar{height:9px;background:rgba(255,255,255,.14);border-radius:2px;margin-top:20px;overflow:hidden;display:flex}
.bar i{display:block;height:100%}
.bar .b-yes{background:#79AE8D}
.bar .b-wip{background:var(--accent)}
.bar .b-no{background:rgba(255,255,255,.16)}
.legend{display:flex;flex-wrap:wrap;gap:16px;margin-top:11px;font-size:13.5px;color:var(--on-navy-dim)}
.legend b{color:var(--on-navy)}

/* фильтры */
.filters{position:sticky;top:0;z-index:20;background:var(--ground);
 border-bottom:1px solid var(--hair);padding:12px 0}
.fr{display:flex;flex-wrap:wrap;gap:8px}
.fbtn{font-family:var(--f);font-size:14.5px;padding:6px 14px;border:1px solid var(--hair);
 background:var(--surface);color:var(--body);border-radius:2px;cursor:pointer;
 display:inline-flex;align-items:center;gap:7px}
.fbtn:hover{border-color:var(--accent)}
.fbtn:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.fbtn[aria-pressed="true"]{background:var(--navy);color:var(--on-navy);border-color:var(--navy)}
.fbtn .c{font-size:12.5px;opacity:.7}

/* блоки */
main{padding:26px 0 60px}
.block{background:var(--surface);border:1px solid var(--hair);border-radius:3px;
 margin-bottom:16px;box-shadow:var(--shadow);overflow:hidden}
.bh{display:flex;align-items:center;gap:13px;padding:15px 20px;background:var(--surface-2);
 border-bottom:1px solid var(--hair);flex-wrap:wrap}
.bnum{font-size:13px;font-weight:700;color:var(--navy);background:var(--accent);
 width:26px;height:26px;display:grid;place-items:center;border-radius:2px;flex:none}
.bh h2{font-size:19px;flex:1;min-width:180px;line-height:1.25}
.kpi{font-size:12.5px;color:var(--accent-deep);background:var(--accent-soft);
 padding:4px 10px;border-radius:2px;white-space:nowrap}
.bcount{font-size:13px;color:var(--muted);white-space:nowrap}
ul{list-style:none;margin:0;padding:0}
li{display:flex;align-items:flex-start;gap:12px;padding:11px 20px;
 border-bottom:1px solid var(--hair)}
li:last-child{border-bottom:none}
li.crit{background:var(--crit-soft)}
.chip{font-size:11.5px;font-weight:700;padding:3px 9px;border-radius:2px;flex:none;
 min-width:74px;text-align:center;margin-top:2px}
.s-yes{background:var(--pos-soft);color:var(--pos)}
.s-wip{background:var(--wip-soft);color:var(--wip)}
.s-no{background:var(--surface-2);color:var(--muted);border:1px solid var(--hair)}
.s-ask{background:var(--ask-soft);color:var(--ask)}
.itxt{flex:1;min-width:0}
.iname{color:var(--ink);font-weight:600}
li.no-doc .iname{font-weight:400;color:var(--body)}
.inote{font-size:13.5px;color:var(--muted);margin-top:2px}
li.crit .inote{color:var(--crit)}
.flag{color:var(--crit);font-weight:700;margin-right:5px}
a.doc{color:var(--accent-deep);text-decoration:none;font-size:13.5px;white-space:nowrap;
 border-bottom:1px solid var(--accent-soft);flex:none;margin-top:3px}
a.doc:hover{border-bottom-color:var(--accent-deep)}
a.doc:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.empty{padding:16px 20px;color:var(--muted);font-size:14.5px}

/* итог */
.summary{background:var(--navy);color:var(--on-navy);border-radius:3px;padding:26px 26px 22px;
 margin-top:26px;border-left:4px solid var(--accent)}
.summary h3{color:var(--on-navy);font-size:19px;margin-bottom:14px}
.summary ol{margin:0;padding-left:20px}
.summary li{display:list-item;padding:0 0 10px;border:none;color:var(--on-navy-dim);font-size:15.5px}
.summary li b{color:var(--on-navy)}
.note{background:var(--surface-2);border:1px solid var(--hair);border-radius:3px;
 padding:18px 20px;margin-top:18px;font-size:15px}
.note b{color:var(--ink)}
@media print{.filters{display:none}.block{page-break-inside:avoid}}
</style>

<header><div class="wrap">
 <div class="eyebrow">Ромашка Стрит Фуд · Операционный департамент</div>
 <h1>Навигатор операционного отдела</h1>
 <p>Все документы, которые должны быть у операций — что есть, что в работе, чего нет.
    Кликай по ссылкам: существующие документы открываются сразу.</p>
''')
    w(f'''<div class="bar">
   <i class="b-yes" style="width:{n_yes/n_all*100:.1f}%"></i>
   <i class="b-wip" style="width:{n_wip/n_all*100:.1f}%"></i>
   <i class="b-no" style="width:{(n_no+n_ask)/n_all*100:.1f}%"></i>
 </div>
 <div class="legend">
   <span><b>{n_yes}</b> есть</span>
   <span><b>{n_wip}</b> в работе</span>
   <span><b>{n_no}</b> нет</span>
   <span><b>{n_ask}</b> уточнить</span>
   <span>Готовность: <b>{pct}%</b> из {n_all} документов</span>
 </div>
</div></header>

<div class="filters"><div class="wrap"><div class="fr">
  <button class="fbtn" data-f="all" aria-pressed="true">Все <span class="c">{n_all}</span></button>
  <button class="fbtn" data-f="yes" aria-pressed="false">Есть <span class="c">{n_yes}</span></button>
  <button class="fbtn" data-f="wip" aria-pressed="false">В работе <span class="c">{n_wip}</span></button>
  <button class="fbtn" data-f="no" aria-pressed="false">Нет <span class="c">{n_no}</span></button>
  <button class="fbtn" data-f="crit" aria-pressed="false">Критично <span class="c">{n_cri}</span></button>
</div></div></div>

<main><div class="wrap">''')

    for num, title, kpi, items in BLOCKS:
        yes = sum(1 for i in items if i[1] == "yes")
        w(f'''<section class="block" data-block="{num}">
   <div class="bh">
     <span class="bnum">{num}</span>
     <h2>{H.escape(title)}</h2>
     <span class="kpi">{H.escape(kpi)}</span>
     <span class="bcount"><b class="bc">{yes}</b>/{len(items)}</span>
   </div>
   <ul>''')
        for name, st, link, note, crit in items:
            cls = f"s-{st}"
            li_cls = ("crit " if crit else "") + ("" if st == "yes" else "no-doc")
            flag = '<span class="flag">❗</span>' if crit else ""
            note_h = f'<div class="inote">{flag}{H.escape(note)}</div>' if note else (
                     f'<div class="inote">{flag}критично</div>' if crit else "")
            link_h = f'<a class="doc" href="{link}" target="_blank" rel="noopener">открыть →</a>' if link else ""
            w(f'''<li class="{li_cls}" data-st="{st}" data-crit="{1 if crit else 0}">
        <span class="chip {cls}">{LABEL[st]}</span>
        <span class="itxt"><span class="iname">{H.escape(name)}</span>{note_h}</span>
        {link_h}
      </li>''')
        w('''<li class="empty" hidden>В этом блоке ничего не подходит под фильтр</li>
   </ul></section>''')

    w(f'''<div class="summary">
  <h3>Пять дыр, которые рвутся первыми</h3>
  <ol>
    <li><b>Чек-листы смены.</b> Стоят в задачах как #p1 с июля. Без них бесперебойная работа точек держится на памяти двух управляющих.</li>
    <li><b>Кассовая дисциплина и инкассация.</b> Не теория: у Зелёного базара денежная позиция −127 567.</li>
    <li><b>Охрана труда и пожарная.</b> Фритюр, газ, ножи. Риск не в KPI, а в «закрыли точку» или травме.</li>
    <li><b>Онбординг и стажировка.</b> Текучка высокая, каждый новый учится «как получится» — страдают время обслуживания и фуд-кост.</li>
    <li><b>Стандарт запуска точки.</b> Цель 6 точек. ОВИР обошёлся в 1,1 млн и 22 месяца окупаемости против 6,4 месяца у старой Ромашки.</li>
  </ol>
 </div>

 <div class="note">
  <b>Что проверить:</b> трудовые документы (договоры, матответственность, табель, медкнижки)
  я не нашёл ни в Vault, ни в Google Drive. Если они в бумаге или у бухгалтера — скажи, уберу из дыр.
  Notion не проверял: если регламенты есть там, добавлю в навигатор.<br><br>
  <b>Каждый документ по одному шаблону:</b> одна страница → что делать → кто контролирует →
  что считается нарушением → под подпись.
 </div>
</div></main>

<script>
(function(){{
  var btns=[].slice.call(document.querySelectorAll('.fbtn'));
  function apply(f){{
    btns.forEach(function(b){{b.setAttribute('aria-pressed', b.dataset.f===f);}});
    document.querySelectorAll('section.block').forEach(function(sec){{
      var shown=0, tot=0, yes=0;
      sec.querySelectorAll('li[data-st]').forEach(function(li){{
        tot++;
        if(li.dataset.st==='yes') yes++;
        var ok = f==='all' ? true
               : f==='crit' ? li.dataset.crit==='1'
               : li.dataset.st===f;
        li.hidden=!ok; if(ok) shown++;
      }});
      sec.hidden = shown===0;
      var em=sec.querySelector('.empty'); if(em) em.hidden = shown!==0;
      var bc=sec.querySelector('.bc');
      if(bc) bc.textContent = (f==='all') ? yes : shown;
      var cnt=sec.querySelector('.bcount');
      if(cnt) cnt.lastChild.textContent = '/'+(f==='all'?tot:shown);
    }});
  }}
  btns.forEach(function(b){{b.addEventListener('click',function(){{apply(b.dataset.f);}});}});
  apply('all');
}})();
</script>''')

    open(OUT, "w", encoding="utf-8").write(o.getvalue())
    print("OK →", OUT)
    print(f"документов: {n_all} | есть {n_yes} · в работе {n_wip} · нет {n_no} · уточнить {n_ask} · критичных {n_cri}")

build()
