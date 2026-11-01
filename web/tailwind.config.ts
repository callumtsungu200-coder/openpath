import type { Config } from 'tailwindcss'
import animate from 'tailwindcss-animate'

const token = (name: string) => `hsl(var(--${name}) / <alpha-value>)`

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  future: { hoverOnlyWhenSupported: true },
  theme: {
    extend: {
      fontFamily: { sans: ['-apple-system', 'BlinkMacSystemFont', 'SF Pro Text', 'Inter Variable', 'system-ui', 'sans-serif'] },
      transitionTimingFunction: { ios: 'cubic-bezier(0.32, 0.72, 0, 1)' },
      colors: {
        background: token('background'),
        shell: token('shell'),
        surface: { DEFAULT: token('surface'), raised: token('surface-raised'), inverse: token('surface-inverse') },
        foreground: token('foreground'),
        muted: { DEFAULT: token('surface-raised'), foreground: token('muted-foreground') },
        subtle: token('subtle-foreground'),
        border: token('border'),
        input: token('input'),
        ring: token('ring'),
        primary: { DEFAULT: token('primary'), foreground: token('primary-foreground') },
        accent: { DEFAULT: token('accent'), foreground: token('accent-foreground'), soft: token('accent-soft') },
        success: { DEFAULT: token('success'), soft: token('success-soft') },
        warning: { DEFAULT: token('warning'), soft: token('warning-soft') },
        danger: { DEFAULT: token('danger'), soft: token('danger-soft') },
      },
      borderRadius: { sm: '0.5rem', md: '0.75rem', lg: '1rem', xl: '1.25rem', '2xl': '1.75rem', '3xl': '2.25rem' },
      boxShadow: { card: '0 1px 2px hsl(220 30% 20% / 0.04), 0 6px 20px hsl(220 30% 20% / 0.05)', pop: '0 12px 40px hsl(220 30% 20% / 0.18)' },
      maxWidth: { shell: '92rem' },
    },
  },
  plugins: [animate],
} satisfies Config
