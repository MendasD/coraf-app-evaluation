/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './templates/**/*.html',
    './evaluations/**/*.py',
  ],
  theme: {
    fontFamily: {
      sans: ['Inter', 'ui-sans-serif', 'system-ui', '-apple-system', 'Segoe UI', 'Roboto', 'sans-serif'],
    },
    extend: {
      colors: {
        coraf: {
          50:  '#f1f8ea',
          100: '#dff0c8',
          200: '#c2e394',
          300: '#9fd05a',
          400: '#7fb934',
          500: '#5fa01f',
          600: '#487d18',
          700: '#3f7723',
          800: '#335c1a',
          900: '#2a4a17',
        },
      },
      boxShadow: {
        card: '0 1px 2px rgba(15,23,42,0.04), 0 1px 3px rgba(15,23,42,0.06)',
        elevated: '0 4px 16px -4px rgba(15,23,42,0.10), 0 2px 4px rgba(15,23,42,0.04)',
      },
    },
  },
  plugins: [],
}
