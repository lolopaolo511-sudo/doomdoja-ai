/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,js}"],
  theme: {
    extend: {
      fontFamily: {
        display: ['"Cinzel"', "Georgia", "serif"],
        body: ['"Spectral"', "Georgia", "serif"],
      },
      colors: {
        aether: {
          ink: "#0d0f1a",
          panel: "#1a1d2e",
          panel2: "#242842",
          edge: "#3a3f63",
          gold: "#e8c87a",
          glow: "#8ad8ff",
          text: "#e6e8f2",
          muted: "#9aa0c0",
        },
      },
      keyframes: {
        fadein: {
          "0%": { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        pop: {
          "0%": { opacity: "0", transform: "scale(0.92)" },
          "100%": { opacity: "1", transform: "scale(1)" },
        },
      },
      animation: {
        fadein: "fadein 0.25s ease-out",
        pop: "pop 0.18s ease-out",
      },
    },
  },
  plugins: [],
};
