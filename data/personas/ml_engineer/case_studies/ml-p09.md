<!-- project_id: ml-p09 | synthetic -->
# Price‑monitoring scraper with anomaly alerts

## Context
Hamza Siddiqui was engaged by an e‑commerce client that needed to keep a close eye on the pricing of thousands of products listed across multiple competitor websites. The client managed a catalog of roughly 12,000 stock‑keeping units (SKUs) and wanted a system that could automatically collect current price information, compare it against internal expectations, and raise an alert the moment a discrepancy appeared. Manual monitoring was costly and slow, often resulting in missed opportunities or price‑matching errors that hurt margins. The goal was to build a reliable, fully automated solution that could run daily, handle large volumes of data, and surface price anomalies within a short time window.

## What I built
I created a lightweight, scheduled script that visits the target web pages, extracts the relevant pricing fields, and stores the results in a structured format for analysis. The script navigates the HTML structure of each page, identifies the element containing the price, and captures the numeric value. After gathering the data for all 12,000 SKUs, the script performs a quick statistical check: it compares each scraped price with the client’s reference price and flags any entry that deviates beyond a predefined tolerance. When an outlier is detected, an automated notification is sent to the pricing team via email, including the SKU identifier, the observed price, and the magnitude of the deviation. The entire workflow is orchestrated to run once per day, ensuring fresh data is always available for decision‑making.

## Results
The solution now tracks approximately 12,000 SKUs each day without human intervention. Price errors are identified and communicated to the team in under an hour from the time the data is collected, dramatically reducing the window for costly pricing mistakes. The client reports a measurable improvement in price compliance and has been able to reallocate manual monitoring resources to higher‑value strategic tasks. The system’s simplicity and reliability have made it a core component of the client’s competitive pricing strategy.
