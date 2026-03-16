/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#F7F8FE',
          100: '#EEF0FD',
          400: '#8FA0F6',
          500: '#6B7FEF',
          600: '#4059D9',
          700: '#3645AE',
          800: '#283080',
          900: '#1A1F52',
        },
        success: {
          50: '#F0FBF5',
          100: '#E6F7EE',
          200: '#BBE8D0',
          500: '#28A062',
          600: '#20885A',
          700: '#1C7A4A',
        },
        warning: {
          50: '#FFFBEE',
          100: '#FEF3D9',
          200: '#FCDFA0',
          500: '#F5A000',
          600: '#CC8500',
          700: '#8A5200',
        },
        danger: {
          50: '#FEF6F6',
          100: '#FDEEEE',
          200: '#F9C6C6',
          500: '#D93535',
          600: '#B82B2B',
          700: '#A32020',
          800: '#7A1818',
        },
        neutral: {
          50: '#F9F9FB',
          100: '#F3F4F7',
          200: '#E2E4E9',
          300: '#CDD0D9',
          400: '#9EA3B0',
          500: '#6B7280',
          600: '#4B5563',
          700: '#374151',
          800: '#1F2937',
          900: '#111827',
        },
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'Cascadia Code', 'ui-monospace', 'monospace'],
      },
      borderRadius: {
        card: '12px',
      },
      boxShadow: {
        card: '0 1px 3px 0 rgb(0 0 0 / 0.06), 0 1px 2px -1px rgb(0 0 0 / 0.04)',
        'card-hover': '0 4px 12px 0 rgb(0 0 0 / 0.08), 0 2px 4px -1px rgb(0 0 0 / 0.05)',
        'card-elevated': '0 8px 24px 0 rgb(0 0 0 / 0.10), 0 4px 8px -2px rgb(0 0 0 / 0.06)',
      },
      animation: {
        'pulse-ring': 'pulse-ring 1.5s ease-in-out infinite',
        'slide-down': 'slide-down 0.3s ease-out',
        'slide-up': 'slide-up 0.3s ease-out',
        'fade-in': 'fade-in 0.2s ease-out',
      },
      keyframes: {
        'pulse-ring': {
          '0%, 100%': { opacity: '1', transform: 'scale(1)' },
          '50%': { opacity: '0.6', transform: 'scale(1.05)' },
        },
        'slide-down': {
          from: { opacity: '0', transform: 'translateY(-8px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        'slide-up': {
          from: { opacity: '1', transform: 'translateY(0)' },
          to: { opacity: '0', transform: 'translateY(-8px)' },
        },
        'fade-in': {
          from: { opacity: '0' },
          to: { opacity: '1' },
        },
      },
    },
  },
  plugins: [],
};
