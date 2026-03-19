/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        serif: ['"Gilda Display"', 'serif'], // Serif 폰트 등록
        sans: ['Inter', 'sans-serif'],        // Sans-serif 폰트 등록
      },
    },
  },
  plugins: [],
}
