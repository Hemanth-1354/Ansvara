/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        display: ['Syne', 'sans-serif'],
      },
      colors: {
        primary: {
          50:  '#f0f4ff',
          100: '#e0e9ff',
          200: '#c7d7fe',
          400: '#7b96fa',
          500: '#4f6ef7',
          600: '#3a57e8',
          700: '#2c43d1',
          900: '#1a2a7a',
          950: '#0f1a50',
        },
      },
    },
  },
  plugins: [],
}
