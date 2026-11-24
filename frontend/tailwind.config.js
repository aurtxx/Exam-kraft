/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#f0f7ff',
          100: '#c4ecff',
          200: '#90d7ff',
          300: '#5abeff',
          400: '#34a5f8',
          500: '#2d8df1',
          600: '#1474D8',
          700: '#0f5bb0',
          800: '#0d488a',
          900: '#0c3b6e',
        },
        navy: {
          50: '#f1f4f9',
          100: '#dde3ef',
          200: '#c0cce2',
          300: '#97add0',
          400: '#688abb',
          500: '#486da7',
          600: '#36558b',
          700: '#2d4571',
          800: '#283c5e',
          900: '#284b92',
          950: '#192849',
        },
        success: {
          500: '#22C969',
          600: '#08af4f',
        },
        danger: {
          500: '#FF614D',
          600: '#e54531',
        },
        review: {
          300: '#b58fff',
          500: '#9967ff',
        },
        warning: {
          400: '#fccc5a',
          500: '#e0b441',
        },
        accent: {
          gold: '#ffad17',
          orange: '#ffac59',
          coral: '#f96a6a',
        },
      },
      fontFamily: {
        sans: ['"DM Sans"', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'monospace'],
      },
      borderRadius: {
        'xl': '12px',
        '2xl': '16px',
      },
    },
  },
  plugins: [],
}
