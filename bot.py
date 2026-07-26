import json
import logging
import signal
import threading
import time
from dataclasses import asdict
from typing import Any

import requests

from config import (
    DECISION_INTERVAL,
    GAMMA_API_URL,
    HEARTBEAT_INTERVAL,
    HTTP_TIMEOUT,
    LOG_FILE,
    MARKET_REFRESH_INTERVAL,
)
from database import (
    init_database,
    insert_paper_trade,
    insert_snapshot,
    upsert_market,
    upsert_result,
)
from feeds import (
    discover_current_markets,
    fetch_books,
    latest_reference,
    reference_change,
    start_binance,
    stop as stop_feeds,
)
from models import Market, Portfolio
from strategy import apply_decision, choose_decision
from telegram_bot import send_message, start_polling, stop as stop_telegram

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ],
)
logger = logging.getLogger("PAPER_BOT_V6")

STOP = threading.Event()
HTTP = requests.Session()

RESOLUTION_CHECK_INTERVAL = 10.0
RESOLUTION_GRACE_PERIOD = 3.0


def shutdown(*_args) -> None:
    STOP.set()
    stop_feeds()
    stop_telegram()


def portfolio_text(p: Portfolio) -> str:
    return (
        f"UP {p.up_qty:.2f} / ${p.up_spent:.2f}\n"
        f"DOWN {p.down_qty:.2f} / ${p.down_spent:.2f}\n"
        f"Всего вложено: ${p.total_spent:.2f}\n"
        f"PnL UP: ${p.pnl_if_up:+.2f}\n"
        f"PnL DOWN: ${p.pnl_if_down:+.2f}\n"
        f"Worst: ${p.worst_pnl:+.2f}\n"
        f"Парное ядро: {p.paired_qty:.2f}\n"
        f"Непарный остаток: {p.unpaired_qty:.2f} {p.unpaired_side or '-'}\n"
        f"Циклов закрыто: {p.cycle_count}"
    )


def decode_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except Exception:
            return []
    return []


def normalize_outcome(value: Any) -> str | None:
    text = str(value or "").strip().upper()
    if text in {"UP", "YES"}:
        return "UP"
    if text in {"DOWN", "NO"}:
        return "DOWN"
    return None


def fetch_event_by_slug(slug: str) -> dict[str, Any] | None:
    for url, params in (
        (f"{GAMMA_API_URL}/events/slug/{slug}", None),
        (f"{GAMMA_API_URL}/events", {"slug": slug}),
    ):
        try:
            response = HTTP.get(url, params=params, timeout=HTTP_TIMEOUT)
            if response.status_code == 404:
                continue
            response.raise_for_status()
            payload = response.json()
            if isinstance(payload, dict):
                return payload
            if isinstance(payload, list) and payload and isinstance(payload[0], dict):
                return payload[0]
        except Exception:
            continue
    return None


def resolve_market_winner(market: Market) -> str | None:
    if not market.slug:
        return None

    event = fetch_event_by_slug(market.slug)
    if not event:
        return None

    raw_markets = event.get("markets")
    if not isinstance(raw_markets, list):
        return None

    selected = None
    for raw in raw_markets:
        if not isinstance(raw, dict):
            continue
        condition_id = str(
            raw.get("conditionId") or raw.get("condition_id") or ""
        )
        if condition_id == market.condition_id:
            selected = raw
            break

    if selected is None and len(raw_markets) == 1 and isinstance(raw_markets[0], dict):
        selected = raw_markets[0]

    if selected is None:
        return None

    outcomes = [
        normalize_outcome(x)
        for x in decode_list(selected.get("outcomes"))
    ]

    prices = []
    for value in decode_list(
        selected.get("outcomePrices")
        or selected.get("outcome_prices")
    ):
        try:
            prices.append(float(value))
        except Exception:
            prices.append(0.0)

    if len(outcomes) < 2 or len(prices) < 2:
        return None

    clearly_resolved = max(prices) >= 0.99 and min(prices) <= 0.01
    if not bool(selected.get("closed") or event.get("closed")) and not clearly_resolved:
        return None

    index = max(range(len(prices)), key=lambda i: prices[i])
    if prices[index] < 0.99 or index >= len(outcomes):
        return None

    return outcomes[index]


def main() -> None:
    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    init_database()
    start_binance()
    start_polling()

    send_message(
        "🧪 Paper Rebalancer v6 запущен.\n"
        "Реальные ордера отключены.\n"
        "Логика: V5 + SMART RESCUE в последнюю минуту."
    )

    active_markets: dict[str, Market] = {}
    all_markets: dict[str, Market] = {}
    portfolios: dict[str, Portfolio] = {}

    last_resolution_check: dict[str, float] = {}
    end_notifications_sent: set[str] = set()

    last_market_refresh = 0.0
    last_decision = 0.0
    last_heartbeat = 0.0

    while not STOP.is_set():
        now = time.time()

        try:
            if now - last_market_refresh >= MARKET_REFRESH_INTERVAL:
                discovered = discover_current_markets()

                for coin, market in discovered.items():
                    active_markets[coin] = market
                    all_markets[market.condition_id] = market

                    portfolios.setdefault(
                        market.condition_id,
                        Portfolio(
                            condition_id=market.condition_id,
                            coin=market.coin,
                        ),
                    )

                    upsert_market(asdict(market), now)

                last_market_refresh = now

            if now - last_decision >= DECISION_INTERVAL and active_markets:
                current_markets = [
                    market
                    for market in active_markets.values()
                    if now < market.end_timestamp
                ]

                books = fetch_books(current_markets)

                for coin, market in list(active_markets.items()):
                    if now >= market.end_timestamp:
                        continue

                    portfolio = portfolios.setdefault(
                        market.condition_id,
                        Portfolio(
                            condition_id=market.condition_id,
                            coin=coin,
                        ),
                    )

                    pair = books.get(market.condition_id, {})
                    up = pair.get("UP")
                    down = pair.get("DOWN")

                    if not up or not down:
                        continue

                    reference_price = latest_reference(coin)
                    change5 = reference_change(coin, 5)
                    change20 = reference_change(coin, 20)

                    insert_snapshot({
                        "timestamp": now,
                        "condition_id": market.condition_id,
                        "coin": coin,
                        "market_second": now - market.start_timestamp,
                        "reference_price": reference_price,
                        "reference_change_5s": change5,
                        "reference_change_20s": change20,
                        "up_bid": up.bid,
                        "up_ask": up.ask,
                        "up_spread": up.spread,
                        "down_bid": down.bid,
                        "down_ask": down.ask,
                        "down_spread": down.spread,
                    })

                    if portfolio.finalized:
                        continue

                    decision = choose_decision(
                        now=now,
                        market=market,
                        portfolio=portfolio,
                        up=up,
                        down=down,
                        reference_price=reference_price,
                        reference_change_5s=change5,
                        reference_change_20s=change20,
                    )

                    if not decision:
                        continue

                    apply_decision(
                        portfolio=portfolio,
                        decision=decision,
                        now=now,
                        reference_price=reference_price,
                    )

                    insert_paper_trade({
                        "timestamp": now,
                        "condition_id": market.condition_id,
                        "coin": coin,
                        "action": decision.action,
                        "side": decision.side,
                        "price": decision.price,
                        "quantity": decision.quantity,
                        "cost": decision.price * decision.quantity,
                        "score": decision.score,
                        "reason": decision.reason,
                        "before_json": decision.before,
                        "after_json": decision.after,
                    })

                    message = (
                        f"🧪 {decision.action} {decision.side} | {coin}\n\n"
                        f"{market.title}\n"
                        f"Цена: ${decision.price:.4f}\n"
                        f"Количество: {decision.quantity:.2f}\n"
                        f"Score: {decision.score:.3f}\n"
                        f"Причина: {decision.reason}\n\n"
                        f"{portfolio_text(portfolio)}"
                    )

                    logger.info(message.replace("\n", " | "))
                    send_message(message)

                last_decision = now

            for condition_id, market in list(all_markets.items()):
                portfolio = portfolios.get(condition_id)

                if not portfolio or portfolio.finalized:
                    continue

                if now < market.end_timestamp + RESOLUTION_GRACE_PERIOD:
                    continue

                if condition_id not in end_notifications_sent:
                    send_message(
                        f"⏳ Торговое окно завершено | {market.coin}\n\n"
                        f"{market.title}\n\n"
                        f"{portfolio_text(portfolio)}\n\n"
                        "Ожидаю официальный результат Polymarket."
                    )
                    end_notifications_sent.add(condition_id)

                if (
                    now - last_resolution_check.get(condition_id, 0.0)
                    < RESOLUTION_CHECK_INTERVAL
                ):
                    continue

                last_resolution_check[condition_id] = now
                winner = resolve_market_winner(market)

                if winner is None:
                    continue

                pnl = (
                    portfolio.pnl_if_up
                    if winner == "UP"
                    else portfolio.pnl_if_down
                )

                portfolio.finalized = True

                upsert_result({
                    "condition_id": market.condition_id,
                    "coin": market.coin,
                    "title": market.title,
                    "end_timestamp": market.end_timestamp,
                    "up_qty": portfolio.up_qty,
                    "down_qty": portfolio.down_qty,
                    "total_spent": portfolio.total_spent,
                    "pnl_if_up": portfolio.pnl_if_up,
                    "pnl_if_down": portfolio.pnl_if_down,
                    "winner": winner,
                    "realized_pnl": pnl,
                    "trade_count": portfolio.trade_count,
                    "guaranteed": portfolio.guaranteed,
                    "finalized_at": now,
                })

                emoji = "✅" if pnl > 0 else "➖" if pnl == 0 else "❌"

                send_message(
                    f"🏁 РЫНОК РАССЧИТАН | {market.coin}\n\n"
                    f"{market.title}\n\n"
                    f"Победитель: {winner}\n"
                    f"{portfolio_text(portfolio)}\n\n"
                    f"{emoji} Фактический paper PnL: ${pnl:+.2f}\n"
                    f"Сделок: {portfolio.trade_count}"
                )

            if now - last_heartbeat >= HEARTBEAT_INTERVAL:
                logger.info(
                    "HEARTBEAT | active=%s | all=%s | portfolios=%s",
                    len(active_markets),
                    len(all_markets),
                    len(portfolios),
                )
                last_heartbeat = now

            STOP.wait(0.2)

        except Exception:
            logger.exception("Main loop error")
            STOP.wait(5)

    logger.info("Paper bot v4 stopped")


if __name__ == "__main__":
    main()
