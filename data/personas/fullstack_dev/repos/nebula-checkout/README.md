# nebula-checkout

A headless storefront built with **Next.js** that leverages the Shopify Storefront API for product data and a custom checkout flow. The repo demonstrates a decoupled architecture where the front‑end is completely separate from Shopify's backend, enabling fine‑grained control over UI, performance, and conversion optimization.

## Architecture
- **Next.js (v14)** – Serves as the React SSR/SSG framework. Pages are statically generated for product listings and dynamically rendered for cart/checkout.
- **Shopify Storefront API** – All product, collection, and inventory queries are performed via GraphQL. Authentication uses a public Storefront access token.
- **Custom Checkout Service** – A thin Node.js serverless function (`/api/checkout`) aggregates cart items, creates a draft order via the Shopify Admin API, and returns a secure checkout URL. This isolates sensitive admin operations from the client.
- **Tailwind CSS** – Utility‑first styling with JIT mode for minimal CSS payload.
- **Shopify Apps Integration** – Webhooks for order fulfillment and discount apps are configured but not part of the core repo.

## Getting Started
1. **Clone** the repo and install dependencies:
   ```bash
   git clone https://github.com/yourusername/nebula-checkout.git
   cd nebula-checkout
   npm ci
   ```
2. **Configure environment variables** in a `.env.local` file:
   ```
   NEXT_PUBLIC_SHOPIFY_STORE_DOMAIN=your-store.myshopify.com
   NEXT_PUBLIC_STOREFRONT_ACCESS_TOKEN=public-token
   SHOPIFY_ADMIN_API_KEY=admin-key
   SHOPIFY_ADMIN_PASSWORD=admin-password
   ```
3. **Run locally**:
   ```bash
   npm run dev
   ```
   The app will be available at `http://localhost:3000`.
4. **Build for production**:
   ```bash
   npm run build && npm start
   ```
   Deploy to Vercel, Netlify, or any Node.js host.

## Performance
The site uses Incremental Static Regeneration (ISR) for product pages, delivering a Lighthouse performance score of 94 in mobile tests. Tailwind JIT and image optimization keep the bundle under 150 KB.

## Contributing
Open issues for bugs or feature requests. Pull requests should include unit tests for any new API routes and adhere to the existing ESLint configuration.
