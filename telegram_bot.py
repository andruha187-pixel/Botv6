import logging
import threading

import requests

from config import (
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    TELEGRAM_POLLING_ENABLED,
)
from database import statistics

logger = logging.getLogger("TELEGRAM")
_STOP = threading.Event()


def configured() -> bool:
    return bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)


def send_message(text: str) -> bool:
    if not configured():
        return False

    try:
        response = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": str(text)[:4096],
                "disable_web_page_preview": True,
            },
            timeout=30,
        )

        if not response.ok:
            logger.warning(
                "Telegram send failed: %s | %s",
                response.status_code,
                response.text,
            )
            return False

        return True

    except Exception as exc:
        logger.warning("Telegram send failed: %s", exc)
        return False


def status_text() -> str:
    stats = statistics()

    return (
        "🧪 PAPER REBALANCER V6 STATUS\n\n"
        f"Рынков найдено: {stats['markets']}\n"
        f"Снимков: {stats['snapshots']}\n"
        f"Виртуальных сделок: {stats['trades']}\n"
        f"Завершённых симуляций: {stats['completed']}\n"
        f"Реализованный paper PnL: ${stats['realized_pnl']:.2f}\n"
        f"Гарантированных позиций: {stats['guaranteed']}"
    )


def handle_command(text: str) -> None:
    command = text.strip().split()[0].split("@")[0].lower()

    if command in {"/start", "/help"}:
        send_message(
            "Команды:\n"
            "/status — статистика\n"
            "/ping — проверка\n\n"
            "Paper Rebalancer v6 работает только в PAPER MODE."
        )

    elif command == "/ping":
        send_message("🏓 Pong. Paper Rebalancer v6 работает.")

    elif command == "/status":
        send_message(status_text())


def polling_loop() -> None:
    if not configured() or not TELEGRAM_POLLING_ENABLED:
        return

    offset = 0

    while not _STOP.is_set():
        try:
            response = requests.get(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates",
                params={"offset": offset, "timeout": 25},
                timeout=35,
            )

            response.raise_for_status()

            for update in response.json().get("result", []):
                offset = max(
                    offset,
                    int(update.get("update_id", 0)) + 1,
                )

                message = update.get("message") or {}
                chat_id = str(
                    (message.get("chat") or {}).get("id") or ""
                )
                text = str(message.get("text") or "")

                if (
                    chat_id == str(TELEGRAM_CHAT_ID)
                    and text.startswith("/")
                ):
                    threading.Thread(
                        target=handle_command,
                        args=(text,),
                        daemon=True,
                    ).start()

        except Exception as exc:
            logger.warning("Telegram polling failed: %s", exc)
            _STOP.wait(5)


def start_polling() -> threading.Thread | None:
    if not configured() or not TELEGRAM_POLLING_ENABLED:
        return None

    _STOP.clear()

    thread = threading.Thread(
        target=polling_loop,
        daemon=True,
    )
    thread.start()

    return thread


def stop() -> None:
    _STOP.set()
