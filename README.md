# Polymarket Paper Rebalancer v6

Отдельная paper-версия на базе v5 с режимом **Smart Rescue**.

## Что изменено

Обычная торговля:

```text
ANCHOR_ENTRY
→ SCALE_ANCHOR
→ PAIR_LOCK
→ NEW_CYCLE
```

Последняя минута:

```text
есть непарный остаток
→ запрещаются новые циклы и усреднения
→ покупается только противоположная сторона
→ после каждой покупки пересчитывается Worst PnL
→ Rescue повторяется, пока риск уменьшается
```

## Лимиты

```text
Обычный капитал на рынок: $30
Аварийный капитал: $45
```

Сумма от $30 до $45 может использоваться только действием Smart Rescue.

## Три ступени Rescue

```text
60–31 секунд:
минимальное улучшение Worst PnL = $0.05
максимальный Worst после Rescue = −$0.60

30–11 секунд:
минимальное улучшение = $0.02
максимальный Worst = −$0.90

10–5 секунд:
минимальное улучшение = $0.005
максимальный Worst = −$1.10
```

## Render

Тип сервиса:

```text
Background Worker
```

Build Command:

```text
pip install -r requirements.txt
```

Start Command:

```text
python bot.py
```

Persistent Disk:

```text
/var/data
```

Environment:

```text
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
DATA_DIR=/var/data
```

Для v6 используй отдельного Telegram-бота, если v5 продолжает работать.
