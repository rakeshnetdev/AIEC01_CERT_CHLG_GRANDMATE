/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          dark: "#0a0f1d",
          card: "#121a2e",
          border: "#1e2942",
          accent: "#38bdf8",
          accentHover: "#0ea5e9",
          text: "#f8fafc",
          muted: "#94a3b8",
        }
      }
    },
  },
  plugins: [],
}
