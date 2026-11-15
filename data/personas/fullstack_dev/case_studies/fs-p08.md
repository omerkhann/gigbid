<!-- project_id: fs-p08 | synthetic -->
# Real-time Delivery Tracking Map

## Context
In 2023, a fast‑growing food‑delivery service was struggling with a high volume of customer inquiries asking "where is my order?". These calls not only increased operational costs but also eroded customer satisfaction. The client needed a solution that would give end‑users instant visibility into the status and location of their deliveries, while also reducing the load on the support team. As a full‑stack developer with expertise in React, Next.js, and Node.js, I was engaged to design and implement a real‑time tracking map that could be embedded directly into the client’s web app.

## What I built
I architected a single‑page application using **React** and **Next.js** for a smooth, responsive UI. The core feature is an interactive map that displays the live position of delivery drivers. To power this, I created a **Node.js** backend that aggregates location data from the drivers' GPS devices via a secure **API Integration**. The backend stores each update in **MongoDB**, enabling quick retrieval and historical analysis. WebSocket connections push new coordinates to the front end in real time, ensuring the map reflects the driver’s current location without page reloads. I also added status badges (e.g., "Picked Up", "On the Way", "Delivered") and an estimated arrival time calculated on the server side. The UI was styled with a clean, mobile‑first approach, allowing customers to track orders from any device.

## Results
After deployment, the tracking map became the primary source of order visibility for customers. The number of inbound "where is my order" calls dropped by **45%**, significantly lowering support costs and freeing agents to handle more complex issues. Customer satisfaction scores improved, and the client reported a measurable increase in repeat orders, attributing the boost to the enhanced transparency of the delivery process. The solution continues to scale with the client’s expanding fleet, thanks to the flexible Node.js and MongoDB architecture.
