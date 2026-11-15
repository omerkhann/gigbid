import type { NextConfig } from "next";

// The browser talks only to this origin; /api/* is proxied to FastAPI, so the session cookie is
// first-party. Live progress (Server-Sent Events) goes straight to the API (NEXT_PUBLIC_EVENTS_URL),
// because a dev proxy may buffer streams.
const API_URL = process.env.API_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_URL}/:path*` }];
  },
};

export default nextConfig;
