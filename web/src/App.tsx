import { lazy, Suspense } from 'react'
import { Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { Skeleton } from './components/ui/states'
import { DesignSystemPage } from './pages/DesignSystem'
import { HomePage } from './pages/Home'
import { NotFoundPage } from './pages/NotFound'
import { OpportunityPage } from './pages/Opportunity'
import { SavedPage } from './pages/Saved'
import { SearchPage } from './pages/Search'
import { SignInPage } from './pages/SignIn'

const AdminPage = lazy(() => import('./pages/Admin'))

export function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<HomePage />} />
        <Route path="search" element={<SearchPage />} />
        <Route path="opportunities/:id" element={<OpportunityPage />} />
        <Route path="saved" element={<SavedPage />} />
        <Route path="sign-in" element={<SignInPage />} />
        <Route path="design-system" element={<DesignSystemPage />} />
        <Route path="admin" element={<Suspense fallback={<Skeleton className="h-96" />}><AdminPage /></Suspense>} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  )
}
