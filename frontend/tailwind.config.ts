import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        gold: {
          50: '#FFF8E7',
          100: '#FFEFC2',
          200: '#FFE099',
          300: '#FFD06B',
          400: '#DEBF6A',
          500: '#CFB991',
          600: '#B89F65',
          700: '#9A8347',
          800: '#7C682E',
          900: '#5E4D1A',
        },
        dark: {
          50: '#2A2A2A',
          100: '#222222',
          200: '#1A1A1A',
          300: '#141414',
          400: '#0F0F0F',
          500: '#0A0A0A',
          600: '#050505',
          700: '#000000',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
      },
      backgroundImage: {
        'gradient-gold': 'linear-gradient(135deg, #CFB991 0%, #E8D5A3 50%, #CFB991 100%)',
        'gradient-dark': 'linear-gradient(180deg, #0A0A0A 0%, #141414 100%)',
        'glass': 'linear-gradient(135deg, rgba(207, 185, 145, 0.05) 0%, rgba(207, 185, 145, 0.02) 100%)',
      },
      boxShadow: {
        'gold': '0 0 20px rgba(207, 185, 145, 0.15)',
        'gold-lg': '0 0 40px rgba(207, 185, 145, 0.2)',
        'card': '0 4px 24px rgba(0, 0, 0, 0.4)',
        'glow': '0 0 60px rgba(207, 185, 145, 0.1)',
      },
      animation: {
        'float': 'float 6s ease-in-out infinite',
        'pulse-gold': 'pulse-gold 2s ease-in-out infinite',
        'slide-up': 'slide-up 0.6s cubic-bezier(0.16, 1, 0.3, 1)',
        'slide-in-right': 'slide-in-right 0.4s cubic-bezier(0.16, 1, 0.3, 1)',
        'fade-in': 'fade-in 0.5s ease-out',
        'scale-in': 'scale-in 0.3s cubic-bezier(0.16, 1, 0.3, 1)',
        'bounce-in': 'bounce-in 0.5s cubic-bezier(0.34, 1.56, 0.64, 1)',
        'shimmer': 'shimmer 2s linear infinite',
        'pete-idle': 'pete-idle 3s ease-in-out infinite',
        'message-in': 'message-in 0.35s cubic-bezier(0.16, 1, 0.3, 1)',
        'slide-up-fade': 'slide-up-fade 0.4s cubic-bezier(0.16, 1, 0.3, 1)',
        'bar-grow': 'bar-grow 0.6s cubic-bezier(0.16, 1, 0.3, 1) forwards',
      },
      keyframes: {
        'pete-idle': {
          '0%, 100%': { transform: 'translateY(0) scale(1)', boxShadow: '0 8px 32px rgba(207, 185, 145, 0.25)' },
          '50%': { transform: 'translateY(-3px) scale(1.02)', boxShadow: '0 12px 40px rgba(207, 185, 145, 0.35)' },
        },
        'message-in': {
          '0%': { opacity: '0', transform: 'translateY(8px) scale(0.96)' },
          '100%': { opacity: '1', transform: 'translateY(0) scale(1)' },
        },
        'slide-up-fade': {
          '0%': { opacity: '0', transform: 'translateY(16px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        float: {
          '0%, 100%': { transform: 'translateY(0px)' },
          '50%': { transform: 'translateY(-10px)' },
        },
        'pulse-gold': {
          '0%, 100%': { boxShadow: '0 0 20px rgba(207, 185, 145, 0.15)' },
          '50%': { boxShadow: '0 0 30px rgba(207, 185, 145, 0.3)' },
        },
        'slide-up': {
          '0%': { opacity: '0', transform: 'translateY(30px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'slide-in-right': {
          '0%': { opacity: '0', transform: 'translateX(20px)' },
          '100%': { opacity: '1', transform: 'translateX(0)' },
        },
        'fade-in': {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        'scale-in': {
          '0%': { opacity: '0', transform: 'scale(0.95)' },
          '100%': { opacity: '1', transform: 'scale(1)' },
        },
        'bounce-in': {
          '0%': { opacity: '0', transform: 'scale(0.3)' },
          '50%': { transform: 'scale(1.05)' },
          '100%': { opacity: '1', transform: 'scale(1)' },
        },
        'shimmer': {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
        'bar-grow': {
          '0%': { transform: 'scaleY(0)', transformOrigin: 'bottom' },
          '100%': { transform: 'scaleY(1)', transformOrigin: 'bottom' },
        },
      },
    },
  },
  plugins: [],
};
export default config;
