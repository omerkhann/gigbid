import requests
from bs4 import BeautifulSoup
import pandas as pd
import time

BASE_URL = "https://example-ecommerce.com/products"
HEADERS = {
    "User-Agent": "PriceMonitor/1.0 (+https://yourdomain.com)"
}

def fetch_product_page(product_id):
    url = f"{BASE_URL}/{product_id}"
    response = requests.get(url, headers=HEADERS, timeout=10)
    response.raise_for_status()
    return response.text

def parse_price(html):
    soup = BeautifulSoup(html, "html.parser")
    price_tag = soup.select_one("span.current-price")
    if not price_tag:
        raise ValueError("Price element not found")
    price_text = price_tag.get_text(strip=True).replace("$,", "")
    return float(price_text)

def scrape_product(product_id):
    html = fetch_product_page(product_id)
    price = parse_price(html)
    timestamp = pd.Timestamp.utcnow()
    return {"product_id": product_id, "price": price, "timestamp": timestamp}

if __name__ == "__main__":
    product_ids = ["12345", "67890", "abcde"]
    records = []
    for pid in product_ids:
        try:
            record = scrape_product(pid)
            records.append(record)
            time.sleep(1)  # polite delay
        except Exception as e:
            print(f"Error scraping {pid}: {e}")
    df = pd.DataFrame(records)
    print(df)
