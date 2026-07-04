import type { NextConfig } from "next";

// The dashboard talks to the Arbiter proxy. We proxy /v1/* through the Next
// server so the browser makes same-origin calls (no CORS) in dev and prod.
const backend = process.env.ARBITER_BACKEND ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  async rewrites() {
    return [{ source: "/v1/:path*", destination: `${backend}/v1/:path*` }];
  },
};

export default nextConfig;
