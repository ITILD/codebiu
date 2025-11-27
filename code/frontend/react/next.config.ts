import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // 使用 Turbopack 而不是 Webpack
  turbopack: {
    // UnoCSS 配置将在其他地方处理
  },
};

export default nextConfig;
