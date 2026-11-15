## physiohub

**Overview**
A full‑stack booking platform built with Next.js and TypeScript that enables patients to schedule physiotherapy sessions across a network of clinics. The system stores appointment data in PostgreSQL, uses Redis for caching and rate‑limiting, and integrates Stripe for secure payment processing. User authentication is handled via JWT‑based sessions with email/password and optional OAuth providers.

**Architecture**
- **Frontend**: Next.js (React) with server‑side rendering for SEO‑friendly clinic pages. TypeScript enforces type safety across components and API routes.
- **API Layer**: Next.js API routes act as the BFF (Backend‑For‑Frontend). Core services include `appointments`, `payments`, `notifications`, and `auth`. Business logic lives in separate service modules under `/src/services`.
- **Database**: PostgreSQL stores users, clinics, therapists, appointment slots, and transaction records. Prisma ORM is used for type‑safe queries and migrations.
- **Cache & Queue**: Redis provides a fast cache for available slot look‑ups and a simple FIFO queue for background email/SMS reminder jobs (handled by BullMQ).
- **Payments**: Stripe Checkout sessions are created server‑side; webhook endpoints verify events and update appointment status.
- **Authentication**: Passwords are hashed with Argon2. JWT access tokens (short‑lived) and refresh tokens (httpOnly cookies) protect routes.

**Running Locally**
1. Clone the repo and `cd physiohub`.
2. `cp .env.example .env` and fill in PostgreSQL, Redis, Stripe, and JWT secrets.
3. Install dependencies: `npm ci`.
4. Start required services via Docker Compose: `docker compose up -d postgres redis`.
5. Run database migrations: `npx prisma migrate dev`.
6. Launch the dev server: `npm run dev`. The app will be available at `http://localhost:3000`.

**Testing**
- Unit tests: `npm test` (Jest + React Testing Library).
- End‑to‑end: `npm run test:e2e` (Playwright).

**Deployment**
The app is containerized; a multi‑stage Dockerfile builds the Next.js app and serves it with `node server.js`. CI pipelines push images to a container registry and deploy to a Kubernetes cluster with Helm charts that expose PostgreSQL, Redis, and the web service.
