/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: { extend: { colors: { navy: { 950: '#070d1a', 900: '#0b1220', 800: '#111a2e', 700: '#1a2742', 600: '#25365a' } } } },
  plugins: [],
}
