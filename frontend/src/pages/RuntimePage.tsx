import { RunListPage } from '../components/RunListPage'

export function RuntimePage() {
  return (
    <RunListPage
      kind="runtime"
      title="Runtime"
      descriptionAll="Every execution run in the workspace. Open a run to replay its trace."
      descriptionFiltered="Execution runs for {project}. Each run captures a trace of function calls, variable snapshots, and any exception."
      startLabel="Run code"
      startErrorTitle="Failed to start run"
      sectionTitle="Runtime runs"
      emptyAll="No runtime runs yet — open a project and run its code there."
      emptyFiltered="No runtime runs for this project yet."
      errorTitle="Failed to load runtime runs"
    />
  )
}
