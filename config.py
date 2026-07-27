import os
from pathlib import Path


# ============================================================
# ХРАНЕНИЕ ДАННЫХ
# ============================================================

DATA_DIR = Path(
    os.getenv(
        "DATA_DIR",
        "/var/data",
    )
)

DATA_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

DB_FILE = str(
    DATA_DIR / "paper_v5.db"
)

LOG_FILE = str(
    DATA_DIR / "paper_v5.log"
)


# ============================================================
# API
# ============================================================

GAMMA_API_URL = "https://gamma-api.polymarket.com"
CLOB_API_URL = "https://clob.polymarket.com"

BINANCE_WS_URL = (
    "wss://stream.binance.com:9443/stream"
    "?streams=btcusdt@aggTrade/ethusdt@aggTrade"
)


# ============================================================
# ИНТЕРВАЛЫ
# ============================================================

HTTP_TIMEOUT = int(
    os.getenv(
        "HTTP_TIMEOUT",
        "20",
    )
)

MARKET_REFRESH_INTERVAL = float(
    os.getenv(
        "MARKET_REFRESH_INTERVAL",
        "10",
    )
)

DECISION_INTERVAL = float(
    os.getenv(
        "DECISION_INTERVAL",
        "1",
    )
)

HEARTBEAT_INTERVAL = float(
    os.getenv(
        "HEARTBEAT_INTERVAL",
        "30",
    )
)


# ============================================================
# ТОРГОВОЕ ОКНО
# ============================================================

START_DELAY_SEC = float(
    os.getenv(
        "START_DELAY_SEC",
        "8",
    )
)

STOP_BEFORE_END_SEC = float(
    os.getenv(
        "STOP_BEFORE_END_SEC",
        "5",
    )
)

MIN_SECONDS_BETWEEN_TRADES = float(
    os.getenv(
        "MIN_SECONDS_BETWEEN_TRADES",
        "8",
    )
)


# ============================================================
# СТАКАН
# ============================================================

MAX_SPREAD = float(
    os.getenv(
        "MAX_SPREAD",
        "0.04",
    )
)

MAX_ASK_PRICE = float(
    os.getenv(
        "MAX_ASK_PRICE",
        "0.80",
    )
)


# ============================================================
# КАПИТАЛ
# ============================================================

# Обычный лимит на рынок.
# Используется для ANCHOR_ENTRY и NEW_CYCLE.
MAX_MARKET_CAPITAL_USDC = float(
    os.getenv(
        "MAX_MARKET_CAPITAL_USDC",
        "30.00",
    )
)

# Аварийный лимит.
# Используется только для покупки противоположной стороны
# при наличии непарного остатка.
EMERGENCY_MARKET_CAPITAL_USDC = float(
    os.getenv(
        "EMERGENCY_MARKET_CAPITAL_USDC",
        "45.00",
    )
)


# ============================================================
# РЕАЛЬНЫЙ МИНИМАЛЬНЫЙ ЛОТ
# ============================================================

PAPER_LOTS = {
    "BTC": float(
        os.getenv(
            "BTC_PAPER_LOT",
            "1",
        )
    ),
    "ETH": float(
        os.getenv(
            "ETH_PAPER_LOT",
            "1",
        )
    ),
}

MIN_ORDER_NOTIONAL_USDC = float(
    os.getenv(
        "MIN_ORDER_NOTIONAL_USDC",
        "1.00",
    )
)

ORDER_SIZE_STEP = float(
    os.getenv(
        "ORDER_SIZE_STEP",
        "0.01",
    )
)


# ============================================================
# ОГРАНИЧЕНИЯ ПОКУПОК
# ============================================================

MAX_BUYS_PER_SIDE = int(
    os.getenv(
        "MAX_BUYS_PER_SIDE",
        "4",
    )
)

MAX_TOTAL_TRADES = int(
    os.getenv(
        "MAX_TOTAL_TRADES",
        "8",
    )
)


# ============================================================
# ПЕРВЫЙ ВХОД
# ============================================================

ANCHOR_MAX_PRICE = float(
    os.getenv(
        "ANCHOR_MAX_PRICE",
        "0.42",
    )
)

# Первая покупка разрешена только тогда,
# когда текущая сумма обеих сторон не выше этого значения.
ENTRY_PAIR_CHECK_MAX_SUM = float(
    os.getenv(
        "ENTRY_PAIR_CHECK_MAX_SUM",
        "1.02",
    )
)

MIN_SECONDS_AFTER_ANCHOR_FOR_PAIR = float(
    os.getenv(
        "MIN_SECONDS_AFTER_ANCHOR_FOR_PAIR",
        "20",
    )
)


# ============================================================
# ОБЫЧНОЕ ЗАКРЫТИЕ ПАРЫ
# ============================================================

PAIR_TARGET_SUM = float(
    os.getenv(
        "PAIR_TARGET_SUM",
        "0.98",
    )
)

PAIR_ACCEPTABLE_SUM = float(
    os.getenv(
        "PAIR_ACCEPTABLE_SUM",
        "0.99",
    )
)


# ============================================================
# ЗАЩИТНОЕ ЗАКРЫТИЕ ПАРЫ
# ============================================================

# За 90 секунд бот начинает агрессивнее искать
# противоположную сторону.
DEFENSIVE_PAIR_WINDOW_SEC = float(
    os.getenv(
        "DEFENSIVE_PAIR_WINDOW_SEC",
        "90",
    )
)

# В защитном режиме разрешаем пару
# с суммой средних цен до 1.03.
DEFENSIVE_PAIR_MAX_SUM = float(
    os.getenv(
        "DEFENSIVE_PAIR_MAX_SUM",
        "1.03",
    )
)


# ============================================================
# АВАРИЙНОЕ ЗАКРЫТИЕ ПАРЫ
# ============================================================

# Последние 30 секунд — аварийный режим.
EMERGENCY_PAIR_WINDOW_SEC = float(
    os.getenv(
        "EMERGENCY_PAIR_WINDOW_SEC",
        "30",
    )
)

# В аварийном режиме допускаем сумму пары до 1.08,
# если это уменьшает worst PnL.
EMERGENCY_PAIR_MAX_SUM = float(
    os.getenv(
        "EMERGENCY_PAIR_MAX_SUM",
        "1.08",
    )
)


# ============================================================
# РИСК
# ============================================================

MAX_TOTAL_WORST_PNL_LOSS = float(
    os.getenv(
        "MAX_TOTAL_WORST_PNL_LOSS",
        "1.10",
    )
)

# Максимальное дополнительное ухудшение worst PnL
# при открытии нового цикла.
MAX_NEW_CYCLE_RISK_USDC = float(
    os.getenv(
        "MAX_NEW_CYCLE_RISK_USDC",
        "1.10",
    )
)


# ============================================================
# НОВЫЕ ЦИКЛЫ
# ============================================================

MAX_CYCLES_PER_MARKET = int(
    os.getenv(
        "MAX_CYCLES_PER_MARKET",
        "3",
    )
)

NEW_CYCLE_MIN_PRICE = float(
    os.getenv(
        "NEW_CYCLE_MIN_PRICE",
        "0.38",
    )
)

NEW_CYCLE_MIN_DELAY_SEC = float(
    os.getenv(
        "NEW_CYCLE_MIN_DELAY_SEC",
        "20",
    )
)

# Не начинать новый цикл слишком близко к окончанию рынка.
NEW_CYCLE_STOP_BEFORE_END_SEC = float(
    os.getenv(
        "NEW_CYCLE_STOP_BEFORE_END_SEC",
        "110",
    )
)


# ============================================================
# СТАРЫЕ ПАРАМЕТРЫ V5
# ============================================================

# Оставлены, чтобы другие файлы проекта
# не получили ImportError при импорте.
MIN_PRICE_IMPROVEMENT = float(
    os.getenv(
        "MIN_PRICE_IMPROVEMENT",
        "0.04",
    )
)

LOCK_PROFIT_PNL = float(
    os.getenv(
        "LOCK_PROFIT_PNL",
        "0.04",
    )
)

MAX_UNPAIRED_QTY = float(
    os.getenv(
        "MAX_UNPAIRED_QTY",
        "10.00",
    )
)

RISK_REDUCTION_WINDOW_SEC = float(
    os.getenv(
        "RISK_REDUCTION_WINDOW_SEC",
        "90",
    )
)

HARD_HEDGE_WINDOW_SEC = float(
    os.getenv(
        "HARD_HEDGE_WINDOW_SEC",
        "30",
    )
)


# ============================================================
# TELEGRAM
# ============================================================

TELEGRAM_BOT_TOKEN = os.getenv(
    "TELEGRAM_BOT_TOKEN",
    "",
).strip()

TELEGRAM_CHAT_ID = os.getenv(
    "TELEGRAM_CHAT_ID",
    "",
).strip()

TELEGRAM_POLLING_ENABLED = (
    os.getenv(
        "TELEGRAM_POLLING_ENABLED",
        "true",
    )
    .strip()
    .lower()
    == "true"
)
