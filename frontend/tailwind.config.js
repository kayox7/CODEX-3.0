/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        warden: {
          dark: '#090d16',
          panel: '#0f172a',
          surface: '#1e293b',
          border: '#334155',
          primary: '#0ea5e9',
          danger: '#ef4444',
          warning: '#f59e0b',
          success: '#10b981',
          accent: '#8b5cf6'
        }
      }
    },
  },
  plugins: [],
}
