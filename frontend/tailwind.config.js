import typography from '@tailwindcss/typography';

/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: [
          'Inter',
          'system-ui',
          '-apple-system',
          'BlinkMacSystemFont',
          '"Segoe UI"',
          'Roboto',
          'sans-serif',
        ],
      },
      colors: {
        page: 'var(--lf-bg-primary)',
        surface: 'var(--lf-bg-content)',
        subtle: 'var(--lf-bg-subtle)',
        hoverbg: 'var(--lf-bg-hover)',
        'hoverbg-strong': 'var(--lf-bg-hover-strong)',
        sidebar: {
          DEFAULT: 'var(--lf-sidebar-bg)',
          surface: 'var(--lf-sidebar-surface)',
          hover: 'var(--lf-sidebar-surface-hover)',
          border: 'var(--lf-sidebar-border)',
          text: 'var(--lf-sidebar-text)',
          muted: 'var(--lf-sidebar-text-muted)',
          active: 'var(--lf-sidebar-active-bg)',
        },
        brand: {
          DEFAULT: 'var(--lf-primary)',
          hover: 'var(--lf-primary-hover)',
          soft: 'var(--lf-primary-soft)',
          'soft-border': 'var(--lf-primary-soft-border)',
        },
        accent: {
          DEFAULT: 'var(--lf-accent)',
          hover: 'var(--lf-accent-hover)',
          soft: 'var(--lf-accent-soft)',
          'soft-border': 'var(--lf-accent-soft-border)',
        },
        ink: {
          primary: 'var(--lf-text-primary)',
          secondary: 'var(--lf-text-secondary)',
          muted: 'var(--lf-text-muted)',
          'secondary-btn': 'var(--lf-text-on-secondary-btn)',
        },
        line: {
          DEFAULT: 'var(--lf-border)',
          strong: 'var(--lf-border-strong)',
        },
        input: {
          bg: 'var(--lf-input-bg)',
          border: 'var(--lf-input-border)',
          placeholder: 'var(--lf-input-placeholder)',
        },
        codeblock: {
          bg: 'var(--lf-code-bg)',
          header: 'var(--lf-code-header)',
          border: 'var(--lf-code-border)',
          text: 'var(--lf-code-text)',
          muted: 'var(--lf-code-muted)',
        },
        status: {
          'success-bg': 'var(--lf-success-bg)',
          'success-border': 'var(--lf-success-border)',
          'success-text': 'var(--lf-success-text)',
          'warning-bg': 'var(--lf-warning-bg)',
          'warning-border': 'var(--lf-warning-border)',
          'warning-text': 'var(--lf-warning-text)',
          'danger-bg': 'var(--lf-danger-bg)',
          'danger-border': 'var(--lf-danger-border)',
          'danger-text': 'var(--lf-danger-text)',
          'danger-solid': 'var(--lf-danger-solid)',
          'danger-solid-hover': 'var(--lf-danger-solid-hover)',
        },
      },
      borderRadius: {
        card: '12px',
        btn: '10px',
      },
      boxShadow: {
        card: 'var(--lf-shadow-card)',
        'card-hover': 'var(--lf-shadow-card-hover)',
        modal: 'var(--lf-shadow-modal)',
      },
    },
  },
  plugins: [
    typography,
  ],
};
