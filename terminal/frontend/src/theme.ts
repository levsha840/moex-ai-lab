import { createTheme, rem } from '@mantine/core'

export const theme = createTheme({
  primaryColor: 'blue',
  fontFamily: "'JetBrains Mono', 'Fira Code', 'Roboto Mono', 'Consolas', monospace",
  fontFamilyMonospace: "'JetBrains Mono', 'Fira Code', 'Roboto Mono', 'Consolas', monospace",
  headings: {
    fontFamily: "'JetBrains Mono', 'Fira Code', 'Roboto Mono', 'Consolas', monospace",
  },
  colors: {
    dark: [
      '#d1d4dc', '#9598a1', '#787b86', '#5d6067',
      '#3d4048', '#2a2e39', '#1e222d', '#161b26',
      '#131722', '#0f1219',
    ],
    blue: [
      '#ebf3ff', '#c3d9ff', '#9fbfff', '#6a9fff',
      '#4680ff', '#2962ff', '#1a4fd4', '#0f3ab0',
      '#0a2a8c', '#061d6a',
    ],
  },
  components: {
    Paper: {
      defaultProps: { radius: 0 },
      styles: {
        root: {
          backgroundColor: '#252b36',
          border: '1px solid #2a2e39',
          borderRadius: 2,
        },
      },
    },
    Card: {
      defaultProps: { radius: 0, p: 'xs' },
      styles: {
        root: {
          backgroundColor: '#252b36',
          border: '1px solid #2a2e39',
          borderRadius: 2,
        },
      },
    },
    Badge: {
      defaultProps: { size: 'xs', radius: 2 },
      styles: {
        root: {
          fontFamily: "'JetBrains Mono', 'Consolas', monospace",
          letterSpacing: '0.5px',
          textTransform: 'uppercase',
        },
      },
    },
    Table: {
      defaultProps: { highlightOnHover: true, striped: false },
    },
    Tooltip: {
      styles: {
        tooltip: {
          backgroundColor: '#2a2e39',
          border: '1px solid #3d4048',
          color: '#d1d4dc',
          fontSize: 11,
          fontFamily: 'monospace',
          borderRadius: 2,
        },
      },
    },
    Loader: {
      defaultProps: { size: 'sm' },
    },
  },
})
