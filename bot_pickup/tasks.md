# Задачи — Бот приёма заказов на самовывоз (Pilot 2)

`bot_pickup/tasks.md` · Версия: 0.1 · Дата: 2026-06-02

> Исполняемый чек-лист, сгенерированный из `plan.md` и сгруппированный **по пользовательским
> историям** из `spec.md` (каждая история выкатывается самостоятельно, со своим `CHECKPOINT`).
> Принципы — `constitution.md`. **Реализация — по одной задаче за раз** (конституция §10, скилл):
> берём первую `[ ]`, делаем, помечаем `[x]`, останавливаемся.

**Легенда.** `[P1]` MVP · `[P2]` важно · `[P3]` потом · `[P]` можно параллельно внутри истории ·
`CHECKPOINT` — история независимо демонстрируема. Фазы релиза (из spec §10): **v0-core** (всё P1,
кроме печати) → **v0-print** (печать, путь C) → v0.1 → v1 → v1.1 → v2+.

**Решение по доставке на кухню (подтверждено 2026-06-02):** MVP-печать — путь **C** (отдельный
ESC/POS-принтер + локальный агент). Путь **A** (закрытое платное API Quick Resto → планшет → штатная
печать + фискализация) — апгрейд в v1.1. До подключения любого из них кухня всегда видит заказ в
Telegram-чате (бэкап, FR-15).

---

## Фаза 0 — Setup (каркас проекта, без бизнес-логики)

- [x] T001 [P1] Инициализировать пакет `bot_pickup`: `pyproject.toml` (Python 3.12+, ruff), зависимости
  с точными пинами — aiogram 3.28.x, redis, sqlalchemy[asyncio], asyncpg, alembic, httpx,
  pydantic-settings (file: `bot_pickup/pyproject.toml`)
- [x] T002 [P1] `.env.example` со всеми ключами из plan §10 (`BOT_TOKEN`, `DATABASE_URL`, `REDIS_URL`,
  `STAFF_CHAT_ID`, `ENABLED_SINKS`, `MENU_SOURCE`, `MENU_PATH`, флаги) — секреты не коммитим
  (file: `bot_pickup/.env.example`)
- [x] T003 [P1] `.gitignore` (`.env`, `__pycache__`, артефакты) (file: `bot_pickup/.gitignore`)
- [x] T004 [P1] Конфиг из окружения на pydantic-settings (file: `bot_pickup/src/config.py`)
- [x] T005 [P1] `docker-compose.yml`: сервисы `bot` + `postgres` + `redis`, миграции Alembic на старте
  (file: `bot_pickup/docker-compose.yml`)
- [x] T006 [P1] [P] Каркас Alembic (env.py async, пустая ревизия) (file: `bot_pickup/alembic/env.py`)
- [ ] CHECKPOINT: `docker compose up` поднимает пустой бот + Postgres + Redis; конфиг читается из `.env`.
  *(Артефакты готовы и проверены статически: ruff чисто, конфиг парсится с fail-fast, пакет собирается,
  `alembic/env.py` валиден. `docker compose up` запустить у себя с заполненным `.env`.)*

## Фаза 1 — Foundational (блокирующее общее; до любой пользовательской истории)

- [x] T007 [P1] Async-движок и фабрика сессий SQLAlchemy (file: `bot_pickup/src/db/engine.py`,
  `bot_pickup/src/db/session.py`)
- [x] T008 [P1] ORM-модели: `clients`, `orders`, `order_items`, `order_status_history`,
  `daily_counter`, `print_jobs` (plan §4; деньги в копейках, `comment` пока не заводим) (file:
  `bot_pickup/src/db/models.py`)
- [x] T009 [P1] Начальная миграция Alembic по моделям (file: `bot_pickup/alembic/versions/0001_init.py`)
- [x] T010 [P1] Репозитории (clients/orders/items/history/counter) — тонкий слой доступа (file:
  `bot_pickup/src/db/repositories.py`)
- [x] T011 [P1] Модуль текстов, нейтральный тон, ru (FR-13) (file: `bot_pickup/src/texts/ru.py`)
- [x] T012 [P1] Базовые клавиатуры навигации: «назад», «в начало», «корзина» — единый стиль,
  без тупиков (FR-13, конституция §7) (file: `bot_pickup/src/keyboards/common.py`)
- [x] T013 [P1] FSM-состояния: `Registration`, `Browsing`, `ItemConfig`, `Cart`, `Checkout`
  (file: `bot_pickup/src/states/order.py`)
- [x] T014 [P1] Точка входа: Dispatcher + `RedisStorage` (FSM наружу процесса), регистрация роутеров,
  startup/shutdown; dev — long-polling (file: `bot_pickup/src/bot.py`)
- [x] T015 [P1] Протокол `OrderSink` + результат `SinkResult` (file: `bot_pickup/src/orders/sinks/base.py`)
- [x] T016 [P1] Протокол `PaymentProvider` + заглушка `NoPaymentProvider` (MVP без оплаты) (file:
  `bot_pickup/src/payments/base.py`, `bot_pickup/src/payments/none.py`)
- [ ] CHECKPOINT: бот стартует на long-polling, отвечает на `/start`, состояние FSM переживает рестарт.
  *(Код готов; БД-слой и миграция 0001 проверены на реальном Postgres, диспетчер собирается, ruff чисто.
  Запуск с живым `BOT_TOKEN` — у себя: впиши токен в `.env`, затем `docker compose up --build`.)*

---

## История D — Меню из источника правды  ·  US-D1, US-D2  ·  v0-core
> Строим первой: меню читают почти все клиентские истории. FR-1, FR-4, FR-12.

- [x] T017 [P1] Pydantic-модели меню: `OptionChoice`, `OptionGroup`, `MenuItem`, `Category`, `Menu`
  (plan §5) (file: `bot_pickup/src/menu/models.py`)
- [x] T018 [P1] `JsonFileMenuSource` (контракт `MenuSource`): грузит `data/menu.json`, **подставляет
  ключ словаря как `OptionGroup.id`**, конвертирует `price`/`price_delta` рубли→копейки, игнорирует
  лишние ключи (plan §5) (file: `bot_pickup/src/menu/sources/json.py`)
- [x] T019 [P1] Кеш меню (TTL ~60 с) + `force_refresh=True` для чтения свежих данных на оформлении
  (FR-16) (file: `bot_pickup/src/menu/cache.py`)
- [x] T020 [P1] Хендлер меню: категории → позиции категории → карточка (название, серьвинг, цена,
  описание); **недоступные позиции не показываются** (FR-4) (file: `bot_pickup/src/handlers/menu.py`)
- [x] T021 [P1] [P] Клавиатуры меню (категории, позиции, карточка) (file:
  `bot_pickup/src/keyboards/menu.py`)
- [x] CHECKPOINT (US-D1/D2) — логика проверена в песочнице (меню грузится: 51 позиция/10 категорий, конвертация руб→коп, недоступные скрыты; полный UX-прогон — на машине Andrey с реальным токеном): меню листается по категориям из `menu.json`; позиция со `available=false`
  не предлагается; правка цены/доступности в файле видна без передеплоя кода.

## История A — Приём заказа (ядро)  ·  US-A1…A5  ·  v0-core (US-A4 — P2)
> FR-2, FR-3, FR-5, FR-6, FR-7, FR-16.

- [x] T022 [P1] Регистрация: при первом обращении спросить **имя один раз**, сохранить в `clients`,
  далее подставлять; адрес/офис не спрашиваем (US-A3, FR-5) (file: `bot_pickup/src/handlers/start.py`)
  *(сделано в Фазе 1 вместе с T014 — чекпойнт фазы требует рабочего `/start`)*
- [x] T023 [P1] Логика корзины: добавить/изменить количество/удалить, **расчёт суммы с учётом опций**
  (дельты), хранение в Redis/FSM (US-A1/A2, FR-2/FR-3) (file: `bot_pickup/src/cart/cart.py`)
- [x] T024 [P1] Хендлер выбора опций позиции (`ItemConfig`): группы `temp`/`alt_milk`/`syrup`/
  `matcha_base`/`tonic_base`/`egg_style`, `required`/`max_choices`, затем «добавить в корзину»
  (US-A1) (file: `bot_pickup/src/handlers/menu.py`)
- [x] T025 [P1] Хендлер корзины: список строк, изменить кол-во, удалить, показать итог, «оформить»
  (US-A2, FR-3) (file: `bot_pickup/src/handlers/cart.py`)
- [x] T026 [P1] [P] Клавиатуры корзины и карточки опций (file: `bot_pickup/src/keyboards/cart.py`)
- [ ] T027 [P2] Выбор времени самовывоза или «как можно скорее», за флагом `PICKUP_TIME_ENABLED`
  (US-A4, FR-5) (file: `bot_pickup/src/handlers/checkout.py`)
- [x] T028 [P1] Нумерация заказа: дневной счётчик `daily_counter`, атомарно
  (`INSERT … ON CONFLICT … RETURNING`), формат `NNN` (plan §4.1, FR-7) (file:
  `bot_pickup/src/orders/numbering.py`)
- [x] T029 [P1] `OrderService.create_order`: **перепроверка стопа по источнику (force_refresh)** — если
  позиция ушла в стоп, заказ **не создаём** и сообщаем какая (FR-16/US-D3); иначе фиксируем заказ +
  снапшоты позиций/опций, присваиваем номер, инициализируем статус, **идемпотентно** к двойному
  «Подтвердить» (file: `bot_pickup/src/orders/service.py`)
- [x] T030 [P1] Хендлер оформления: подтверждение (FR-6) → `create_order` → фан-аут в включённые
  sink'и → показать клиенту **номер заказа** + подтверждение (US-A5, FR-7) (file:
  `bot_pickup/src/handlers/checkout.py`)
- [x] T031 [P1] [P] Юнит-тесты: расчёт суммы корзины с опциями; атомарность/формат нумерации;
  стоп-перепроверка отклоняет заказ (file: `bot_pickup/tests/test_cart.py`,
  `bot_pickup/tests/test_numbering.py`, `bot_pickup/tests/test_stop_recheck.py`)
- [x] CHECKPOINT (A1–A5) — логика проверена на живом PG (заказ создаётся, номер NNN, снапшоты позиций/опций с дельтами, история new/system, перепроверка стопа отклоняет; UX-прогон — на машине Andrey): новый пользователь без подсказок указывает имя один раз, собирает ≥2 позиции
  (в т.ч. с опциями), правит корзину, оформляет; итоговая сумма = сумме позиций; получает короткий
  номер; при повторе имя не спрашивается; позиция-в-стопе при оформлении → заказ не создан, видно какая.

## История B — Кухня/кофейня  ·  US-B1, US-B2, US-B3 (v0-core); US-B4 (v0-print)
> FR-8, FR-9, FR-11, FR-15.

- [x] T032 [P1] `TelegramStaffChatSink` — **всегда включён** (бэкап, FR-15): шлёт заказ в чат сотрудников
  (позиции, опции, кол-во, имя, номер, время), читаемо (US-B1, FR-8) (file:
  `bot_pickup/src/orders/sinks/telegram_staff.py`)
- [x] T033 [P1] Машина статусов `new → accepted → almost_ready → ready → handed_out`; ветка `rejected`
  (с причиной); запись каждой смены в `order_status_history` (US-B3, FR-11) (file:
  `bot_pickup/src/orders/status.py`)
- [x] T034 [P1] Хендлер сотрудника: inline-кнопки статусов; **«почти готово» одним действием** (US-B2,
  FR-9); «отклонить» с причиной (file: `bot_pickup/src/handlers/staff.py`)
- [x] T035 [P1] [P] Клавиатуры управления заказом для чата сотрудников (file:
  `bot_pickup/src/keyboards/staff.py`)
- [x] T036 [P1] [P] Юнит-тесты переходов статусов (валидные/невалидные) (file:
  `bot_pickup/tests/test_status.py`)
- [x] CHECKPOINT (US-B1/B2/B3, v0-core) — логика/БД проверены в песочнице (тикет рендерится с позициями/опциями/именем/номером/итогом; машина статусов и история new→accepted→almost_ready→ready→handed_out с актором-сотрудником на живом PG; невалидные переходы отклоняются; sink собирается, роутеры включают staff; доставка в Telegram-чат и пуши клиенту — на машине Andrey с реальным токеном): оформленный заказ появляется в чате сотрудников за секунды со всеми деталями; «почти готово» доставляет сигнал клиенту; статусы переключаются и пишутся в историю.

> **— Граница v0-core / v0-print —** Ниже — печать (путь C). Зависит от железа (принтер + агент);
> до него кухня работает по Telegram-чату.

- [ ] T037 [P1] `EscPosPrinterSink`: кладёт `print_job` (формат билета: позиции, опции, кол-во, имя,
  номер, время) (US-B4, FR-15) (file: `bot_pickup/src/orders/sinks/escpos.py`)
- [ ] T038 [P1] Очередь печати с **сохранением задания при недоступности** и допечаткой при возврате
  связи (`print_jobs`: pending/printed/failed, attempts) (FR-15) (file:
  `bot_pickup/src/orders/service.py`, `bot_pickup/src/db/repositories.py`)
- [ ] T039 [P1] Эндпоинты ретрансляции для агента (prod, aiohttp): `GET /agent/print/next`,
  `POST /agent/print/ack` (исходящее соединение агента, NAT) (file: `bot_pickup/src/bot.py`)
- [ ] T040 [P1] Локальный агент печати: long-poll сервера → печать через `python-escpos`
  (`Network(host):9100`/USB) → ack (file: `bot_pickup/agent/agent.py`)
- [ ] CHECKPOINT (US-B4, v0-print): оформленный заказ печатается на ESC/POS-принтере; при выключенном
  принтере задание не теряется и допечатывается; дубль в Telegram-чат остаётся.

## История C — Статус у клиента  ·  US-C1, US-C2 (v0-core); US-C3 (P2)
> FR-7, FR-10, FR-11.

- [x] T041 [P1] Подтверждение приёма заказа клиенту сразу после оформления (US-C1) (file:
  `bot_pickup/src/handlers/checkout.py`)
- [x] T042 [P1] Пуш клиенту «почти готово» в тот же чат, где оформлял (US-C2, FR-10); триггерится
  переходом статуса (file: `bot_pickup/src/handlers/status.py`)
- [ ] T043 [P2] Команда/кнопка «статус заказа»: клиент видит текущий статус активного заказа (US-C3)
  (file: `bot_pickup/src/handlers/status.py`)
- [x] CHECKPOINT (US-C1/C2) — реализовано (подтверждение при оформлении из Фазы 2; пуш клиенту при значимых сменах статуса — accepted/almost_ready/ready/rejected; UX-доставка пушей — на машине Andrey). (P2 T043 — просмотр статуса по запросу — отложен.): клиент получает подтверждение и сигнал «почти готово».

## История E — История заказов (опц.)  ·  US-E1  ·  P3
- [ ] T044 [P3] Просмотр прошлых заказов + «повторить заказ» (частый сценарий — минимум шагов,
  конституция §7) (file: `bot_pickup/src/handlers/status.py`, `bot_pickup/src/db/repositories.py`)
- [ ] CHECKPOINT (US-E1): клиент видит прошлые заказы и повторяет один в пару нажатий.

## История F — Допы (add-ons)  ·  FR-18  ·  v0-core
> Доп — настоящая позиция: продаётся самостоятельно (уже работает, категория «Можем добавить»)
> и прикладывается к блюду с количеством. Отличается от варианта-опции (модификатор, отдельно не продаётся).

- [x] T063 [P1] Модель: `MenuItem.addons: [item_id]`; на `Menu` — `addon_category`,
  `addon_offer_categories`; хелперы `addon_items()`, `addons_for(item)` (file:
  `bot_pickup/src/menu/models.py`)
- [x] T064 [P1] Загрузчик: парсинг блока `addons` (`category` + `offer_to_categories`) и поля
  `addons` у позиций; блок `addons` в `data/menu.json` (file: `bot_pickup/src/menu/sources/json.py`,
  `bot_pickup/data/menu.json`)
- [x] T065 [P1] Корзина: `CartLine.addons: {item_id: qty}`; учёт в сигнатуре слияния; цена строки =
  (цена + дельты опций + Σ допы) × кол-во; снапшот допов; отображение допов в названии строки (file:
  `bot_pickup/src/cart/cart.py`)
- [x] T066 [P1] БД: колонка `order_items.addons_snapshot` (jsonb, nullable) + миграция; запись допов
  в `create_order`; перепроверка стопа и для допов (FR-16/18) (file: `bot_pickup/src/db/models.py`,
  `bot_pickup/alembic/versions/*`, `bot_pickup/src/orders/service.py`)
- [x] T067 [P1] UX: степперы допов в карточке позиции (если допы предложены); карточка открывается
  и для позиции без опций, но с допами; допы под блюдом в билете кухни (file:
  `bot_pickup/src/keyboards/menu.py`, `bot_pickup/src/handlers/menu.py`,
  `bot_pickup/src/orders/sinks/telegram_staff.py`)
- [x] T068 [P1] [P] Юнит-тесты: цена строки с допами и кол-вом >1; слияние с разными допами;
  стоп-перепроверка по допу (file: `bot_pickup/tests/test_addons.py`)
- [x] CHECKPOINT (FR-18) — проверено на живом PG (завтрак+бекон+2×яйцо=1900₽ ×порции; бекон отдельной строкой; снапшот допов в order_items.addons_snapshot; билет кухни показывает допы под блюдом; стоп по допу отклоняет заказ; миграция 0002 обратима; UX в Telegram — на машине Andrey): доп можно взять отдельной позицией и приложить к блюду (с кол-вом); сумма и билет кухни учитывают допы.

---

## Полировка и нефункц. (перед демо v0-core)
- [x] T045 [P1] Бюджет отклика ≤ ~1–2 с; на тяжёлых операциях — индикатор «обрабатываю…»
  (конституция §8) (file: `bot_pickup/src/handlers/checkout.py`) — индикатор «Оформляю заказ…» на
  подтверждении (запись + перепроверка стопа + доставка на кухню), спиннер гасится сразу, кнопка
  «Подтвердить» убирается (заодно защита от двойного нажатия); экран после заказа ведёт «В начало»
  (не тупик).
- [x] T046 [P1] [P] `ruff` чисто; типы где разумно; форматирование до коммита (конституция §4)
  (file: `bot_pickup/pyproject.toml`) — ruff чисто по всему `src`+`tests`; типы у `build_dispatcher`
  и слоёв; 33 юнита.
- [ ] T047 [P1] [P] `quickstart.md`: как поднять локально (long-polling, `.env`, миграции)
  (file: `bot_pickup/quickstart.md`)
- [ ] T048 [P1] Ручной прогон каждого пути по чек-листу `spec.md` §6; правка точек трения
  (тест с реальными людьми — бариста-дизайнер; конституция §7)
- [ ] CHECKPOINT (релиз v0-core): сквозной путь меню→корзина→оформление→чат кухни→«почти готово»→статус
  работает на моках, без оплаты и без POS; клиентский путь не зависит от интернета кофейни (FR-14).

---

## Будущие фазы (вне v0; каждая — отдельный инкремент)

### v0.1 — Меню из редактируемой таблицы (зеркало)  ·  US-D1
- [ ] T049 [P2] `SheetMenuSource` (Google/Yandex Sheets) под тем же контрактом `MenuSource`; кофейня
  правит позиции/доступность без кода (file: `bot_pickup/src/menu/sources/sheet.py`)
- [ ] T050 [P2] Переключение `MENU_SOURCE=sheet` без изменения пользовательских сценариев (file:
  `bot_pickup/src/config.py`)
- [ ] CHECKPOINT: правка в таблице отражается в боте; поведение клиента не изменилось.

### v1 — Quick Resto открытое API (целевой источник правды по меню)
- [ ] T051 [P2] `QuickRestoMenuSource`: `warehouse.nomenclature.dish`, Basic Auth (логин/пароль из
  Предприятие → Настройки), маппинг «толстого» JSON в нашу модель (file:
  `bot_pickup/src/menu/sources/quickresto.py`)
- [ ] T052 [P2] Переключение `MENU_SOURCE=quickresto`; кеш + force_refresh работают как раньше
  (file: `bot_pickup/src/config.py`)
- [ ] CHECKPOINT: меню и стоп берутся из Quick Resto; сценарии клиента не изменились.

### v1.1 — Оплата (Точка СБП), фискализация и учёт в POS  ·  US-F1, FR-17  ·  отдельная спека
> Сначала завести отдельный `spec.md` фазы оплаты (54-ФЗ, фискализация — явный слой; constitution §6).
- [ ] T053 [P3] `TochkaSbpProvider`: динамический QR (`Register Qr Code`, сумма в копейках) → клиенту
  `payload`-ссылка → вебхук `incomingSbpPayment` помечает заказ оплаченным (file:
  `bot_pickup/src/payments/tochka.py`)
- [ ] T054 [P3] Фискальный чек: путь A (закрытое API QR) или libfptr10 на АТОЛ; **оговорка 54-ФЗ** —
  ККТ под «расчёты в Интернете» (уточнить у бухгалтера) (file: `bot_pickup/src/payments/tochka.py`)
- [ ] T055 [P3] `QuickRestoTerminalSink` (**путь A, апгрейд печати/учёта**): заказ → кассовый планшет →
  штатная печать на кухонный АТОЛ + фискализация; параметры закрытого API — по итогам звонка (file:
  `bot_pickup/src/orders/sinks/quickresto.py`)
- [ ] T056 [P3] Отмена части заказа + рефанд за оплаченные позиции (FR-17) (file:
  `bot_pickup/src/orders/service.py`)
- [ ] T057 [P3] Вебхук Точки `/webhook/tochka` (prod, aiohttp) (file: `bot_pickup/src/bot.py`)
- [ ] CHECKPOINT: оплата по СБП с корректным фискальным чеком; (опц.) продажи видны в учёте Quick Resto.

### v2+ — Другие площадки
- [ ] T058 [P3] Канал ВКонтакте под тем же ядром (меню/корзина/оформление/статус)
- [ ] T059 [P3] Канал Max
- [ ] CHECKPOINT: заказ собирается и доходит до кухни из VK / Max.

---

## Деплой (нужен начиная с v0-print; для v0-core — long-polling локально)
- [ ] T060 [P1] VPS в РФ (дата-центр РФ — 152-ФЗ, храним имя клиента), ~2 vCPU / 4 ГБ; не куплен
  (research §7)
- [ ] T061 [P1] Prod: webhook (aiohttp, HTTPS); тот же сервер обслуживает `/agent/print/*`
  (file: `bot_pickup/src/bot.py`)
- [ ] T062 [P2] Бэкапы Postgres (у провайдера обычно платно — заложить)

---

## Приложение — покрытие FR (Analyze: spec ↔ plan ↔ tasks)

| FR | Задачи |
|---|---|
| FR-1 меню по категориям | T017–T021 |
| FR-2 добавить/кол-во/удалить | T023, T025 |
| FR-3 корзина + сумма | T023, T025 |
| FR-4 стоп не предлагается | T020 |
| FR-5 имя один раз, без адреса; (опц.) время | T022, T027 |
| FR-6 подтверждение | T030 |
| FR-7 короткий номер | T028, T030, T041 |
| FR-8 заказ сотруднику со всеми деталями | T032 |
| FR-9 «почти готово» одним действием | T034 |
| FR-10 сигнал клиенту в тот же чат | T042 |
| FR-11 жизненный цикл статусов + история | T033, T034 |
| FR-12 меню из внешнего источника | T018, T049, T051 |
| FR-13 ru, нейтральный тон, без тупиков | T011, T012 |
| FR-14 независимость от интернета кофейни | T060–T061 + CHECKPOINT v0-core |
| FR-15 печать на кухне + не теряется + бэкап-чат | T032 (бэкап), T037–T040 |
| FR-16 перепроверка стопа, заказ не создаётся | T019, T029 |
| FR-17 (later) отмена части + рефанд | T056 |
| FR-18 допы: отдельно + к блюду | T063–T068 |

**Статус Analyze:** каждое FR закрыто ≥1 задачей; каждое архитектурное решение plan (aiogram+FSM/Redis,
Postgres+SQLAlchemy+Alembic, адаптеры `MenuSource`/`OrderSink`, нумерация, статусы, заглушка оплаты,
Docker/VPS, long-polling↔webhook) отражено в задачах; задачи не выходят за структуру plan §11. Чисто.

## Дальше
Implement по одной задаче: первая `[ ]` — **T001** (инициализация пакета `bot_pickup`).
