import React, { useState, useRef, useEffect } from 'react';
import { useAuth } from '../../context/AuthContext';
import { LogOut, Shield, ChevronDown } from 'lucide-react';

export const ProfileDropdown: React.FC = () => {
  const { user, organization, logout } = useAuth();
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  if (!user) return null;

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 p-1.5 rounded-xl hover:bg-slate-100 transition-colors focus:outline-none"
        aria-label="User Menu"
      >
        <div className="w-8 h-8 rounded-full bg-primary-500 text-white flex items-center justify-center font-bold text-sm shadow-sm">
          {user.username.charAt(0).toUpperCase()}
        </div>
        <div className="hidden md:flex flex-col text-left">
          <span className="text-sm font-semibold text-slate-800 leading-tight">
            {user.profile?.full_name || user.username}
          </span>
          <span className="text-xs text-slate-500 leading-none">
            {user.role}
          </span>
        </div>
        <ChevronDown size={14} className="text-slate-400 hidden md:block" />
      </button>

      {isOpen && (
        <div className="absolute right-0 mt-2 w-64 bg-white rounded-2xl shadow-xl border border-slate-200 py-2 z-50 animate-in fade-in slide-in-from-top-1 duration-150">
          <div className="px-4 py-3 border-b border-slate-100">
            <p className="text-sm font-semibold text-slate-900 truncate">
              {user.profile?.full_name || user.username}
            </p>
            <p className="text-xs text-slate-500 truncate">{user.email || user.username}</p>
            {organization && (
              <div className="mt-2 flex items-center gap-1.5 px-2 py-1 rounded-md bg-slate-100 text-xs text-slate-600">
                <Shield size={12} className="text-primary-500" />
                <span className="truncate">{organization.name}</span>
              </div>
            )}
          </div>

          <div className="py-1">
            <div className="px-4 py-2 text-xs font-semibold uppercase text-slate-400">
              Role: <span className="text-primary-600 font-bold">{user.role}</span>
            </div>
          </div>

          <div className="border-t border-slate-100 pt-1">
            <button
              onClick={() => {
                setIsOpen(false);
                logout();
              }}
              className="w-full flex items-center gap-2.5 px-4 py-2 text-sm text-danger-500 hover:bg-red-50 transition-colors"
            >
              <LogOut size={16} />
              <span>Log Out</span>
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default ProfileDropdown;
