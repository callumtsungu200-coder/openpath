import type { Config } from 'tailwindcss'
import animate from 'tailwindcss-animate'

const token = (name: string) => `hsl(var(--${name}) / <alpha-value>)`

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: { sans: ['Figtree Variable', 'system-ui', 'sans-serif'] },
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
      boxShadow: { card: '0 1px 2px hsl(220 60% 3% / 0.25)', pop: '0 16px 40px hsl(220 60% 3% / 0.45)' },
      maxWidth: { shell: '92rem' },
    },
  },
  plugins: [animate],
} satisfies Config
