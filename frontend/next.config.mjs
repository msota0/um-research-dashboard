// API base for the dev proxy. Use 127.0.0.1 (not "localhost") so we hit the
// IPv4 backend — on macOS the AirPlay Receiver squats on localhost:5000 over
// IPv6. Override with API_PROXY_TARGET when the backend runs elsewhere.
const API_PROXY_TARGET = process.env.API_PROXY_TARGET ?? 'http://127.0.0.1:5000';

const nextConfig = {
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${API_PROXY_TARGET}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
