import React from 'react';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';
import { CheckCircle2, Award, ArrowLeft } from 'lucide-react';
import { SubmitResult } from '../../services/studentExamApi';

export const ExamFinishPage: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();

  const state = location.state as { submitResult?: SubmitResult; examName?: string } | undefined;
  const result = state?.submitResult;
  const examName = state?.examName || 'Examination';

  if (!result) return <Navigate to="/student" replace />;

  return (
    <div className="min-h-screen bg-slate-100 flex flex-col items-center justify-center p-6 font-sans">
      <div className="bg-white rounded-3xl max-w-lg w-full p-8 shadow-xl border border-slate-200 text-center flex flex-col items-center space-y-6">
        {/* Success Icon */}
        <div className="w-20 h-20 rounded-full bg-emerald-100 text-emerald-600 flex items-center justify-center shadow-inner animate-in zoom-in-75 duration-300">
          <CheckCircle2 className="w-12 h-12 stroke-[2.5]" />
        </div>

        {/* Title & Message */}
        <div className="space-y-2">
          <span className="text-xs font-bold uppercase tracking-widest text-emerald-600 bg-emerald-50 px-3 py-1 rounded-full border border-emerald-200">
            Attempt Submitted Successfully
          </span>
          <h1 className="text-2xl font-extrabold text-slate-800">{examName}</h1>
          <p className="text-xs text-slate-600 max-w-sm mx-auto leading-relaxed">
            Your answers and telemetry have been securely synchronized with the central evaluation server.
          </p>
        </div>

        {/* Metadata Details Card */}
        <div className="w-full bg-slate-50 border border-slate-200 rounded-2xl p-4 text-xs space-y-2.5 text-slate-700">
          <div className="flex items-center justify-between border-b border-slate-200 pb-2">
            <span className="text-slate-500 font-medium">Status:</span>
            <span className="font-bold text-emerald-600 uppercase">
              {result.submission_status}
            </span>
          </div>
          <div className="flex items-center justify-between border-b border-slate-200 pb-2">
            <span className="text-slate-500 font-medium">Attempt ID:</span>
            <span className="font-mono text-slate-800 font-bold">
              {result.attempt_id}
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-slate-500 font-medium">Submitted At:</span>
            <span className="font-mono text-slate-800">
              {new Date(result.submitted_at).toLocaleString()}
            </span>
          </div>
        </div>

        <div className="bg-primary-50 border border-primary-200 rounded-xl p-3.5 text-xs text-primary-900 leading-relaxed flex items-center gap-2.5 text-left">
          <Award className="w-5 h-5 text-primary-600 flex-shrink-0" />
          <span>
            Results, scores, and comparative cohort analytics will be published by your institution once grading is finalized.
          </span>
        </div>

        {/* Action Buttons */}
        <div className="w-full flex flex-col sm:flex-row items-center justify-center gap-3 pt-2">
          <button
            type="button"
            onClick={() => navigate(`/student/attempts/${result.attempt_id}/report`)}
            className="w-full sm:flex-1 py-3 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs transition-colors shadow-sm flex items-center justify-center gap-2"
          >
            <Award className="w-4 h-4" />
            <span>View Performance Report</span>
          </button>
          <button
            type="button"
            onClick={() => navigate('/student')}
            className="w-full sm:flex-1 py-3 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold text-xs transition-colors flex items-center justify-center gap-2"
          >
            <ArrowLeft className="w-4 h-4" />
            <span>My Examinations</span>
          </button>
        </div>
      </div>
    </div>
  );
};

export default ExamFinishPage;
