import math
from dataclasses import dataclass

from config import (
    ANCHOR_MAX_PRICE,
    DEFENSIVE_PAIR_MAX_SUM,
    DEFENSIVE_PAIR_WINDOW_SEC,
    EMERGENCY_MARKET_CAPITAL_USDC,
    EMERGENCY_PAIR_MAX_SUM,
    EMERGENCY_PAIR_WINDOW_SEC,
    ENTRY_PAIR_CHECK_MAX_SUM,
    MAX_ASK_PRICE,
    MAX_CYCLES_PER_MARKET,
    MAX_MARKET_CAPITAL_USDC,
    MAX_NEW_CYCLE_RISK_USDC,
    MAX_SPREAD,
    MAX_TOTAL_TRADES,
    MAX_TOTAL_WORST_PNL_LOSS,
    MIN_ORDER_NOTIONAL_USDC,
    MIN_SECONDS_AFTER_ANCHOR_FOR_PAIR,
    MIN_SECONDS_BETWEEN_TRADES,
    NEW_CYCLE_MIN_DELAY_SEC,
    NEW_CYCLE_MIN_PRICE,
    NEW_CYCLE_STOP_BEFORE_END_SEC,
    ORDER_SIZE_STEP,
    PAIR_ACCEPTABLE_SUM,
    PAIR_TARGET_SUM,
    PAPER_LOTS,
    START_DELAY_SEC,
    STOP_BEFORE_END_SEC,
)
from models import BookSide, Market, Portfolio


EPSILON = 1e-9

# Между 90 и 30 секундами разрешается строгий добор
# исходной стороны, только если её цена сильно снизилась.
LATE_SAME_SIDE_PRICE_DROP = 0.08

# Максимальное ухудшение worst PnL при таком доборе.
LATE_SAME_SIDE_MAX_WORST_DETERIORATION = 0.20

# В последние 30 секунд исходную сторону больше не покупаем.
LATE_SAME_SIDE_STOP_BEFORE_END_SEC = 30.0


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


def _valid_book(book: BookSide) -> bool:
    if book.ask is None:
        return False

    if book.spread is None:
        return False

    price = float(book.ask)
    spread = float(book.spread)

    if price <= 0:
        return False

    if price > MAX_ASK_PRICE:
        return False

    if spread < 0:
        return False

    if spread > MAX_SPREAD:
        return False

    return True


def _round_up(
    value: float,
    step: float,
) -> float:
    if step <= 0:
        return value

    return (
        math.ceil(
            (value - 1e-12) / step
        )
        * step
    )


def _minimum_quantity(
    coin: str,
    book: BookSide,
    requested_quantity: float | None = None,
) -> float | None:
    if book.ask is None:
        return None

    price = float(book.ask)

    if price <= 0:
        return None

    base_quantity = float(
        PAPER_LOTS[coin]
    )

    requested = float(
        requested_quantity or 0.0
    )

    exchange_minimum = max(
        0.0,
        float(
            book.min_order_size or 0.0
        ),
    )

    notional_minimum = (
        MIN_ORDER_NOTIONAL_USDC
        / price
    )

    quantity = max(
        base_quantity,
        requested,
        exchange_minimum,
        notional_minimum,
    )

    return round(
        _round_up(
            quantity,
            ORDER_SIZE_STEP,
        ),
        8,
    )


def update_observed_prices(
    portfolio: Portfolio,
    up: BookSide,
    down: BookSide,
) -> None:
    if up.ask is not None:
        up_price = float(up.ask)

        if portfolio.best_up_ask_seen is None:
            portfolio.best_up_ask_seen = up_price
        else:
            portfolio.best_up_ask_seen = min(
                portfolio.best_up_ask_seen,
                up_price,
            )

    if down.ask is not None:
        down_price = float(down.ask)

        if portfolio.best_down_ask_seen is None:
            portfolio.best_down_ask_seen = down_price
        else:
            portfolio.best_down_ask_seen = min(
                portfolio.best_down_ask_seen,
                down_price,
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


def _opposite_book(
    side: str,
    up: BookSide,
    down: BookSide,
) -> BookSide:
    if side == "UP":
        return down

    return up


def _book_for_side(
    side: str,
    up: BookSide,
    down: BookSide,
) -> BookSide:
    if side == "UP":
        return up

    return down


def _last_buy_price(
    portfolio: Portfolio,
    side: str,
) -> float | None:
    if side == "UP":
        return portfolio.last_up_buy_price

    return portfolio.last_down_buy_price


def _anchor_decisions(
    portfolio: Portfolio,
    up: BookSide,
    down: BookSide,
) -> list[Decision]:
    decisions: list[Decision] = []

    for side, book in (
        ("UP", up),
        ("DOWN", down),
    ):
        if not _valid_book(book):
            continue

        opposite = _opposite_book(
            side=side,
            up=up,
            down=down,
        )

        if not _valid_book(opposite):
            continue

        price = float(book.ask)
        opposite_price = float(opposite.ask)
        spread = float(book.spread)

        if price > ANCHOR_MAX_PRICE:
            continue

        current_pair_sum = (
            price
            + opposite_price
        )

        if (
            current_pair_sum
            > ENTRY_PAIR_CHECK_MAX_SUM
        ):
            continue

        quantity = _minimum_quantity(
            coin=portfolio.coin,
            book=book,
        )

        if quantity is None:
            continue

        candidate = _simulate(
            portfolio=portfolio,
            side=side,
            price=price,
            quantity=quantity,
        )

        if (
            candidate.total_spent
            > MAX_MARKET_CAPITAL_USDC
        ):
            continue

        if (
            candidate.worst_pnl
            < -MAX_TOTAL_WORST_PNL_LOSS
        ):
            continue

        value = 1.0 - price

        pair_bonus = max(
            0.0,
            ENTRY_PAIR_CHECK_MAX_SUM
            - current_pair_sum,
        )

        score = (
            value * 0.50
            + pair_bonus * 3.0
            - spread * 1.50
        )

        decisions.append(
            _decision(
                action="ANCHOR_ENTRY",
                side=side,
                price=price,
                quantity=quantity,
                score=score,
                reason=(
                    f"ANCHOR_ENTRY; "
                    f"ask={price:.4f}; "
                    f"opposite_ask={opposite_price:.4f}; "
                    f"current_pair_sum={current_pair_sum:.4f}; "
                    f"entry_limit={ENTRY_PAIR_CHECK_MAX_SUM:.4f}; "
                    f"qty={quantity:.2f}; "
                    f"min_size={book.min_order_size:.2f}; "
                    f"notional=${price * quantity:.2f}; "
                    f"worst_after={candidate.worst_pnl:+.3f}"
                ),
                portfolio=portfolio,
            )
        )

    return decisions


def _new_cycle_decisions(
    now: float,
    market: Market,
    portfolio: Portfolio,
    up: BookSide,
    down: BookSide,
) -> list[Decision]:
    if portfolio.unpaired_qty > EPSILON:
        return []

    if (
        portfolio.cycle_count
        >= MAX_CYCLES_PER_MARKET
    ):
        return []

    if (
        portfolio.trade_count
        >= MAX_TOTAL_TRADES
    ):
        return []

    if (
        now - portfolio.last_trade_timestamp
        < NEW_CYCLE_MIN_DELAY_SEC
    ):
        return []

    seconds_left = (
        market.end_timestamp - now
    )

    if (
        seconds_left
        <= NEW_CYCLE_STOP_BEFORE_END_SEC
    ):
        return []

    decisions: list[Decision] = []

    for side, book in (
        ("UP", up),
        ("DOWN", down),
    ):
        if not _valid_book(book):
            continue

        opposite = _opposite_book(
            side=side,
            up=up,
            down=down,
        )

        if not _valid_book(opposite):
            continue

        price = float(book.ask)
        opposite_price = float(opposite.ask)

        if price > NEW_CYCLE_MIN_PRICE:
            continue

        current_pair_sum = (
            price
            + opposite_price
        )

        if (
            current_pair_sum
            > ENTRY_PAIR_CHECK_MAX_SUM
        ):
            continue

        quantity = _minimum_quantity(
            coin=portfolio.coin,
            book=book,
        )

        if quantity is None:
            continue

        candidate = _simulate(
            portfolio=portfolio,
            side=side,
            price=price,
            quantity=quantity,
        )

        if (
            candidate.total_spent
            > MAX_MARKET_CAPITAL_USDC
        ):
            continue

        absolute_risk_limit = (
            -MAX_TOTAL_WORST_PNL_LOSS
        )

        relative_risk_limit = (
            portfolio.worst_pnl
            - MAX_NEW_CYCLE_RISK_USDC
        )

        allowed_worst = max(
            absolute_risk_limit,
            relative_risk_limit,
        )

        if (
            candidate.worst_pnl
            < allowed_worst
        ):
            continue

        pair_bonus = max(
            0.0,
            ENTRY_PAIR_CHECK_MAX_SUM
            - current_pair_sum,
        )

        score = (
            (1.0 - price) * 0.40
            + pair_bonus * 3.0
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
                    f"NEW_CYCLE; "
                    f"cycle={portfolio.cycle_count + 1}; "
                    f"ask={price:.4f}; "
                    f"opposite_ask={opposite_price:.4f}; "
                    f"current_pair_sum={current_pair_sum:.4f}; "
                    f"qty={quantity:.2f}; "
                    f"notional=${price * quantity:.2f}; "
                    f"worst_before={portfolio.worst_pnl:+.3f}; "
                    f"worst_after={candidate.worst_pnl:+.3f}; "
                    f"seconds_left={seconds_left:.1f}"
                ),
                portfolio=portfolio,
            )
        )

    return decisions


def _pair_limit(
    seconds_left: float,
) -> tuple[str, float]:
    if (
        seconds_left
        <= EMERGENCY_PAIR_WINDOW_SEC
    ):
        return (
            "EMERGENCY_PAIR",
            EMERGENCY_PAIR_MAX_SUM,
        )

    if (
        seconds_left
        <= DEFENSIVE_PAIR_WINDOW_SEC
    ):
        return (
            "DEFENSIVE_PAIR",
            DEFENSIVE_PAIR_MAX_SUM,
        )

    return (
        "PAIR_LOCK",
        PAIR_ACCEPTABLE_SUM,
    )


def _pair_decisions(
    now: float,
    market: Market,
    portfolio: Portfolio,
    up: BookSide,
    down: BookSide,
) -> list[Decision]:
    if portfolio.unpaired_side is None:
        return []

    if portfolio.unpaired_qty <= EPSILON:
        return []

    seconds_left = (
        market.end_timestamp - now
    )

    waited = (
        now - portfolio.anchor_timestamp
    )

    if (
        waited
        < MIN_SECONDS_AFTER_ANCHOR_FOR_PAIR
        and seconds_left
        > DEFENSIVE_PAIR_WINDOW_SEC
    ):
        return []

    opposite_side = (
        "DOWN"
        if portfolio.unpaired_side == "UP"
        else "UP"
    )

    book = _book_for_side(
        opposite_side,
        up,
        down,
    )

    if not _valid_book(book):
        return []

    price = float(book.ask)

    quantity = _minimum_quantity(
        coin=portfolio.coin,
        book=book,
        requested_quantity=(
            portfolio.unpaired_qty
        ),
    )

    if quantity is None:
        return []

    candidate = _simulate(
        portfolio=portfolio,
        side=opposite_side,
        price=price,
        quantity=quantity,
    )

    # До 90 секунд действует обычный лимит.
    # В последние 90 секунд разрешено использовать до $45,
    # но только для противоположной стороны.
    capital_limit = (
        EMERGENCY_MARKET_CAPITAL_USDC
        if seconds_left
        <= DEFENSIVE_PAIR_WINDOW_SEC
        else MAX_MARKET_CAPITAL_USDC
    )

    if (
        candidate.total_spent
        > capital_limit
    ):
        return []

    up_average = (
        candidate.up_spent
        / candidate.up_qty
        if candidate.up_qty > 0
        else 0.0
    )

    down_average = (
        candidate.down_spent
        / candidate.down_qty
        if candidate.down_qty > 0
        else 0.0
    )

    pair_sum = (
        up_average
        + down_average
    )

    action, allowed_pair_sum = _pair_limit(
        seconds_left=seconds_left
    )

    if (
        pair_sum
        > allowed_pair_sum
    ):
        return []

    worst_improvement = (
        candidate.worst_pnl
        - portfolio.worst_pnl
    )

    unpaired_reduction = (
        portfolio.unpaired_qty
        - candidate.unpaired_qty
    )

    if worst_improvement <= 0:
        return []

    if unpaired_reduction <= EPSILON:
        return []

    target_bonus = max(
        0.0,
        PAIR_TARGET_SUM - pair_sum,
    ) * 5.0

    urgency_bonus = 0.0

    if action == "DEFENSIVE_PAIR":
        urgency_bonus = 2.0

    if action == "EMERGENCY_PAIR":
        urgency_bonus = 4.0

    score = (
        worst_improvement * 1.50
        + unpaired_reduction * 0.20
        + target_bonus
        + urgency_bonus
        - float(book.spread)
    )

    return [
        _decision(
            action=action,
            side=opposite_side,
            price=price,
            quantity=quantity,
            score=score,
            reason=(
                f"{action}; "
                f"pair_sum={pair_sum:.4f}; "
                f"allowed_sum={allowed_pair_sum:.4f}; "
                f"qty={quantity:.2f}; "
                f"min_size={book.min_order_size:.2f}; "
                f"notional=${price * quantity:.2f}; "
                f"capital_after=${candidate.total_spent:.2f}/"
                f"${capital_limit:.2f}; "
                f"unpaired={portfolio.unpaired_qty:.2f}"
                f"->{candidate.unpaired_qty:.2f}; "
                f"worst={portfolio.worst_pnl:+.3f}"
                f"->{candidate.worst_pnl:+.3f}; "
                f"seconds_left={seconds_left:.1f}; "
                f"waited={waited:.1f}s"
            ),
            portfolio=portfolio,
        )
    ]


def _late_same_side_decisions(
    now: float,
    market: Market,
    portfolio: Portfolio,
    up: BookSide,
    down: BookSide,
) -> list[Decision]:
    """
    Между 90 и 30 секундами разрешает строгий добор
    исходной стороны, если её цена сильно снизилась.

    Последние 30 секунд добор исходной стороны запрещён.
    """

    if portfolio.unpaired_side is None:
        return []

    seconds_left = (
        market.end_timestamp - now
    )

    if (
        seconds_left
        > DEFENSIVE_PAIR_WINDOW_SEC
    ):
        return []

    if (
        seconds_left
        <= LATE_SAME_SIDE_STOP_BEFORE_END_SEC
    ):
        return []

    side = portfolio.unpaired_side

    book = _book_for_side(
        side,
        up,
        down,
    )

    if not _valid_book(book):
        return []

    price = float(book.ask)

    last_price = _last_buy_price(
        portfolio,
        side,
    )

    if last_price is None:
        return []

    price_drop = (
        last_price - price
    )

    required_drop = max(
        LATE_SAME_SIDE_PRICE_DROP,
        0.08,
    )

    if price_drop < required_drop:
        return []

    quantity = _minimum_quantity(
        coin=portfolio.coin,
        book=book,
    )

    if quantity is None:
        return []

    candidate = _simulate(
        portfolio=portfolio,
        side=side,
        price=price,
        quantity=quantity,
    )

    # Аварийный лимит нельзя использовать
    # для увеличения исходной стороны.
    if (
        candidate.total_spent
        > MAX_MARKET_CAPITAL_USDC
    ):
        return []

    worst_deterioration = (
        portfolio.worst_pnl
        - candidate.worst_pnl
    )

    if (
        worst_deterioration
        > LATE_SAME_SIDE_MAX_WORST_DETERIORATION
    ):
        return []

    if (
        candidate.worst_pnl
        < -MAX_TOTAL_WORST_PNL_LOSS
    ):
        return []

    # Низкий score специально:
    # противоположная сторона всегда имеет приоритет.
    score = (
        price_drop * 1.50
        - worst_deterioration * 2.0
        - float(book.spread)
        - 10.0
    )

    return [
        _decision(
            action="LATE_SAME_SIDE",
            side=side,
            price=price,
            quantity=quantity,
            score=score,
            reason=(
                f"LATE_SAME_SIDE; "
                f"seconds_left={seconds_left:.1f}; "
                f"last_price={last_price:.4f}; "
                f"ask={price:.4f}; "
                f"price_drop={price_drop:.4f}; "
                f"qty={quantity:.2f}; "
                f"notional=${price * quantity:.2f}; "
                f"worst={portfolio.worst_pnl:+.3f}"
                f"->{candidate.worst_pnl:+.3f}; "
                f"deterioration={worst_deterioration:.3f}"
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

    update_observed_prices(
        portfolio=portfolio,
        up=up,
        down=down,
    )

    market_second = (
        now - market.start_timestamp
    )

    seconds_left = (
        market.end_timestamp - now
    )

    if (
        market_second
        < START_DELAY_SEC
    ):
        return None

    if (
        seconds_left
        <= STOP_BEFORE_END_SEC
    ):
        return None

    # За 90 секунд пересчитываем позицию чаще.
    minimum_trade_delay = (
        3.0
        if seconds_left
        <= DEFENSIVE_PAIR_WINDOW_SEC
        else MIN_SECONDS_BETWEEN_TRADES
    )

    if (
        portfolio.last_trade_timestamp > 0
        and now - portfolio.last_trade_timestamp
        < minimum_trade_delay
    ):
        return None

    candidates: list[Decision] = []

    # Когда есть непарная позиция,
    # противоположная сторона проверяется первой.
    if portfolio.unpaired_qty > EPSILON:
        pair_candidates = _pair_decisions(
            now=now,
            market=market,
            portfolio=portfolio,
            up=up,
            down=down,
        )

        if pair_candidates:
            return max(
                pair_candidates,
                key=lambda item: item.score,
            )

        # Между 90 и 30 секундами допускается строгий
        # добор исходной стороны, если цена сильно снизилась.
        same_side_candidates = _late_same_side_decisions(
            now=now,
            market=market,
            portfolio=portfolio,
            up=up,
            down=down,
        )

        return max(
            same_side_candidates,
            key=lambda item: item.score,
            default=None,
        )

    # Эти ограничения относятся только к новым входам.
    # Закрытие пары проверяется выше и может использовать $45.
    if (
        portfolio.total_spent
        >= MAX_MARKET_CAPITAL_USDC
    ):
        return None

    if (
        portfolio.trade_count
        >= MAX_TOTAL_TRADES
    ):
        return None

    if portfolio.trade_count == 0:
        candidates.extend(
            _anchor_decisions(
                portfolio=portfolio,
                up=up,
                down=down,
            )
        )
    else:
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

    cost = (
        decision.price
        * decision.quantity
    )

    if decision.side == "UP":
        portfolio.up_qty += (
            decision.quantity
        )

        portfolio.up_spent += cost
        portfolio.up_buy_count += 1

        portfolio.last_up_buy_price = (
            decision.price
        )

    else:
        portfolio.down_qty += (
            decision.quantity
        )

        portfolio.down_spent += cost
        portfolio.down_buy_count += 1

        portfolio.last_down_buy_price = (
            decision.price
        )

    portfolio.last_trade_timestamp = now
    portfolio.trade_count += 1

    if decision.action in {
        "ANCHOR_ENTRY",
        "NEW_CYCLE",
    }:
        portfolio.anchor_side = (
            decision.side
        )

        portfolio.anchor_timestamp = now

        portfolio.anchor_price = (
            decision.price
        )

    if decision.action in {
        "PAIR_LOCK",
        "DEFENSIVE_PAIR",
        "EMERGENCY_PAIR",
    }:
        portfolio.cycle_count += 1

        portfolio.anchor_side = None
        portfolio.anchor_timestamp = 0.0
        portfolio.anchor_price = None
