from dataclasses import dataclass

@dataclass(slots=True)
class BookSide:
    bid: float | None = None
    ask: float | None = None
    bid_size: float | None = None
    ask_size: float | None = None
    spread: float | None = None
    min_order_size: float = 1.0
    tick_size: float = 0.01

@dataclass(slots=True)
class Market:
    condition_id: str
    coin: str
    title: str
    slug: str | None
    start_timestamp: int
    end_timestamp: int
    up_token_id: str
    down_token_id: str

@dataclass(slots=True)
class Portfolio:
    condition_id: str
    coin: str
    up_qty: float = 0.0
    down_qty: float = 0.0
    up_spent: float = 0.0
    down_spent: float = 0.0
    last_trade_timestamp: float = 0.0
    trade_count: int = 0
    cycle_count: int = 0
    up_buy_count: int = 0
    down_buy_count: int = 0
    anchor_side: str | None = None
    anchor_timestamp: float = 0.0
    anchor_price: float | None = None
    best_up_ask_seen: float | None = None
    best_down_ask_seen: float | None = None
    last_up_buy_price: float | None = None
    last_down_buy_price: float | None = None
    finalized: bool = False

    @property
    def total_spent(self) -> float:
        return self.up_spent + self.down_spent

    @property
    def pnl_if_up(self) -> float:
        return self.up_qty - self.total_spent

    @property
    def pnl_if_down(self) -> float:
        return self.down_qty - self.total_spent

    @property
    def worst_pnl(self) -> float:
        return min(self.pnl_if_up, self.pnl_if_down)

    @property
    def paired_qty(self) -> float:
        return min(self.up_qty, self.down_qty)

    @property
    def unpaired_qty(self) -> float:
        return abs(self.up_qty - self.down_qty)

    @property
    def unpaired_side(self) -> str | None:
        if self.up_qty > self.down_qty:
            return "UP"
        if self.down_qty > self.up_qty:
            return "DOWN"
        return None

    @property
    def guaranteed(self) -> bool:
        return self.up_qty > 0 and self.down_qty > 0 and self.worst_pnl > 0
