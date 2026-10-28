import React from 'react';
import { BrowserRouter, Routes, Route, Navigate, Outlet } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { ToastProvider } from './context/ToastContext';
import { Navbar } from './components/common/Navbar';
import { LoginPage } from './pages/auth/LoginPage';
import { RegisterPage } from './pages/auth/RegisterPage';
import { VerifyEmailPage } from './pages/auth/VerifyEmailPage';
import { ForgotPasswordPage } from './pages/auth/ForgotPasswordPage';
import { ResetPasswordPage } from './pages/auth/ResetPasswordPage';
import { DashboardPage } from './pages/dashboard/DashboardPage';
import { StudentsPage } from './pages/students/StudentsPage';
import { StudentDetailPage } from './pages/students/StudentDetailPage';
import { CounsellingPage } from './pages/counselling/CounsellingPage';
import { AnalyticsPage } from './pages/analytics/AnalyticsPage';
import { FacultyPage } from './pages/faculty/FacultyPage';
import { HodManagementPage } from './pages/admin/HodManagementPage';
import { SubjectsPage } from './pages/hod/SubjectsPage';
import { TeacherSubjectsPage } from './pages/teacher/TeacherSubjectsPage';
import { MarksEntryPage } from './pages/teacher/MarksEntryPage';
import { StudentPortalPage } from './pages/student/StudentPortalPage';
import type { UserRole } from './types';
import { Loader2 } from 'lucide-react';

const ProtectedLayout: React.FC<{ allowedRoles?: UserRole[] }> = ({ allowedRoles }) => {
  const { user, isAuthenticated, loading, hasRole } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-cream-50 dark:bg-charcoal-900">
        <Loader2 className="w-8 h-8 text-clay-500 animate-spin" />
      </div>
    );
  }

  if (!isAuthenticated || !user) {
    return <Navigate to="/login" replace />;
  }

  if (allowedRoles && !hasRole(allowedRoles)) {
    return <Navigate to="/" replace />;
  }

  return (
    <div className="min-h-screen flex flex-col bg-cream-50 dark:bg-charcoal-900 text-ink-900 dark:text-sand-100 transition-colors">
      <Navbar />
      <main className="flex-1">
        <Outlet />
      </main>
    </div>
  );
};

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <ToastProvider>
          <Routes>
            {/* Public Auth Routes */}
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />
            <Route path="/verify-email" element={<VerifyEmailPage />} />
            <Route path="/forgot-password" element={<ForgotPasswordPage />} />
            <Route path="/reset-password" element={<ResetPasswordPage />} />

            {/* Authenticated General Routes */}
            <Route element={<ProtectedLayout />}>
              <Route path="/" element={<DashboardPage />} />
              <Route path="/students/:id" element={<StudentDetailPage />} />
            </Route>

            {/* Admin Dedicated Hierarchy Routes */}
            <Route element={<ProtectedLayout allowedRoles={['admin']} />}>
              <Route path="/admin/hods" element={<HodManagementPage />} />
            </Route>

            {/* HOD & Admin Curriculum Routes */}
            <Route element={<ProtectedLayout allowedRoles={['hod', 'admin']} />}>
              <Route path="/hod/subjects" element={<SubjectsPage />} />
            </Route>

            {/* Teacher, HOD & Admin Teaching / Marks Routes */}
            <Route element={<ProtectedLayout allowedRoles={['teacher', 'hod', 'admin']} />}>
              <Route path="/teacher/subjects" element={<TeacherSubjectsPage />} />
              <Route path="/teacher/marks" element={<MarksEntryPage />} />
            </Route>

            {/* Faculty & Staff Shared Roster & Counselling */}
            <Route element={<ProtectedLayout allowedRoles={['admin', 'hod', 'teacher']} />}>
              <Route path="/students" element={<StudentsPage />} />
              <Route path="/counselling" element={<CounsellingPage />} />
            </Route>

            {/* Admin & HOD Analytics & Faculty Mentorship Management */}
            <Route element={<ProtectedLayout allowedRoles={['admin', 'hod']} />}>
              <Route path="/faculty" element={<FacultyPage />} />
              <Route path="/analytics" element={<AnalyticsPage />} />
            </Route>

            {/* Student Dedicated Self-Service Routes */}
            <Route element={<ProtectedLayout allowedRoles={['student', 'admin', 'hod', 'teacher']} />}>
              <Route path="/student/performance" element={<StudentPortalPage />} />
              <Route path="/student/marks" element={<StudentPortalPage />} />
              <Route path="/student/attendance" element={<StudentPortalPage />} />
              <Route path="/student/backlogs" element={<StudentPortalPage />} />
              <Route path="/student/risk" element={<StudentPortalPage />} />
              <Route path="/student/counselling" element={<StudentPortalPage />} />
              <Route path="/student/study-plan" element={<StudentPortalPage />} />
            </Route>

            {/* Fallback */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </ToastProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}
