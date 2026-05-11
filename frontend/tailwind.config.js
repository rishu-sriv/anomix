/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // FinPulse brand palette — dark terminal feel
        surface: {
          DEFAULT: "#0f1117",
          card: "#161b22",
          elevated: "#1c2230",
          border: "#2d3748",
        },
        accent: {
          DEFAULT: "#3b82f6",    // blue-500
          muted: "#1e3a5f",
        },
        severity: {
          high: "#ef4444",       // red-500
          "high-bg": "#450a0a",
          medium: "#f59e0b",     // amber-500
          "medium-bg": "#451a03",
          low: "#22c55e",        // green-500
          "low-bg": "#052e16",
        },
      },
      fontFamily: {
        mono: ["'JetBrains Mono'", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      animation: {
        "pulse-slow": "pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite",
      },
    },
  },
  plugins: [],
}
