import { RunListPage } from '../components/RunListPage'

export function AnalysisPage() {
  return (
    <RunListPage
      kind="analysis"
      title="Analysis"
      descriptionAll="Every static analysis run in the workspace. Open a run to inspect its graphs."
      descriptionFiltered="Static pipeline runs for {project}. Graphs are built per run: dependency, call, control flow, and dataflow."
      startLabel="Start analysis"
      startErrorTitle="Failed to start analysis"
      sectionTitle="Analysis runs"
      emptyAll="No analysis runs yet — open a project and start analysis there."
      emptyFiltered="No analysis runs for this project yet."
      errorTitle="Failed to load analysis runs"
    />
  )
}
