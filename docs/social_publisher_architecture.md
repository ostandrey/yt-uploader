# Coin Wire — шар автопостингу (SocialPublisher)

**Статус:** прийнято як напрям, вендор ще не підписаний.  
**Оновлено:** 2026-08-11  
**Не робити:** власний TikTok Login Kit, власний Meta Graph, cookies/Playwright.

Північна зірка дистрибуції лишається та сама: ролик мають побачити люди. YouTube + Telegram уже вміємо офіційно. TikTok / Instagram / Threads / X — тільки через чужий уже-аудований додаток.

---

## Інваріанти

Один зовнішній провайдер публікації. Наш код не тримає TikTok/Meta OAuth. YouTube і Telegram лишаються нашими прямими клієнтами і ніколи не йдуть через цей шар. Помилка провайдера не валить рендер і не валить YouTube. Поки `social_publisher.provider = disabled`, кроспост просто SKIP — мертві `tiktok_publisher` / `instagram_publisher` / `threads_publisher` не викликати як fallback. Legacy-файли не видаляти, лише заморозити. Ключ провайдера тільки в env (Railway Secrets), не в yaml.

---

## Що з чужого плану беремо як є

Проблема дистрибуції не в ffmpeg. Природні SDK заблоковані: TikTok відхилив нашу апку категорією crypto; Graph у нас немає і не буде умовою старту. Легальний шар — API-of-APIs: оператор один раз логіниться в TikTok/IG у кабінеті провайдера; воркер шле REST з MP4 (або URL) і caption.

Один клас `SocialPublisher` кращий за три наші OAuth. Інтерфейс:

`publish(video_path, caption, platforms, schedule_for=None) -> dict[platform, status]`

`run_crosspost` викликає його після рендеру, незалежно від успіху YouTube (як зараз). Якщо в caption є YouTube-лінк і ролик ще unlisted — або не класти лінк у TikTok/IG, або шедулити crosspost після PUBLIC (~30 хв). Не блокувати TikTok очікуванням YouTube, якщо лінк там не потрібен.

Телефонний міст (бот шле MP4 + captions) лишається fallback, не «автоматизацією».

---

## Що поправляємо (перевірено в docs, серпень 2026)

Ціна Ayrshare у чернетці була занижена. У 2026 Premium — **$149/міс** за один профіль (усі мережі всередині профілю). Launch $299, Business $599. Це інфраструктура для SaaS, не для одного криптоканалу на 2 пости/день. Trial Launch 28 днів без карти — можна потикати API, підписуватись не варто, поки не доведено що дешевший вендор не тягне відео.

Ayrshare `/post` хоче **публічний https URL** у `mediaUrls` (або спочатку їхній `/media`). Multipart MP4 у `/post` немає. URL має кінчатись на `.mp4` або треба `isVideo: true`. Presigned URL з `?X-Amz-Signature` погано дружить з перевіркою розширення — або публічний шлях `.../uuid.mp4`, або `isVideo`. Відео — платний план. TikTok у них асинхронний (`id: pending`), ліміт TikTok API ~15 відео/день (нам вистачає). Webhooks є. У ToS немає явної заборони cryptocurrency news; є заборона «inappropriate» і вимога дотримуватись правил мереж. Писати в support до оплати все одно треба.

Upload-Post приймає **multipart файл або URL** — це краще для Railway без публічного R2. Маркетинг «без App Review» означає їхній додаток уже аудований, не те що TikTok відкритий для всіх. ToS забороняє crypto **scams / fake giveaways / financial fraud**, не новинний канал як клас. Free: 10 upload/міс (нам треба ~60). Paid Basic орієнтовно **$24/міс** ($16 annual), unlimited, 5 profiles. Менший вендор, вищий ризик зникнення, зате ціна під наш обсяг.

Late (getlate.dev) у 2026 ребрендиться в **Zernio**. Є REST + SDK, TikTok video / IG Reels / Threads у матриці. Безкоштовно кілька акаунтів для проби; далі дешево за connected account. Docs ще пливуть після ребренду — перед підпискою відкрити актуальний `docs.getlate.dev` або zernio.

Publer має справжній REST (Bearer, upload media → schedule). У їхніх docs для TikTok API зазначено **Business account required**. Дешевший scheduler, не «SaaS для продуктів». Перевірити, чи API входить у потрібний план, не лише web UI.

Buffer у UI вміє auto-publish TikTok. Публічний Buffer API — слабкий fit для серверного MP4. Metricool — аналітика + календар; для воркера не брати, поки немає явного REST video upload.

Не лити YouTube і Telegram через провайдера. Дубль OAuth, зайва точка відмови, у нас це вже працює.

R2 lifecycle на 2 години — ненадійний (у R2 правила часто добові). Якщо вендору потрібен URL: публічний префікс `https://…/coinwire/{id}.mp4` + `isVideo` якщо треба, прибирання кроном раз на день. Якщо вендор бере multipart — R2 для кроспосту не чіпати.

Крок «якщо provider != disabled: raise DeprecatedPath» у чернетці інвертований. Правило: provider виставлений → тільки SocialPublisher; provider `disabled` → SKIP соцмереж, **не** кликати legacy Graph/TikTok.

Instagram Professional (Creator) все одно майже напевно потрібен навіть у партнера. Особистий IG спершу перемкнути в Creator — безкоштовно.

---

## Цільовий вендор (рекомендація, не підписка)

Порядок проби, не порядок фанатизму:

1. **Upload-Post** — безкоштовний ключ, multipart з диска Railway, ціна після проби ~$24. Перший кандидат на `SOCIAL_PROVIDER=upload_post`.
2. **Late / Zernio** — запасний дешевий API, якщо Upload-Post ріже crypto або TikTok.
3. **Publer** — якщо потрібен звичний scheduler + API, і TikTok-акаунт можна зробити Business.
4. **Ayrshare** — лише якщо дешеві впали на відео/ToS, а нам важлива зрілість. Тоді trial 28 днів, далі $149 лише свідомо.

Перед оплатою будь-кого: лист у support «crypto news commentary, not trading signals / not ads — чи ок органічний TikTok + IG Reels через ваш API?». Поки немає письмового «ок» або успішного тестового ролика — код у проді з `provider: disabled`.

---

## Впровадження в цей репо (коли вендор вибрано)

Крок 0. У `config/coin_wire.yaml` блок `publishing.social_publisher` з `provider: disabled`, список платформ, delay. YouTube/Telegram не чіпати.

Крок 1. У `run_crosspost`: якщо provider disabled — SKIP tiktok/instagram/threads як зараз по суті, без виклику legacy. Якщо provider заданий — тільки `SocialPublisher`.

Крок 2. `src/publishers/social_publisher.py` + тонкий `src/publishers/providers/<name>.py`. Try/except як у нинішньому crosspost. Результат у той самий `format_crosspost_summary` → Telegram.

Крок 3. Env: `SOCIAL_PROVIDER`, `SOCIAL_API_KEY`, `SOCIAL_PLATFORMS`, опційно `SOCIAL_PROFILE` / user id кабінету. Не `SOCIAL_API_KEY` у yaml.

Крок 4. `scripts/test_social_publisher.py` — локальний MP4, без YouTube-пайплайна. Спочатку одна мережа (TikTok або IG).

Крок 5. Rollback: `SOCIAL_PROVIDER=disabled` у Railway. Деплой коду не обов’язковий, якщо default disabled.

Крок 6. R2 public upload — тільки якщо обраний вендор не їсть multipart.

Не вмикати цей шар, доки YouTube volume `/app/tokens` + `/app/data` живі. Інакше будемо дебажити «немає MP4» замість «немає поста».

---

## Ризики (коротко)

Провайдер теж може сказати no crypto або відкликати TikTok-партнерку. Тоді TikTok/IG знову телефон, канал живе на YouTube+Telegram. Не будувати бренд навколо одного вендора без запасного в списку.

Revoked OAuth у кабінеті провайдера → алерт у Telegram власнику, не тихий SKIP на тиждень.

Файл > ~45 МБ: Telegram-міст уже впирається в 50 МБ; для провайдера ліміти інші, але CRF тримати розумним.

Не реанімувати Login Kit. Не ставити GPU/ElevenLabs умовою дистрибуції.

---

## Нульовий бюджет (оператор: не платити)

Жоден з переглянутих OSS-репо (серпень 2026) не дає легального безкоштовного автопосту TikTok+IG 2×/день з Railway. Вони або cookies/Playwright, або твій відхилений Login Kit, або платний SaaS під капотом, або взагалі не паблішери.

Безкоштовний автопайплайн лишається: YouTube Data API + Telegram Bot API + телефонний міст для TikTok/IG/Threads.

Єдиний легальний «$0» експеримент на обмеженому обсязі: free tier Upload-Post (10 upload/міс) або Late/Zernio (кілька акаунтів, ліміт постів). Це не покриває 2 Shorts/день. Cookie-репо в цей проєкт не беремо.
