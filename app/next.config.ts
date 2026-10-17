import type { NextConfig } from "next";

/**
 * Where the browser's /api/* requests are proxied to. Read at build time (rewrites are baked into the build),
 * so the Docker image takes it as a build argument.
 */
const API_INTERNAL_URL = (
  process.env.API_INTERNAL_URL || "http://localhost:8080"
).replace(/\/+$/, "");

const nextConfig: NextConfig = {
  /* config options here */
  output: "standalone",
  experimental: {
    agentFeedback: true,
    // OCR and local speech-to-text can take minutes; the default proxy timeout is 30 s.
    proxyTimeout: 240_000,
  },
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
  // The API is served from the same origin as the app, so the session cookie is first-party and no CORS is involved.
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${API_INTERNAL_URL}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
