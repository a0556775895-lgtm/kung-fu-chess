# Kung Fu Chess — ארכיטקטורת הלקוח והתצוגה

מסמך זה מתאר את המבנה לאחר ארגון הפרויקט מחדש. כל קוד הלקוח נמצא תחת `client/`, והנכסים הגרפיים נמצאים תחת `client/assets/`.

## עקרונות

- השרת הוא מקור האמת היחיד למצב המשחק ולזמנים.
- הלקוח שולח בקשות `MOVE` ו-`JUMP`, ומציג snapshots ואירועים שחזרו מהשרת.
- ללקוח אין מצב משחק מקומי והוא אינו מייבא חוקי משחק מתוך `server/`.
- משכי תנועה וקפיצה מגיעים באירועי הרשת; זמני מנוחה נגזרים מה-snapshot.
- רכיבי Loader טוענים נכסים, ורכיבי Renderer מציירים אותם.

## עץ הקבצים

```text
client/
├── main.py
├── config.py
├── cli_auth.py
├── lobby_controller.py
├── network_client.py
├── network_event_adapter.py
├── remote_game_engine_proxy.py
├── snapshot_board_view.py
│
├── input/
│   ├── board_mapper.py
│   ├── commands.py
│   ├── input_controller.py
│   └── mouse_command_extractor.py
│
├── transport/
│   ├── connection_state.py
│   ├── errors.py
│   ├── lobby_session.py
│   └── websocket_transport.py
│
├── view/
│   ├── config.py
│   ├── geometry.py
│   ├── image_utils.py
│   ├── img.py
│   ├── display_manager.py
│   ├── animation/
│   ├── audio/
│   ├── background/
│   ├── board/
│   ├── game_over/
│   ├── hud/
│   ├── lobby/
│   ├── pieces/
│   └── selection/
│
└── assets/
    ├── pieces/
    ├── sounds/
    └── waiting_animation/
```

החוזים והמודלים שהלקוח חולק עם השרת נמצאים תחת `networking/`. הקבצים הישנים `view/renderer.py`, ‏`view/observer.py` ו-`view/protocols.py` הוסרו משום שלא היו בשימוש לאחר המעבר לחוזים המשותפים.

## זרימת קלט

```text
OpenCV mouse callback
  -> MouseCommandExtractor
  -> ClickCommand / JumpCommand
  -> InputController / RemoteGameEngineProxy
  -> NetworkClient
  -> WebSocket
```

`client/input/input_controller.py` מחזיק את בחירת הכלי ומתרגם זוג קליקים לבקשת מהלך. השם `InputController` מבדיל אותו מ-`GameController` בצד השרת ומ-`LobbyController` בצד הלקוח.

`client/input/board_mapper.py` הוא מקור האמת להמרת פיקסלים לתאי לוח. `client/view/geometry.py` אחראי לכיוון ההפוך ולגודל הלוח בחלון.

## זרימת מצב ואירועים

```text
STATE / EVENT מהשרת
  -> NetworkClient
  -> NetworkEventAdapter / RemoteGameEngineProxy
  -> EventBus מקומי
  -> DisplayManager, PieceAnimator, MovesLogData, SoundPlayer
```

המודלים `GameSnapshot` ו-`PieceSnapshot` נמצאים ב-`networking/models/snapshot.py`. אירועים משותפים, לרבות `MotionStarted`, ‏`JumpStarted` ו-`Arrival`, נמצאים ב-`networking/events.py`.

`JumpStarted` כולל `duration_ms`, כך שהלקוח אינו צריך להכיר את קבועי חוקי המשחק. `PieceAnimator` משתמש ב-`resting_until` וב-`server_time_ms` שב-snapshot כדי לחשב את זמן המנוחה החזותי.

## `DisplayManager`

`client/view/display_manager.py` מקבל בהזרקה:

- תצוגת לוח לקריאת snapshots;
- proxy לשליחת בקשות משחק;
- updater שמקדם את מצב הלקוח;
- מקור אירועים להרשמת רכיבי התצוגה.

אין בו מסלול שמקים `GameEngine` מקומי. `client/main.py` מרכיב אותו עם `RemoteGameEngineProxy` ועם מתאם אירועי הרשת.

`DisplayManager` הוא הרכיב שמנהל את חלון OpenCV, את לולאת הפריימים ואת callback העכבר. פעולות הציור עצמן עוברות דרך `Img` ורכיבי ה-Renderer.

## אנימציה

`client/view/animation/animation_library.py` טוען מראש את חמשת מצבי האנימציה של כל סוג וצבע:

- `idle`
- `move`
- `jump`
- `short_rest`
- `long_rest`

`PieceAnimator` משלב בין האירועים המשותפים לבין ה-snapshot העדכני. התקדמות התנועה מבוססת על משך האירוע, והמעבר למנוחה מבוסס על זמן השרת שב-snapshot. אם כלי נעלם מה-snapshot לאחר תפיסה, המצב החזותי המקומי שלו מנוקה.

## נכסים ונתיבים

כל הנתיבים נגזרים מ-`Path(__file__)` ב-`client/view/config.py`, ולכן ההפעלה אינה תלויה בתיקיית העבודה הנוכחית.

```text
client/assets/pieces/{KIND}{COLOR}/states/{state}/
├── config.json
└── sprites/{n}.png
```

סדר שם תיקיית כלי הוא `Kind+Color`, לדוגמה `QW`. תמונות נקראות באמצעות `numpy.fromfile` ו-`cv2.imdecode` כדי לתמוך גם בנתיב פרויקט שמכיל תווי Unicode.

## HUD

- `hud/score/` מציג ניקוד סמכותי מה-snapshot.
- `hud/moves_log/` מחזיק יומן תצוגה מקומי שניזון מאירועי הגעה.
- `hud/connection_status/` מציג את מצב החיבור.
- שמות השחקנים ומצב המשחק מגיעים מהשרת דרך ה-snapshot.

## גבולות תלות

- `client/` רשאי לייבא מתוך `networking/`.
- `client/` אינו מייבא מתוך `server/`.
- `networking/` אינו מייבא מתוך `client/` או `server/`.
- נכסים ופרטי OpenCV נשארים בצד הלקוח בלבד.
