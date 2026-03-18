/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#eff6ff',
          100: '#dbeafe',
          200: '#bfdbfe',
          300: '#93c5fd',
          400: '#60a5fa',
          500: '#3b82f6',
          600: '#2563eb',
          700: '#1d4ed8',
          800: '#1e40af',
          900: '#1e3a8a',
          950: '#172554',
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
          50: '#f8fafc',
          100: '#f1f5f9',
          200: '#e2e8f0',
          300: '#cbd5e1',
          400: '#94a3b8',
          500: '#64748b',
          600: '#475569',
          700: '#334155',
          800: '#1e293b',
          900: '#0f172a',
          950: '#020617',
        },
        // Dark mode surface colors
        dark: {
          bg: '#060d1f',
          surface: '#0d1b3e',
          border: '#1e3a8a',
          sidebar: '#030712',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'Cascadia Code', 'ui-monospace', 'monospace'],
      },
      borderRadius: {
        card: '12px',
        button: '8px',
      },
      boxShadow: {
        card: '0 1px 3px 0 rgb(37 99 235 / 0.06), 0 1px 2px -1px rgb(37 99 235 / 0.04)',
        'card-hover': '0 4px 16px 0 rgb(37 99 235 / 0.12), 0 2px 4px -1px rgb(37 99 235 / 0.06)',
        'card-elevated': '0 8px 32px 0 rgb(37 99 235 / 0.14), 0 4px 8px -2px rgb(37 99 235 / 0.08)',
        'card-dark': '0 1px 3px 0 rgb(0 0 0 / 0.4), 0 1px 2px -1px rgb(0 0 0 / 0.3)',
        'card-dark-hover': '0 4px 16px 0 rgb(0 0 0 / 0.5), 0 2px 4px -1px rgb(0 0 0 / 0.3)',
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
