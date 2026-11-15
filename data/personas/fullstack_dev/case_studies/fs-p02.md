<!-- project_id: fs-p02 | synthetic -->
# B2B Ordering Portal for a Textile Exporter

## Context
Sara Malik was approached by a mid‑size textile exporter looking to modernize its order intake process. The company relied heavily on email and phone calls for B2B orders, which led to frequent miscommunications, duplicated entries, and a high error rate. With a growing client base across multiple regions, the exporter needed a scalable, user‑friendly solution that could centralize order management, reduce manual work, and provide real‑time visibility into order status. The goal was to shift the majority of orders from email to a dedicated portal while maintaining a seamless experience for existing business customers.

## What I built
Sara designed and delivered a full‑stack web application using **React** for the front end and **Node.js** with **ExpressJS** for the back end, persisting data in **MongoDB**. The portal features:
- A responsive React UI with intuitive order forms, product catalogs, and order history screens.
- Role‑based authentication ensuring that only approved B2B clients can place orders.
- A RESTful API built with ExpressJS that handles order creation, validation, and status updates.
- Real‑time validation and auto‑complete fields to minimize entry errors.
- Integration with the existing ERP system via secure API endpoints for automatic synchronization of order data.
- Administrative dashboards for the exporter’s staff to monitor incoming orders, track fulfillment, and generate reports.

The development process included iterative feedback sessions with the client’s sales team, ensuring the portal matched real‑world workflows. Sara also implemented comprehensive unit and integration tests to guarantee reliability under load.

## Results
Within three months of launch, the textile exporter successfully moved **60% of its orders off email** to the new portal. This shift streamlined the order workflow, cutting the average processing time by half. More importantly, **order errors decreased by 50%**, thanks to built‑in validation and a single source of truth for product data. The client reported higher customer satisfaction and projected further cost savings as adoption continues to grow.
