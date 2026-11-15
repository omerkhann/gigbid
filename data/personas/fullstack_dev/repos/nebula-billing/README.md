# nebula-billing

A multi‑tenant SaaS starter kit that bundles Next.js front‑end, a Stripe‑driven billing layer, and a PostgreSQL data store with per‑tenant isolation. The stack runs on AWS and uses Redis for session caching and rate‑limiting.

## Architecture
- **Next.js** (App Router) serves the UI and API routes. Server‑side rendering is used for tenant‑specific dashboards.
- **PostgreSQL** (Amazon RDS) stores core entities: `tenants`, `users`, `subscriptions`, and `invoices`. Row‑level security (RLS) enforces tenant isolation.
- **Stripe** is integrated via webhook listeners that update subscription status and emit events to a job queue.
- **Redis** (Elasticache) caches JWT validation results and holds a distributed lock for idempotent webhook processing.
- **AWS**: The application is containerised with Docker and deployed to ECS/Fargate behind an Application Load Balancer. Secrets are managed with Parameter Store.
- **Authentication** uses NextAuth.js with email/password and social providers; JWTs are signed with a rotating secret.

## Getting Started
```bash
# Clone and enter repo
git clone https://github.com/youruser/nebula-billing.git && cd nebula-billing

# Set environment variables (see .env.example)
cp .env.example .env
# Edit .env with your AWS, Stripe, and DB credentials

# Build and run locally with Docker Compose
docker compose up --build
```
The API will be reachable at `http://localhost:3000/api` and the UI at `http://localhost:3000`.

## Deployment
1. Push the Docker image to Amazon ECR.
2. Update the ECS task definition to use the new image tag.
3. Run `terraform apply` (in the `infra/` directory) to provision the RDS instance, Elasticache cluster, and ALB.
4. Configure Stripe webhook endpoint to point to `https://<your‑domain>/api/webhooks/stripe`.

## Extending
- Add new tenant‑scoped services by creating separate schemas in PostgreSQL and referencing the `tenant_id` from the request context.
- Swap Redis for DynamoDB Streams if you need durable event sourcing.
- Plug in additional payment providers by implementing the `PaymentProvider` interface.

---
This repo provides a production‑grade foundation for SaaS teams that need rapid onboarding of multiple products with unified billing and authentication.
