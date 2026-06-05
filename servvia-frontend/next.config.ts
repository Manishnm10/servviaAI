import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // We removed the static rewrites() in favor of the dynamic API route proxy
  // located at src/app/api/proxy/[...path]/route.ts for reliable Turbopack streaming
};

export default nextConfig;
