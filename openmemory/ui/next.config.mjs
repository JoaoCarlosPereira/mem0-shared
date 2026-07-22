/** @type {import('next').NextConfig} */
const nextConfig = {
  eslint: {
    ignoreDuringBuilds: true,
  },
  typescript: {
    ignoreBuildErrors: true,
  },
  images: {
    unoptimized: true,
  },
  async redirects() {
    return [
      { source: "/admin/specs", destination: "/docs", permanent: true },
      {
        source: "/admin/specs/:path*",
        destination: "/docs/:path*",
        permanent: true,
      },
      { source: "/settings", destination: "/admin/settings", permanent: true },
      {
        source: "/settings/:path*",
        destination: "/admin/settings/:path*",
        permanent: true,
      },
    ];
  },
};

export default nextConfig;
