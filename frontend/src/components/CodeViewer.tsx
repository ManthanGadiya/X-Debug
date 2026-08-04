import { Box, Text } from '@mantine/core'

interface CodeViewerProps {
  title?: string
  code: string
  maxHeight?: number
}

/** A read-only code/text viewer rendered in a monospace block. */
export function CodeViewer({ title, code, maxHeight = 320 }: CodeViewerProps) {
  return (
    <Box>
      {title ? (
        <Text size="sm" fw={600} mb={4}>
          {title}
        </Text>
      ) : null}
      <Box
        component="pre"
        style={{
          margin: 0,
          padding: '12px 16px',
          background: 'var(--mantine-color-dark-6)',
          color: 'var(--mantine-color-gray-3)',
          borderRadius: 'var(--mantine-radius-md)',
          overflow: 'auto',
          maxHeight,
          fontSize: 13,
          lineHeight: 1.6,
        }}
        data-testid="code-viewer"
      >
        <code>{code}</code>
      </Box>
    </Box>
  )
}
