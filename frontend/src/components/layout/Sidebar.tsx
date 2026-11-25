import React, { useState } from 'react';
import { NavLink } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import {
  CheckCircle,
  Users,
  Settings,
  CreditCard,
  Palette,
  PlayCircle,
  UserCheck,
  Building2,
  Bell,
  Star,
  ChevronDown,
  ChevronRight,
  BookOpen,
  Layers,
} from 'lucide-react';

interface SidebarProps {
  isOpen: boolean;
}

export const Sidebar: React.FC<SidebarProps> = ({ isOpen }) => {
  const { user } = useAuth();
  const [isManagementOpen, setIsManagementOpen] = useState(true);

  if (!isOpen) return null;

  return (
    <aside className="w-64 min-h-[calc(100vh-4rem)] bg-white border-r border-slate-200 flex flex-col flex-shrink-0 select-none">
      {/* User Profile Card Banner */}
      <div className="bg-gradient-to-r from-navy-900 to-primary-600 p-4 text-white flex items-center gap-3 shadow-inner">
        <div className="w-12 h-12 rounded-full border-2 border-white/60 bg-white/20 flex items-center justify-center font-bold text-lg">
          {user?.username?.charAt(0).toUpperCase() || 'U'}
        </div>
        <div className="overflow-hidden">
          <p className="font-semibold text-sm truncate leading-tight">
            {user?.profile?.full_name || user?.username || 'Staff Member'}
          </p>
          <div className="flex items-center gap-1 mt-0.5">
            <span className="inline-block px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-white/20 text-white">
              {user?.role || 'Staff'}
            </span>
          </div>
        </div>
      </div>

      {/* Main Navigation Menu */}
      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto custom-scrollbar">
        <NavLink
          to="/staff/exams"
          className={({ isActive }) =>
            `flex items-center gap-3 px-3 py-2.5 rounded-xl font-medium text-sm transition-all ${
              isActive
                ? 'bg-primary-50 text-primary-600 font-semibold shadow-sm'
                : 'text-slate-600 hover:text-primary-600 hover:bg-slate-50'
            }`
          }
        >
          <CheckCircle size={18} />
          <span>Exams</span>
        </NavLink>

        <NavLink
          to="/staff/question-bank"
          className={({ isActive }) =>
            `flex items-center gap-3 px-3 py-2.5 rounded-xl font-medium text-sm transition-all ${
              isActive
                ? 'bg-primary-50 text-primary-600 font-semibold shadow-sm'
                : 'text-slate-600 hover:text-primary-600 hover:bg-slate-50'
            }`
          }
        >
          <BookOpen size={18} />
          <span>Question Bank</span>
        </NavLink>

        <NavLink
          to="/staff/students"
          className={({ isActive }) =>
            `flex items-center gap-3 px-3 py-2.5 rounded-xl font-medium text-sm transition-all ${
              isActive
                ? 'bg-primary-50 text-primary-600 font-semibold shadow-sm'
                : 'text-slate-600 hover:text-primary-600 hover:bg-slate-50'
            }`
          }
        >
          <Users size={18} />
          <span>Students</span>
        </NavLink>

        <NavLink
          to="/staff/settings"
          className={({ isActive }) =>
            `flex items-center gap-3 px-3 py-2.5 rounded-xl font-medium text-sm transition-all ${
              isActive
                ? 'bg-primary-50 text-primary-600 font-semibold shadow-sm'
                : 'text-slate-600 hover:text-primary-600 hover:bg-slate-50'
            }`
          }
        >
          <Settings size={18} />
          <span>Settings</span>
        </NavLink>

        <NavLink
          to="/staff/plans"
          className={({ isActive }) =>
            `flex items-center gap-3 px-3 py-2.5 rounded-xl font-medium text-sm transition-all ${
              isActive
                ? 'bg-primary-50 text-primary-600 font-semibold shadow-sm'
                : 'text-slate-600 hover:text-primary-600 hover:bg-slate-50'
            }`
          }
        >
          <CreditCard size={18} />
          <span>Payments & Plans</span>
        </NavLink>

        <NavLink
          to="/staff/customize"
          className={({ isActive }) =>
            `flex items-center gap-3 px-3 py-2.5 rounded-xl font-medium text-sm transition-all ${
              isActive
                ? 'bg-primary-50 text-primary-600 font-semibold shadow-sm'
                : 'text-slate-600 hover:text-primary-600 hover:bg-slate-50'
            }`
          }
        >
          <Palette size={18} />
          <span>Customize Site</span>
        </NavLink>

        <NavLink
          to="/staff/demo-videos"
          className={({ isActive }) =>
            `flex items-center gap-3 px-3 py-2.5 rounded-xl font-medium text-sm transition-all ${
              isActive
                ? 'bg-primary-50 text-primary-600 font-semibold shadow-sm'
                : 'text-slate-600 hover:text-primary-600 hover:bg-slate-50'
            }`
          }
        >
          <PlayCircle size={18} />
          <span>Demo Videos</span>
        </NavLink>

        {/* Institution Management Accordion */}
        <div className="pt-2">
          <button
            onClick={() => setIsManagementOpen(!isManagementOpen)}
            className="w-full flex items-center justify-between px-3 py-2 text-xs font-bold uppercase tracking-wider text-slate-400 hover:text-slate-600"
          >
            <span>Institution Management</span>
            {isManagementOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          </button>

          {isManagementOpen && (
            <div className="mt-1 space-y-1 pl-2">
              <NavLink
                to="/staff/batches"
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-2 rounded-xl text-sm font-medium transition-colors ${
                    isActive
                      ? 'bg-primary-50 text-primary-600 font-semibold'
                      : 'text-slate-600 hover:text-primary-600 hover:bg-slate-50'
                  }`
                }
              >
                <Layers size={16} />
                <span>Batches</span>
              </NavLink>

              <NavLink
                to="/staff/faculty"
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-2 rounded-xl text-sm font-medium transition-colors ${
                    isActive
                      ? 'bg-primary-50 text-primary-600 font-semibold'
                      : 'text-slate-600 hover:text-primary-600 hover:bg-slate-50'
                  }`
                }
              >
                <UserCheck size={16} />
                <span>Faculty</span>
              </NavLink>

              <NavLink
                to="/staff/centers"
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-2 rounded-xl text-sm font-medium transition-colors ${
                    isActive
                      ? 'bg-primary-50 text-primary-600 font-semibold'
                      : 'text-slate-600 hover:text-primary-600 hover:bg-slate-50'
                  }`
                }
              >
                <Building2 size={16} />
                <span>Centres</span>
              </NavLink>

              <NavLink
                to="/staff/notices"
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-2 rounded-xl text-sm font-medium transition-colors ${
                    isActive
                      ? 'bg-primary-50 text-primary-600 font-semibold'
                      : 'text-slate-600 hover:text-primary-600 hover:bg-slate-50'
                  }`
                }
              >
                <Bell size={16} />
                <span>Notices</span>
              </NavLink>
            </div>
          )}
        </div>
      </nav>

      {/* Bottom Upgrade CTA */}
      <div className="p-3 border-t border-slate-200">
        <div className="bg-gradient-to-br from-amber-50 to-amber-100/60 border border-amber-200 rounded-2xl p-3">
          <div className="flex items-center gap-2 text-amber-800 font-semibold text-xs">
            <Star size={16} className="text-amber-500 fill-amber-500" />
            <span>Exam-Kraft Dedicated</span>
          </div>
          <p className="text-[11px] text-amber-700 mt-1 leading-snug">
            Support for 500+ concurrent live candidates and dedicated database.
          </p>
          <button className="mt-2.5 w-full bg-accent-gold hover:bg-[#e69b14] text-white py-1.5 px-3 rounded-xl text-xs font-bold transition-colors shadow-sm">
            Upgrade Plan
          </button>
        </div>
      </div>
    </aside>
  );
};

export default Sidebar;
