/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Set NEXT_OUTPUT=export to produce a fully static site (frontend/out) that
  // FastAPI can serve same-origin in the deployment container. Dev/`next start`
  // leave this unset and run normally.
  output: process.env.NEXT_OUTPUT === "export" ? "export" : undefined,
  images: { unoptimized: true },
  // Trailing slash only matters for the static export (deep links →
  // <route>/index.html). Keep it off for the normal server build.
  trailingSlash: process.env.NEXT_OUTPUT === "export",
};

export default nextConfig;
