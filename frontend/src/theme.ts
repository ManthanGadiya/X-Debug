import { createTheme, type MantineColorsTuple } from '@mantine/core'

// XDebug "diagnostic instrument" theme.
// A dark lab console: ink backgrounds, a signal-cyan accent, and monospace
// readouts for anything quantitative.

const brand: MantineColorsTuple = [
  '#e2fbff',
  '#c0f2fb',
  '#8ee4f5',
  '#55d4ee',
  '#2cc6e8',
  '#12bce2',
  '#00b5dd',
  '#009fc3',
  '#008eac',
  '#007a93',
]

const signal: MantineColorsTuple = [
  '#e6fbf3',
  '#c9f2e2',
  '#9ce6c7',
  '#6bdaab',
  '#44d095',
  '#2cc988',
  '#1cc57f',
  '#0fae6c',
  '#049a5e',
  '#00874e',
]

const dark: MantineColorsTuple = [
  '#f5f7fa',
  '#dce4ea',
  '#b8c4cd',
  '#8f9ea9',
  '#6e7e8b',
  '#5a6a77',
  '#4c5b67',
  '#232c36',
  '#131a22',
  '#0a0f15',
]

export const theme = createTheme({
  primaryColor: 'brand',
  primaryShade: { light: 6, dark: 7 },
  colors: {
    brand,
    signal,
    dark,
  },
  fontFamily: "'IBM Plex Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
  fontFamilyMonospace:
    "'IBM Plex Mono', ui-monospace, 'SF Mono', Menlo, Consolas, monospace",
  headings: {
    fontFamily: "'IBM Plex Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
    fontWeight: '600',
    sizes: {
      h1: { fontSize: '2.2rem', lineHeight: '1.15' },
      h2: { fontSize: '1.6rem', lineHeight: '1.2' },
      h3: { fontSize: '1.25rem', lineHeight: '1.3' },
      h4: { fontSize: '1.05rem', lineHeight: '1.35' },
    },
  },
  defaultRadius: 'md',
  defaultGradient: { from: 'brand', to: 'signal', deg: 120 },
  components: {
    AppShell: {
      defaultProps: {
        bg: 'dark.9',
      },
    },
    Card: {
      defaultProps: {
        bg: 'dark.8',
        withBorder: true,
        radius: 'md',
      },
    },
    Table: {
      defaultProps: {
        verticalSpacing: 'sm',
        horizontalSpacing: 'md',
      },
    },
    Badge: {
      defaultProps: {
        radius: 'sm',
        tt: 'none',
        fw: 500,
      },
    },
    Button: {
      defaultProps: {
        fw: 500,
      },
    },
  },
})
