"""Graficul evoluției prețului (matplotlib)."""

from datetime import datetime

import matplotlib

matplotlib.use("Agg")  # fără fereastră grafică; salvăm direct în fișier
import matplotlib.dates as mdates
import matplotlib.pyplot as plt


def plot_history(name, rows, target_price=None, out_path="grafic.png"):
    """rows: rândurile din db.history(). Salvează graficul ca PNG."""
    dates = [datetime.fromisoformat(r["checked_at"]) for r in rows]
    prices = [r["price"] for r in rows]
    currency = rows[0]["currency"]

    fig, ax = plt.subplots(figsize=(9, 4.5))
    # "steps-post": prețul rămâne constant până la următoarea verificare
    ax.plot(dates, prices, drawstyle="steps-post", marker="o", markersize=4,
            linewidth=2, color="#2563eb", label="Preț")

    low = min(prices)
    ax.annotate(f"minim: {low:.2f}", (dates[prices.index(low)], low),
                textcoords="offset points", xytext=(-8, 8), ha="right",
                fontsize=9, color="#15803d")

    if target_price is not None:
        ax.axhline(target_price, color="#dc2626", linestyle="--", linewidth=1.2,
                   label=f"Prag alertă ({target_price:.2f})")

    ax.set_title(name if len(name) <= 70 else name[:67] + "...", fontsize=11)
    ax.set_ylabel(f"Preț ({currency})")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m.%Y"))
    ax.grid(True, alpha=0.3)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path
