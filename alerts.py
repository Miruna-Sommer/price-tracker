"""Alerte: preț sub pragul ales sau scădere față de verificarea anterioară."""

from datetime import datetime

ALERT_LOG = "alerts.log"


def check_alerts(name, new_price, old_price, target_price, currency="RON"):
    """Întoarce lista de mesaje de alertă pentru o verificare (poate fi goală)."""
    messages = []
    if target_price is not None and new_price <= target_price:
        messages.append(
            f"PRAG ATINS: {name} costă {new_price:.2f} {currency} "
            f"(prag: {target_price:.2f} {currency})"
        )
    if old_price is not None and new_price < old_price:
        diff = old_price - new_price
        percent = diff / old_price * 100
        messages.append(
            f"SCĂDERE: {name} a scăzut cu {diff:.2f} {currency} "
            f"(-{percent:.1f}%): {old_price:.2f} -> {new_price:.2f}"
        )
    return messages


def notify(messages, log_path=ALERT_LOG):
    """Afișează alertele în consolă și le adaugă în fișierul de log."""
    if not messages:
        return
    stamp = datetime.now().isoformat(timespec="seconds")
    with open(log_path, "a", encoding="utf-8") as f:
        for msg in messages:
            print(f"  🔔 {msg}")
            f.write(f"[{stamp}] {msg}\n")
