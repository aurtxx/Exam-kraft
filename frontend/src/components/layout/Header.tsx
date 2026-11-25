import React from 'react';
import { useAuth } from '../../context/AuthContext';
import { Menu, Search, HelpCircle, Bell } from 'lucide-react';
import ProfileDropdown from './ProfileDropdown';

interface HeaderProps {
  onToggleSidebar: () => void;
  isSidebarOpen: boolean;
}

export const Header: React.FC<HeaderProps> = ({ onToggleSidebar }) => {
  const { organization } = useAuth();

  return (
    <header className="h-16 bg-white border-b border-slate-200 px-4 flex items-center justify-between z-30 sticky top-0 shadow-sm">
      {/* Left: Menu toggle & Brand */}
      <div className="flex items-center gap-3">
        <button
          onClick={onToggleSidebar}
          className="w-10 h-10 rounded-xl flex items-center justify-center hover:bg-slate-100 text-slate-600 hover:text-primary-500 transition-colors focus:outline-none"
          aria-label="Toggle Sidebar"
        >
          <Menu size={20} />
        </button>

        <div className="flex items-center gap-2">
          {organization?.settings?.logo_url ? (
            <img
              src={organization.settings.logo_url}
              alt={organization.name}
              className="h-8 max-w-[120px] object-contain"
            />
          ) : (
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-primary-600 to-primary-400 flex items-center justify-center text-white font-black text-base shadow-sm">
                EK
              </div>
              <span className="font-bold text-lg text-navy-900 tracking-tight">
                {organization?.name || 'Exam-Kraft'}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Center: Global Search Bar */}
      <div className="hidden md:flex items-center flex-1 max-w-md mx-8">
        <div className="relative w-full">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            placeholder="Find Students, Exams, or Batches..."
            className="w-full pl-9 pr-4 py-1.5 rounded-xl bg-slate-100 border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500 transition-all placeholder:text-slate-400"
          />
        </div>
      </div>

      {/* Right: Actions, Plans & User Profile */}
      <div className="flex items-center gap-3">
        <button className="hidden sm:inline-flex items-center gap-1.5 bg-accent-gold hover:bg-[#e69b14] text-white px-3.5 py-1.5 rounded-full text-xs font-semibold uppercase tracking-wider shadow-sm transition-colors">
          <span>Pro Plans</span>
        </button>

        <button
          className="w-9 h-9 rounded-xl flex items-center justify-center text-slate-500 hover:bg-slate-100 hover:text-primary-500 transition-colors"
          title="Notifications"
        >
          <Bell size={18} />
        </button>

        <button
          className="w-9 h-9 rounded-xl flex items-center justify-center text-slate-500 hover:bg-slate-100 hover:text-primary-500 transition-colors"
          title="Help & Support"
        >
          <HelpCircle size={18} />
        </button>

        <div className="h-6 w-px bg-slate-200 mx-1" />

        <ProfileDropdown />
      </div>
    </header>
  );
};

export default Header;
