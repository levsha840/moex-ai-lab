import { createTheme, rem } from '@mantine/core'

export const theme = createTheme({
  primaryColor: 'blue',
  fontFamily: "'Roboto Mono', 'Consolas', 'Monaco', monospace",
  fontFamilyMonospace: "'Roboto Mono', 'Consolas', monospace",
  headings: {
    fontFamily: "'Roboto Mono', 'Consolas', monospace",
  },
  colors: {
    dark: [
      '#C1C2C5', '#A6A7AB', '#909296', '#5C5F66',
      '#373A40', '#2C2E33', '#25262b', '#1A1B1E',
      '#141517', '#101113',
    ],
  },
  components: {
    Paper: {
      defaultProps: { radius: 'sm' },
      styles: {
        root: {
          backgroundColor: '#161b22',
          border: '1px solid #30363d',
        },
      },
    },
    Card: {
      defaultProps: { radius: 'sm', p: 'md' },
      styles: {
        root: {
          backgroundColor: '#161b22',
          border: '1px solid #30363d',
        },
      },
    },
    Table: {
      styles: {
        th: { backgroundColor: '#0d1117', color: '#8b949e', fontSize: rem(11) },
        td: { fontSize: rem(12), padding: '6px 10px' },
      },
    },
    Badge: {
      defaultProps: { size: 'xs', radius: 'sm' },
    },
  },
})
