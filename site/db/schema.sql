-- Схема операционной системы Ромашки. PostgreSQL 16.
--
-- Повторяет то, что сегодня лежит в листах Google Таблицы, но с двумя
-- принципиальными отличиями:
--
--   1. Человек опознаётся внутренним идентификатором, а не chat_id из
--      телеграма. Сегодня сотрудника без телеграма в систему не завести,
--      и это упирается прямо в найм. Здесь chat_id — обычное поле,
--      которого может не быть.
--
--   2. Ссылки между сущностями настоящие. В таблице связь держалась
--      на совпадении имени строкой: два тёзки означали общую явку,
--      общие баллы и взаимное закрытие отрезков.
--
-- Порядок таблиц — от справочников к движению.

BEGIN;

-- ── справочники ──────────────────────────────────────────────────────────

CREATE TABLE points (
    code        text PRIMARY KEY,          -- ЗБ, ОВИР
    label       text NOT NULL,             -- «ЗБ · Лохути 11»
    address     text        DEFAULT '',
    lat         double precision,
    lon         double precision,
    radius_m    integer     NOT NULL DEFAULT 150,
    -- Срок закрытия у точек разный: ЗБ гасит свет в 00:30, ОВИР в 03:30.
    closes_at   text        NOT NULL DEFAULT '00:30',
    active      boolean     NOT NULL DEFAULT true
);

CREATE TABLE people (
    id          bigserial PRIMARY KEY,
    name        text    NOT NULL,
    point_code  text    REFERENCES points(code),
    role        text    NOT NULL DEFAULT 'staff',   -- staff | senior | manager | coo
    dept        text    NOT NULL DEFAULT '',
    active      boolean NOT NULL DEFAULT true,
    chat_id     bigint UNIQUE,              -- может отсутствовать: телеграм больше не обязателен
    login       text UNIQUE,
    pass_hash   text    NOT NULL DEFAULT '',
    -- Кем может подменить и может ли быть старшим — как в «Команде».
    can_cover   text[]  NOT NULL DEFAULT '{}',
    can_senior  boolean NOT NULL DEFAULT false,
    created_at  timestamptz NOT NULL DEFAULT now()
);
-- Тёзки в коллективе на два десятка человек — вопрос времени, а имя
-- сегодня служит ключом. Здесь оно всего лишь подпись.
CREATE INDEX people_name_idx ON people (name);

-- Чек-листы и их пункты. Источник правды прежний — checklists.romashka.json,
-- сюда он переносится скриптом: править руками бессмысленно.
CREATE TABLE checklists (
    key             text PRIMARY KEY,       -- shift_bar_open
    title           text NOT NULL,
    type            text NOT NULL,          -- checklist | shift | journal | form | quiz
    stage           text,                   -- open | give | take | close
    station         text,
    dept            text,
    roles           text[] NOT NULL DEFAULT '{}',
    points          text[] NOT NULL DEFAULT '{}',   -- пусто = обе точки
    deadline        text   NOT NULL DEFAULT '',
    deadline_by     jsonb  NOT NULL DEFAULT '{}',   -- срок отдельной точки
    deadline_from   text,                   -- in | out — срок от отметки человека
    deadline_plus   integer NOT NULL DEFAULT 0,
    remind_before   integer NOT NULL DEFAULT 45,
    total           integer NOT NULL DEFAULT 0
);

CREATE TABLE checklist_items (
    id          bigserial PRIMARY KEY,
    key         text    NOT NULL REFERENCES checklists(key) ON DELETE CASCADE,
    n           integer NOT NULL,           -- номер пункта внутри листа
    block       text    NOT NULL DEFAULT '',
    text        text    NOT NULL,
    photo       boolean NOT NULL DEFAULT false,
    measure     jsonb,                      -- что измеряем и в каких границах
    UNIQUE (key, n)
);

-- ── движение ─────────────────────────────────────────────────────────────

-- Явка. День операционный: сутки кончаются в 05:00, поэтому смена,
-- начатая вчера и закрытая в 00:30, остаётся вчерашней.
CREATE TABLE shifts (
    id          bigserial PRIMARY KEY,
    day         date    NOT NULL,
    point_code  text    NOT NULL REFERENCES points(code),
    person_id   bigint  NOT NULL REFERENCES people(id),
    part        text    NOT NULL DEFAULT 'one',   -- open | close | one
    came_at     text    NOT NULL DEFAULT '',
    left_at     text    NOT NULL DEFAULT '',
    hours       numeric(5,2),
    late_min    integer NOT NULL DEFAULT 0,
    geo_in      text    NOT NULL DEFAULT '',
    geo_out     text    NOT NULL DEFAULT '',
    UNIQUE (day, point_code, person_id)
);

-- Отрезки работы на местах. Именно они, а не «где стоит сейчас»:
-- человек за день бывает на двух станциях, и для зарплаты нужен каждый
-- отрезок отдельно. Затирать прошлую запись нельзя — вместе с ней
-- стирается отработанный час.
CREATE TABLE segments (
    id          bigserial PRIMARY KEY,
    day         date    NOT NULL,
    point_code  text    NOT NULL REFERENCES points(code),
    person_id   bigint  NOT NULL REFERENCES people(id),
    station     text    NOT NULL,
    part        text    NOT NULL DEFAULT 'one',
    start_at    text    NOT NULL,
    end_at      text    NOT NULL DEFAULT '',
    minutes     integer NOT NULL DEFAULT 0,
    how         text    NOT NULL DEFAULT 'выбрал сам',
    from_person bigint  REFERENCES people(id)
);
-- Одно место — один человек: открытый отрезок на станции может быть
-- только один, иначе двое встают на одну саладетту.
CREATE UNIQUE INDEX segments_live_idx
    ON segments (day, point_code, station) WHERE end_at = '';

-- Заполнения листов.
CREATE TABLE fills (
    id          bigserial PRIMARY KEY,
    day         date    NOT NULL,
    point_code  text    NOT NULL REFERENCES points(code),
    key         text    NOT NULL REFERENCES checklists(key),
    person_id   bigint  NOT NULL REFERENCES people(id),
    filled_at   timestamptz NOT NULL DEFAULT now(),
    done        integer NOT NULL DEFAULT 0,
    total       integer NOT NULL DEFAULT 0,
    minutes     numeric(6,2),
    comment     text    NOT NULL DEFAULT '',
    part        text    NOT NULL DEFAULT '',
    handed_to   bigint  REFERENCES people(id),   -- кому сдана смена
    checked_by  bigint  REFERENCES people(id),
    checked_at  timestamptz,
    mismatch    text    NOT NULL DEFAULT ''
);
-- Этап дня делает одна смена: повтор здесь означает именно повтор.
CREATE UNIQUE INDEX fills_stage_idx ON fills (day, point_code, key)
    WHERE key LIKE 'shift\_%';

CREATE TABLE fill_marks (
    fill_id     bigint  NOT NULL REFERENCES fills(id) ON DELETE CASCADE,
    n           integer NOT NULL,
    ok          boolean NOT NULL,
    measured    text    NOT NULL DEFAULT '',
    PRIMARY KEY (fill_id, n)
);

-- Фото хранятся файлами на диске сервера, в базе — путь и хеш.
-- Пустая ссылка недопустима: строка «фото есть» без файла хуже,
-- чем честное «фото нет».
CREATE TABLE fill_photos (
    id          bigserial PRIMARY KEY,
    fill_id     bigint  NOT NULL REFERENCES fills(id) ON DELETE CASCADE,
    n           integer NOT NULL,
    path        text    NOT NULL CHECK (path <> ''),
    sha256      text    NOT NULL DEFAULT '',
    made_at     timestamptz NOT NULL DEFAULT now()
);

-- ── баллы, задачи, обучение ──────────────────────────────────────────────

CREATE TABLE score (
    id          bigserial PRIMARY KEY,
    day         date    NOT NULL,
    point_code  text    NOT NULL REFERENCES points(code),
    person_id   bigint  NOT NULL REFERENCES people(id),
    event       text    NOT NULL,
    points      integer NOT NULL,
    why         text    NOT NULL DEFAULT '',
    kind        text    NOT NULL DEFAULT 'базовый',   -- базовый | доп
    period      text    NOT NULL DEFAULT '',
    link        text    NOT NULL DEFAULT '',
    dispute     text    NOT NULL DEFAULT '',
    verdict     text    NOT NULL DEFAULT ''
);
CREATE INDEX score_period_idx ON score (person_id, day);

CREATE TABLE tasks (
    id          bigserial PRIMARY KEY,
    created     date    NOT NULL DEFAULT current_date,
    point_code  text    NOT NULL REFERENCES points(code),
    what        text    NOT NULL,
    source      text    NOT NULL DEFAULT '',
    owner_id    bigint  REFERENCES people(id),
    due         date,
    done_at     timestamptz,
    done_by     bigint  REFERENCES people(id)
);

CREATE TABLE training (
    id          bigserial PRIMARY KEY,
    day         date    NOT NULL DEFAULT current_date,
    person_id   bigint  NOT NULL REFERENCES people(id),
    key         text    NOT NULL,
    score       integer NOT NULL DEFAULT 0,
    passed      boolean NOT NULL DEFAULT false,
    UNIQUE (person_id, key)
);

CREATE TABLE reads (
    id          bigserial PRIMARY KEY,
    at          timestamptz NOT NULL DEFAULT now(),
    person_id   bigint  NOT NULL REFERENCES people(id),
    code        text    NOT NULL,
    title       text    NOT NULL DEFAULT '',
    UNIQUE (person_id, code)
);

-- ── состав смены и журнал ────────────────────────────────────────────────

CREATE TABLE roster (
    id          bigserial PRIMARY KEY,
    day         date    NOT NULL,
    point_code  text    NOT NULL REFERENCES points(code),
    person_id   bigint  NOT NULL REFERENCES people(id),
    dept        text    NOT NULL DEFAULT '',
    start_at    text    NOT NULL DEFAULT '',
    instead_of  bigint  REFERENCES people(id),
    confirm     text    NOT NULL DEFAULT '',      -- буду | не смогу | пусто
    mark        text    NOT NULL DEFAULT '',      -- вышел | не вышел
    author      text    NOT NULL DEFAULT '',
    UNIQUE (day, point_code, person_id)
);

-- Кто появился, сменил точку или ушёл. Людей заводят трое, и остальные
-- узнают об этом случайно — журнал ведётся сам.
CREATE TABLE people_log (
    id          bigserial PRIMARY KEY,
    at          timestamptz NOT NULL DEFAULT now(),
    what        text    NOT NULL,
    person_id   bigint  REFERENCES people(id),
    details     jsonb   NOT NULL DEFAULT '{}'
);

-- Служебное: что расписание уже сделало сегодня. Отметка ставится
-- по факту успеха, иначе одна неудача съедает сутки — так мы остались
-- без резервных копий на восемнадцать дней.
CREATE TABLE done_log (
    day         date    NOT NULL,
    key         text    NOT NULL,
    at          timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (day, key)
);

COMMIT;
