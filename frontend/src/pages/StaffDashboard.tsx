import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiService } from '../services/api';
import type { Examination } from '../types';
import { useAuth } from '../context/AuthContext';
import {
  FileText,
  Users,
  Building2,
  CheckCircle,
  Plus,
  Search,
  Calendar,
  Layers,
} from 'lucide-react';

type ExamStatusFilter = 'ALL' | 'PUBLISHED' | 'DRAFT' | 'SCHEDULED' | 'CLOSED';

export const StaffDashboard: React.FC = () => {
  const { user, organization } = useAuth();
  const navigate = useNavigate();
  const [exams, setExams] = useState<Examination[]>([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedStatus, setSelectedStatus] = useState<ExamStatusFilter>('ALL');
  const [loadState, setLoadState] = useState<'loading' | 'ready' | 'error'>('loading');
  const [counts, setCounts] = useState<{
    students: number | null;
    papers: number | null;
    centers: number | null;
  } | null>(null);

  useEffect(() => {
    let cancelled = false;
    setExams([]);
    setLoadState('loading');
    setCounts(null);
    apiService.getExaminations().then(
      (data) => {
        if (!cancelled) {
          setExams(data);
          setLoadState('ready');
        }
      },
      () => {
        if (!cancelled) setLoadState('error');
      },
    );
    Promise.allSettled([
      apiService.getStudents({ page_size: 1 }),
      apiService.getQuestionBanks(),
      apiService.getCenters(),
    ]).then(([students, papers, centers]) => {
      if (!cancelled) {
        setCounts({
          students: students.status === 'fulfilled' ? students.value.count : null,
          papers: papers.status === 'fulfilled' ? papers.value.length : null,
          centers: centers.status === 'fulfilled' ? centers.value.length : null,
        });
      }
    });
    return () => { cancelled = true; };
  }, [organization?.id]);

  const query = searchTerm.trim().toLowerCase();
  const filteredExams = exams.filter(
    (exam) => (selectedStatus === 'ALL' || exam.status === selectedStatus)
      && (exam.name.toLowerCase().includes(query) || exam.code?.toLowerCase().includes(query)),
  );
  const activeExamCount = loadState === 'ready'
    ? exams.filter((exam) => exam.status === 'PUBLISHED' || exam.status === 'SCHEDULED').length
    : '—';

  return (
    <div className="space-y-6">
      {/* Top Banner / Welcome */}
      <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl md:text-2xl font-bold text-slate-900 tracking-tight">
            Welcome back, {user?.profile?.full_name || user?.username}
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Active Institution: <span className="font-semibold text-primary-600">{organization?.name || '—'}</span>
            {organization?.slug && <span className="text-xs text-slate-400 ml-2">({organization.slug})</span>}
          </p>
        </div>

        <div className="flex items-center gap-3 flex-wrap">
          <button type="button" onClick={() => navigate('/staff/examinations')} className="inline-flex items-center gap-2 bg-primary-500 hover:bg-primary-600 text-white font-semibold text-sm px-4 py-2 rounded-xl transition-all shadow-sm">
            <Plus size={16} />
            <span>Create Exam</span>
          </button>
          <button type="button" onClick={() => navigate('/staff/students')} className="inline-flex items-center gap-2 bg-white hover:bg-slate-50 text-slate-700 border border-slate-200 font-semibold text-sm px-4 py-2 rounded-xl transition-all shadow-sm">
            <Users size={16} />
            <span>Add Student</span>
          </button>
        </div>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-sm flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-blue-50 text-primary-500 flex items-center justify-center font-bold">
            <CheckCircle size={24} />
          </div>
          <div>
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Active Exams</p>
            <p className="text-2xl font-bold text-slate-900 mt-0.5">{activeExamCount}</p>
          </div>
        </div>

        <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-sm flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-emerald-50 text-success-500 flex items-center justify-center font-bold">
            <Users size={24} />
          </div>
          <div>
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Enrolled Students</p>
            <p className="text-2xl font-bold text-slate-900 mt-0.5">{counts?.students ?? '—'}</p>
          </div>
        </div>

        <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-sm flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-purple-50 text-review-500 flex items-center justify-center font-bold">
            <FileText size={24} />
          </div>
          <div>
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Question Papers</p>
            <p className="text-2xl font-bold text-slate-900 mt-0.5">{counts?.papers ?? '—'}</p>
          </div>
        </div>

        <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-sm flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-amber-50 text-amber-500 flex items-center justify-center font-bold">
            <Building2 size={24} />
          </div>
          <div>
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Exam Centers</p>
            <p className="text-2xl font-bold text-slate-900 mt-0.5">{counts?.centers ?? '—'}</p>
          </div>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="bg-white rounded-2xl p-4 border border-slate-200 shadow-sm flex flex-col md:flex-row items-center justify-between gap-3">
        <div className="relative w-full md:w-80">
          <Search size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            aria-label="Search examinations"
            placeholder="Search examinations..."
            value={searchTerm}
            onChange={(event) => setSearchTerm(event.target.value)}
            className="w-full pl-9 pr-4 py-2 rounded-xl bg-slate-50 border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500 transition-all placeholder:text-slate-400"
          />
        </div>

        <div className="flex items-center gap-2 w-full md:w-auto">
          <select
            aria-label="Examination status"
            value={selectedStatus}
            onChange={(event) => setSelectedStatus(event.target.value as ExamStatusFilter)}
            className="px-3 py-2 rounded-xl border border-slate-200 bg-white text-xs font-semibold text-slate-600 hover:bg-slate-50"
          >
            <option value="ALL">All Statuses</option>
            <option value="PUBLISHED">Published</option>
            <option value="DRAFT">Draft</option>
            <option value="SCHEDULED">Scheduled</option>
            <option value="CLOSED">Closed</option>
          </select>
          <button className="flex items-center gap-1.5 px-3 py-2 rounded-xl border border-slate-200 text-xs font-semibold text-slate-600 hover:bg-slate-50">
            <Calendar size={14} />
            <span>This Month</span>
          </button>
        </div>
      </div>

      {/* Data Table Container */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
          <h2 className="font-semibold text-base text-slate-800 flex items-center gap-2">
            <Layers size={18} className="text-primary-500" />
            <span>Scheduled & Ongoing Examinations</span>
          </h2>
          <span className="text-xs font-medium text-slate-400">Tenant Scoped Data</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm text-slate-600">
            <thead className="bg-slate-50 text-xs uppercase font-semibold text-slate-500 border-b border-slate-100">
              <tr>
                <th className="px-6 py-3">Exam Name</th>
                <th className="px-6 py-3">Code</th>
                <th className="px-6 py-3">Duration</th>
                <th className="px-6 py-3">Window</th>
                <th className="px-6 py-3">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filteredExams.map((exam) => (
                <tr key={exam.id} className="hover:bg-slate-50/70 transition-colors">
                  <td className="px-6 py-4 font-semibold text-slate-900">{exam.name}</td>
                  <td className="px-6 py-4 font-mono text-xs text-slate-500">{exam.code || '—'}</td>
                  <td className="px-6 py-4">{exam.duration_minutes} mins</td>
                  <td className="px-6 py-4 text-xs text-slate-500">
                    {exam.start_window ? new Date(exam.start_window).toLocaleString() : '—'}
                    {' – '}
                    {exam.end_window ? new Date(exam.end_window).toLocaleString() : '—'}
                  </td>
                  <td className="px-6 py-4">{exam.status}</td>
                </tr>
              ))}
              {filteredExams.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-6 py-8 text-center" role="status">
                    {loadState === 'loading' && 'Loading examinations…'}
                    {loadState === 'error' && 'Unable to load examinations.'}
                    {loadState === 'ready' && 'No examinations found.'}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default StaffDashboard;
