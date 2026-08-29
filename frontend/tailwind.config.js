/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#0b1020",
        panel: "#141a2e",
        edge: "#232c48",
        muted: "#8b96b4",
        accent: "#5b8cff",
        pass: "#31c48d",
        warn: "#f5a524",
        fail: "#f26d6d",
      },
      fontFamily: {
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
    },
  },
  plugins: [],
};
