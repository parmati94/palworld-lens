/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./login.html",
    "./js/**/*.js",
    "./partials/**/*.html"
  ],
  theme: {
    extend: {
      // `font-display` -> the self-hosted wordmark face (see @font-face in css/styles.css).
      // Body text stays on the system sans stack; only the wordmark uses this.
      fontFamily: {
        display: ['"Space Grotesk"', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
      // The "lens" palette, shared with satisfactory-lens. Every `accent-*`
      // utility resolves to R G B triplets defined per `[data-theme]` in
      // css/styles.css, so retinting the app is one attribute on <html>.
      // `<alpha-value>` keeps opacity modifiers (bg-accent-500/20) working.
      colors: {
        // Mid-steps the partials already reference (hover surfaces).
        gray: { 650: '#414b5a', 750: '#2b3544' },
        accent: {
          50: 'rgb(var(--accent-50) / <alpha-value>)',
          100: 'rgb(var(--accent-100) / <alpha-value>)',
          200: 'rgb(var(--accent-200) / <alpha-value>)',
          300: 'rgb(var(--accent-300) / <alpha-value>)',
          400: 'rgb(var(--accent-400) / <alpha-value>)',
          500: 'rgb(var(--accent-500) / <alpha-value>)',
          600: 'rgb(var(--accent-600) / <alpha-value>)',
          700: 'rgb(var(--accent-700) / <alpha-value>)',
          800: 'rgb(var(--accent-800) / <alpha-value>)',
          900: 'rgb(var(--accent-900) / <alpha-value>)',
        },
        // Fixed meaning colours: ok = healthy/active, warn = needs attention,
        // danger = starving/injured/error. Never themed, so meaning stays constant.
        ok: {
          50: 'rgb(var(--ok-50) / <alpha-value>)', 100: 'rgb(var(--ok-100) / <alpha-value>)',
          200: 'rgb(var(--ok-200) / <alpha-value>)', 300: 'rgb(var(--ok-300) / <alpha-value>)',
          400: 'rgb(var(--ok-400) / <alpha-value>)', 500: 'rgb(var(--ok-500) / <alpha-value>)',
          600: 'rgb(var(--ok-600) / <alpha-value>)', 700: 'rgb(var(--ok-700) / <alpha-value>)',
          800: 'rgb(var(--ok-800) / <alpha-value>)', 900: 'rgb(var(--ok-900) / <alpha-value>)',
        },
        warn: {
          50: 'rgb(var(--warn-50) / <alpha-value>)', 100: 'rgb(var(--warn-100) / <alpha-value>)',
          200: 'rgb(var(--warn-200) / <alpha-value>)', 300: 'rgb(var(--warn-300) / <alpha-value>)',
          400: 'rgb(var(--warn-400) / <alpha-value>)', 500: 'rgb(var(--warn-500) / <alpha-value>)',
          600: 'rgb(var(--warn-600) / <alpha-value>)', 700: 'rgb(var(--warn-700) / <alpha-value>)',
          800: 'rgb(var(--warn-800) / <alpha-value>)', 900: 'rgb(var(--warn-900) / <alpha-value>)',
        },
        danger: {
          50: 'rgb(var(--danger-50) / <alpha-value>)', 100: 'rgb(var(--danger-100) / <alpha-value>)',
          200: 'rgb(var(--danger-200) / <alpha-value>)', 300: 'rgb(var(--danger-300) / <alpha-value>)',
          400: 'rgb(var(--danger-400) / <alpha-value>)', 500: 'rgb(var(--danger-500) / <alpha-value>)',
          600: 'rgb(var(--danger-600) / <alpha-value>)', 700: 'rgb(var(--danger-700) / <alpha-value>)',
          800: 'rgb(var(--danger-800) / <alpha-value>)', 900: 'rgb(var(--danger-900) / <alpha-value>)',
        },
      },
    },
  },
  plugins: [],
}
