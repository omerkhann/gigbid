<!-- project_id: fs-p14 | synthetic -->
# Restaurant Ordering Web App with Kitchen Display

## Context
Sara Malik was engaged by a hospitality client to modernize their ordering workflow across four restaurant locations. The existing system relied on manual paper tickets, causing delays and errors in the kitchen. The client needed a fast, reliable web application that could handle simultaneous orders from diners, synchronize them with the kitchen display, and scale as the business grew. The project was slated for 2025 and required a full‑stack solution that could integrate a responsive front‑end, a robust back‑end, and a reliable data store while ensuring quick order propagation to the kitchen.

## What I built
Sara designed and delivered a single‑page web application using a modern JavaScript framework for the user interface, providing diners with an intuitive menu, cart, and checkout experience. The back‑end was built with a versatile server‑side technology that supports both RESTful APIs and real‑time communication, handling order creation, payment processing, and status updates. Data was stored in a relational database, ensuring transactional integrity for orders, menu items, and user accounts.

To guarantee that newly placed orders appeared on kitchen screens instantly, Sara implemented a lightweight in‑memory data store that temporarily holds order messages and pushes them to the kitchen display service. This approach eliminated the latency typically introduced by disk‑based storage and allowed the kitchen to receive updates within seconds.

The entire stack was containerized, enabling consistent deployment across development, staging, and production environments. Docker images were orchestrated to run on the client’s infrastructure, simplifying scaling when traffic spikes during peak dining hours.

## Results
The new system reduced order‑to‑kitchen time to under two seconds, a dramatic improvement over the previous paper‑based process. All four restaurant branches went live simultaneously, and staff reported fewer order errors and faster service. The client highlighted the seamless real‑time updates and the ease of adding new menu items without downtime. Sara’s solution not only met the immediate performance goals but also provided a scalable foundation for future enhancements such as loyalty programs and analytics dashboards.
