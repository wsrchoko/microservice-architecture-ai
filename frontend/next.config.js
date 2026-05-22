/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  images: {
    remotePatterns: [
      { protocol: 'https', hostname: '**' },
    ],
  },
  async rewrites() {
    return [
      { source: '/api/auth/:path*', destination: `${process.env.AUTH_SERVICE_URL || 'http://localhost:8001'}/api/v1/auth/:path*` },
      { source: '/api/users/:path*', destination: `${process.env.USER_SERVICE_URL || 'http://localhost:8002'}/api/v1/users/:path*` },
      { source: '/api/roles/:path*', destination: `${process.env.ROLE_SERVICE_URL || 'http://localhost:8003'}/api/v1/roles/:path*` },
      { source: '/api/audit/:path*', destination: `${process.env.AUDIT_SERVICE_URL || 'http://localhost:8004'}/api/v1/audit/:path*` },
      { source: '/api/ai/:path*', destination: `${process.env.AI_SERVICE_URL || 'http://localhost:8005'}/api/v1/ai/:path*` },
    ];
  },
};

module.exports = nextConfig;