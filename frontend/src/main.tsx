import { ColorSchemeScript, MantineProvider } from '@mantine/core'
import { createRoot } from 'react-dom/client'
import { RouterProvider, createBrowserRouter } from 'react-router-dom'
import '@mantine/core/styles.css'
import { AppLayout } from './components/AppLayout'
import { HomePage } from './pages/HomePage'
import { theme } from './theme'

const router = createBrowserRouter([
  {
    element: <AppLayout />,
    children: [{ path: '/', element: <HomePage /> }],
  },
])

createRoot(document.getElementById('root')!).render(
  <>
    <ColorSchemeScript />
    <MantineProvider theme={theme}>
      <RouterProvider router={router} />
    </MantineProvider>
  </>,
)
