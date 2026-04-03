import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  async redirects() {
    return [
      {
        source: "/feed",
        destination: "/dashboard",
        permanent: false,
      },
    ];
  },
};

export default nextConfig;
