import { createTheme, type MantineColorsTuple } from '@mantine/core'

const brand: MantineColorsTuple = [
  '#eef3ff',
  '#dce4f5',
  '#b9c7e2',
  '#92a9d0',
  '#7190c1',
  '#5c81b8',
  '#5179b4',
  '#41679f',
  '#385c90',
  '#2b4f81',
]

export const theme = createTheme({
  primaryColor: 'brand',
  primaryShade: 6,
  colors: {
    brand,
  },
  fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
  headings: {
    fontWeight: '700',
  },
  defaultRadius: 'md',
})
