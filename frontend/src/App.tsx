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
            <Route path="/student/exam/:id/test" element={<ExamCBTPage />} />
            <Route path="/student/exam/:id/finish" element={<ExamFinishPage />} />
            <Route path="/student/exam/:id/report" element={<ExamResultReportPage />} />
            <Route path="/student/exam/:id/results" element={<ExamResultReportPage />} />
            <Route path="/student/attempts/:id/report" element={<ExamResultReportPage />} />
            <Route path="/student/results/:id" element={<ExamResultReportPage />} />
            <Route path="/online-exams/:id" element={<ExamLobbyPage />} />
            <Route path="/online-exams/:id/test" element={<ExamCBTPage />} />
          </Route>

          <Route element={<ProtectedRoutes />}>
            <Route element={<Shell />}>
              <Route path="/staff" element={<Navigate to="/staff/exams" replace />} />
              <Route path="/staff/exams" element={<ExaminationsPage />} />
              <Route path="/staff/examinations" element={<ExaminationsPage />} />
              <Route path="/staff/exams/:id/analytics" element={<BatchAnalyticsPage />} />
              <Route path="/staff/examinations/:id/analytics" element={<BatchAnalyticsPage />} />
              <Route path="/staff/analytics/:id" element={<BatchAnalyticsPage />} />
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
