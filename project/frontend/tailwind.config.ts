import type { Config } from 'tailwindcss';

const config: Config = {
  content: ['./app/**/*.{js,ts,jsx,tsx}', './components/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: '#0B1021',
        glow: '#8B5CF6'
      },
      boxShadow: {
        soft: '0 8px 30px rgba(0,0,0,0.12)'
      }
    }
  },
  plugins: []
};

export default config;
