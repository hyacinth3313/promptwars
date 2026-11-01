/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: { extend: {
    colors: { cream: '#f8f6f2', charcoal: '#45434b', muted: '#76727c', lavender: '#e9e0f3', mint: '#e0eee5', peach: '#f8e5d9', powder: '#e1edf4', pink: '#f5e0e6', coral: '#edb5a6', lilac: '#816994' },
    fontFamily: { sans: ['"DM Sans"', 'sans-serif'], display: ['"Manrope"', 'sans-serif'] },
    boxShadow: { clay: '8px 12px 28px rgba(146,128,150,.10), -6px -6px 18px rgba(255,255,255,.9), inset 2px 2px 3px rgba(255,255,255,.85)', button: '0 5px 10px rgba(132,106,151,.13), inset 0 2px 2px rgba(255,255,255,.6)' },
  } }, plugins: [],
};
