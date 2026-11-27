import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import ProtectedRoutes, { RoleHome } from './components/layout/ProtectedRoutes';
import CandidatePortal from './pages/student/CandidatePortal';
import Shell from './components/layout/Shell';
import Login from './pages/Login';
import StaffDashboard from './pages/StaffDashboard';
import BatchesPage from './pages/staff/BatchesPage';
import CentersPage from './pages/staff/CentersPage';
import FacultyPage from './pages/staff/FacultyPage';
import StudentsPage from './pages/staff/StudentsPage';
import QuestionBankPage from './pages/staff/QuestionBankPage';
import ExaminationsPage from './pages/staff/ExaminationsPage';
import NoticesPage from './pages/staff/NoticesPage';
import ExamLobbyPage from './pages/student/ExamLobbyPage';
import ExamCBTPage from './pages/student/ExamCBTPage';
import ExamFinishPage from './pages/student/ExamFinishPage';
import ExamResultReportPage from './pages/student/ExamResultReportPage';
import BatchAnalyticsPage from './pages/staff/BatchAnalyticsPage';
import NotFound from './pages/NotFound';

class ExamErrorBoundary extends React.Component<
  { children: React.ReactNode },
  { hasError: boolean }
> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(): { hasError: boolean } {
    return { hasError: true };
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen flex items-center justify-center bg-slate-50 p-6">
          <div className="max-w-md w-full bg-white rounded-2xl border border-slate-200 p-6 text-center shadow-sm space-y-4">
            <h2 className="text-lg font-bold text-slate-900">
              An error occurred — your progress is auto-saved
            </h2>
            <p className="text-sm text-slate-600">
              You can reload the page to resume your exam or return to the student portal.
            </p>
            <div className="flex items-center justify-center gap-3 pt-2">
              <button
                type="button"
                onClick={() => window.location.reload()}
                className="px-4 py-2 rounded-lg bg-[#2d8df1] text-white text-sm font-semibold hover:bg-[#1f7ad8]"
              >
                Reload Exam
              </button>
              <a
                href="/student"
                className="px-4 py-2 rounded-lg border border-slate-300 text-slate-700 text-sm font-semibold hover:bg-slate-50"
              >
                Return to Portal
              </a>
            </div>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

export const App: React.FC = () => {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/" element={<RoleHome />} />

          {/* Student CBT Examination Engine Routes */}
          <Route element={<ProtectedRoutes student />}>
            <Route path="/student" element={<CandidatePortal />} />
            <Route path="/student/exam/:id/lobby" element={<ExamLobbyPage />} />
            <Route path="/student/exam/:id/test" element={<ExamErrorBoundary><ExamCBTPage /></ExamErrorBoundary>} />
            <Route path="/student/exam/:id/finish" element={<ExamFinishPage />} />
            <Route path="/student/attempts/:id/report" element={<ExamResultReportPage />} />
            <Route path="/online-exams/:id" element={<ExamLobbyPage />} />
            <Route path="/online-exams/:id/test" element={<ExamErrorBoundary><ExamCBTPage /></ExamErrorBoundary>} />
          </Route>

          <Route element={<ProtectedRoutes />}>
            <Route element={<Shell />}>
              <Route path="/staff" element={<Navigate to="/staff/exams" replace />} />
              <Route path="/staff/exams" element={<ExaminationsPage />} />
              <Route path="/staff/examinations" element={<ExaminationsPage />} />
              <Route path="/staff/exams/:id/analytics" element={<BatchAnalyticsPage />} />
              <Route path="/staff/examinations/:id/analytics" element={<BatchAnalyticsPage />} />
              <Route path="/staff/analytics/:id" element={<BatchAnalyticsPage />} />
              <Route path="/staff/attempts/:id/report" element={<ExamResultReportPage />} />
              <Route path="/staff/reports" element={<ExaminationsPage />} />
              <Route path="/staff/question-bank" element={<QuestionBankPage />} />
              <Route path="/staff/students" element={<StudentsPage />} />
              <Route path="/staff/batches" element={<BatchesPage />} />
              <Route path="/staff/centers" element={<CentersPage />} />
              <Route path="/staff/faculty" element={<FacultyPage />} />
              <Route path="/staff/notices" element={<NoticesPage />} />
              <Route path="/staff/settings" element={<StaffDashboard />} />
              <Route path="/staff/plans" element={<StaffDashboard />} />
              <Route path="/staff/customize" element={<StaffDashboard />} />
              <Route path="/staff/demo-videos" element={<StaffDashboard />} />
              <Route path="/staff/*" element={<NotFound />} />
            </Route>
          </Route>
          <Route path="*" element={<NotFound />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
};

export default App;
