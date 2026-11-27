import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  AlertCircle,
  ArrowRight,
  BookOpen,
  Calendar,
  Clock,
  LogOut,
  RefreshCw,
  ShieldCheck,
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import studentExamApi, { CandidateExamination } from '../../services/studentExamApi';

function getWindowBadge(exam: CandidateExamination, nowMs: number) {
  const startsAt = exam.start_window ? Date.parse(exam.start_window) : null;
  const endsAt = exam.end_window ? Date.parse(exam.end_window) : null;

  if (endsAt && endsAt <= nowMs) {
    return {
      label: 'Closed',
      className: 'bg-slate-100 text-slate-600 border-slate-200',
    };
  }
  if (startsAt && startsAt > nowMs) {
    return {
      label: 'Upcoming',
      className: 'bg-amber-50 text-amber-700 border-amber-200',
    };
  }
  return {
    label: 'Available Now',
    className: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  };
}

export default function CandidatePortal() {
  const { user, logout } = useAuth();
  const [exams, setExams] = useState<CandidateExamination[] | null>(null);
  const [failed, setFailed] = useState(false);

  const loadExaminations = useCallback(() => {
    let active = true;
    setFailed(false);
    setExams(null);
    studentExamApi.listExaminations().then(
      (items) => { if (active) setExams(items); },
      () => { if (active) setFailed(true); },
    );
    return () => { active = false; };
  }, []);

  useEffect(() => loadExaminations(), [loadExaminations]);

  const nowMs = Date.now();
  const candidateDisplayName = user?.profile?.full_name || user?.username || 'Candidate';

  return (
    <div className="min-h-screen bg-slate-100">
      <header className="bg-white border-b border-slate-200 shadow-xs sticky top-0 z-20">
        <div className="mx-auto max-w-4xl px-4 sm:px-6 py-4 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3 min-w-0">
            <div className="w-10 h-10 rounded-xl bg-primary-600 flex items-center justify-center text-white font-extrabold text-base shadow-xs flex-shrink-0">
              EK
            </div>
            <div className="min-w-0">
              <h1 className="text-xl font-bold text-slate-900 leading-tight truncate">
                My Examinations
              </h1>
              <p className="text-xs text-slate-500 truncate">{candidateDisplayName}</p>
            </div>
          </div>
          <button
            type="button"
            className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl border border-slate-200 bg-white hover:bg-slate-50 text-xs font-semibold text-slate-700 transition-colors"
            onClick={() => void logout()}
          >
            <LogOut className="w-3.5 h-3.5" />
            <span>Sign out</span>
          </button>
        </div>
      </header>

      <main className="mx-auto max-w-4xl space-y-4 px-4 sm:px-6 py-6">
        {failed && (
          <div
            role="alert"
            className="bg-white rounded-2xl border border-rose-200 p-6 shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-4"
          >
            <div className="flex items-start gap-3">
              <div className="w-10 h-10 rounded-xl bg-rose-50 text-rose-600 flex items-center justify-center flex-shrink-0">
                <AlertCircle className="w-5 h-5" />
              </div>
              <div>
                <h2 className="text-sm font-bold text-slate-900">Could not load examinations</h2>
                <p className="text-xs text-slate-600 mt-0.5">
                  Please check your connection and try refreshing your assigned tests.
                </p>
              </div>
            </div>
            <button
              type="button"
              onClick={loadExaminations}
              className="inline-flex items-center justify-center gap-1.5 px-4 py-2 rounded-xl bg-primary-600 hover:bg-primary-700 text-white text-xs font-semibold transition-colors flex-shrink-0"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              <span>Retry</span>
            </button>
          </div>
        )}

        {!failed && exams === null && (
          <div role="status" aria-busy="true" className="space-y-4">
            <span className="sr-only">Loading examinations…</span>
            {[0, 1, 2].map((idx) => (
              <div
                key={idx}
                className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs animate-pulse space-y-3"
              >
                <div className="flex items-center justify-between gap-4">
                  <div className="h-5 w-56 bg-slate-200 rounded-md" />
                  <div className="h-5 w-24 bg-slate-100 rounded-full" />
                </div>
                <div className="flex flex-wrap gap-3">
                  <div className="h-4 w-28 bg-slate-100 rounded-md" />
                  <div className="h-4 w-44 bg-slate-100 rounded-md" />
                </div>
                <div className="pt-2 flex justify-end">
                  <div className="h-9 w-32 bg-slate-200 rounded-xl" />
                </div>
              </div>
            ))}
          </div>
        )}

        {!failed && exams?.length === 0 && (
          <div className="rounded-2xl border border-slate-200 bg-white p-10 text-center shadow-xs space-y-3">
            <div className="w-12 h-12 rounded-2xl bg-slate-100 text-slate-500 flex items-center justify-center mx-auto">
              <BookOpen className="w-6 h-6" />
            </div>
            <h2 className="text-base font-bold text-slate-800">
              No current or upcoming examinations
            </h2>
            <p className="text-xs text-slate-500 max-w-sm mx-auto">
              Tests assigned to your batch or examination centre will appear here once published by your institution.
            </p>
            <button
              type="button"
              onClick={loadExaminations}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl border border-slate-200 bg-slate-50 hover:bg-slate-100 text-xs font-semibold text-slate-700 transition-colors"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              <span>Check Again</span>
            </button>
          </div>
        )}

        {exams?.map((exam) => {
          const badge = getWindowBadge(exam, nowMs);
          return (
            <article
              key={exam.id}
              className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs hover:shadow-md transition-shadow flex flex-col sm:flex-row sm:items-center justify-between gap-4"
            >
              <div className="space-y-2 min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="font-bold text-base text-slate-900 truncate">{exam.name}</h2>
                  <span
                    className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-[11px] font-semibold border ${badge.className}`}
                  >
                    {badge.label}
                  </span>
                </div>
                <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-600">
                  <span className="inline-flex items-center gap-1.5">
                    <Clock className="w-3.5 h-3.5 text-slate-400" />
                    <span>{exam.duration_minutes} minutes</span>
                  </span>
                  {exam.start_window && (
                    <span className="inline-flex items-center gap-1.5">
                      <Calendar className="w-3.5 h-3.5 text-slate-400" />
                      <span>Opens {new Date(exam.start_window).toLocaleString()}</span>
                    </span>
                  )}
                  {exam.camera_proctoring && (
                    <span className="inline-flex items-center gap-1.5 text-slate-500">
                      <ShieldCheck className="w-3.5 h-3.5 text-slate-400" />
                      <span>Proctored</span>
                    </span>
                  )}
                </div>
              </div>

              <Link
                className="inline-flex items-center justify-center gap-1.5 px-4 py-2.5 rounded-xl bg-primary-600 hover:bg-primary-700 text-white text-xs font-bold transition-colors shadow-xs flex-shrink-0"
                to={`/student/exam/${exam.id}/lobby`}
              >
                <span>Open lobby</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </Link>
            </article>
          );
        })}
      </main>
    </div>
  );
}
