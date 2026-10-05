import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async redirects() {
    // The chat assistant was renamed from Copilot to Lotse.
    return [{ source: "/copilot", destination: "/lotse", permanent: true }];
  },
};

export default nextConfig;
