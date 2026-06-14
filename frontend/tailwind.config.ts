import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./lib/**/*.{js,ts,jsx,tsx,mdx}"
  ],
  theme: {
    extend: {
      colors: {
        ink: "#151712",
        paper: "#fbfaf6",
        line: "#dedbd2",
        moss: "#556b2f",
        copper: "#9a5f33",
        sky: "#446b86"
      },
      boxShadow: {
        panel: "0 18px 48px rgba(32, 27, 20, 0.08)"
      }
    }
  },
  plugins: []
};

export default config;
