import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* 도커 배포를 위한 독립 실행형(standalone) 빌드 설정 */
  output: "standalone",
};

export default nextConfig;

