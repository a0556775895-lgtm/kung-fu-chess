# Kung Fu Chess — מצב הפרויקט הנוכחי

## תיאור כללי

משחק שחמט בזמן-אמת: כלים נעים לפי חוקי תנועת שחמט רגילים, אך התנועה אינה מיידית — כלי שנבחר ונשלח ליעד נע במהירות קבועה, ומגיע ליעד אחרי זמן פרופורציונלי למרחק.

## מבנה שכבות

| שכבה | קובץ | תפקיד |
|---|---|---|
| Model | `model/position.py` | קואורדינטת תא (row, col) — value object אימוטבילי |
| Model | `model/piece.py` | ישות כלי: id, color, kind, cell, state (IDLE/MOVING/CAPTURED) |
| Model | `model/board.py` | רשת לוגית: מיקום כלים, בדיקת גבולות, ביצוע מהלך (כולל תפיסה) |
| Model | `model/game_state.py` | דגל game_over בלבד |
| Movement rules | `rules/piece_rules.py` | חוקיות תנועה לכל סוג כלי, תאי-ביניים לבדיקת חסימה, תזמון הגעה |
| Rules | `rules/piece_factory.py` | יצירת כלי מ-token טקסטואלי, כולל הקצאת id ייחודי |
| Validation | `rules/rule_engine.py` | בדיקת חוקיות מהלך מבוקש מול מצב הלוח |
| Real-time | `realtime/motion.py` | ייצוג תנועה בודדת שבביצוע |
| Real-time | `realtime/real_time_arbiter.py` | ניהול כל התנועות הפעילות, פתרון הגעות והתנגשויות |
| Application service | `engine/game_engine.py` | תיאום Board/RuleEngine/RealTimeArbiter, גבול הפקודות הציבורי |
| Input | `input/board_mapper.py` | תרגום פיקסלים לתא לוחי |
| Input | `input/controller.py` | ניהול בחירה, תרגום קליקים לפקודות |
| Text I/O | `boardio/board_parser.py` | פרסור טקסט ללוח |
| Text I/O | `boardio/board_printer.py` | הדפסת מצב לוח לוגי |
| View | `view/renderer.py` | רינדור טקסטואלי של GameSnapshot |
| Text tests | `texttests/script_parser.py` | פרסור תסריטי בדיקה (`Board:`/`Commands:`) |
| Text tests | `texttests/script_runner.py` | הרצת תסריט דרך נתיב הפקודות האמיתי |
| Entry point | `main.py` | קריאת קלט מ-stdin, הרצת פקודות |

## כללי בעלות בין שכבות

- **Model** (Position/Piece/Board): לא יודע דבר על פיקסלים, קליקים, רינדור, פרסור, חוקי תנועה, או זמן.
- **Movement rules** (PieceRules): stateless. מחשב יעדים חוקיים ותאי-ביניים מתוך board ו-piece בלבד. לא מבצע capture או מוטציה.
- **RuleEngine**: read-only ביחס ל-Board. מחזיר `MoveValidation(is_valid, reason)`. לא בודק game_over ולא בודק אם כלי כבר בתנועה — אלה guards ברמת GameEngine.
- **RealTimeArbiter**: מנהל אובייקטי Motion, מתקדם בזמן מדומה, מבצע arrival, מדווח על תפיסת מלך. לא מחליט מה קורה בעקבות זה.
- **GameEngine**: מתאם Board/RuleEngine/RealTimeArbiter. הבעלים היחיד של החלטת game_over. לא מכיל לוגיקת תנועה ספציפית לכלי, קוד רינדור, פרסור קלט, או מיפוי פיקסלים.
- **Controller**: מתרגם קליקים לבחירה ולפקודות GameEngine. לא מחליט חוקיות שחמט, לא קורא ל-RuleEngine ישירות, לא נוגע ב-Board.move_piece.
- **Renderer**: מקבל GameSnapshot בלבד (לעולם לא אובייקטי Board/Piece חיים).
- **BoardParser/BoardPrinter**: אחראים על טקסט בלבד — לא על חוקי תנועה, ביצוע פקודות, או רינדור.

## חוקי המשחק

1. הלוח מלבני, בגודל הנקבע מהטקסט.
2. כלים: K, Q, R, B, N, P, בצבע w/b כ-prefix. `.` = תא ריק.
3. אין check, checkmate, castling, en passant.
4. אין הכתרת רגלי (promotion) — נאסר במפורש.
5. תפיסת מלך מסיימת את המשחק.
6. כלים חוסמים (sliding pieces לא עוברים דרך חוסם).
7. מהירות תנועה קבועה: N משבצות = N × 1000ms, **חוץ מפרש**, שקופץ בזמן קבוע של 3000ms ללא תלות במרחק.
8. הלוח הלוגי מתעדכן רק בהגעה בפועל (arrival), לא בתחילת התנועה.

### הרחבות מעבר למסמך המקורי (מאושרות במפורש)

- **תנועה בו-זמנית של מספר כלים**: אין מגבלת "מוטציה פעילה אחת" גלובלית. מוגבל רק ברמת כלי בודד — אי אפשר להתחיל תנועה שנייה לאותו כלי בזמן שהוא כבר בתנועה.
- **רגל בצעד פתיחה כפול**: רגל שטרם זזה (מוסק ממיקומה בשורת הפתיחה) יכולה לנוע שתי משבצות קדימה בפעם הראשונה.
- **התנגשות כלי אויב על אותו יעד**: אם שני כלים ממתחים שונים "נוחתים" על אותה משבצת (כי שניהם החליפו מקומות, או ממקורות שונים), הכלי שהתחיל לזוז ראשון מנצח ומבצע תפיסה רגילה; הכלי השני נחסם באופן שקט (לא נוגע בלוח כלל, כי הכלי שהיה אמור להיתפס כבר לא קיים).
- **קליק שני על כלי ידידותי**: מחליף את הבחירה לכלי החדש (במקום לנסות מהלך או לבטל את הבחירה).

### נקודות פתוחות שלא מומשו (במכוון)

- כלל "כמעט-התנגשות" בין כלים מאותו צבע (עצירה משבצת אחת לפני המכשול) — תואר מילולית אך לא מומש; דורש מעקב מלא אחר מסלול כלי, לא רק יעד סופי.

## ה-DSL לבדיקות טקסט

פורמט קלט (משמש גם ב-`main.py` וגם ב-`texttests`):

```
Board:
<שורות הלוח>
Commands:
click <x> <y>
wait <milliseconds>
print board
```

- `click x y` — קליק בפיקסלים (CELL_SIZE = 100).
- `wait ms` — קידום זמן מדומה (אין sleep אמיתי בשום מקום).
- `print board` — הדפסת המצב הלוגי הנוכחי.
- שגיאת פרסור (token לא מוכר / אי-התאמת רוחב שורות) מייצרת פלט יחיד: `ERROR UNKNOWN_TOKEN` או `ERROR ROW_WIDTH_MISMATCH`, וקוצרת את כל הרצת הפקודות.

## API ציבורי בין שכבות

```
BoardParser.parse(board_lines) -> Board
BoardPrinter.print(grid) -> None (מדפיס)
BoardMapper.pixel_to_position(x, y) -> Position
BoardMapper.is_inside_board(position) -> bool
Controller.handle_pixel_click(x, y) -> None
Controller.handle_click(position) -> None
GameEngine.request_move(source, destination) -> MoveResult(is_accepted, reason)
GameEngine.wait(milliseconds) -> None
GameEngine.snapshot(selected_cell=None) -> GameSnapshot
RuleEngine.validate_move(board, source, destination) -> MoveValidation(is_valid, reason)
RealTimeArbiter.has_active_motion(piece) -> bool
RealTimeArbiter.start_motion(piece, source, destination) -> None
RealTimeArbiter.advance_time(ms) -> ArrivalEvents(events, king_captured)
```

### Reason strings

- **MoveValidation** (RuleEngine): `"ok"`, `"outside_board"`, `"empty_source"`, `"friendly_destination"`, `"illegal_piece_move"` (כולל גם נתיב חסום).
- **MoveResult** (GameEngine): `"ok"`, `"game_over"`, `"motion_in_progress"`, או reason שהועתק מ-MoveValidation.

## מבנה נתונים מרכזיים

```
GameSnapshot:
  board_width: int
  board_height: int
  pieces: list[PieceSnapshot]
  selected_cell: Position | None
  game_over: bool

PieceSnapshot:
  kind: str
  color: str
  cell: Position       # תא לוגי, לא פיקסלים — Renderer ממיר בעצמו
  state: str
```

## סטטוס בדיקות

כל 20 מקרי הבדיקה שהוגדרו כ"קובעים" (parsing, בחירה, תנועת כל סוגי הכלים, חסימה, שגיאות טוקן/רוחב שורה) עוברים בהרצה מלאה דרך `main.py` / `texttests.script_runner`.

## מבנה קבצים

```
kungfu_chess/
  main.py
  model/
    position.py
    piece.py
    board.py
    game_state.py
  rules/
    piece_rules.py
    piece_factory.py
    rule_engine.py
  realtime/
    motion.py
    real_time_arbiter.py
  engine/
    game_engine.py
  input/
    board_mapper.py
    controller.py
  boardio/
    board_parser.py
    board_printer.py
  view/
    renderer.py
  texttests/
    script_parser.py
    script_runner.py
  tests/
    integration/
      test_text_scripts.py
```

## מה עדיין לא קיים בפרויקט

- שכבת רינדור גרפי (`view/image_view.py`) — לא נדרשה ולא נבנתה.
- קבצי טסטי-יחידה (unit tests) פר-שכבה — נבנה רק מסלול האינטגרציה הטקסטואלי.
- אף אחת מתכונות ה-Extra Route (cooldown, replay, בוט) — לא נדונו ולא מומשו.
