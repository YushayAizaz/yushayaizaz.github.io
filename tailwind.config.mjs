import typography from '@tailwindcss/typography';

/** @type {import('tailwindcss').Config} */
export default {
  content: ['./src/**/*.{astro,html,js,jsx,md,mdx,ts,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        paper: 'rgb(var(--paper) / <alpha-value>)',
        surface: 'rgb(var(--surface) / <alpha-value>)',
        ink: 'rgb(var(--ink) / <alpha-value>)',
        muted: 'rgb(var(--muted) / <alpha-value>)',
        accent: 'rgb(var(--accent) / <alpha-value>)',
        forest: 'rgb(var(--forest) / <alpha-value>)',
      },
      fontFamily: {
        display: ['Cormorant Garamond', 'Georgia', 'serif'],
        body: ['"Source Serif 4"', 'Georgia', 'serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      maxWidth: { reading: '42rem', edition: '90rem' },
      lineHeight: { literary: '1.8' },
      typography: {
        DEFAULT: {
          css: {
            '--tw-prose-body': 'rgb(var(--ink))',
            '--tw-prose-headings': 'rgb(var(--ink))',
            '--tw-prose-lead': 'rgb(var(--muted))',
            '--tw-prose-links': 'rgb(var(--accent))',
            '--tw-prose-bold': 'rgb(var(--ink))',
            '--tw-prose-counters': 'rgb(var(--muted))',
            '--tw-prose-bullets': 'rgb(var(--accent))',
            '--tw-prose-hr': 'rgb(var(--muted) / 0.25)',
            '--tw-prose-quotes': 'rgb(var(--ink))',
            '--tw-prose-quote-borders': 'rgb(var(--accent))',
            '--tw-prose-captions': 'rgb(var(--muted))',
            '--tw-prose-code': 'rgb(var(--ink))',
            '--tw-prose-th-borders': 'rgb(var(--muted) / 0.4)',
            '--tw-prose-td-borders': 'rgb(var(--muted) / 0.2)',
            lineHeight: '1.8',
            maxWidth: '42rem',
            'h1, h2, h3, h4': { fontFamily: 'Cormorant Garamond, Georgia, serif' },
            a: { textUnderlineOffset: '0.2em' },
            blockquote: { fontWeight: '400' },
          },
        },
      },
    },
  },
  plugins: [typography],
};
