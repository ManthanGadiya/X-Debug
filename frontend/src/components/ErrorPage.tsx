import { Alert, Button, Center, Stack, Text } from '@mantine/core'
import { Link, useRouteError } from 'react-router-dom'

/** Route-level fallback rendered when a matched route throws during render. */
export function ErrorPage() {
  const error = useRouteError()
  const message = error instanceof Error ? error.message : 'Something went wrong.'

  return (
    <Center mih="100vh">
      <Stack align="center" gap="md">
        <Alert color="red" title="Unexpected error" w="min(90vw, 480px)">
          <Text size="sm">{message}</Text>
        </Alert>
        <Button component={Link} to="/">
          Back to dashboard
        </Button>
      </Stack>
    </Center>
  )
}
