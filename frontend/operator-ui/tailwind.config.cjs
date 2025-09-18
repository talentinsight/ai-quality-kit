/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50:  "#eef2ff",
          100: "#e0e7ff",
          500: "#3b5bff",
          600: "#2b59ff",
          700: "#2249d8"
        }
      },
      boxShadow: {
        card: "0 1px 2px rgba(0,0,0,.04), 0 12px 24px -12px rgba(0,0,0,.10)"
      },
      borderRadius: {
        xl: "14px",
        "2xl": "20px"
      }
    }
  },
  darkMode: "class",
  plugins: [],
};
