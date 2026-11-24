import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import Shell from './components/layout/Shell';
import Login from './pages/Login';
import StaffDashboard from './pages/StaffDashboard';
import NotFound from './pages/NotFound';

export const App: React.FC = () => {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/" element={<Navigate to="/staff" replace />} />
          <Route element={<Shell />}>
            <Route path="/staff" element={<StaffDashboard />} />
            {/* Additional routes will be attached in subsequent milestones */}
            <Route path="/staff/students" element={<StaffDashboard />} />
            <Route path="/staff/settings" element={<StaffDashboard />} />
            <Route path="/staff/plans" element={<StaffDashboard />} />
            <Route path="/staff/customize" element={<StaffDashboard />} />
            <Route path="/staff/demo-videos" element={<StaffDashboard />} />
            <Route path="/staff/faculty" element={<StaffDashboard />} />
            <Route path="/staff/centers" element={<StaffDashboard />} />
            <Route path="/staff/notices" element={<StaffDashboard />} />
          </Route>
          <Route path="*" element={<NotFound />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
};

export default App;
