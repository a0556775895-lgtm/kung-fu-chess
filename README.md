# Kong-Fu Chess – Current Architecture

## Overview

הפרויקט מממש משחק Kong-Fu Chess בזמן אמת.

הארכיטקטורה הנוכחית מבוססת על מחלקת `Board` מרכזית, מחלקת בסיס `Piece` שממנה יורשים כל סוגי הכלים, ו־`PieceFactory` האחראית על יצירתם.

המערכת עובדת באופן מלא, ומטרת הרפקטורינג היא לשפר את חלוקת האחריות ואת יכולת ההרחבה, ללא שינוי בהתנהגות המשחק.

---

# Current Architecture

```
Game
 │
 ▼
Board
 │
 ├── מנהל את מצב המשחק
 ├── מנהל תנועות
 ├── מנהל בחירת כלים
 ├── מנהל התנגשויות
 ├── מנהל קפיצות
 ├── מנהל Promotion
 ├── מנהל זמן
 └── מחזיק את הלוח
        │
        ▼
      Piece
        ▲
        │
 ┌──────┼──────────────────────────┐
 │      │      │      │      │
Pawn  Queen  King  Bishop Knight ...
```

---

# Board

מחלקת Board היא המחלקה המרכזית של המערכת.

אחריותה כיום:

- שמירת הלוח (`grid`)
- יצירת הלוח
- ניהול בחירת כלי
- קבלת לחיצות המשתמש
- בדיקת מהלכים
- חישוב זמן תנועה
- ניהול Pending Move
- ביצוע הגעה ליעד
- טיפול בלכידות
- טיפול בקפיצה
- טיפול בהכתרת רגלי
- סיום משחק
- ניהול זמן המשחק

כיום Board מרכזת אחריות רבה, ולכן היא המועמדת הראשונה לרפקטורינג.

---

# Piece

מחלקת בסיס שממנה יורשים כל הכלים.

## מידע שהיא מחזיקה

### זהות

- symbol
- color

### מיקום

- position
- board

### מאפייני הכלי

- move_duration
- cooldown_duration
- jump_duration

### מצב בזמן ריצה

- cooldown_end_time
- jump_end_time
- is_jumping

---

# Piece Hierarchy

```
Piece
 │
 ├── Pawn
 ├── Queen
 ├── King
 ├── Knight
 ├── Bishop
 ├── Rook
```

כל כלי מממש בעצמו:

```
is_valid_move()
```

ולעיתים גם:

```
get_path_cells()
```

---

# PieceFactory

אחראית על יצירת כל הכלים.

יתרון:
- ריכוז לוגיקת יצירת הכלים במקום אחד.

---

# Current Design

המערכת משתמשת בעיקר ב־Inheritance.

```
Piece
    ▲
    │
 Pawn
 Queen
 King
 ...
```

---

# Current Strengths

✔ קוד עובד באופן מלא

✔ חלוקה טובה בין סוגי הכלים

✔ PieceFactory כבר קיימת

✔ כל כלי אחראי ללוגיקת התנועה שלו

✔ אין כפילויות רבות בין הכלים

---

# Main Weakness

מחלקת Board מכילה אחריות רבה מדי.

היא אחראית גם על:

- מצב המשחק
- זמן
- בחירה
- תנועה
- התנגשויות
- Promotion
- Jump
- סיום משחק

כלומר היא מהווה למעשה Game Manager.

---

# Planned Refactoring

המטרה אינה לכתוב את הפרויקט מחדש.

המטרה היא לפרק את האחריות בהדרגה תוך שמירה על התנהגות זהה.

## שלב 1

יצירת מחלקת

```
PendingMove
```

שתרכז את כל נתוני המהלך הפעיל.

---

## שלב 2

הוצאת ניהול הבחירה למחלקה ייעודית.

---

## שלב 3

הוצאת Promotion למחלקה נפרדת.

---

## שלב 4

הוצאת Collision למחלקה נפרדת.

---

## שלב 5

הוצאת Jump למחלקה נפרדת.

---

# Future Improvements

## Piece State

במקום

```
is_jumping
```

תיווצר מחלקת Enum:

```
PieceState

IDLE
MOVING
COOLDOWN
JUMPING
CAPTURED
```

כך לכל כלי יהיה מצב יחיד וברור.

---

# Long-Term Goal

בעתיד נשקול מעבר חלקי מ־Inheritance ל־Composition.

כרגע אין החלטה לבצע שינוי זה.

העדיפות הראשונה היא פירוק האחריות של Board.

לאחר מכן תיבחן האפשרות להעביר חלק מההתנהגויות ל־Behaviors (Movement, Cooldown, Promotion וכו').