/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./renderer/index.html', './renderer/src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: {
          950: '#060b10',
          900: '#0a1218',
          800: '#101d26',
          700: '#172b37',
        },
        mint: {
          300: '#8ff5d2',
          400: '#5ee9b8',
          500: '#2fd39a',
        },
        amber: {
          300: '#ffd88a',
          400: '#ffc35c',
          500: '#f2a93c',
        },
        rose: {
          300: '#ffb3b3',
          400: '#ff8a8a',
        },
      },
      fontFamily: {
        sans: [
          'ui-rounded',
          '-apple-system',
          'BlinkMacSystemFont',
          'Segoe UI',
          'Inter',
          'system-ui',
          'sans-serif',
        ],
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
      boxShadow: {
        glass: '0 24px 80px -30px rgba(0, 0, 0, 0.85)',
        halo: '0 0 60px -10px rgba(94, 233, 184, 0.45)',
      },
      keyframes: {
        'aurora-drift': {
          '0%, 100%': { transform: 'translate3d(-4%, -2%, 0) scale(1)' },
          '50%': { transform: 'translate3d(4%, 3%, 0) scale(1.08)' },
        },
        'soft-blink': {
          '0%, 94%, 100%': { transform: 'scaleY(1)' },
          '96%': { transform: 'scaleY(0.08)' },
        },
      },
      animation: {
        'aurora-drift': 'aurora-drift 18s ease-in-out infinite',
        'soft-blink': 'soft-blink 6s ease-in-out infinite',
      },
    },
  },
  plugins: [],
}
