/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Dark theme airport control room colors
        'control-bg': '#0a0e1a',
        'control-panel': '#141824',
        'control-border': '#1e2433',
        'control-text': '#e5e7eb',
        'control-text-dim': '#9ca3af',
        'status-active': '#10b981',
        'status-progress': '#f59e0b',
        'status-alert': '#ef4444',
        'status-complete': '#3b82f6',
      },
      fontFamily: {
        'mono': ['JetBrains Mono', 'Courier New', 'monospace'],
        'sans': ['Inter', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
