/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      // Oatmeal-inspired color palette with olive accent
      colors: {
        // Neutral warm tones (light mode)
        cream: {
          50: '#fefdfb',
          100: '#fdf9f3',
          200: '#f9f1e4',
          300: '#f3e5d0',
          400: '#e8d4b5',
          500: '#d9c09a',
          600: '#c4a67a',
          700: '#a8885c',
          800: '#8a6d47',
          900: '#70563a',
        },
        // Olive accent (from Oatmeal theme)
        olive: {
          50: '#f7f8f5',
          100: '#eef0e8',
          200: '#dde1d1',
          300: '#c4cbad',
          400: '#a7b185',
          500: '#8a9766',
          600: '#6d7a4e',
          700: '#556040',
          800: '#464e36',
          900: '#3c4230',
        },
        // Dark mode surface colors - warm dark tones
        surface: {
          50: '#f8f8f7',
          100: '#f0efed',
          200: '#e0dedb',
          300: '#c9c5c0',
          400: '#a9a49d',
          500: '#918b83',
          600: '#7a746c',
          700: '#635e58',
          800: '#514d49',
          900: '#44413e',
          950: '#282624',
        },
        // Dark mode background colors
        dark: {
          50: '#3d3a37',
          100: '#343230',
          200: '#2d2b29',
          300: '#262422',
          400: '#201e1c',
          500: '#1a1917',
          600: '#151413',
          700: '#100f0e',
          800: '#0b0a0a',
          900: '#060606',
        }
      },
      fontFamily: {
        // Serif for headings (Oatmeal style)
        serif: ['Instrument Serif', 'Georgia', 'serif'],
        // Sans for body
        sans: ['Inter', 'system-ui', 'sans-serif'],
        // Mono for code/technical
        mono: ['JetBrains Mono', 'monospace'],
      },
      borderRadius: {
        'xl': '1rem',
        '2xl': '1.5rem',
        '3xl': '2rem',
      },
      boxShadow: {
        'soft': '0 2px 15px -3px rgba(0, 0, 0, 0.07), 0 10px 20px -2px rgba(0, 0, 0, 0.04)',
        'medium': '0 4px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 25px -5px rgba(0, 0, 0, 0.04)',
        'soft-dark': '0 2px 15px -3px rgba(0, 0, 0, 0.3), 0 10px 20px -2px rgba(0, 0, 0, 0.2)',
        'medium-dark': '0 4px 25px -5px rgba(0, 0, 0, 0.4), 0 10px 25px -5px rgba(0, 0, 0, 0.3)',
      },
      animation: {
        'fade-in': 'fadeIn 0.3s ease-out',
        'slide-up': 'slideUp 0.4s ease-out',
        'pulse-subtle': 'pulseSubtle 2s infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        pulseSubtle: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.7' },
        },
      },
    },
  },
  plugins: [],
}
