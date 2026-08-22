/** @type {import('next').NextConfig} */
const nextConfig = {
  // Django's URLs end in a slash. Without this, Next strips it before proxying and
  // Django answers every API call with a 301 back to the slashed form.
  trailingSlash: true,

  // Proxy API calls to Django so the browser only ever talks to one origin.
  // Avoids CORS entirely in development and keeps API URLs relative in the client.
  async rewrites() {
    const backend = process.env.BACKEND_URL || "http://localhost:8000";
    return [
      // The slashed rule comes first: `:path*` reassembles without the trailing
      // slash, and Django answers slashless API URLs with a 301.
      { source: "/api/:path*/", destination: `${backend}/api/:path*/` },
      { source: "/api/:path*", destination: `${backend}/api/:path*` },
      { source: "/media/:path*", destination: `${backend}/media/:path*` },
    ];
  },
};

module.exports = nextConfig;
