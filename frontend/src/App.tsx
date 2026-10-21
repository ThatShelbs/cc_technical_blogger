import { Navigate, Route, Routes } from 'react-router'

import { usePersonas } from './api/hooks'
import { AppShell } from './components/AppShell'
import { Spinner } from './components/ui'
import { NewProjectPage } from './pages/NewProjectPage'
import { PersonaPage } from './pages/PersonaPage'
import { PersonasPage } from './pages/PersonasPage'
import { ProjectPage } from './pages/project/ProjectPage'
import { ProjectsPage } from './pages/ProjectsPage'
import { SettingsPage } from './pages/SettingsPage'
import { WelcomePage } from './pages/WelcomePage'

/** First run (no personas yet) goes straight to the setup guide. */
function Home() {
  const { data: personas, isLoading } = usePersonas()
  if (isLoading) return <Spinner />
  if (personas && personas.length === 0) return <Navigate to="/welcome" replace />
  return <ProjectsPage />
}

export default function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/welcome" element={<WelcomePage />} />
        <Route path="/projects/new" element={<NewProjectPage />} />
        <Route path="/projects/:id" element={<ProjectPage />} />
        <Route path="/personas" element={<PersonasPage />} />
        <Route path="/personas/:id" element={<PersonaPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AppShell>
  )
}
