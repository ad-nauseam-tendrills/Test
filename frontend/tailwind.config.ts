import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        canvas: "#faf9f7",
        ink: "#1c1b19",
        stone: {
          50: "#faf9f7",
          100: "#f2f0ec",
          200: "#e4e1da",
          300: "#cdc8bd",
          400: "#a8a196",
          500: "#847c6f",
          600: "#655e54",
          700: "#4c463f",
          800: "#332f2a",
          900: "#1c1b19",
        },
        accent: "#a8442f",
      },
      fontFamily: {
        display: ["Georgia", "Cambria", "Times New Roman", "serif"],
        sans: ["-apple-system", "BlinkMacSystemFont", "Segoe UI", "Helvetica", "Arial", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;
