<!-- project_id: fs-p16 | synthetic -->
# Stripe Subscription and Invoicing Integration

## Context
Sara Malik was engaged by a SaaS company in 2024 to overhaul its payment workflow. The existing system suffered from high churn due to failed subscription payments and lacked automated recovery mechanisms. The client needed a robust, scalable solution that could handle recurring billing, generate invoices, and intelligently engage customers when payments failed. The project required deep integration with Stripe, a modern TypeScript‑based Node.js backend, and a clear API contract to support future front‑end extensions.

## What I built
- **Stripe API Integration**: Implemented Stripe’s subscription, invoice, and webhook endpoints using the official Stripe Node.js SDK. Configured webhook listeners for `invoice.payment_failed`, `invoice.payment_succeeded`, and `customer.subscription.updated` events.
- **Dunning Workflow**: Designed a TypeScript‑driven state machine that tracks payment status and triggers a series of automated dunning emails. Each email includes a secure payment link generated via Stripe’s `payment_intent` API, allowing customers to resolve failures with a single click.
- **Node.js Service Layer**: Built a modular Node.js service (TypeScript) that abstracts Stripe calls, handles retries, and logs all interactions to a centralized audit store. The service exposes a clean REST API for the front‑end to query subscription status and invoice history.
- **Error Handling & Idempotency**: Leveraged Stripe’s idempotency keys to guarantee exactly‑once processing of webhook events, preventing duplicate email sends or invoice creation.
- **Testing & Monitoring**: Added unit and integration tests using Jest, and set up monitoring dashboards in Stripe Dashboard and a custom Grafana panel to track payment‑failure rates and email delivery metrics.

## Results
The new integration dramatically improved the client’s revenue recovery process. Failed‑payment recovery increased by **31%**, driven by timely, personalized dunning emails and a frictionless re‑payment flow. The system also reduced manual support tickets related to billing issues by half, freeing the support team to focus on higher‑value tasks. The modular architecture positioned the SaaS product for future expansion, such as adding new payment methods or integrating additional analytics tools.
