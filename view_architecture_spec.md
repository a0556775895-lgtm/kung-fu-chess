# KungFu Chess — מפרט ארכיטקטורת ה-View

## עקרון-על

כל רכיב גרפי = תיקייה נפרדת עם **Loader** (טעינה חד-פעמית מהדיסק) ו-**Renderer** (ציור חוזר בכל frame). התפקידים לא מתערבבים. מידע משותף מוחזק במבנים ממוקדים, מוזרקים (dependency injection) רק למי שבאמת צריך אותם.

**ללא שינוי:** `model/`, `rules/`, `realtime/`, `input/board_mapper.py`, `input/controller.py`, `view/img.py`.
**תוספות ל-`engine/game_engine.py`:** `subscribe()`, והתראות `on_arrival`/`on_motion_started`/`on_jump_started`/`on_game_over` מתוך `wait()`/`request_move()`/`request_jump()`.

---

## עץ הקבצים

```
view/
├── config.py                      # BOARD_ROWS/COLS, WINDOW_SIZE, FRAME_DELAY_MS, MAX_DT_MS,
│                                   #   ASSETS_ROOT, PIECE_KINDS, PIECE_COLORS, ANIMATION_STATES
├── protocols.py                   # Renderer, Loader — Protocol
├── image_utils.py                 # ensure_alpha()
├── geometry.py                    # BoardGeometry
├── img.py                         # מסופק, קבוע
│
├── board/
│   ├── board_loader.py            # BoardLoader
│   └── board_renderer.py          # BoardRenderer
│
├── pieces/
│   ├── piece_loader.py            # PieceLoader
│   └── piece_renderer.py          # PieceRenderer
│
├── animation/
│   ├── state_config.py            # PhysicsConfig / GraphicsConfig / StateConfig
│   ├── animation_config_loader.py # AnimationConfigLoader
│   ├── animation_library.py       # AnimationLibrary
│   └── piece_animator.py          # PieceAnimator
│
├── hud/
│   ├── score/score_renderer.py
│   ├── moves_log/{moves_log_data.py, moves_log_renderer.py}
│   └── player_panel/player_panel_renderer.py
│
├── input/
│   ├── mouse_command_extractor.py # MouseCommandExtractor
│   └── commands.py                # ClickCommand / JumpCommand / CommandSender / LocalCommandSender
│
├── observer.py                    # GameObserver (Protocol)
└── display_manager.py             # DisplayManager

engine/
└── game_engine.py                 # + subscribe(), + התראות מתוך wait()/request_move()/request_jump()
```

---

## מפרט המודולים

### `config.py`
קבועים גלובליים יחידים לכל הפרויקט: `BOARD_ROWS=8`, `BOARD_COLS=8`, `WINDOW_SIZE=(640,640)`, `FRAME_DELAY_MS=30`, `MAX_DT_MS=100`, `ASSETS_ROOT=Path("view")/"assest"/"PIECE3"`, `PIECE_KINDS=("P","N","B","R","Q","K")`, `PIECE_COLORS=("W","B")`, `ANIMATION_STATES=("idle","move","jump","short_rest","long_rest")`. כל שאר הקבצים מייבאים משם — אין ערך קבוע כפול באף מקום אחר.

### `protocols.py`
```python
class Renderer(Protocol):
    def render(self, canvas, snapshot) -> None: ...

class Loader(Protocol):
    def load(self) -> None: ...
```
כל renderer בפרויקט מיישם את אותה חתימה, כדי ש-`DisplayManager` יחזיק רשימה גנרית בלי branching לפי סוג.

### `geometry.py` — `BoardGeometry`
מקור האמת היחיד לגודל תא/לוח, מוזרק (instance משותף אחד) לכל מי שצריך אותו — `board/`, `pieces/`, `input/`.
```python
@dataclass
class BoardGeometry:
    rows: int = config.BOARD_ROWS
    cols: int = config.BOARD_COLS
    window_width: int = config.WINDOW_SIZE[0]
    window_height: int = config.WINDOW_SIZE[1]
    board_origin_x: int = 0   # offset בגלל HUD
    board_origin_y: int = 0

    @property
    def cell_w(self) -> int: return self.window_width // self.cols
    @property
    def cell_h(self) -> int: return self.window_height // self.rows

    def cell_to_pixel(self, position: Position) -> tuple[int, int]:
        return (self.board_origin_x + position.col * self.cell_w,
                self.board_origin_y + position.row * self.cell_h)

    def resize(self, width: int, height: int) -> None:
        self.window_width, self.window_height = width, height
```
אין `pixel_to_cell` כאן — התרגום ההפוך מבוצע ע"י `BoardMapper` הקיים (`input/board_mapper.py`), אין כפילות חישוב.

### `board/board_loader.py` — `BoardLoader`
טוען את `board.png` **בגודל שנקבע ע"י `geometry.window_width/height` הנוכחי** (לא קבוע נפרד), מבטיח ערוץ אלפא (`image_utils.ensure_alpha`), שומר עותק "נקי" (ללא כלים). חושף `fresh_canvas()` (מחזיר עותק נקי לכל frame) ו-`reload()` (טעינה מחדש בגודל עדכני, לקריאה בעת resize בלבד).

### `pieces/piece_loader.py` — `PieceLoader`
בונה נתיב וקורא sprite בודד: `(kind, color, state, frame_index) -> Img`. ממיר `Color+Kind` (מוסכמת המודל) ל-`Kind+Color` (מוסכמת תיקיית הנכסים): `folder = f"{kind}{color}"`.

### `pieces/piece_renderer.py` — `PieceRenderer`
מצייר כל כלי חי לפי ה-`snapshot` הנוכחי, בקריאה בלעדית ל-`AnimationLibrary` (זיכרון) — אף פעם לא ל-`PieceLoader` ישירות בזמן ריצה.

### `animation/state_config.py`
```python
@dataclass(frozen=True)
class PhysicsConfig:
    speed_m_per_sec: float
    next_state_when_finished: str

@dataclass(frozen=True)
class GraphicsConfig:
    frames_per_sec: int
    is_loop: bool

@dataclass(frozen=True)
class StateConfig:
    physics: PhysicsConfig
    graphics: GraphicsConfig
```
מיפוי ישיר לסכימת ה-`config.json` בתיקיית כל state. `physics.speed_m_per_sec`/`next_state_when_finished` משמשים רק לבניית גרף המעברים בין 5 ה-states; לא משמשים לחישוב תזמון בפועל (זה בבעלות `piece_rules.get_arrival_duration` הקיים, ומקבוע 1000ms לקפיצה — ראו `piece_animator.py`).

### `animation/animation_config_loader.py`
טוען את כל 5 קובצי ה-`config.json` של כלי, ומוודא ב-startup שכל `next_state_when_finished` מצביע ל-state קיים בפועל (typo נתפס מיד, לא כתקיעה חזותית בזמן ריצה).

### `animation/animation_library.py` — `AnimationLibrary`
```python
@dataclass(frozen=True)
class AnimationClip:
    frames: list[Img]
    state_config: StateConfig

class AnimationLibrary:
    def __init__(self, assets_root=config.ASSETS_ROOT, kinds=config.PIECE_KINDS,
                 colors=config.PIECE_COLORS, states=config.ANIMATION_STATES, cell_size=None):
        self._clips: dict[tuple[str,str,str], AnimationClip] = {}
        # טוען הכל פעם אחת, כשל מוקדם + fallback ויזואלי אם sprite חסר

    def get_clip(self, kind, color, state) -> AnimationClip: ...
    def reload(self, cell_size) -> None: ...   # נקרא רק באירוע resize, לא בכל frame
```
כל 12 הכלים × 5 states נטענים פעם אחת ל-startup; אין קריאת דיסק בזמן ריצה רגיל.

### `animation/piece_animator.py` — `PieceAnimator`
ממפה, לכל כלי, בין `PieceState` (המודל: `IDLE/MOVING/CAPTURED/AIRBORNE`) ל-state חזותי (5 states). מקבל התראות `on_motion_started`/`on_jump_started` (מקור: `GameObserver`) לדעת יעד ומשך זמן, ומריץ בעצמו את מעברי `move→long_rest→idle` / `jump→short_rest→idle` על בסיס `next_state_when_finished` מה-config.

**חישוב זמן:** `PieceAnimator.update(dt_ms)` מקבל את **אותו `dt_ms`** (אחרי `MAX_DT_MS` clamp) שמוזן ל-`game_engine.wait(dt_ms)` באותו frame — לא שעון אמיתי (`time.time()`) נפרד. כך זמן ה-view וזמן המנוע הפנימי (`RealTimeArbiter._current_time`) תמיד זהים במבנה, ואין פער בין progress ויזואלי (100%) לבין רגע ההגעה בפועל במנוע.

**ניקוי מצב:** אם כלי נעלם מ-`snapshot.pieces` (תפיסה שקטה — התנגשות בין שתי תנועות או תפיסת כלי מרחף) בלי `on_arrival` תואם, `PieceAnimator` מנקה את רשומת ה-motion הפנימית שלו לפי היעדרות מה-snapshot, לא רק לפי אירוע.

**קבוע קפיצה:** משך זמן קפיצה תמיד **1000ms** (תואם ל-hardcode בפועל ב-`RealTimeArbiter.start_jump`) — לא נעשה שימוש ב-`piece_rules.get_jump_duration()`/`JUMP_DURATION` (מוגדרים בקוד הקיים אך לא נקראים בשום מקום).

### `hud/*`
רכיבי ה-HUD מציירים בלבד או מחזיקים מידע תצוגתי שאינו סמכותי. `ScoreRenderer` קורא את הניקוד הסמכותי מתוך `GameSnapshot.scores`; הוא אינו מחשב תפיסות. `MovesLogData` נשאר `GameObserver` משום שיומן המהלכים הוא מידע תצוגתי מקומי בשלב הנוכחי.

### `input/mouse_command_extractor.py` — `MouseCommandExtractor`
אחראי רק על **offset** (מיקום הלוח בחלון, `geometry.board_origin_x/y`). כל חישוב פיקסל→תא מואצל ל-`BoardMapper` הקיים. שני מסלולים: `extract_left_click` → `ClickCommand`, `extract_right_click` → `JumpCommand`. מחזיר `None` אם הקליק מחוץ ללוח (על ה-HUD).

### `input/commands.py`
```python
@dataclass(frozen=True)
class ClickCommand:
    position: Position

@dataclass(frozen=True)
class JumpCommand:
    position: Position

Command = ClickCommand | JumpCommand

class CommandSender(Protocol):
    def send(self, command: Command) -> None: ...

class LocalCommandSender:
    def __init__(self, controller, game_engine):
        self._controller, self._game_engine = controller, game_engine

    def send(self, command: Command) -> None:
        match command:
            case ClickCommand(position=p): self._controller.handle_click(p)
            case JumpCommand(position=p): self._game_engine.request_jump(p)
```
`JumpCommand` פונה ל-`GameEngine` ישירות, לא דרך `Controller` — אין selection לפני קפיצה. פקודה אחת גנרית מאפשרת בעתיד `NetworkCommandSender` (סריאליזציה ל-JSON ושליחה לשרת אמיתי) בלי לשנות קוד קלט/תצוגה כלל.

### `observer.py` — `GameObserver`
```python
class GameObserver(Protocol):
    def on_arrival(self, event) -> None: ...                       # כל מהלך שמגיע ליעד (גם בלי תפיסה)
    def on_motion_started(self, piece, source, destination, duration_ms) -> None: ...
    def on_jump_started(self, piece, position) -> None: ...          # duration תמיד 1000ms
    def on_game_over(self) -> None: ...
```

### `engine/game_engine.py` — תוספות
```python
def __init__(self, board):
    ...
    self._observers: list[GameObserver] = []

def subscribe(self, observer): self._observers.append(observer)

def wait(self, milliseconds):
    arrival_events = self._arbiter.advance_time(milliseconds)
    for event in arrival_events.events:
        for obs in self._observers: obs.on_arrival(event)
    if arrival_events.king_captured:
        self._game_state.end_game()
        for obs in self._observers: obs.on_game_over()

def request_move(self, source, destination):
    ...
    self._arbiter.start_motion(piece, source, destination)
    duration = piece_rules.get_arrival_duration(piece.kind, source, destination)
    for obs in self._observers: obs.on_motion_started(piece, source, destination, duration)
    return _MoveResult(True, "ok")

def request_jump(self, source):
    ...
    self._arbiter.start_jump(piece)
    for obs in self._observers: obs.on_jump_started(piece, source)
```
`request_move`/`request_jump`/`snapshot` הלוגיים לא משתנים מעבר לתוספת ההתראה.

### `display_manager.py` — `DisplayManager`
המחלקה היחידה שמכירה את כל שאר הרכיבים, ומחזיקה `BoardGeometry` יחיד המוזרק לכולם. אחראית על:
- `update(dt_ms)` — `game_engine.wait(dt_ms)` + `piece_animator.update(dt_ms)` (אותו `dt_ms`, אחרי `MAX_DT_MS` clamp).
- `render()` — `board_loader.fresh_canvas()` → מעבר על כל ה-renderers (`board_renderer`, `piece_renderer`, `hud/*`).
- לולאה ראשית + קליטת עכבר + זיהוי resize.

**היחיד בפרויקט שמותר לו לגעת ב-`cv2` ישירות**, ורק לשלוש פעולות תשתית: `imshow` (הצגה), `waitKey` (תזמון לולאה, לא-חוסם), `setMouseCallback` (קליטת עכבר) + השוואת גודל חלון לזיהוי resize. **אסור** שימוש ב-`cv2` לציור (`rectangle`/`circle`/`putText`/`resize` עצמאי) — כל ציור עובר דרך `Img` בלבד.

**סדר קריאות ב-resize handler (מחייב):**
```python
def _on_resize(self, new_width, new_height):
    self._geometry.resize(new_width, new_height)                       # 1
    self._board_mapper.cell_size = self._geometry.cell_w               # 2
    self._board_loader.reload()                                        # 3 — לפי geometry הנוכחי
    self._animation_library.reload(cell_size=self._geometry.cell_w)    # 4
```

---

## מוסכמות נכסים

- תיקיית ספרייטים: `PIECE3/{KIND}{COLOR}/states/{state}/sprites/{n}.png` (סדר `Kind+Color`, הפוך מ-`Piece` במודל).
- 5 states חזותיים: `idle`, `move`, `jump`, `short_rest`, `long_rest`.
- כל sprite: PNG ריבועי, RGBA עם שקיפות אמיתית, 256×256 פיקסלים.
- `config.json` לכל state: `{"physics": {"speed_m_per_sec", "next_state_when_finished"}, "graphics": {"frames_per_sec", "is_loop"}}`.

---

## החלטות עיצוב נוספות

- הקירור החזותי (`short_rest`/`long_rest`) אינו אכוף לוגית — המודל מאפשר להזיז כלי מיד עם ההגעה (`realtime/` לא משתנה). ייתכן פער בין המראה להתנהגות; זו התנהגות מקובלת.
- משחק יחיד על מחשב אחד, לוח פתיחה רגיל, ללא פרמטרים חיצוניים.
- `pathlib.Path` בכל בניית נתיב — לא `\`/`/` קשיח.
