# pricewatcher

A Python‑based price‑monitoring scraper that continuously crawls product pages, stores snapshot data, and emits anomaly alerts when price deviations exceed configurable thresholds.

## Architecture
- **Crawler**: Uses `requests` + `BeautifulSoup` to fetch HTML and extract SKU, price, and timestamp. Concurrency is achieved with `concurrent.futures.ThreadPoolExecutor` to parallelise up to 50 simultaneous requests while respecting `robots.txt` and rate‑limit settings.
- **Data Store**: Persists raw snapshots in a SQLite database (`prices.db`). A normalized schema (`skus`, `price_history`) enables fast range queries and historical trend analysis.
- **Anomaly Engine**: Runs after each crawl batch. For each SKU it computes a rolling median and standard deviation over the last 24 h. If the current price deviates > 3σ or exceeds a user‑defined absolute delta, an alert record is inserted into the `alerts` table.
- **Notifier**: A lightweight module that reads pending alerts and sends JSON payloads to a configurable webhook (e.g., Slack, Teams, or internal monitoring system).
- **Scheduler**: A simple `cron`‑compatible entry point (`pricewatcher/run.py`) that can be invoked every 5 minutes to maintain the 12 k SKU daily cadence.

## Setup & Execution
```bash
# Clone and install dependencies
git clone https://github.com/yourname/pricewatcher.git
cd pricewatcher
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Initialise the database
python -c "from pricewatcher.db import init_db; init_db()"

# Run the scraper (adjust --workers and --batch-size as needed)
python run.py --config config.yaml --workers 30 --batch-size 5000
```

## Configuration
All runtime parameters live in `config.yaml`: target URL patterns, request headers, rate limits, anomaly thresholds, and webhook URLs. The file is loaded at start‑up and validated with `pydantic`.

## Extensibility
- Swap SQLite for PostgreSQL by changing the `engine` URI in `db.py`.
- Replace the thread pool with `asyncio` + `aiohttp` for higher concurrency.
- Add custom alert handlers (email, SMS) by implementing the `Notifier` interface.

---
*pricewatcher* provides a reproducible, testable pipeline for large‑scale price surveillance and rapid error detection.
