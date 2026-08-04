import { ColorSchemeScript, MantineProvider } from '@mantine/core'
import { Notifications } from '@mantine/notifications'
import { createRoot } from 'react-dom/client'
import { RouterProvider, createBrowserRouter } from 'react-router-dom'
import '@fontsource/ibm-plex-sans/400.css'
import '@fontsource/ibm-plex-sans/500.css'
import '@fontsource/ibm-plex-sans/600.css'
import '@fontsource/ibm-plex-mono/400.css'
import '@fontsource/ibm-plex-mono/500.css'
import '@mantine/core/styles.css'
import '@mantine/notifications/styles.css'
import './styles.css'
import { AppLayout } from './components/AppLayout'
import { ErrorPage } from './components/ErrorPage'
import { AnalysisDetailPage } from './pages/AnalysisDetailPage'
import { AnalysisPage } from './pages/AnalysisPage'
import { DashboardPage } from './pages/DashboardPage'
import { ProjectDetailPage } from './pages/ProjectDetailPage'
import { ProjectsPage } from './pages/ProjectsPage'
import { ReportsPage } from './pages/ReportsPage'
import { RuntimeDetailPage } from './pages/RuntimeDetailPage'
import { RuntimePage } from './pages/RuntimePage'
import { TestDetailPage } from './pages/TestDetailPage'
import { TestsPage } from './pages/TestsPage'
import { theme } from './theme'

const router = createBrowserRouter([
  {
    element: <AppLayout />,
    errorElement: <ErrorPage />,
    children: [
      { path: '/', element: <DashboardPage /> },
      { path: '/projects', element: <ProjectsPage /> },
      { path: '/projects/:projectId', element: <ProjectDetailPage /> },
      { path: '/analysis', element: <AnalysisPage /> },
      { path: '/analysis/:analysisId', element: <AnalysisDetailPage /> },
      { path: '/runtime', element: <RuntimePage /> },
      { path: '/runtime/:runId', element: <RuntimeDetailPage /> },
      { path: '/tests', element: <TestsPage /> },
      { path: '/tests/:runId', element: <TestDetailPage /> },
      { path: '/reports', element: <ReportsPage /> },
    ],
  },
])

createRoot(document.getElementById('root')!).render(
  <>
    <ColorSchemeScript />
    <MantineProvider theme={theme}>
      <Notifications />
      <RouterProvider router={router} />
    </MantineProvider>
  </>,
)
