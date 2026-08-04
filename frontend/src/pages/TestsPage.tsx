import { RunListPage } from '../components/RunListPage'

export function TestsPage() {
  return (
    <RunListPage
      kind="tests"
      title="Tests"
      descriptionAll="Every test run in the workspace. Open a run to see per-suite pass/fail details."
      descriptionFiltered="Test runs for {project}. Each run executes the project's test suites in isolation."
      startLabel="Run tests"
      startErrorTitle="Failed to start test run"
      sectionTitle="Test runs"
      emptyAll="No test runs yet — open a project and run its tests there."
      emptyFiltered="No test runs for this project yet."
      errorTitle="Failed to load test runs"
    />
  )
}
