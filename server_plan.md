# תוכנית עבודה: KungFu Chess Server (CTD 26)

## 1. הקשר ומקור הדרישות

כרגע קיים רק מצב "hot-seat" מקומי: `main.py` פותח חלון OpenCV יחיד, ושני השחקנים משחקים על אותה מקלדת/עכבר מול אותו תהליך. הדרישות (מצגת CTD 26 + סרטון מלווה) מבקשות להפוך את זה למשחק רשת אמיתי, בסדר הבא (כל שלב = שקף אחד במצגת, ונשען על הקודם):

| שלב | שקף | דרישה מדויקת |
|---|---|---|
| A | 2 | Pub/sub bus עבור לוג מהלכים, סאונד ואנימציות; הניקוד הסמכותי נשמר במנוע ונשלח ב-snapshot |
| B | 3 | שרת מקומי יחיד-תהליך, תקשורת WebSocket. שליחת פקודות (בדוגמת `WQe2e5`); קבלת מצב משחק |
| C | 4 | מסך בית: login עם שם משתמש בלבד (shell, לא GUI). רק 2 שחקנים — הראשון לבן, השני שחור |
| D | 5 | login עם שם משתמש+סיסמה (shell), נשמר ב-SQLite בצד השרת. דירוג החל מ-1200, מתעדכן ב-ELO |
| E | 6 | כפתור "Play": מחפש יריב בטווח ELO ±100. לא נמצא מיד → ממתין עד דקה → הודעת "לא נמצא". ניתוק → resign אוטומטי אחרי 20 שניות, עם ספירה לאחור על המסך |
| F | 7 | כפתור "Room": חלון Windows עם תיבת טקסט + Create/Join/Cancel. Create מייצר מזהה חדר ומציג בראש המסך. Join נכנס לחדר לפי המזהה שהוקלד, גם הוא מוצג בראש המסך. בתוך חדר: השני שמצטרף = שחור, כל הבא = צופה. לוגים בצד השרת ובצד הלקוח לכל פעילות |

**ממצא מרכזי מבדיקת הקוד הקיים**: `model`/`rules`/`realtime`/`engine`/`boardio` הם כבר headless (לא תלויים ב-`cv2`), עם ממשק ציבורי נקי (`GameEngine.request_move/request_jump/wait/snapshot/subscribe`). מבחינה **תפקודית** זו שכבת ה-BLL (Business Logic Layer) של המשחק — גם אם היא לא יושבת פיזית תחת תיקייה בשם `bll`. **אין שום קוד רשת קיים היום.**

**הערה חשובה, בעקבות סקירה**: הדרישה "תמיכה בעוד שחקנים בעתיד" מרחיבה את קנה המידה בפועל — מ-2 לקוחות בודדים למשחק אחד גלובלי, לכדי אלפי משתמשים מקבילים (שחקנים+צופים) במשחקים רבים בו-זמנית. סעיף 10 מפרט את ההשלכות.

## 2. ארכיטקטורת השכבות שנבחרה

בעקבות דיון, ובהתאמה לשקף 3 ("שליחת פקודות; קבלת מצב משחק" — כלומר הלקוח לא מכיל שום כלל משחק, רק שולח/מציג) — מודל N-tier בצד השרת:

```
┌─────────────┐     WS      ┌──────────────┐     ┌─────────────┐     ┌──────────────┐     ┌────────┐
│Presentation │ ─────────── │  Controller  │ ──▶ │     BLL      │ ──▶ │     DAL      │ ──▶ │ SQLite │
│(client/view)│  "WQe2e5"   │(server/      │     │(model/rules/ │     │(server/dal/) │     │        │
│             │ ◀────────── │ controller.py)│     │ realtime/    │◀────│              │◀────│        │
└─────────────┘   EVENT/    └──────────────┘     │ boardio/     │     └──────────────┘     └────────┘
                   STATE                          │ engine/,     │
                                                   │ + server/    │
                                                   │ auth·elo·    │
                                                   │ matchmaker·  │
                                                   │ rooms)       │
                                                   └─────────────┘
```

- **Presentation** (`client/`, `view/`, `input/`): שולח פקודות טקסט, מציג מה שהתקבל. אפס לוגיקת משחק.
- **Controller** (`server/game/controller.py`, **חדש**): מקבל הודעה שפוענחה בעזרת `networking/protocol.py` ומנתב אותה לשירות ה-BLL הנכון, **בהקשר של משחק ספציפי** (ראו סעיף 10 — לא ניתוב גלובלי), ומחזיר תגובה מיידית. **שונה מ-`input/controller.py` הקיים** (Controller של קלט-משתמש בצד הלקוח) — שני מושגים שונים באותו שם נפוץ, לא כפילות, ו-`input/controller.py` לא זז ולא משתנה.
- **BLL** — **החלטה מתוקנת**: `model/`, `rules/`, `realtime/`, `boardio/`, `engine/` **נשארים במקומם המקורי בשורש הפרויקט, ללא שינוי מיקום**. `server/` מייבא מהם ישירות (`from engine.game_engine import GameEngine`, `from model.board import Board` וכו'). **אין תיקיית `server/bll/`.** הלוגיקה העסקית החדשה (`auth`, ‏`elo`, ‏`matchmaker`, ‏`rooms`) תרוכז תחת `server/services/`; זו שכבת שירותי שרת, בעוד חוקי המשחק המשותפים נשארים ניטרליים בשורש.
  **הנימוק לשינוי**: מעביר תוכן/מיקום פיזי לתיקיות אחרות דורש עדכון import בכל קובץ קיים שנוגע בהן — `input/controller.py`, `texttests/`, `tests/test_suite.py`, `tests/integration/`, `tools/`. זה מגדיל את שטח הפגיעה לרגרסיות בלי תועלת אמיתית, כשההפרדה הלוגית כבר קיימת (המודולים כבר headless ונקיים). ייבוא ישיר מ-`server/` אל השורש משיג את אותה הפרדת אחריות בלי הזזה.
- **DAL** (`server/dal/`, **חדש**): גישה טהורה ל-SQLite, אפס כללים עסקיים.
- **DTO** (`server/dto.py` + `engine/snapshot.py`): אובייקטים פשוטים להעברת נתונים בין שכבות/ברשת (`UserDTO`, `GameSnapshot`/`PieceSnapshot`).
- **Serialization** (`networking/snapshot_serializer.py`): גבול תעבורה מפורש שממיר `GameSnapshot` ל-JSON ובחזרה. הוא משותף לשרת וללקוח, אינו מכיל חוקי משחק ואינו תלוי ב-WebSocket, כך שפורמט ה-snapshot מוגדר ונבדק במקום יחיד.

**עקרון מנחה: כמה שפחות שינויים**. אף קובץ BLL קיים לא זז ולא נכתב מחדש. קבצי View/Input כמעט ולא זזים. מצב hot-seat ממשיך לעבוד זהה לחלוטין, כי `client/local_session.py` קורא ל-BLL **ישירות באותו תהליך** (בלי socket, בלי Controller/DAL — ראו גם סעיף 9, זו חריגה מודעת לשכבתיות, לא תקלה).

## 3. עץ קבצים מלא — קיים + חדש

`[חדש]` = קובץ/תיקייה חדשים. `← שינוי` = תוכן קיים משתנה. `← import בלבד` = שורת import מתעדכנת בלבד. כל השאר — ללא שינוי כלל, כולל מיקום.

```
kung-fu-chess/
├── main.py                          ← שינוי קטן: קורא ל-client.local_session.run_local() בלבד,
│                                        לא בונה Board/GameEngine/DisplayManager בעצמו
├── requirements.txt                 [חדש] — לא קיים היום קובץ תלויות כלל
├── CLAUDE.md / README.md / run_tests.ps1 / .coveragerc     ← עדכון תיעוד/coverage לפי קבצים חדשים
│
├── model/                            קיים ברמת השורש — ללא שום שינוי (BLL תפקודית, לא תיקייתית)
│   └── board.py / game_state.py / piece.py / position.py         ללא שינוי
├── rules/                            קיים — ללא שינוי
│   └── piece_factory.py / piece_rules.py / rule_engine.py         ללא שינוי
├── realtime/                         קיים — ללא שינוי
│   └── motion.py / real_time_arbiter.py                            ללא שינוי
├── boardio/                          קיים
│   ├── board_parser.py / board_printer.py                          ללא שינוי
│   └── standard_opening.py          [חדש שלב B] קבוע הפתיחה, עובר לכאן מ-view/display_manager.py
│                                        (עדיין באותה תיקייה קיימת — לא מהלך "העברה ל-server")
├── engine/                           קיים
│   ├── game_engine.py                ← שינוי: EventBus פנימי (A), start_game() (A),
│   │                                     winner_color (D), resign(color) (E)
│   ├── events.py                     [חדש A] MotionStarted/JumpStarted/Arrival/GameStarted/GameOver
│   └── snapshot.py                   [חדש B] GameSnapshot/PieceSnapshot — עוברים מ-view/renderer.py
│                                        (כדי ש-engine/, וממילא server/, לעולם לא ייבאו view/)
│
├── bus/                              קיים ברמת השורש — pub/sub גנרי, לא ספציפי-שחמט
│   └── event_bus.py                    [חדש שלב A] EventBus: subscribe/publish/subscribe_all
│
├── networking/                       [חדש B] חוזי תעבורה משותפים, ללא I/O וללא חוקי משחק
│   ├── protocol.py                     [חדש B] קידוד/פענוח MOVE/JUMP/STATE/EVENT — משותף לצדדים
│   └── snapshot_serializer.py          [חדש B] GameSnapshotSerializer: JSON ↔ GameSnapshot,
│                                           כולל ולידציית schema/version ובדיקת round-trip
│
├── server/                           [חדש] תהליך השרת — מייבא מהליבה המשותפת ישירות
│   ├── game/                          [חדש B] ניהול והרשאות של משחקים
│   │   ├── controller.py                GameController — מנתב **לפי game_id** ל-Match הנכון
│   │   ├── game_registry.py             dict[game_id, Match], למשחק קבוע ב-B ודינמי ב-E/F
│   │   └── match.py                     engine + connections + sequence של משחק מבודד אחד
│   ├── transport/                     [חדש B] גבול ה-I/O של השרת
│   │   ├── connection.py                ConnectionContext + תור יוצא מוגבל
│   │   ├── broadcaster.py               ServerBroadcaster אחד per Match
│   │   └── game_server.py               [חדש B3] websockets.serve(...), Reader/Writer
│   ├── services/                      [חדש D–F] auth/elo/matchmaker/rooms
│   ├── dal/                           [חדש D] Data Access Layer — אפס כללים עסקיים
│   │   ├── database.py                  חיבור sqlite3 + init_schema()
│   │   └── repository.py                UserRepository + GameRepository
│   ├── logging_config.py              [חדש F] לוגים מובנים עם game_id/request_id/user_id,
│   │                                     קובץ מתחלף נפרד לכל משחק וסגירת handler בניקוי Match
│   ├── config.py                      [חדש B] TICK_MS, PORT, ELO_K, DISCONNECT_GRACE_S, MATCH_TIMEOUT_S
│   ├── main.py                        [חדש B] נקודת כניסה: python -m server.main
│   └── dto.py                         [חדש D] UserDTO (GameSnapshot/PieceSnapshot כבר DTO משלהם)
│
├── input/                            קיים — Controller של קלט-משתמש (לא BLL, לא ה-Controller החדש)
│   ├── controller.py                  ללא שינוי (Board עדיין מ-model, אין import חדש כי model/ לא זז)
│   └── board_mapper.py                ללא שינוי
│
├── view/                             קיים — כמעט ללא שינוי
│   ├── display_manager.py             ← שינוי: __init__(self, board, game_engine) — חובה, בלי
│   │                                      בנייה מרומזת בפנים
│   ├── renderer.py                    ← import בלבד: GameSnapshot/PieceSnapshot מ-engine.snapshot
│   ├── observer.py / config.py / geometry.py / img.py / protocols.py     ללא שינוי
│   ├── animation/ / board/ / pieces/ / selection/ / background/          ללא שינוי
│   ├── input/commands.py, input/mouse_command_extractor.py               ללא שינוי
│   ├── hud/score/, hud/moves_log/     ללא שינוי (אין import חדש — engine/ לא זז)
│   ├── hud/countdown/                 [חדש שלב E] countdown_data.py + countdown_renderer.py
│   ├── hud/room_banner/               [חדש שלב F] room_banner_data.py + room_banner_renderer.py
│   └── audio/sound_player.py          [חדש שלב A]
│
├── client/                           [חדש] הרצה/תצוגה בלבד — אין כאן Controller/DAL
│   ├── local_session.py               [חדש B] run_local(): מייבא boardio/model/engine *ישירות*
│   │                                      (אותו תהליך, בלי socket, בלי Controller) — עוקף במכוון
│   │                                      את שכבת ה-Controller (ראו סעיף 9). main.py קורא לכאן
│   ├── main.py                        [חדש B] נקודת כניסה רשתית: python -m client.main
│   ├── network_client.py              [חדש B] חיבור WS ברקע (thread+queues)
│   ├── remote_game_engine_proxy.py    [חדש B] מתחזה ל-GameEngine, מתרגם ל/מ-הודעות רשת
│   ├── snapshot_board_view.py         [חדש B] מתחזה ל-Board מעל ה-snapshot האחרון
│   ├── cli_login.py                   [חדש C/D] קלט שם משתמש/סיסמה בשורת פקודה
│   └── room_dialog.py                 [חדש F] חלון Tkinter (טקסט + Create/Join/Cancel)
│
├── texttests/                        קיים — ללא שינוי כלל (לא נוגע ב-server/, אין import לעדכן)
├── tools/                            קיים — ללא שינוי
└── tests/                            קיים + בדיקות חדשות
    ├── test_suite.py, integration/    ללא שינוי (BLL לא זז — אין import לעדכן)
    ├── test_event_bus.py              [חדש A]
    ├── test_protocol.py               [חדש B] קידוד/פענוח WQe2e5 — פונקציות טהורות
    ├── test_snapshot_serializer.py    [חדש B] round-trip, schema version ו-payload פגום
    ├── test_game_registry.py          [חדש B] בידוד בין משחקים מקבילים (ראו סעיף 10)
    ├── test_elo.py                    [חדש D]
    ├── test_auth.py / test_repository.py   [חדש D]
    ├── test_matchmaker.py             [חדש E]
    ├── test_rooms.py                  [חדש F]
    └── integration/test_server_roundtrip.py   [חדש B]
```

## 4. זרימת קריאה לדוגמה: ביצוע מהלך (MOVE)

```
לקוח A                              שרת (תהליך אחד, מספר משחקים מקבילים)         לקוח B (אותו משחק)
──────                              ──────────────────────────────────           ──────────────────
קליק → Controller (input/) מחליט
מהלך → RemoteGameEngineProxy
  → protocol.encode_move(...) = "MOVE WQe2e5"
  → NetworkClient.send_move(...) ──────▶ match.py (המשחק הספציפי הזה): מקבל שורה
                                          → controller.handle_message(game_id, "MOVE WQe2e5")
                                            [Controller מנתב לפי game_id ל-Match הנכון]
                                          → protocol.decode_move(...) →
                                            engine.request_move(src,dst)  [BLL, engine/game_engine.py]
                                          → rules.validate + realtime.start_motion
                                          → engine.bus.publish(MotionStarted)
                                          → broadcaster **של אותו משחק** (מנוי על ה-bus שלו) מקודד
                                            "EVENT MOTION ..." ומשדר **רק** לחיבורי אותו game_id
                    ◀─────────────────────────────┴──────────────────────────▶
NetworkClient מקבל                                                    NetworkClient מקבל
→ RemoteGameEngineProxy.wait() מפרסם מחדש על bus מקומי
→ PieceAnimator/SoundPlayer מגיבים; ScoreRenderer קורא את הניקוד מה-snapshot
→ render_snapshot מצייר
```

**נקודות מפתח**: (1) תיקוף חוקיות קורה **רק** בשרת (`rules`/`realtime`, דרך ה-Controller) — תואם שקף 3. (2) השידור מוגבל ל-**אותו משחק/חדר בלבד** — קריטי כששני משחקים רצים בו-זמנית (ראו סעיף 10); ללא ההגבלה הזו, מהלכים "יזלגו" בין משחקים שונים.

## 5. שלבי המימוש

### שלב A — Bus (שקף 2)
- `bus/event_bus.py`: `subscribe(type, handler)`, `publish(event)`, `subscribe_all(observer)` — האחרון עוטף רישום ישן-סגנון (`on_motion_started`/`on_jump_started`/`on_arrival`/`on_game_over`) עבור `PieceAnimator` ו-`MovesLogData`. הניקוד נשמר במנוע ומוצג מתוך ה-snapshot.
- `engine/events.py`: דאטהקלאסים `MotionStarted`/`JumpStarted`/`Arrival`/`GameStarted`/`GameOver`.
- `engine/game_engine.py`: `self._observers=[]` → `self._bus = EventBus()`; כל לולאת `for observer in self._observers` → `self._bus.publish(...)`; `subscribe()` → `self._bus.subscribe_all(observer)`; `bus` property חדש; `start_game()` חדש שמפרסם `GameStarted()`.
- `view/display_manager.py`: אחרי ה-subscribe הקיימים — `game_engine.start_game()` + subscribe ל-`SoundPlayer`.
- `view/audio/sound_player.py`: מנוי על טיפוסי אירוע → צליל (`winsound`, Windows), נכשל בשקט אם אין asset.
- **אימות**: `_RecordingObserver` הקיים ב-`tests/test_suite.py` חייב לעבור בלי שינוי — שער רגרסיה.

### שלב B — Controller + DAL + שרת/לקוח WebSocket, מתוכנן למשחקים מקבילים (שקף 3)

**סטטוס תתי-השלבים**:

| תת-שלב | סטטוס | תוצאה |
|---|---|---|
| B1 — חוזי Snapshot ופרוטוקול | הושלם ואושר | `engine/snapshot.py`, ‏`GameSnapshotSerializer`, פרוטוקול `MOVE`/`JUMP`/`STATE`/`EVENT`; כל 139 הבדיקות עוברות |
| B2 — ליבת ניהול משחק בשרת | הושלם ואושר | `ConnectionContext`, ‏`GameRegistry`, ‏`Match`, ‏`GameController` ו-`ServerBroadcaster`; בידוד משחקים והרשאות נבדקו; הניקוד הועבר למצב הסמכותי ומופץ ב-snapshot; כל 157 הבדיקות עוברות |
| B3.1 — בסיס שרת WebSocket | הושלם ואושר | מקור משותף ללוח הפתיחה, `GameServer` עם start/serve/close, נקודת כניסה ותלויות; כל 161 הבדיקות עברו |
| B3.2a — חוזה הגדרת משחק | הושלם ואושר | `GameConfig`, serializer, ‏`JOIN`/`CONFIG_ACCEPTED`/`CONFIG_OVERRIDDEN` ו-Board factory שמאשר רק preset קיים; כל 174 הבדיקות עברו |
| B3.2b — קבלת שחקנים והקצאת צבע | הושלם ואושר | יצירת Match מה-JOIN הראשון, הקצאה אטומית של לבן/שחור, override להגדרת השני, `server_full`, שחרור צבע בניתוק ו-JOIN אמיתי דרך WebSocket; כל 181 הבדיקות עברו |
| B3.2c — Reader/Writer | הושלם ואושר | Reader מעביר פקודות ל-`GameController`, Writer יחיד שולח מהתור, המשימות נסגרות יחד והחיבור מנוקה; MOVE ו-ERR נבדקו דרך WebSocket אמיתי; כל 185 הבדיקות עברו |
| B3.3 — לולאת tick וסנכרון | הושלם ואושר | TickLoop שרתי יחיד מודד זמן מונוטוני אמיתי, שומר שברי מילישנייה, מחלק עיכוב לצעדים ומקדם את כל ה-Match-ים; ARRIVAL ו-STATE סופי נבדקו דרך WebSocket; כל 189 הבדיקות עברו |
| B3.4 — אינטגרציית WebSocket אמיתית | הושלם ואושר | בדיקת round-trip מפעילה שרת ושני לקוחות WebSocket אמיתיים על localhost, מאמתת הקצאת לבן/שחור ומוודאת שמהלך של הלבן מסתיים באותו מצב לוח אצל שני הלקוחות; כל 190 הבדיקות עברו |
| B4 — לקוח רשת ושילוב בתצוגה | ממתין | טרם מומש |
| B5 — בדיקות אינטגרציה והרשאות | ממתין | טרם מומש |

- **אין הזזת קבצים**: `model/rules/realtime/boardio/engine` נשארים בשורש. `server/` מייבא מהם ישירות. `pytest tests/` נשאר ירוק לאורך כל השלב הזה בלי שינוי import אחד בבדיקות הקיימות.
- **תכנון למשחקים מקבילים כבר בשלב זה** (המימוש בפועל של יצירה דינמית נשאר ב-E/F, אבל הממשק נבנה כך מההתחלה כדי לא לדרוש מבנה-מחדש בהמשך):
  - `server/game/game_registry.py`: `dict[game_id, Match]`. ב-B — `GameServer` יוצר משחק קבוע יחיד ורושם אותו ב-registry עם `game_id` קבוע (למשל `"default"`), רק כדי לספק את הדרישה הפשוטה של השקף (2 לקוחות, משחק אחד). אבל שום קוד לא מניח "יש בדיוק משחק אחד" — הניתוב תמיד עובר דרך ה-registry.
  - `server/game/controller.py`: כל מתודה מקבלת `game_id` (או `connection` שכבר יודע לאיזה `game_id` הוא שייך, מוקצה ב-`game_server.py` בזמן החיבור) — לא Singleton גלובלי של `engine`.
  - `server/transport/broadcaster.py`: **מופע אחד per Match**, לא מופע גלובלי יחיד — נבנה ונרשם על ה-bus כשה-`Match` נוצר, משדר רק ל-connections השייכים לאותו `game_id`.
- פרוטוקול טקסט (שורה=הודעה), תואם לדוגמה מהשקף:

  | כיוון | תבנית | דוגמה |
  |---|---|---|
  | C→S | `MOVE <Color><Kind><src><dst>` | `MOVE WQe2e5` |
  | C→S | `JUMP <Color><Kind><src>` | `JUMP BNe4` |
  | S→C | `OK`/`ERR <reason>` | `ERR resting` (משתמש חוזר במחרוזות `_MoveResult.reason` הקיימות) |
  | S→C | `STATE <לוח>\|<flags>` | פורמט קרוב ל-`board_printer.py` |
  | S→C | `EVENT MOTION/JUMP/ARRIVAL/GAMEOVER ...` | שידור ישיר של אירועי ה-bus, מוגבל למשחק |

- **פורמט המהלך נשמר בהתאם לדרישה** (`WQe2e5` / `BNe4`). עם זאת, הצבע וסוג הכלי שמופיעים בהודעה אינם מקור סמכות: השרת מאמת אותם מול החיבור, הצבע שהוקצה לו והכלי שנמצא בפועל במשבצת המקור. לקוח אינו יכול להזיז כלי של היריב באמצעות שינוי הטקסט.
- לכל בקשת לקוח יוצמד `request_id`, שיוחזר ב-`OK`/`ERR`, כדי שאפשר יהיה לשייך תשובה לפקודה גם כשכמה הודעות נמצאות בתנועה במקביל.
- כל `STATE`/`EVENT` יכלול `game_id`, מספר `sequence` עולה ו-`server_time_ms`. הלקוח יתעלם מהודעות ישנות או כפולות. פקודות המהלך נשארות בפורמט הטקסט הנדרש; payload מורכב של `STATE`/`EVENT` יישלח כ-JSON בתוך מעטפת טקסט, במקום פורמט לוח עמום.
- `networking/snapshot_serializer.py` הוא המקור היחיד לפורמט ה-JSON של `STATE`: הוא מבצע המרה דו-כיוונית, כולל `schema_version`, ולידציית שדות ו-round-trip. `networking/protocol.py` עוטף את ה-JSON במעטפת הטקסט בלבד; השרת והלקוח אינם מרכיבים payload ידנית.
- `STATE` הוא snapshot מלא שמספיק לחיבור באמצע משחק או לחיבור מחדש. הוא כולל: כלים ומצביהם, תנועה פעילה (מקור/יעד/זמן הגעה), זמני נחיתה ומנוחה, ניקוד, מצב משחק, מנצח, תפקיד הלקוח וזמן השרת.
- לכל חיבור נשמר `ConnectionContext`: `user_id`, `session_token`, `game_id`, `role` (`PLAYER`/`SPECTATOR`) ו-`color`. ה-Controller בודק הרשאה לפני כל `MOVE`/`JUMP`, בנוסף לבדיקת חוקיות המהלך ב-BLL.

- `server/game/match.py`: לולאת קליטה לכל חיבור (מעבירה ל-Controller עם ה-`game_id` שלה) + לולאת טיק (`engine.wait(TICK_MS)` כל 50ms — תחליף ללולאת ה-`cv2`, אחת per Match).
- לולאת הטיק משתמשת בשעון מונוטוני ומעבירה ל-`engine.wait(...)` את הזמן שעבר בפועל, ולא מניחה שכל סיבוב ארך בדיוק 50ms. כך עומס רגעי בשרת לא ייצור drift בזמן המשחק.
- `server/transport/game_server.py`: `websockets.serve(...)`, מקצה `game_id` לחיבור (ב-B: תמיד "default"), חיבור ראשון=White, שני=Black (מספיק לדרישת שלב C).
- `client/network_client.py`: thread נפרד + asyncio (כי `cv2.waitKey` חוסם וצריך thread ראשי) + `queue.Queue` יוצא/נכנס.
- `EventBus.publish()` נשאר סינכרוני ואינו מבצע `await websocket.send()`. ה-Broadcaster מכניס הודעות לתור יוצא מוגבל לכל חיבור, ומשימת writer אסינכרונית שולחת אותן. לקוח איטי אינו רשאי לחסום את ה-GameEngine או לקוחות אחרים.
- `client/remote_game_engine_proxy.py` + `client/snapshot_board_view.py`: מתחזים ל-`GameEngine`/`Board` כך ש-`Controller`/`DisplayManager` הקיימים לא זזים בלוגיקה.
- **בעלות על הזמן**: רק השרת מקדם את זמן המשחק ומכריע הגעה, תפיסה, נחיתה ו-cooldown. שעון הלקוח משמש לאנימציה, heartbeat וזיהוי ניתוק בלבד. בזמן ניתוק הלקוח רשאי להשלים חזותית אנימציה שכבר ידועה לו, אך אינו משנה מצב משחק סמכותי; לאחר reconnect מתקבל `STATE` מלא שמיישר את התצוגה.
- `view/display_manager.py`: `__init__(self, board, game_engine)` חובה.
- `client/local_session.py`: בונה BLL ישירות (מקומי) ומריץ `DisplayManager` — `main.py` קורא לכאן. **עוקף את ה-Controller במכוון** (ראו סעיף 9).

### שלב C — Login שם משתמש בלבד (שקף 4)
- `client/cli_login.py`: `input("Username: ")`, נשלח כ-`LOGIN <username>` לפני הכל.
- שרת: 2 שחקנים בלבד — חיבור שלישי מקבל `ERR server_full`. שיוך צבע לפי סדר חיבור (כבר קיים משלב B).

### שלב D — סיסמה + SQLite + ELO (שקף 5)
- `server/dal/database.py`: `sqlite3` + `init_schema()` — טבלאות `users(id, username UNIQUE, password_hash, salt, rating DEFAULT 1200, created_at)`, `games(id, white_user_id, black_user_id, winner_color, ratings before/after, started_at, ended_at)`.
- `server/dal/repository.py`: `UserRepository.get_by_username/create_user/update_rating` (מחזיר `UserDTO`), `GameRepository.record_game`.
- `server/services/auth.py`: `register`/`login` — מגבב (`hashlib.pbkdf2_hmac`+`secrets.token_hex` salt), קורא ל-`server/dal/`, **לא נוגע ב-SQL**.
- `server/services/elo.py`: `compute_elo(rating_a, rating_b, score_a, k=32)` — נוסחה סטנדרטית, פונקציה טהורה.
- `server/game/controller.py`: מטפל גם ב-`LOGIN <user> <pass>`/`REGISTER`.
- **שינוי BLL קטן**: `GameEngine` לא מדווח היום מי ניצח. מוסיף `winner_color` property (Protocol `on_game_over()` לא משתנה) — `server/game/match.py` קורא לזה בסיום, מזין ל-`elo.compute_elo` ואז ל-DAL.
- תוצאת משחק היא אובייקט מפורש הכולל `winner_color`, סיבה (`KING_CAPTURE`/`RESIGN`/`DISCONNECT`) וזמן סיום. כל מסלולי הסיום עוברים דרך `Match.finish(result)` אידמפוטנטי, כדי ששמירת המשחק ועדכון ELO יתבצעו פעם אחת בלבד ובטרנזקציה אחת.

### שלב E — Matchmaking + ניתוקים (שקף 6)
- `server/services/matchmaker.py`: `find_or_wait(player)` — התאמה בטווח ±100; אם לא — `asyncio.sleep` עד 60 שניות ואז `MATCH TIMEOUT`. בדיקת timeout מבודדת בפונקציה טהורה (`has_timed_out`) לבדיקה בלי `sleep` אמיתי. עם התאמה — **יוצר `Match` חדש ורושם אותו ב-`game_registry`** (כאן, לראשונה, ה-registry מקבל יותר ממשחק אחד בפועל).
- ניתוק: `server/game/match.py` תופס `ConnectionClosed`, פותח טיימר 20 שניות, משדר `EVENT DISCONNECT <sec>` (מוגבל לאותו משחק), ואם חולף — קורא ל-`GameEngine.resign(color)` (חדש, מקביל ל"מלך נתפס").
- זיהוי ניתוק נעשה באמצעות ping/pong של WebSocket ו-timeout, ולא באמצעות קידום זמן משחק בצד הלקוח. הלקוח עובר בין `CONNECTED`/`UNSTABLE`/`DISCONNECTED`/`RECONNECTING`, חוסם פקודות משחק כשהקשר אבד ומציג את מצב החיבור.
- login מוצלח מחזיר `session_token` זמני. בתוך חלון החסד הלקוח שולח `RECONNECT <session_token>`; השרת משייך את החיבור החדש לאותו משתמש, Match וצבע, מבטל resign ושולח snapshot מלא.
- `view/hud/countdown/`: ספירה לאחור על המסך.

### שלב F — חדרים + צופים + לוגים (שקף 7)
- `client/room_dialog.py`: חלון Tkinter (Entry + Create/Join/Cancel), רץ ומסתיים **לפני** פתיחת ה-OpenCV.
- `server/services/rooms.py`: `create_room()` (מזהה קצר) → יוצר=White, **יוצר `Match` חדש ב-`game_registry`**; `join_room(id, player)` → שני=Black, כל הבא=צופה (חסום מ-MOVE/JUMP, מקבל STATE/EVENT של אותו `game_id`).
- השרת מנהל מצב משתמש מפורש (`OFFLINE`/`LOBBY`/`QUEUED`/`IN_GAME`/`SPECTATING`) כדי למנוע כניסה כפולה לתור, התאמה לשני משחקים או משחק וצפייה במקביל.
- מזהה חדר "בראש המסך": `view/hud/room_banner/` — בנר בתוך קנבס ה-OpenCV.
- לוגים: `server/main.py`→`server.log`; `client/main.py`→`client_<username>.log` (נקבע אחרי login, כדי ששני לקוחות מקומיים לא ידרסו קובץ זה של זה).
- בנוסף, לכל `Match` ייכתב לוג פעילות מתחלף משלו (`logs/games/game_<game_id>.log`) עם `game_id`, ‏`request_id`, ‏`user_id`, סוג אירוע וזמן שרת. ה-handler נסגר עם ניקוי המשחק ונקבעת מדיניות rotation/retention כדי למנוע גדילה בלתי מוגבלת.

## 6. אסטרטגיית בדיקות

- הליבה (`model`/`rules`/`realtime`/`engine`/`boardio`) ממשיכה להיבדק headless דרך `texttests/` הקיים — **אין שום שינוי import**, כי הקבצים לא זזו.
- `test_event_bus.py`/`test_protocol.py` — יחידה טהורה, בלי asyncio/sockets.
- `test_game_registry.py` (שלב B) — מוודא שני `Match` מדומים לא "מדליפים" אירועים אחד לשני (בודק את `broadcaster`/`controller` עם מזהי game_id שונים, בלי sockets אמיתיים).
- `test_elo.py`, `test_auth.py`+`test_repository.py` (מול `sqlite3.connect(":memory:")`).
- `test_matchmaker.py` (שעון מוזרק, בלי sleep אמיתי), `test_rooms.py` (בלי sockets).
- בדיקת אינטגרציה אחת (`test_server_roundtrip.py`, שלב B) — שרת+לקוח אמיתיים על localhost.
- בדיקות נוספות לפרוטוקול והרשאות: לקוח שחור שמתחזה ללבן, צופה ששולח מהלך, הודעה פגומה, `sequence` ישן/כפול ושיוך `request_id` לתגובה.
- בדיקות מחזור חיים: reconnect בתוך חלון החסד, resign לאחר timeout, סיום משחק אידמפוטנטי, ניקוי Match מה-registry ולקוח איטי שאינו חוסם אחרים.
- בדיקות serialization: round-trip מלא של snapshot, תאימות `schema_version`, שדות חסרים/payload פגום ושמירה על כל נתוני התנועה, המנוחה, הניקוד והתפקיד.
- בדיקות עומס וביצועים (`tests/load/` או כלי ייעודי): משחקים מקבילים, צופים רבים, לקוח איטי, burst של פקודות וניקוי משחקים. נאספים לפחות latency ‏p95, סטיית tick, גודל תורים, זיכרון וקצב הודעות. ספי ההצלחה המספריים יוסכמו לפני הרצת בדיקת הקבלה; הבדיקה אינה טוענת לתמיכה באלפי משתמשים על ארכיטקטורת התהליך היחיד.
- `requirements.txt` חדש: `opencv-python`, `numpy`, `websockets` (מותקן כבר, גרסה 16.0), `pytest`, `pytest-cov`.

## 7. אימות End-to-End לכל שלב

1. אחרי A: `python main.py` — ניקוד/לוג/בחירה זהים להיום, `pytest tests/` ירוק.
2. אחרי B: `python -m server.main` + שני `python -m client.main` — מהלך בחלון אחד מופיע בשני. `pytest tests/` (כולל הישנות) עדיין ירוק בלי עדכון import.
3. אחרי C-F: login בשורת פקודה, הרשמה+דירוג, Play עם יריב קרוב/רחוק בדירוג, ניתוק (Ctrl+C) → countdown+resign, יצירת/הצטרפות לחדר עם 3 לקוחות (2 שחקנים+צופה), **וכן: שני משחקים/חדרים פתוחים בו-זמנית — לוודא שמהלכים בחדר אחד לא מופיעים בחדר השני**.

## 8. קבצים קריטיים למימוש

- `engine/game_engine.py`, `server/game/controller.py`, `networking/protocol.py`, `server/game/game_registry.py`, `server/transport/broadcaster.py` (ליבת השלב הרשתי, כולל בידוד בין משחקים)
- `view/display_manager.py`, `view/renderer.py`
- `main.py` (root), `client/local_session.py`
- `input/controller.py` (ללא שינוי בפועל — לא להתבלבל עם `server/game/controller.py` החדש)
- `server/dal/repository.py`, `server/dto.py`
- `tests/test_suite.py`, `texttests/` — נשארים ירוקים לאורך כל התהליך בלי עדכון import (כי BLL לא זז)

## 9. נקודות שהנחתי / חריגות מודעות — נא לאשר/לתקן

- **חריגה מודעת בשכבתיות**: `client/local_session.py` (מצב hot-seat מקומי) עוקף לגמרי את שכבת ה-Controller ומדבר ישירות מול ה-BLL (`engine.game_engine.GameEngine`) — באותו תהליך, בלי socket, בלי `networking/protocol.py`, בלי `server/game/controller.py`. זה **מכוון**, לא פספוס: המטרה היא ששחקן יחיד/hot-seat לא יזדקק לתהליך שרת נפרד כדי לשחק. אך זו בהחלט חריגה מעקרון "כל בקשה עוברת Controller" שמוחל בנתיב הרשתי — מתועד כאן במפורש כדי שלא "יתגלה" כהפתעה בסקירת קוד.
- פורמט ההודעות הלא-move (login/room/play/state) — הדרישות נותנות רק דוגמת move (`WQe2e5`); שאר הפורמט (`LOGIN`, `ROOM CREATE`, `STATE ...`) הוא הרחבה סבירה באותו סגנון טקסטואלי, לא כתוב במפורש בשקפים.
- "Room" ב-Create מושיב את היוצר כ-White מיד (לא רק שומר מזהה) — סביר לפי "the second person that joins... is Black", אך לא נאמר מפורש מה קורה ליוצר.
- חלון ה-Room (שקף 7) הוא Tkinter (טקסט+3 כפתורים) — לא ctypes MessageBox פשוט, כי צריך תיבת טקסט וגם 3 כפתורים מותאמים.
- פורמט `MOVE WQe2e5` נשמר לפי הדרישה. הנתונים `WQ` מאומתים בצד השרת ואינם משמשים כהרשאה.
- פורמט `STATE`/`EVENT` המורכב ניתן לשינוי ולכן יוגדר כמעטפת טקסט עם payload מסוג JSON, כולל `sequence` וזמן שרת.
- בזמן ניתוק שעון התצוגה ממשיך מקומית לצורכי אנימציה וזיהוי timeout, אך שעון המשחק והכרעות המשחק נשארים בשרת בלבד.

## 10. שיקולי קנה מידה (אלפי משתמשים מקבילים)

הדרישות המקוריות מתארות 2 לקוחות/משחק אחד; הבהרה מאוחרת יותר מציינת שבפועל השרת צריך לשרת בסופו של דבר אלפי משתמשים (שחקנים+צופים) במשחקים רבים במקביל. התוכנית הזו **לא מיישמת** תשתית full-scale (זה מעבר לתכולת שקפים 2-7), אבל התכנון משלב B ואילך כבר לא מניח "משחק גלובלי יחיד" (ראו `game_registry`/`broadcaster` per-match לעיל). הבחנה בין מה שכבר לא חוסם קנה-מידה עתידי לבין מה שכן:

**כבר לא חוסם (מוכן למעבר עתידי, בלי לשנות את התוכנית הזו)**:
- כל `Match` מחזיק `GameEngine`/`Board`/`RuleEngine`/`RealTimeArbiter` משלו — כבר יחידת-בידוד נקייה per-game מ-B ואילך; זו בדיוק היחידה שהייתה עוברת לתהליך/worker נפרד אילו נדרש מעבר ל-multi-process.
- ה-BLL (`engine`/`rules`/`realtime`/`model`) חסר I/O לגמרי — ניתן להריץ בכל מודל ריצה (thread/coroutine/worker process) בלי שינוי.
- `server/dal/` מבודד מאחורי ממשק repository — מעבר מ-SQLite ל-DB אחר (Postgres וכו') נשאר מוכל שם, לא נוגע ב-BLL/Controller.
- פרוטוקול הטקסט לא מניח טופולוגיית תהליכים — לקוח פשוט מדבר WS "עם השרת", לא משנה אם זה תהליך יחיד או שער שמנתב לשירוד (shard).

**כן חוסם היום, ודורש עבודה עתידית מפורשת (מחוץ לתכולת התוכנית הזו)**:
- **event loop יחיד, תהליך יחיד**: כל לולאות הטיק של כל ה-`Match`ים רצות קואופרטיבית על אותו `asyncio` event loop/ליבת CPU אחת. אלפי משחקים מקבילים ידרשו כמה תהליכים/workers עם שכבת ניתוב (איזה תהליך מחזיק איזה `game_id`) — לא מתוכנן כאן, ודורש שינוי ארכיטקטורה נפרד.
- **SQLite**: קובץ יחיד, writer יחיד — מספיק לפרויקט לימודי/קנה-מידה נמוך, לא לכתיבות מקבילות בקנה-מידה גדול. בזכות בידוד ה-DAL, זה שינוי מוכל (להחליף repository implementation), לא ripple effect.
- **מצב זיכרון פנימי** של `Matchmaker`/`game_registry` (רשימות ממתינים, מיפוי game_id) חי בזיכרון של תהליך יחיד — מעבר למספר תהליכי שרת ידרוש מצב משותף (Redis/DB), כי כל תהליך "רואה" רק את הזיכרון שלו.
- **בידוד broadcast בין משחקים** (הוזכר בשלב B) הוא תיקון-קדם נדרש **גם בלי** שאלת קנה-המידה — בלעדיו, משחק שני מקביל היה "מדליף" מהלכים לשחקנים במשחק אחר. זו לא רק דאגת עומס, אלא תקינות פונקציונלית בסיסית.

## 11. כללי עבודה מוסכמים למימוש התוכנית

- עוזר הקידוד רשאי להציע חלופות, סיכונים ורעיונות, אך אינו קובע החלטות מוצר או ארכיטקטורה במקום בעל הפרויקט.
- לפני כל שינוי בקוד יינתן הסבר על השינוי המוצע, הסיבה לו ומקומו בתמונה הכללית, ויידרש אישור מפורש מבעל הפרויקט.
- שינוי בתיעוד או בקוד יתבצע רק במסגרת שאושרה; אישור לשלב אחד אינו אישור אוטומטי לשלבים הבאים.
- ההסברים יהיו ברורים ומפורטים מספיק לקבלת החלטה, אך התשובות עצמן יישארו קצרות ותמציתיות ככל האפשר.

## 12. סטטוס וקריטריוני השלמה

סטטוס משתנה ל-`הושלם` רק לאחר שכל קריטריוני הקבלה של השלב עברו ותועדו. יצירת הקבצים לבדה אינה השלמת שלב.

| שלב | סטטוס נוכחי | קריטריוני השלמה מרכזיים |
|---|---|---|
| A — Bus | הושלם | כל אירועי המשחק עוברים ב-EventBus; צרכני ה-View והצלילים פועלים; בדיקות היחידה והרגרסיה ירוקות |
| B — Network | בתהליך — B1–B2 הושלמו ואושרו | שני לקוחות מסונכרנים מול שרת סמכותי; serializer עובר round-trip; הרשאות צבע ו-request_id תקינים; אין דליפת אירועים בין משחקים; בדיקות ישנות ו-round-trip אמיתי ירוקות |
| C — Username Login | ממתין | login בשם משתמש, הקצאת White/Black והודעת `server_full` מאומתים מקצה לקצה |
| D — Auth + SQLite + ELO | ממתין | register/login מאובטחים; rating מתחיל ב-1200; סיום משחק מעדכן DB ו-ELO פעם אחת ובטרנזקציה אחת |
| E — Matchmaking + Disconnect | ממתין | התאמה בטווח ±100 ו-timeout; reconnect בחלון 20 שניות; countdown ו-auto-resign נבדקו |
| F — Rooms + Spectators + Logs | ממתין | Create/Join/Cancel; שני שחקנים וצופים עם הרשאות נכונות; שני חדרים מבודדים; לוגי שרת/לקוח/משחק נוצרים ונסגרים כראוי |

## 13. קריטריוני Release סופיים

Release מוכן רק כאשר:

- כל שלבים A–F עומדים בקריטריוני ההשלמה שלהם וכל חבילת `pytest tests/` ירוקה.
- התקנה והרצה מצליחות מ-clone נקי לפי `requirements.txt` ו-README, הן במצב offline והן במצב שרת+שני לקוחות.
- תרחיש E2E כולל login, משחק, תפיסה, סיום, ELO, reconnect, חדר וצופה עבר ללא התערבות בקוד.
- שני משחקים מקבילים נשארים מבודדים, ולקוח איטי אינו חוסם את לולאת המשחק או לקוחות אחרים.
- בדיקות העומס עברו מול ספי הקבלה שסוכמו מראש, ללא גידול זיכרון/תורים בלתי מוגבל וללא drift חריג של שעון המשחק.
- אין סיסמאות, session tokens או מידע רגיש בלוגים; rotation/retention וניקוי Match נבדקו.
- התיעוד כולל הוראות התקנה, הרצה, בדיקות, פרוטוקול, מגבלות ידועות וגרסת schema של snapshot.

## 14. הרחבות עתידיות — מחוץ לשלבי החובה

- **Player Profile**: מסך/DTO להצגת שם משתמש, דירוג, היסטוריית משחקים ונתונים מצטברים. יישקל לאחר ששלבים D–F יציבים, כדי לא להרחיב מוקדם את סכמת הנתונים ואת ממשק המשתמש. תוספת זו אינה תנאי ל-Release הנוכחי ולא תמומש ללא תכנון ואישור נפרדים.
