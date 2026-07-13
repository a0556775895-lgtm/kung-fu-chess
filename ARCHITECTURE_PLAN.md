# Kung-Fu Chess — תוכנית ארכיטקטורה חדשה (Layered Architecture)

> מסמך זה מתעד את מבנה היעד של הפרויקט לאחר הרפקטורינג, את המיפוי מהקוד הקיים,
> ואת ההחלטות העיצוביות שהתקבלו. הוא מיועד ללוות את התהליך עד להשלמת המימוש —
> הן עבור בן-אדם והן עבור LLM שממשיך את העבודה בהמשך.
>
> **מקור:** מסמך "השכבות הנדרשות" (Word) + שיחת סיכום דרישות.
> **סטטוס (עדכון אחרון):** שלבים 1–11 מתוך 12 הושלמו ונבדקו (`model/position.py` עד
> `view/renderer.py`). ר' עדכון מפורט בסעיף 8. שלב 12 (`texttests/`) — פורמט
> הוחלט (זהה ל-`Board:`/`Commands:` הקיים), אך המימוש בהמתנה ביוזמת
> המשתמש (לא רוצה לכתוב טסטים כרגע). ר' סעיף 7, פריט 7.

---

## 1. רקע — למה עוברים ארכיטקטורה

הארכיטקטורה הקיימת מבוססת על `Board` כמחלקה מרכזית שמרכזת כמעט כל אחריות
(parsing, בחירה, תנועה, זמן, לכידה, promotion, קפיצה, ניצחון). זה עבד, אבל:

1. הדרישה האמיתית של Kung-Fu Chess היא **תנועות מקבילות של כמה כלים בו-זמנית**,
   וזה לא נתמך במודל הנוכחי (`Board.click` נועל את כל הלוח כל עוד יש מהלך פעיל אחד).
2. אין הפרדה בין "בדיקת חוקיות מהלך" ל"ביצוע מהלך" — שתי האחריויות שזורות זו בזו.
3. אין parser/printer/renderer נפרדים מה-Model.
4. שגיאות מטופלות ב-string comparison (`str(error) == "UNKNOWN_TOKEN"`) במקום
   exception hierarchy אמיתי.

המעבר הוא **לא** קוסמטי — הוא כולל שינוי אמיתי במודל הנתונים (ר' סעיף 4) כדי לתמוך
בתנועות מקבילות.

---

## 2. עץ הקבצים היעד

```
kungfu_chess/
├── model/
│   ├── position.py          # Position: row, col
│   ├── piece.py              # Piece: id, color, kind, cell, state
│   ├── board.py               # Board: אחסון, גבולות, מיקום, ביצוע בלבד
│   └── gamestate.py          # GameState: game_over, current_time, תוצאה
│
├── rules/
│   ├── piece_rules.py         # חוקי תנועה לכל סוג כלי (Movement Design)
│   └── rule_engine.py         # מאמת חוקיות מהלך; זורק exceptions
│
├── realtime/
│   ├── motion.py               # Motion: תזוזה בודדת בתהליך (מקור, יעד, זמנים, מזהה כלי)
│   └── real_time_arbiter.py    # ניהול כל התנועות הפעילות במקביל
│
├── engine/
│   └── game_engine.py          # מנהל את המשחק כולו: תזמור בין השכבות, סיום משחק
│
├── input/
│   ├── board_mapper.py         # פיקסל -> תא, בדיקת גבולות (=BoardGeometry היום)
│   └── controller.py           # מתרגם קליקים לפקודות; קורא ל-Rule Engine
│
├── io/
│   ├── board_parser.py         # פרסור טקסט קלט ל-Model
│   └── board_printer.py        # הדפסת מצב הלוח
│
├── view/
│   ├── renderer.py             # לוגיקת רינדור כללית (טקסט/מופשט)
│   └── image_view.py           # תצוגה גרפית (אם/כאשר תמומש)
│
├── texttests/
│   ├── script_parser.py        # פרסור תרחישי .kfc
│   └── script_runner.py        # הרצת תרחישים
│
├── app.py                      # entry point
│
└── tests/
    ├── unit/
    │   ├── test_position.py
    │   ├── test_board.py
    │   ├── test_piece_rules.py
    │   ├── test_rule_engine.py
    │   ├── test_real_time_arbiter.py
    │   ├── test_game_engine.py
    │   ├── test_board_mapper.py
    │   ├── test_controller.py
    │   ├── test_board_parser.py
    │   └── test_board_printer.py
    └── integration/
        ├── scripts/
        │   ├── 01_board_parsing.kfc
        │   ├── 02_click_to_move.kfc
        │   ├── 03_rook_moves.kfc
        │   ├── 04_invalid_moves.kfc
        │   ├── 05_capture.kfc
        │   └── 06_game_over.kfc
        └── test_text_scripts.py
```

---

## 3. מיפוי: קוד קיים → מבנה יעד

| קובץ/רכיב קיים | הופך ל־ | הערות |
|---|---|---|
| `board.py` (`_grid`, `rows`, `cols`) | `model/board.py` | Board נשאר Model בלבד — **בלי** לוגיקת חוקיות. רק אחסון + ביצוע לאחר אישור. |
| `board.py` (`_current_time`, `_game_over`) | `model/gamestate.py` | מופרד מ-Board כישות עצמאית. |
| `board.py._parse_board` | `io/board_parser.py` | טהור I/O, לא חלק מה-Model. |
| `board.py.print_board` | `io/board_printer.py` | טהור I/O. |
| `piece.py` (בסיס) + כל תת-מחלקה | `model/piece.py` + `rules/piece_rules.py` | **הפרדה חשובה:** הזהות (`id`, `color`, `kind`, `cell`, `state`) עוברת ל-Model; ה-`is_valid_move`/`get_pathcells` עוברים ל-`piece_rules.py`. |
| `piece_factory.py` | נשאר בערך זהה, כנראה עובר ל-`model/` או `rules/` (לא צויין במפורש) | ליצירה מ-token. |
| `pending_move.py` | `realtime/motion.py` (ייצוג תזוזה בודדת) | **משתנה מהותית**: כיום אובייקט יחיד; במבנה החדש כל `Motion` הוא ישות בפני עצמה, וריבוי מהן מנוהל ע"י `real_time_arbiter.py`. |
| `board.wait()` (הלוגיקה שמריצה pending move) | `realtime/real_time_arbiter.py` | מנהל **את כל** התנועות הפעילות בו-זמנית, לא רק אחת. |
| `selection_controller.py` | `input/controller.py` | לפי המסמך: מתרגם קליק לפקודה, **קורא ל-Rule Engine** לבדיקת חוקיות — לא בודק צבע/תקינות בעצמו כמו היום. |
| `board_geometry.py` | `input/board_mapper.py` | שם חדש, תפקיד זהה (pixel↔cell, בדיקת גבולות). |
| הלוגיקה החסרה: בדיקת "צבע ידידותי", "תזוזה חוקית", "נתיב פנוי" שמפוזרת היום בין `SelectionController` ל-`Board._is_path_clear` | `rules/rule_engine.py` | **מרוכזת כולה כאן**, עם exceptions מפורשים (ר' סעיף 5). |
| `board._execute_arrival` (airborne-capture, promotion, game_over) | מפוצל בין `model/board.py` (ביצוע גרידא), `engine/game_engine.py` (תזמור/game_over), וכלל collision שצריך בית משלו (לא הוזכר קובץ ייעודי במסמך — ר' "שאלות פתוחות") | |
| `main.py` | `app.py` + `io/board_parser.py` + `input/controller.py` | מפוצל: parsing קלט, dispatch פקודות, והרצה בפועל — כל אחד בשכבה שלו. |

---

## 4. שינוי מודל הנתונים — `Piece` עם `id` ו-`cell`

### המצב היום
- piece לא יודע איפה הוא נמצא — המיקום נגזר אך ורק מהאינדקס שלו ב-`grid` של Board.
- אין `id` — piece מזוהה implicitly לפי מיקום.
- מקור אמת יחיד למיקום (ה-grid).

### המצב החדש (לפי החלטה)
```python
class Piece:
    id: str          # מזהה ייחודי, קבוע לאורך חיי הכלי
    color: PieceColor
    kind: str          # "P", "Q", "K"... (מקביל ל-symbol היום)
    cell: Position      # המיקום הנוכחי הידוע לכלי עצמו
    state: PieceState   # IDLE / MOVING / COOLDOWN / JUMPING / CAPTURED
```

### למה זה הכרחי (לא סתם תוספת)
ברגע שתומכים בתנועות מקבילות: כלי שנמצא כרגע ב-`Motion` פעיל **אינו נמצא פיזית
באף תא ב-grid** (או: נמצא בתא המקור אבל "תפוס" עד סיום). כדי לדעת:
- אילו כלים "בתנועה" כרגע (בלי לסרוק את כל ה-grid),
- ולמנוע בחירה חוזרת של כלי שכבר "בתנועה" (ר' החלטה בסעיף 6),

צריך ישות עצמאית עם `id` שניתן לעקוב אחריה גם כשהיא לא "יושבת" ב-grid.

### ⚠️ סיכון לתשומת לב
מרגע שיש שני מקומות שיודעים "איפה הכלי" — `Board`/`grid` **וגם** `piece.cell` —
זה two-sources-of-truth. חובה להחליט **מי הבעלים הסופי** ולוודא עדכון אטומי בשניהם
בכל שינוי מיקום (ליד `RealTimeArbiter` ו-`model/board.py`). מומלץ: `Board` הוא
היחיד שמעדכן את `piece.cell` בפועל (setter מוגן), כדי למנוע רגרסיה של חוסר-סנכרון.

---

## 5. Rule Engine — Exceptions Hierarchy

לפי ההחלטה: שגיאות **נזרקות כ-exceptions פייתוניים**, לא מוחזרות כערך/מודפסות.

```python
class RuleViolation(Exception):
    """Base class for all rule-engine rejections."""

class OutOfBoardError(RuleViolation):
    """Destination cell is outside the board boundaries."""

class EmptyCellError(RuleViolation):
    """Source cell has no piece to move."""

class FriendlyFireError(RuleViolation):
    """Destination cell is occupied by a piece of the same color."""

class IllegalPatternError(RuleViolation):
    """Move does not match the piece's movement rules (piece_rules.py)."""

class PieceAlreadyMovingError(RuleViolation):
    """Piece is currently mid-motion and cannot be selected/moved again."""

class PathBlockedError(RuleViolation):
    """A piece blocks the path between source and destination."""
```

### זרימת האימות (`rule_engine.py`) לפי סדר המסמך המקורי

1. דחיית ניסיון תזוזה **מחוץ ללוח** → `OutOfBoardError`
2. דחיית ניסיון תזוזה **מתא ריק** → `EmptyCellError`
3. דחיית ניסיון תזוזה **לתא עם חייל ידידותי** → `FriendlyFireError`
4. *(תוספת נדרשת מההחלטה על תנועות מקבילות)* דחיית ניסיון להזיז כלי שכבר
   `state == MOVING/JUMPING` → `PieceAlreadyMovingError`
5. קריאה ל-`piece_rules` (Movement Design) לאימות התבנית → `IllegalPatternError`
   אם לא תואם
6. בדיקת נתיב פנוי (למי שצריך `get_pathcells`) → `PathBlockedError`
7. אם הכל עבר: **מחזיר את המיקום/את אישור המהלך** (לא exception — נתיב הצלחה רגיל)

**נקודת החלטה פתוחה:** מי תופס את ה-exceptions האלה בפועל — ה-`Controller`?
ה-`GameEngine`? ה-`View`? המסמך לא מפרט. מוצע: `Controller` תופס, מתרגם ל-הודעה
קריאה, ומעביר ל-`View`/`io` להצגה — כדי ש-`rule_engine` עצמו יישאר "טהור" (לוגי בלבד,
לא יודע כלום על הצגה).

---

## 6. תנועות מקבילות — החלטות שהתקבלו

| שאלה | החלטה |
|---|---|
| האם לתמוך בתנועה של כמה כלים בו-זמנית? | **כן** |
| מה קורה כשלוחצים על כלי שכבר `MOVING`/`JUMPING`? | **נעול לגמרי** — אי אפשר לבחור אותו כלל עד סיום התנועה. נזרק `PieceAlreadyMovingError` אם מנסים. |
| מי מנהל את אוסף התנועות הפעילות? | `realtime/real_time_arbiter.py` |
| מה מייצג תזוזה בודדת? | `realtime/motion.py` — יורש קונספטואלית מ-`PendingMove` הקיים, אבל תומך בריבוי מופעים במקביל (מוחזק ע"י ה-Arbiter, לא ע"י Board ישירות) |

### השלכה על `real_time_arbiter.py`
- מחזיק **אוסף** של `Motion` פעילים (למשל `dict[pieceid, Motion]`).
- בכל `tick`/`wait`, עובר על **כל** התנועות הפעילות (לא רק אחת), בודק אילו הגיעו
  ל-arrival/finish, ומבצע.
- חייב לטפל בהתנגשות בין שתי תנועות שמגיעות לאותו תא יעד באותו רגע (כלל collision —
  ר' "שאלות פתוחות" למטה, לא מפורט במסמך המקורי).

### השלכה על `input/controller.py`
- לפני קריאה ל-Rule Engine: לבדוק אם ה-piece הנבחר כבר `state != IDLE` → אם כן,
  `PieceAlreadyMovingError` מיידי, בלי לפנות בכלל ל-`rule_engine` לבדיקת התבנית.
  (או: `rule_engine` עצמו עושה את הבדיקה הזו כצעד 4 ברשימה שלמעלה — צריך להחליט היכן
  בדיוק הבדיקה גרה; מוצע ב-`rule_engine` כדי לשמור אחריות מרוכזת).

---

## 7. שאלות פתוחות — עדכון סטטוס

רשימה זו חשובה כדי לא "לשכוח" נקודות תלויות לפני שממשיכים במימוש. סטטוס
מעודכן נכון לסיום שלב 9:

1. ✅ **הוכרע (שלב 9). כלל Airborne-capture** — נמצא ב-
   `realtime/real_time_arbiter.py` (`_execute_arrival`), לא ב-`rule_engine`.
   הנימוק: זו לוגיקה תלוית-תזמון (רלוונטית רק ברגע ש-`arrival_time` של
   Motion מגיע), לא בדיקת חוקיות מוקדמת — לכן שייכת ל-Arbiter ולא ל-Rule
   Engine. הועברה 1:1 מ-`Board._execute_arrival` הישן, ללא שינוי לוגי.

2. ✅ **הוכרע (שלב 9). Promotion** — גם היא ב-
   `realtime/real_time_arbiter.py` (`_maybe_promote`), מאותה סיבה: קורה
   רק בזמן ביצוע הגעה בפועל. לא נוצר `rules/promotion.py` נפרד — נשארה
   פונקציה פרטית בתוך ה-Arbiter.

3. ✅ **הוכרע (שלב 9). Collision בין תנועות מקבילות לאותו יעד** — כלל
   עסקי שהוגדר: **"הראשון-נרשם-מנצח"**. אם כמה `Motion` הופכים
   arrival-pending לאותו תא באותו tick, זה שנוצר (נלחץ) ראשון מבצע את
   ההגעה כרגיל; כל השאר **"בונקים"** — לא תופסים את התא בכלל, אלא
   מקבלים הארכת מנעול (`MOVING`) בזמן שווה למשך ההלוך המקורי (מסע הלוך-
   חזור סימטרי), ואז חוזרים ל-`IDLE` בדיוק בתא המקור שממנו יצאו. ממומש
   ב-`Motion.bounce()` + `RealTimeArbiter._resolve_arrivals`. נבדק
   end-to-end (שני צריחים בצבעים שונים מתנגשים על אותו יעד).

4. ✅ **הוכרע בפועל (שלבים 4/9). `piece_factory.py`** — נכנס ל-`rules/`
   (לא `model/`), עם ייבוא `from model.piece import Piece, PieceColor`.
   נקרא הן מ-`boardio/board_parser.py` (יצירה ראשונית) והן מ-
   `realtime/real_time_arbiter.py` (יצירת כלי מוכתר ב-promotion).

5. ✅ **הוכרע (שלב 8). מי תופס את ה-`RuleViolation` exceptions** —
   `input/controller.py` תופס אותן (catch גורף לעת עתה, לא לפי תת-מחלקה),
   ומדשלקט (deselect) בשקט — אותה UX כמו הקוד הישן. יש `TODO` מפורש
   בקוד: ברגע ש-`view/` ייכתב (שלב 11), התפיסה צריכה להתפצל לפי סוג
   ה-exception ולהעביר הודעה קריאה, במקום ה-catch הגורף הנוכחי.

6. **עדיין פתוח. `view/image_view.py`** — לא קיימת שום תצוגה גרפית היום.
   אושר מחדש בשלב 11: אין עדיין כיוון לספריית גרפיקה. `view/renderer.py`
   הוא כרגע כל שכבת ה-view (טקסט בלבד).

7. **הפורמט הוחלט (שלב 12, טרם מומש). פורמט `.kfc`** (`texttests/`) —
   הוחלט להיות **זהה** לפורמט `Board:`/`Commands:` שכבר קיים ונקרא
   מ-stdin ב-`main.py` (click/wait/jump/print board) — אין שדות/תחביר
   נוספים. המימוש בפועל (`script_parser.py`, `script_runner.py`,
   קבצי `.kfc` עצמם, ופורמט ה-expected-output) בהמתנה ביוזמת המשתמש.

### תוספת: החלטה חדשה שלא הייתה במסמך המקורי כלל

8. ✅ **פער `state=MOVING` שהתגלה בשלב 7 ותוקן.** ב-`Piece` (המקורי
   שהועלה) לא היה שום קוד שמעביר `state` ל-`MOVING` עבור מהלך רגיל
   (לעומת קפיצה, שכן טופלה ע"י `start_jump`) — מה שהיה הופך את
   `PieceAlreadyMovingError` ל"אות מתה" עבור מהלכים רגילים. נוסף
   `Piece.start_move()` / `Piece.finish_move()` (סימטרי ל-
   `start_jump`/`finish_jump`), מחוברים כעת דרך
   `RealTimeArbiter.schedule()` (קביעה) ו-`RealTimeArbiter._resolve_finishes`
   (איפוס). נבדק שהחסימה עובדת בפועל (סעיף הבדיקות בשלב 9).

9. ✅ **הוכרע (שלב 10). מי מחליט על סיום משחק בעקבות לכידת מלך** —
   `RealTimeArbiter` עדיין **מזהה** את הלכידה (ב-`_execute_arrival`),
   אבל כבר לא קורא ל-`Board.end_game()` בעצמו. במקום זאת הוא רק מדגל
   (`_royal_captured`), נחשף דרך `consume_royal_capture()` (consume
   semantics — קריאה מנקה את הדגל). `engine/game_engine.py` (חדש,
   שלב 10) הוא היחיד שקורא בפועל ל-`Board.end_game()`, בתוך
   `GameEngine.wait()` אחרי `board.wait()`. `main.py` עודכן לדבר עם
   `GameEngine` במקום עם `Board` ישירות (import swap בלבד — שאר
   הלוגיקה לא השתנתה).

10. ✅ **הוכרע (שלב 11). מי תופס ומציג `RuleViolation`, ומי מדפיס
    את הלוח** — `input/controller.py` ממשיך לתפוס עם `except
    RuleViolation` גורף (לא מתפצל לפי תת-מחלקה בתוך ה-controller
    עצמו), אבל כעת קורא ל-`view/renderer.print_rule_violation(error)`
    לפני הדשלקט — המיפוי מתת-מחלקה להודעה קריאה גר ב-`renderer.py`
    (`_MESSAGES` dict), לא ב-controller. בנוסף, הודפסת הלוח הוצאה
    **לגמרי** מ-`model/board.py` (הוסרו `print_board()` וה-import של
    `boardio.board_printer`) — Board חושף רק `get_grid()` כנתון
    read-only. `view/renderer.py` הוא כעת נקודת הכניסה היחידה לכל פלט
    טקסטואלי (גם מצב לוח וגם הודעות שגיאה), ועוטף את
    `boardio.board_printer.print_board` בלי לשכפל את לוגיקת הפורמט.
    `engine/game_engine.py.print_board()` מתווך בין `Board.get_grid()`
    ל-`renderer.print_board()`.

---

## 8. סדר עבודה מוצע (Migration Plan) — עדכון התקדמות

מומלץ לבנות מלמטה למעלה — קודם Model נקי, אחר כך Rules בלי תלות בזמן-אמת, ורק
בסוף להכניס את המורכבות של concurrency:

1. ✅ **`model/position.py`** — הושלם. עטיפה ל-`(row, col)`, כולל `__iter__`
   שמאפשר `row, col = position` בנקודות מעבר עם קוד ישן שעדיין מצפה ל-tuple.
2. ✅ **`model/piece.py`** — הושלם. `id` (מזהה רץ, `f"{kind}{counter}"`),
   `cell`, `state`. `setcell` הוא הדרך היחידה לעדכן מיקום (Board הוא
   הקורא היחיד). **תוספת לא-מתוכננת:** `start_move()`/`finish_move()`
   (ר' סעיף 7, פריט 8).
3. ✅ **`rules/piece_rules.py`** — הושלם. `is_valid_move`/`get_pathcells`
   מכל תת-מחלקת piece הישנה, ללא שינוי לוגי. גם `piece_factory.py` נכנס
   בפועל ל-`rules/` (ר' סעיף 7, פריט 4).
4. ✅ **`rules/rule_engine.py`** — הושלם, עם היררכיית ה-exceptions המלאה
   (`OutOfBoardError` עד `PathBlockedError`). תלוי ב-`BoardView` (Protocol),
   לא ב-`Board` הקונקרטי — כפי שתוכנן.
5. ✅ **`model/board.py`** (עדיין בשם `board.py`, טרם הועבר פיזית לתיקיית
   `model/`) — צומצם בהדרגה: שלב 7 הוציא רק parsing/printing; שלב 9 הוציא גם
   את `_execute_arrival`/`_finish_pending_move` (עברו ל-Arbiter). Board כיום
   הוא בעיקר grid + `place_piece`/`remove_piece` שה-Arbiter קורא להם.
6. ✅ **`model/gamestate.py`** — הושלם (שלב 7). `current_time`/`game_over`
   הוצאו מ-`Board`, באותו pattern שכבר שימש את `PendingMove`.
7. ✅ **`boardio/board_parser.py`, `boardio/board_printer.py`** — הושלמו
   (שלב 7). מיקום בפועל: `boardio/`, לא `io/` כמתוכנן במקור (כנראה כדי
   להימנע מהתנגשות שם עם מודול ה-`io` המובנה של Python).
8. ✅ **`input/board_mapper.py`, `input/controller.py`** — הושלמו (שלב 8).
   `Controller` מחובר ל-`rule_engine.validate_move` במקום לבדוק חוקיות
   בעצמו. תוקן תוך כדי: באג בהשוואת `Position`/tuple ב-`Board.jump()`.
9. ✅ **`realtime/motion.py`, `realtime/real_time_arbiter.py`** — הושלמו
   (שלב 9), כולל כלל ה-collision (ר' סעיף 7, פריט 3) ומעבר מלא ל-מהלכים
   מקבילים אמיתיים — **המנעול הגלובלי הוסר מ-`Board.click()`**. נבדק
   end-to-end: רגרסיה של מהלך יחיד, שני מהלכים מקבילים בלי חסימה,
   התנגשות+בונקה, ואכיפת `PieceAlreadyMovingError` בפועל.

   ⚠️ **Breaking change שנרשם:** ה-properties הישנות
   `_pending_source`/`_pending_destination`/`_pending_arrival_time`/
   `_pending_finish_time` (מתועדות ב-`API.md` כ"legacy test-facing")
   **הוסרו** מ-`Board` בשלב זה — אין יותר "ה-pending move" יחיד להצביע
   אליו ברגע שיש כמה `Motion` פעילים. טסטים שתלויים בהן צריכים לעבור
   לבדוק דרך ה-Arbiter (`board._arbiter`).

10. ✅ **`engine/game_engine.py`** — הושלם (שלב 10). מחלקה חדשה,
    עוטפת `model/board.py` ומחזירה 1:1 את אותו public surface
    (`click`/`wait`/`jump`/`print_board`/`game_over`) כדי ש-`main.py`
    יזדקק רק ל-import swap. אחריות `game_over` הסופית הועברה לכאן:
    `RealTimeArbiter` רק מדווח לכידת מלך (`consume_royal_capture`),
    ו-`GameEngine.wait()` הוא היחיד שקורא בפועל ל-`Board.end_game()`.
    `main.py` עודכן לבנות `GameEngine` במקום `Board`.

11. ✅ **`view/`** — `renderer.py` הושלם (שלב 11); `image_view.py`
    עדיין לא נוצר (ר' סעיף 7, פריט 6 — אין כיוון גרפי). `renderer.py`
    פתר את ה-TODO שהיה ב-`controller.py` (הודעה קריאה לכל
    `RuleViolation`, ממופה ב-`_MESSAGES`), וגם קיבל אליו את כל אחריות
    ההדפסה שהייתה ב-`Board.print_board()` — Board כבר לא מדפיס שום
    דבר, רק חושף `get_grid()`. `boardio/board_printer.py` לא השתנה
    בעצמו; רק ה-caller שלו עבר מ-`Board` ל-`view/renderer.py`.

12. ⬜ **`texttests/`** — פורמט `.kfc` הוחלט (זהה ל-`Board:`/`Commands:`
    הקיים — ר' סעיף 7, פריט 7), אך `script_parser.py`,
    `script_runner.py`, קבצי `.kfc` בפועל, ו-`tests/integration/
    test_text_scripts.py` (השוואת stdout מול expected-output מוענד)
    עדיין לא ממומשים — בהמתנה ביוזמת המשתמש.

---

## 9. עקרונות מנחים לאורך כל המימוש

- **Model לא בודק חוקיות** — Board מבצע רק לאחר שה-Rule Engine אישר.
- **Rule Engine לא יודע כלום על View/IO** — רק לוגיקה + exceptions.
- **מקור אמת יחיד למיקום** — `piece.cell` מתעדכן רק דרך Board (setter מוגן),
  לעולם לא ישירות מ-Controller/Engine.
- **כלי `MOVING`/`JUMPING` = נעול** — נבדק **לפני** כל בדיקת תבנית אחרת ב-Rule Engine.
- **כל exception חדש יורש מ-`RuleViolation`** — כדי לאפשר `except RuleViolation`
  גורף בשכבות גבוהות יותר בעת הצורך.

---

*מסמך זה חי — יש לעדכן אותו ברגע שמכריעים אחת מהשאלות הפתוחות בסעיף 7, ולסמן שלבים
שהושלמו בסעיף 8.*