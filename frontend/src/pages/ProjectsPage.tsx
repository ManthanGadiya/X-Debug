import { Stack } from '@mantine/core'
import { api } from '../api/client'
import { HistoryTable } from '../components/HistoryTable'
import { PageHeader } from '../components/PageHeader'
import { projectColumns } from '../components/projectColumns'
import { SectionCard } from '../components/SectionCard'
import { UploadPanel } from '../components/UploadPanel'
import { usePolling } from '../hooks/usePolling'

export function ProjectsPage() {
  const projects = usePolling(() => api.listProjects(), { interval: 10000 })

  const columns = projectColumns({ source: true, actions: true })

  return (
    <Stack gap="lg">
      <PageHeader
        title="Projects"
        description="Every repository indexed by the workspace. Open a project to run analysis, runtime, tests, and report generation."
      />

      <SectionCard
        title="New repository"
        subtitle="Upload a zip archive or clone from GitHub"
        delay={60}
      >
        <UploadPanel />
      </SectionCard>

      <SectionCard title="All projects" subtitle="Indexed repositories" delay={120}>
        <HistoryTable
          rows={projects.data ?? []}
          columns={columns}
          getRowId={(project) => project.id}
          loading={projects.loading}
          error={projects.error}
          errorTitle="Failed to load projects"
          emptyLabel="No projects yet — upload a repository above."
        />
      </SectionCard>
    </Stack>
  )
}
