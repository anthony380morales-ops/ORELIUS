/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'oreilus-dark': '#0a0e1a',
        'oreilus-blue': '#1e40af',
        'oreilus-accent': '#3b82f6',
        // Premium Navy Blue & White Theme
        'navy': {
          50: '#f0f9ff',   // Very light blue-white
          100: '#e0f2fe',  // Light blue-white
          200: '#bae6fd',  // Soft blue
          300: '#7dd3fc',  // Sky blue
          400: '#38bdf8',  // Bright blue
          500: '#0ea5e9',  // Ocean blue
          600: '#0284c7',  // Deep ocean
          700: '#0369a1',  // Navy blue
          800: '#075985',  // Dark navy
          900: '#0c4a6e',  // Deep navy
          950: '#082f49',  // Darkest navy
        },
        'rich': {
          navy: '#000814',      // Very dark navy primary
          'navy-light': '#001d3d', // Dark navy
          'navy-dark': '#000000',  // Pure black
          gold: '#ffd700',      // Premium gold accent
          silver: '#c0c0c0',    // Silver accent
          white: '#ffffff',     // Pure white
          'off-white': '#f8fafc', // Soft white
        },
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'float': 'float 6s ease-in-out infinite',
        'glow': 'glow 2s ease-in-out infinite',
        'shimmer': 'shimmer 2s linear infinite',
        'shooting-star': 'shooting-star 3s linear infinite',
      },
      keyframes: {
        float: {
          '0%, 100%': { transform: 'translateY(0px)' },
          '50%': { transform: 'translateY(-20px)' },
        },
        glow: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.5' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-1000px 0' },
          '100%': { backgroundPosition: '1000px 0' },
        },
        'shooting-star': {
          '0%': {
            transform: 'translateX(0) translateY(0) rotate(-45deg)',
            opacity: '1',
          },
          '70%': {
            opacity: '1',
          },
          '100%': {
            transform: 'translateX(1000px) translateY(1000px) rotate(-45deg)',
            opacity: '0',
          },
        },
      },
      backgroundImage: {
        'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
        'gradient-navy': 'linear-gradient(to bottom, #001f3f, #00142b)',
        'shimmer-gradient': 'linear-gradient(90deg, transparent, rgba(255,255,255,0.1), transparent)',
      },
    },
  },
  plugins: [],
}
