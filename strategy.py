import math
from dataclasses import dataclass

from config import (
    ANCHOR_MAX_PRICE,
    EMERGENCY_MARKET_CAPITAL_USDC,
    LOCK_PROFIT_PNL,
    MAX_ASK_PRICE,
    MAX_BUYS_PER_SIDE,
    MAX_CYCLES_PER_MARKET,
    MAX_MARKET_CAPITAL_USDC,
    MAX_RESCUE_ASK_PRICE,
    MAX_RESCUE_SPREAD,
    MAX_RESCUE_TRADES,
    MAX_RESCUE_WORST_LOSS_10S,
    MAX_RESCUE_WORST_LOSS_30S,
    MAX_RESCUE_WORST_LOSS_60S,
    MAX_SPREAD,
    MAX_TOTAL_TRADES,
    MAX_TOTAL_WORST_PNL_LOSS,
    MAX_UNPAIRED_QTY,
    MIN_ORDER_NOTIONAL_USDC,
    MIN_PRICE_IMPROVEMENT,
    MIN_SECONDS_AFTER_ANCHOR_FOR_PAIR,
    MIN_SECONDS_BETWEEN_TRADES,
    NEW_CYCLE_MIN_DELAY_SEC,
    NEW_CYCLE_MIN_PRICE,
    NEW_CYCLE_STOP_BEFORE_END_SEC,
    ORDER_SIZE_STEP,
    PAIR_ACCEPTABLE_SUM,
    PAIR_TARGET_SUM,
    PAPER_LOTS,
    RESCUE_MIN_IMPROVEMENT_10S,
    RESCUE_MIN_IMPROVEMENT_30S,
    RESCUE_MIN_IMPROVEMENT_60S,
    RESCUE_MIN_SECONDS_BETWEEN_TRADES,
    SMART_RESCUE_FINAL_WINDOW_SEC,
    SMART_RESCUE_STRONG_WINDOW_SEC,
    SMART_RESCUE_WINDOW_SEC,
    START_DELAY_SEC,
    STOP_BEFORE_END_SEC,
)
from models import BookSide, Market, Portfolio


EPSILON = 1e-9


@dataclass(slots=True)
class Decision:
    action: str
    side: str
    price: float
    quantity: float
    score: float
    reason: str
    before: dict
    after: dict


def _state(portfolio: Portfolio) -> dict:
    return {
        "up_qty": round(portfolio.up_qty, 6),
        "down_qty": round(portfolio.down_qty, 6),
        "up_spent": round(portfolio.up_spent, 6),
        "down_spent": round(portfolio.down_spent, 6),
        "total_spent": round(portfolio.total_spent, 6),
        "pnl_if_up": round(portfolio.pnl_if_up, 6),
        "pnl_if_down": round(portfolio.pnl_if_down, 6),
        "worst_pnl": round(portfolio.worst_pnl, 6),
        "paired_qty": round(portfolio.paired_qty, 6),
        "unpaired_qty": round(portfolio.unpaired_qty, 6),
        "unpaired_side": portfolio.unpaired_side,
        "cycle_count": portfolio.cycle_count,
        "trade_count": portfolio.trade_count,
    }


def _clone(portfolio: Portfolio) -> Portfolio:
    return Portfolio(
        condition_id=portfolio.condition_id,
        coin=portfolio.coin,
        up_qty=portfolio.up_qty,
        down_qty=portfolio.down_qty,
        up_spent=portfolio.up_spent,
        down_spent=portfolio.down_spent,
        last_trade_timestamp=portfolio.last_trade_timestamp,
        trade_count=portfolio.trade_count,
        cycle_count=portfolio.cycle_count,
        up_buy_count=portfolio.up_buy_count,
        down_buy_count=portfolio.down_buy_count,
        anchor_side=portfolio.anchor_side,
        anchor_timestamp=portfolio.anchor_timestamp,
        anchor_price=portfolio.anchor_price,
        best_up_ask_seen=portfolio.best_up_ask_seen,
        best_down_ask_seen=portfolio.best_down_ask_seen,
        last_up_buy_price=portfolio.last_up_buy_price,
        last_down_buy_price=portfolio.last_down_buy_price,
        finalized=portfolio.finalized,
    )


def _simulate(
    portfolio: Portfolio,
    side: str,
    price: float,
    quantity: float,
) -> Portfolio:
    candidate = _clone(portfolio)
    cost = price * quantity

    if side == "UP":
        candidate.up_qty += quantity
        candidate.up_spent += cost
        candidate.up_buy_count += 1
        candidate.last_up_buy_price = price
    else:
        candidate.down_qty += quantity
        candidate.down_spent += cost
        candidate.down_buy_count += 1
        candidate.last_down_buy_price = price

    candidate.trade_count += 1
    return candidate


def _valid_normal_book(book: BookSide) -> bool:
    return (
        book.ask is not None
        and book.spread is not None
        and 0 < float(book.ask) <= MAX_ASK_PRICE
        and 0 <= float(book.spread) <= MAX_SPREAD
    )


def _valid_rescue_book(book: BookSide) -> bool:
    return (
        book.ask is not None
        and book.spread is not None
        and 0 < float(book.ask) <= MAX_RESCUE_ASK_PRICE
        and 0 <= float(book.spread) <= MAX_RESCUE_SPREAD
    )


def _round_up(value: float, step: float) -> float:
    if step <= 0:
        return value
    return math.ceil((value - 1e-12) / step) * step


def _minimum_quantity(
    coin: str,
    book: BookSide,
    requested_quantity: float | None = None,
) -> float | None:
    if book.ask is None or float(book.ask) <= 0:
        return None

    price = float(book.ask)
    base_quantity = float(PAPER_LOTS[coin])
    requested = float(requested_quantity or 0.0)
    exchange_minimum = max(0.0, float(book.min_order_size or 0.0))
    notional_minimum = MIN_ORDER_NOTIONAL_USDC / price

    quantity = max(
        base_quantity,
        requested,
        exchange_minimum,
        notional_minimum,
    )

    return round(_round_up(quantity, ORDER_SIZE_STEP), 8)


def update_observed_prices(
    portfolio: Portfolio,
    up: BookSide,
    down: BookSide,
) -> None:
    if up.ask is not None:
        price = float(up.ask)
        portfolio.best_up_ask_seen = (
            price
            if portfolio.best_up_ask_seen is None
            else min(portfolio.best_up_ask_seen, price)
        )

    if down.ask is not None:
        price = float(down.ask)
        portfolio.best_down_ask_seen = (
            price
            if portfolio.best_down_ask_seen is None
            else min(portfolio.best_down_ask_seen, price)
        )


def _decision(
    action: str,
    side: str,
    price: float,
    quantity: float,
    score: float,
    reason: str,
    portfolio: Portfolio,
) -> Decision:
    candidate = _simulate(
        portfolio=portfolio,
        side=side,
        price=price,
        quantity=quantity,
    )

    return Decision(
        action=action,
        side=side,
        price=price,
        quantity=quantity,
        score=score,
        reason=reason,
        before=_state(portfolio),
        after=_state(candidate),
    )


def _buy_count(portfolio: Portfolio, side: str) -> int:
    return (
        portfolio.up_buy_count
        if side == "UP"
        else portfolio.down_buy_count
    )


def _last_buy_price(
    portfolio: Portfolio,
    side: str,
) -> float | None:
    return (
        portfolio.last_up_buy_price
        if side == "UP"
        else portfolio.last_down_buy_price
    )


def _opposite_side(side: str) -> str:
    return "DOWN" if side == "UP" else "UP"


def _book_for_side(
    side: str,
    up: BookSide,
    down: BookSide,
) -> BookSide:
    return up if side == "UP" else down


def _anchor_decisions(
    portfolio: Portfolio,
    up: BookSide,
    down: BookSide,
) -> list[Decision]:
    decisions: list[Decision] = []

    for side, book in (("UP", up), ("DOWN", down)):
        if not _valid_normal_book(book):
            continue

        price = float(book.ask)
        spread = float(book.spread)

        if price > ANCHOR_MAX_PRICE:
            continue

        quantity = _minimum_quantity(portfolio.coin, book)
        if quantity is None:
            continue

        candidate = _simulate(portfolio, side, price, quantity)

        if candidate.total_spent > MAX_MARKET_CAPITAL_USDC:
            continue

        if candidate.unpaired_qty > MAX_UNPAIRED_QTY:
            continue

        if candidate.worst_pnl < -MAX_TOTAL_WORST_PNL_LOSS:
            continue

        value = 1.0 - price
        score = value * 0.70 - spread * 1.50

        decisions.append(
            _decision(
                action="ANCHOR_ENTRY",
                side=side,
                price=price,
                quantity=quantity,
                score=score,
                reason=(
                    f"ANCHOR_ENTRY; ask={price:.4f}; qty={quantity:.2f}; "
                    f"min_size={book.min_order_size:.2f}; "
                    f"notional=${price * quantity:.2f}; "
                    f"spread={spread:.4f}; "
                    f"worst_after={candidate.worst_pnl:+.3f}"
                ),
                portfolio=portfolio,
            )
        )

    return decisions


def _scale_anchor_decisions(
    portfolio: Portfolio,
    up: BookSide,
    down: BookSide,
) -> list[Decision]:
    side = portfolio.unpaired_side
    if side is None:
        return []

    if _buy_count(portfolio, side) >= MAX_BUYS_PER_SIDE:
        return []

    book = _book_for_side(side, up, down)
    if not _valid_normal_book(book):
        return []

    price = float(book.ask)
    last_price = _last_buy_price(portfolio, side)

    if last_price is None:
        return []

    improvement = last_price - price
    if improvement < MIN_PRICE_IMPROVEMENT:
        return []

    quantity = _minimum_quantity(portfolio.coin, book)
    if quantity is None:
        return []

    candidate = _simulate(portfolio, side, price, quantity)

    if candidate.total_spent > MAX_MARKET_CAPITAL_USDC:
        return []

    if candidate.unpaired_qty > MAX_UNPAIRED_QTY:
        return []

    if candidate.worst_pnl < -MAX_TOTAL_WORST_PNL_LOSS:
        return []

    score = improvement * 3.0 - float(book.spread)

    return [
        _decision(
            action="SCALE_ANCHOR",
            side=side,
            price=price,
            quantity=quantity,
            score=score,
            reason=(
                f"SCALE_ANCHOR; last={last_price:.4f}; ask={price:.4f}; "
                f"qty={quantity:.2f}; improvement={improvement:.4f}; "
                f"worst_after={candidate.worst_pnl:+.3f}"
            ),
            portfolio=portfolio,
        )
    ]


def _pair_lock_decisions(
    now: float,
    portfolio: Portfolio,
    up: BookSide,
    down: BookSide,
) -> list[Decision]:
    side = portfolio.unpaired_side
    if side is None or portfolio.unpaired_qty <= EPSILON:
        return []

    if (
        now - portfolio.anchor_timestamp
        < MIN_SECONDS_AFTER_ANCHOR_FOR_PAIR
    ):
        return []

    buy_side = _opposite_side(side)
    book = _book_for_side(buy_side, up, down)

    if not _valid_normal_book(book):
        return []

    price = float(book.ask)
    quantity = _minimum_quantity(
        portfolio.coin,
        book,
        requested_quantity=portfolio.unpaired_qty,
    )

    if quantity is None:
        return []

    candidate = _simulate(portfolio, buy_side, price, quantity)

    if candidate.total_spent > MAX_MARKET_CAPITAL_USDC:
        return []

    up_average = (
        candidate.up_spent / candidate.up_qty
        if candidate.up_qty > 0
        else 0.0
    )
    down_average = (
        candidate.down_spent / candidate.down_qty
        if candidate.down_qty > 0
        else 0.0
    )
    pair_sum = up_average + down_average

    if pair_sum > PAIR_ACCEPTABLE_SUM:
        return []

    worst_gain = candidate.worst_pnl - portfolio.worst_pnl
    if worst_gain <= 0:
        return []

    target_bonus = max(0.0, PAIR_TARGET_SUM - pair_sum) * 5.0
    score = (
        worst_gain * 1.40
        + target_bonus
        - float(book.spread)
    )

    return [
        _decision(
            action="PAIR_LOCK",
            side=buy_side,
            price=price,
            quantity=quantity,
            score=score,
            reason=(
                f"PAIR_LOCK; pair_sum={pair_sum:.4f}; "
                f"qty={quantity:.2f}; notional=${price * quantity:.2f}; "
                f"worst_before={portfolio.worst_pnl:+.3f}; "
                f"worst_after={candidate.worst_pnl:+.3f}"
            ),
            portfolio=portfolio,
        )
    ]


def _new_cycle_decisions(
    now: float,
    market: Market,
    portfolio: Portfolio,
    up: BookSide,
    down: BookSide,
) -> list[Decision]:
    if portfolio.unpaired_qty > EPSILON:
        return []

    if portfolio.cycle_count >= MAX_CYCLES_PER_MARKET:
        return []

    if (
        now - portfolio.last_trade_timestamp
        < NEW_CYCLE_MIN_DELAY_SEC
    ):
        return []

    seconds_left = market.end_timestamp - now
    if seconds_left <= NEW_CYCLE_STOP_BEFORE_END_SEC:
        return []

    if (
        portfolio.worst_pnl >= LOCK_PROFIT_PNL
        and portfolio.cycle_count >= 1
    ):
        return []

    decisions: list[Decision] = []

    for side, book in (("UP", up), ("DOWN", down)):
        if not _valid_normal_book(book):
            continue

        price = float(book.ask)
        if price > NEW_CYCLE_MIN_PRICE:
            continue

        quantity = _minimum_quantity(portfolio.coin, book)
        if quantity is None:
            continue

        candidate = _simulate(portfolio, side, price, quantity)

        if candidate.total_spent > MAX_MARKET_CAPITAL_USDC:
            continue

        if candidate.unpaired_qty > MAX_UNPAIRED_QTY:
            continue

        if candidate.worst_pnl < -MAX_TOTAL_WORST_PNL_LOSS:
            continue

        score = (
            (1.0 - price) * 0.60
            - float(book.spread) * 1.50
        )

        decisions.append(
            _decision(
                action="NEW_CYCLE",
                side=side,
                price=price,
                quantity=quantity,
                score=score,
                reason=(
                    f"NEW_CYCLE; ask={price:.4f}; qty={quantity:.2f}; "
                    f"notional=${price * quantity:.2f}; "
                    f"worst_before={portfolio.worst_pnl:+.3f}; "
                    f"worst_after={candidate.worst_pnl:+.3f}; "
                    f"cycle={portfolio.cycle_count + 1}"
                ),
                portfolio=portfolio,
            )
        )

    return decisions


def _rescue_tier(
    seconds_left: float,
) -> tuple[str, float, float]:
    if seconds_left <= SMART_RESCUE_FINAL_WINDOW_SEC:
        return (
            "SMART_RESCUE_FINAL",
            RESCUE_MIN_IMPROVEMENT_10S,
            MAX_RESCUE_WORST_LOSS_10S,
        )

    if seconds_left <= SMART_RESCUE_STRONG_WINDOW_SEC:
        return (
            "SMART_RESCUE_STRONG",
            RESCUE_MIN_IMPROVEMENT_30S,
            MAX_RESCUE_WORST_LOSS_30S,
        )

    return (
        "SMART_RESCUE",
        RESCUE_MIN_IMPROVEMENT_60S,
        MAX_RESCUE_WORST_LOSS_60S,
    )


def _smart_rescue_decisions(
    now: float,
    market: Market,
    portfolio: Portfolio,
    up: BookSide,
    down: BookSide,
) -> list[Decision]:
    if portfolio.unpaired_qty <= EPSILON:
        return []

    seconds_left = market.end_timestamp - now
    if seconds_left > SMART_RESCUE_WINDOW_SEC:
        return []

    # Rescue может работать быстрее обычных сделок.
    if (
        portfolio.last_trade_timestamp > 0
        and now - portfolio.last_trade_timestamp
        < RESCUE_MIN_SECONDS_BETWEEN_TRADES
    ):
        return []

    action, minimum_improvement, maximum_loss = _rescue_tier(
        seconds_left
    )

    buy_side = _opposite_side(portfolio.unpaired_side or "UP")
    book = _book_for_side(buy_side, up, down)

    if not _valid_rescue_book(book):
        return []

    price = float(book.ask)
    quantity = _minimum_quantity(
        portfolio.coin,
        book,
        requested_quantity=portfolio.unpaired_qty,
    )

    if quantity is None:
        return []

    candidate = _simulate(
        portfolio,
        buy_side,
        price,
        quantity,
    )

    if candidate.total_spent > EMERGENCY_MARKET_CAPITAL_USDC:
        return []

    improvement = candidate.worst_pnl - portfolio.worst_pnl

    if improvement < minimum_improvement:
        return []

    # Не превращаем спасение в гарантированно бессмысленную переплату.
    # В финальной ступени допускается больший убыток, но только при улучшении.
    if candidate.worst_pnl < -maximum_loss:
        return []

    unpaired_reduction = (
        portfolio.unpaired_qty - candidate.unpaired_qty
    )

    if (
        unpaired_reduction <= EPSILON
        and improvement <= minimum_improvement
    ):
        return []

    urgency = max(
        0.0,
        (SMART_RESCUE_WINDOW_SEC - seconds_left)
        / SMART_RESCUE_WINDOW_SEC,
    )

    score = (
        improvement * 2.0
        + max(0.0, unpaired_reduction) * 0.10
        + urgency
        - float(book.spread) * 0.50
    )

    return [
        _decision(
            action=action,
            side=buy_side,
            price=price,
            quantity=quantity,
            score=score,
            reason=(
                f"{action}; seconds_left={seconds_left:.1f}; "
                f"qty={quantity:.2f}; min_size={book.min_order_size:.2f}; "
                f"notional=${price * quantity:.2f}; "
                f"capital_after=${candidate.total_spent:.2f}/"
                f"${EMERGENCY_MARKET_CAPITAL_USDC:.2f}; "
                f"unpaired={portfolio.unpaired_qty:.2f}"
                f"->{candidate.unpaired_qty:.2f}; "
                f"worst={portfolio.worst_pnl:+.3f}"
                f"->{candidate.worst_pnl:+.3f}; "
                f"improvement={improvement:+.3f}"
            ),
            portfolio=portfolio,
        )
    ]


def choose_decision(
    now: float,
    market: Market,
    portfolio: Portfolio,
    up: BookSide,
    down: BookSide,
    reference_price: float | None,
    reference_change_5s: float | None,
    reference_change_20s: float | None,
) -> Decision | None:
    del reference_price
    del reference_change_5s
    del reference_change_20s

    update_observed_prices(portfolio, up, down)

    market_second = now - market.start_timestamp
    seconds_left = market.end_timestamp - now

    if market_second < START_DELAY_SEC:
        return None

    if seconds_left <= STOP_BEFORE_END_SEC:
        return None

    # Smart Rescue имеет абсолютный приоритет и может работать
    # после достижения обычного лимита капитала и числа сделок.
    if (
        portfolio.unpaired_qty > EPSILON
        and seconds_left <= SMART_RESCUE_WINDOW_SEC
    ):
        rescue_candidates = _smart_rescue_decisions(
            now=now,
            market=market,
            portfolio=portfolio,
            up=up,
            down=down,
        )
        return max(
            rescue_candidates,
            key=lambda item: item.score,
            default=None,
        )

    if (
        portfolio.last_trade_timestamp > 0
        and now - portfolio.last_trade_timestamp
        < MIN_SECONDS_BETWEEN_TRADES
    ):
        return None

    if portfolio.total_spent >= MAX_MARKET_CAPITAL_USDC:
        return None

    if portfolio.trade_count >= MAX_TOTAL_TRADES:
        return None

    candidates: list[Decision] = []

    if portfolio.trade_count == 0:
        candidates.extend(
            _anchor_decisions(
                portfolio=portfolio,
                up=up,
                down=down,
            )
        )
    else:
        # До последней минуты сохраняем исходную логику v5.
        candidates.extend(
            _pair_lock_decisions(
                now=now,
                portfolio=portfolio,
                up=up,
                down=down,
            )
        )

        candidates.extend(
            _scale_anchor_decisions(
                portfolio=portfolio,
                up=up,
                down=down,
            )
        )

        candidates.extend(
            _new_cycle_decisions(
                now=now,
                market=market,
                portfolio=portfolio,
                up=up,
                down=down,
            )
        )

    return max(
        candidates,
        key=lambda item: item.score,
        default=None,
    )


def apply_decision(
    portfolio: Portfolio,
    decision: Decision,
    now: float,
    reference_price: float | None,
) -> None:
    del reference_price

    cost = decision.price * decision.quantity

    if decision.side == "UP":
        portfolio.up_qty += decision.quantity
        portfolio.up_spent += cost
        portfolio.up_buy_count += 1
        portfolio.last_up_buy_price = decision.price
    else:
        portfolio.down_qty += decision.quantity
        portfolio.down_spent += cost
        portfolio.down_buy_count += 1
        portfolio.last_down_buy_price = decision.price

    portfolio.last_trade_timestamp = now
    portfolio.trade_count += 1

    if decision.action in {"ANCHOR_ENTRY", "NEW_CYCLE"}:
        portfolio.anchor_side = decision.side
        portfolio.anchor_timestamp = now
        portfolio.anchor_price = decision.price

    if decision.action == "PAIR_LOCK":
        portfolio.cycle_count += 1
        portfolio.anchor_side = None
        portfolio.anchor_timestamp = 0.0
        portfolio.anchor_price = None

    if decision.action.startswith("SMART_RESCUE"):
        if portfolio.unpaired_qty <= EPSILON:
            portfolio.cycle_count += 1
            portfolio.anchor_side = None
            portfolio.anchor_timestamp = 0.0
            portfolio.anchor_price = None
