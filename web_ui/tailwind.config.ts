import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        stone: {
          50: "#fcf9f3",
          100: "#f5efe4",
          200: "#e2d9c8",
          400: "#a6a09a",
          700: "#44403c",
        },
        sage: {
          50: "#f4f6f0",
          200: "#c9cfa8",
          500: "#6b7c4f",
          700: "#454f33",
        },
        moss: {
          DEFAULT: "#4d5c32",
          light: "#eef2e4",
        },
        amber: {
          warm: "#a67c38",
          soft: "#faf6e8",
        },
        ink: {
          primary: "#1c1917",
          secondary: "#57534e",
          muted: "#78716c",
        },
      },
      fontFamily: {
        sans: ["var(--font-inter)", "system-ui", "sans-serif"],
        mono: ["var(--font-jetbrains)", "ui-monospace", "monospace"],
      },
      borderRadius: {
        lg: "16px",
        md: "12px",
        sm: "8px",
      },
      maxWidth: {
        shell: "1180px",
      },
      backgroundImage: {
        "page-gradient":
          "linear-gradient(180deg, #f4f6f0 0%, #fcf9f3 42%, #f5efe4 100%)",
        "landing-hero":
          "radial-gradient(ellipse 120% 80% at 50% -20%, rgba(107, 124, 79, 0.08), transparent), linear-gradient(180deg, #f4f6f0 0%, #fcf9f3 45%, #f5efe4 100%)",
      },
      boxShadow: {
        card: "0 4px 20px rgba(28, 25, 23, 0.05)",
      },
    },
  },
  plugins: [],
};

export default config;
