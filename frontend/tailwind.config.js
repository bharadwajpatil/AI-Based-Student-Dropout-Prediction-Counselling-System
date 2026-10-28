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
        cream: {
          50: '#FFFBF5',
          100: '#FFF4E6',
        },
        clay: {
          400: '#E08E6B',
          500: '#D2734E',
          600: '#B85C3A',
        },
        sand: {
          100: '#F5EFE6',
          200: '#EADBC8',
          300: '#DCC7AC',
          400: '#CBB291',
        },
        sage: {
          50: '#F2F7F4',
          100: '#E2EFE6',
          400: '#8FB39A',
          500: '#75A182',
          600: '#5E8C6E',
        },
        amber: {
          50: '#FEF9EE',
          100: '#FDF1D6',
          400: '#F2B84B',
          500: '#E0A130',
          600: '#C98A12',
        },
        rose: {
          50: '#FDF2F2',
          100: '#FCE4E4',
          400: '#E5787A',
          500: '#D85A5D',
          600: '#C2474A',
        },
        ink: {
          500: '#6B574B',
          700: '#4A3B32',
          800: '#382B24',
          900: '#2B211B',
        },
        charcoal: {
          800: '#27211D',
          900: '#1F1A17',
          950: '#171311',
        }
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        display: ['Poppins', 'Inter', 'sans-serif'],
      },
      borderRadius: {
        xl: '0.9rem',
        '2xl': '1.25rem',
      },
      boxShadow: {
        soft: '0 1px 2px rgba(74,59,50,.06), 0 2px 6px rgba(74,59,50,.05)',
        lift: '0 4px 12px rgba(74,59,50,.10), 0 2px 4px rgba(74,59,50,.06)',
      },
      keyframes: {
        'fade-up': {
          '0%': { opacity: '0', transform: 'translateY(8px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'pulse-subtle': {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.65' },
        }
      },
      animation: {
        'fade-up': 'fade-up 250ms ease-out forwards',
        'pulse-subtle': 'pulse-subtle 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
      }
    },
  },
  plugins: [],
}
