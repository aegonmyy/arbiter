import type { NextConfig } from "next";
import { createMDX } from "fumadocs-mdx/next";

// Two modes:
//  - dev / standalone: proxy /v1 to a separate backend (ARBITER_BACKEND).
//  - export (NEXT_OUTPUT=export): emit a static site that FastAPI serves on the
//    same origin, so /v1 calls are same-origin and no proxy/CORS is needed.
const isExport = process.env.NEXT_OUTPUT === "export";
const backend = process.env.ARBITER_BACKEND ?? "http://localhost:8000";

const nextConfig: NextConfig = isExport
  ? { output: "export", trailingSlash: true, images: { unoptimized: true } }
  : {
      async rewrites() {
        return [{ source: "/v1/:path*", destination: `${backend}/v1/:path*` }];
      },
    };

export default createMDX()(nextConfig);
