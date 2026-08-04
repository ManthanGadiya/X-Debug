import { Button, Card, FileInput, Group, Stack, Text, TextInput, Title } from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'

/**
 * Repository upload panel: accepts a zip archive or a GitHub URL and
 * navigates to the resulting project detail page on success.
 */
export function UploadPanel() {
  const navigate = useNavigate()
  const [file, setFile] = useState<File | null>(null)
  const [url, setUrl] = useState('')
  const [uploading, setUploading] = useState(false)
  const [cloning, setCloning] = useState(false)

  const handleUpload = async () => {
    if (!file) return
    setUploading(true)
    try {
      const project = await api.uploadProject(file)
      notifications.show({
        color: 'green',
        title: 'Repository uploaded',
        message: project.name,
      })
      navigate(`/projects/${project.id}`)
    } catch (cause) {
      notifications.show({
        color: 'red',
        title: 'Upload failed',
        message: cause instanceof Error ? cause.message : 'Unknown error',
      })
    } finally {
      setUploading(false)
    }
  }

  const handleClone = async () => {
    if (!url.trim()) return
    setCloning(true)
    try {
      const project = await api.ingestGithub(url.trim())
      notifications.show({
        color: 'green',
        title: 'Repository cloned',
        message: project.name,
      })
      setUrl('')
      navigate(`/projects/${project.id}`)
    } catch (cause) {
      notifications.show({
        color: 'red',
        title: 'Clone failed',
        message: cause instanceof Error ? cause.message : 'Unknown error',
      })
    } finally {
      setCloning(false)
    }
  }

  return (
    <Stack gap="lg">
      <Card withBorder>
        <Title order={4} mb="sm">
          Upload a repository
        </Title>
        <Text size="sm" c="dimmed" mb="md">
          Start with a zip archive of a local repository or a GitHub URL. XDebug detects supported
          languages and indexes every source file.
        </Text>
        <Stack gap="md">
          <Group align="flex-end" gap="sm">
            <FileInput
              label="Zip archive"
              placeholder="repo.zip"
              value={file}
              onChange={setFile}
              clearable
              style={{ flex: 1 }}
            />
            <Button onClick={() => void handleUpload()} loading={uploading} disabled={!file}>
              Upload
            </Button>
          </Group>
          <Group align="flex-end" gap="sm">
            <TextInput
              label="GitHub repository"
              placeholder="https://github.com/owner/repo"
              value={url}
              onChange={(event) => setUrl(event.currentTarget.value)}
              style={{ flex: 1 }}
            />
            <Button
              onClick={() => void handleClone()}
              loading={cloning}
              disabled={!url.trim()}
              variant="light"
            >
              Clone
            </Button>
          </Group>
        </Stack>
      </Card>
    </Stack>
  )
}
