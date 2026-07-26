import os
from pathlib import Path

DATA_DIR = Path(os.getenv("DATA_DIR", "/var/data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_FILE = str(DATA_DIR / "paper_v6.db")
LOG_FILE = str(DATA_DIR / "paper_v6.log")

GAMMA_API_URL = "https://gamma-api.polymarket.com"
CLOB_API_URL = "https://clob.polymarket.com"

BINANCE_WS_URL = (
    "wss://stream.binance.com:9443/stream"
    "?streams=btcusdt@aggTrade/ethusdt@aggTrade"
)

HTTP_TIMEOUT = int(os.getenv("HTTP_TIMEOUT", "20"))
MARKET_REFRESH_INTERVAL = float(os.getenv("MARKET_REFRESH_INTERVAL", "10"))
DECISION_INTERVAL = float(os.getenv("DECISION_INTERVAL", "1"))
HEARTBEAT_INTERVAL = float(os.getenv("HEARTBEAT_INTERVAL", "30"))

START_DELAY_SEC = float(os.getenv("START_DELAY_SEC", "8"))
STOP_BEFORE_END_SEC = float(os.getenv("STOP_BEFORE_END_SEC", "5"))
MIN_SECONDS_BETWEEN_TRADES = float(
    os.getenv("MIN_SECONDS_BETWEEN_TRADES", "8")
)
RESCUE_MIN_SECONDS_BETWEEN_TRADES = float(
    os.getenv("RESCUE_MIN_SECONDS_BETWEEN_TRADES", "2")
)

MAX_SPREAD = float(os.getenv("MAX_SPREAD", "0.04"))
MAX_RESCUE_SPREAD = float(os.getenv("MAX_RESCUE_SPREAD", "0.12"))
MAX_ASK_PRICE = float(os.getenv("MAX_ASK_PRICE", "0.80"))
MAX_RESCUE_ASK_PRICE = float(os.getenv("MAX_RESCUE_ASK_PRICE", "0.99"))

# Обычный лимит используется для входов, усреднений и новых циклов.
MAX_MARKET_CAPITAL_USDC = float(
    os.getenv("MAX_MARKET_CAPITAL_USDC", "30.00")
)

# Дополнительный капитал можно использовать только для покупки
# противоположной стороны и сокращения непарного риска.
EMERGENCY_MARKET_CAPITAL_USDC = float(
    os.getenv("EMERGENCY_MARKET_CAPITAL_USDC", "45.00")
)

PAPER_LOTS = {
    "BTC": float(os.getenv("BTC_PAPER_LOT", "1")),
    "ETH": float(os.getenv("ETH_PAPER_LOT", "1")),
}

MIN_ORDER_NOTIONAL_USDC = float(
    os.getenv("MIN_ORDER_NOTIONAL_USDC", "1.00")
)
ORDER_SIZE_STEP = float(os.getenv("ORDER_SIZE_STEP", "0.01"))

MAX_BUYS_PER_SIDE = int(os.getenv("MAX_BUYS_PER_SIDE", "5"))
MAX_TOTAL_TRADES = int(os.getenv("MAX_TOTAL_TRADES", "10"))
MAX_RESCUE_TRADES = int(os.getenv("MAX_RESCUE_TRADES", "6"))

ANCHOR_MAX_PRICE = float(os.getenv("ANCHOR_MAX_PRICE", "0.42"))
MIN_PRICE_IMPROVEMENT = float(
    os.getenv("MIN_PRICE_IMPROVEMENT", "0.04")
)
MIN_SECONDS_AFTER_ANCHOR_FOR_PAIR = float(
    os.getenv("MIN_SECONDS_AFTER_ANCHOR_FOR_PAIR", "20")
)

PAIR_TARGET_SUM = float(os.getenv("PAIR_TARGET_SUM", "0.98"))
PAIR_ACCEPTABLE_SUM = float(os.getenv("PAIR_ACCEPTABLE_SUM", "0.99"))
LOCK_PROFIT_PNL = float(os.getenv("LOCK_PROFIT_PNL", "0.04"))

MAX_UNPAIRED_QTY = float(os.getenv("MAX_UNPAIRED_QTY", "10.00"))
MAX_TOTAL_WORST_PNL_LOSS = float(
    os.getenv("MAX_TOTAL_WORST_PNL_LOSS", "1.10")
)

MAX_CYCLES_PER_MARKET = int(os.getenv("MAX_CYCLES_PER_MARKET", "4"))
NEW_CYCLE_MIN_PRICE = float(os.getenv("NEW_CYCLE_MIN_PRICE", "0.38"))
NEW_CYCLE_MIN_DELAY_SEC = float(
    os.getenv("NEW_CYCLE_MIN_DELAY_SEC", "20")
)
NEW_CYCLE_STOP_BEFORE_END_SEC = float(
    os.getenv("NEW_CYCLE_STOP_BEFORE_END_SEC", "75")
)

# Smart Rescue включается за минуту до конца.
SMART_RESCUE_WINDOW_SEC = float(
    os.getenv("SMART_RESCUE_WINDOW_SEC", "60")
)
SMART_RESCUE_STRONG_WINDOW_SEC = float(
    os.getenv("SMART_RESCUE_STRONG_WINDOW_SEC", "30")
)
SMART_RESCUE_FINAL_WINDOW_SEC = float(
    os.getenv("SMART_RESCUE_FINAL_WINDOW_SEC", "10")
)

# Минимальное улучшение worst PnL для каждой ступени.
RESCUE_MIN_IMPROVEMENT_60S = float(
    os.getenv("RESCUE_MIN_IMPROVEMENT_60S", "0.05")
)
RESCUE_MIN_IMPROVEMENT_30S = float(
    os.getenv("RESCUE_MIN_IMPROVEMENT_30S", "0.02")
)
RESCUE_MIN_IMPROVEMENT_10S = float(
    os.getenv("RESCUE_MIN_IMPROVEMENT_10S", "0.005")
)

# Ограничение гарантированного убытка после спасения.
MAX_RESCUE_WORST_LOSS_60S = float(
    os.getenv("MAX_RESCUE_WORST_LOSS_60S", "0.60")
)
MAX_RESCUE_WORST_LOSS_30S = float(
    os.getenv("MAX_RESCUE_WORST_LOSS_30S", "0.90")
)
MAX_RESCUE_WORST_LOSS_10S = float(
    os.getenv("MAX_RESCUE_WORST_LOSS_10S", "1.10")
)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()
TELEGRAM_POLLING_ENABLED = (
    os.getenv("TELEGRAM_POLLING_ENABLED", "true").strip().lower() == "true"
)
