import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Clock,
  Award,
  AlertCircle,
  Camera,
  Maximize2,
  CheckCircle2,
  ShieldAlert,
  ArrowRight,
  BookOpen,
} from 'lucide-react';
import studentExamApi from '../../services/studentExamApi';
import apiClient from '../../services/api';
import { Examination } from '../../types';

export const ExamLobbyPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [exam, setExam] = useState<Examination | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [declared, setDeclared] = useState(false);
  const [webcamReady, setWebcamReady] = useState(false);
  const [starting, setStarting] = useState(false);

  useEffect(() => {
    const fetchExam = async () => {
      if (!id) return;
      try {
        setLoading(true);
        // Try preview or list to fetch metadata
        const res = await apiClient.get<{ exam: Examination }>(`/examinations/${id}/preview/`);
        if (res.data?.exam) {
          setExam(res.data.exam);
        }
      } catch (err: unknown) {
        // Fallback: exam details might still be loadable upon start
        console.warn('Could not prefetch exam preview, will load at start', err);
      } finally {
        setLoading(false);
      }
    };
    fetchExam();
  }, [id]);

  const handleStartExam = async () => {
    if (!id || !declared) return;
    try {
      setStarting(true);
      setError(null);
      const payload = await studentExamApi.startExam(id);
      // Navigate to test screen with attempt payload state
      navigate(`/student/exam/${id}/test`, {
        state: { attemptPayload: payload },
      });
    } catch (err: unknown) {
      const e = err as { response?: { data?: { message?: string; code?: string } } };
      const msg = e.response?.data?.message || 'Failed to start examination. Please check eligibility or try again.';
      setError(msg);
      setStarting(false);
    }
  };

  const handleTestWebcam = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true });
      if (stream) {
        setWebcamReady(true);
        // Stop test stream after verification
        stream.getTracks().forEach((track) => track.stop());
      }
    } catch {
      setWebcamReady(false);
      alert('Camera access denied or no webcam found. Please allow camera permissions.');
    }
  };

  const handleFullscreenRequest = () => {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen().catch((err) => {
        console.warn('Fullscreen request failed', err);
      });
    }
  };

  return (
    <div className="min-h-screen bg-slate-100 flex flex-col font-sans">
      {/* Top Header */}
      <header className="bg-white border-b border-slate-200 px-6 py-4 shadow-xs">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-primary-600 flex items-center justify-center text-white font-extrabold text-xl shadow-sm">
              EZ
            </div>
            <div>
              <h1 className="text-lg font-bold text-slate-800 leading-tight">
                {exam?.name || 'Computer Based Test Examination Portal'}
              </h1>
              <p className="text-xs text-slate-500 font-medium">
                National Testing Agency (NTA) Standard CBT Delivery Engine
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 text-xs font-semibold px-3 py-1.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
            Server Ready & Synchronized
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main className="max-w-6xl mx-auto w-full p-6 flex-1 flex flex-col gap-6">
        {error && (
          <div className="bg-rose-50 border border-rose-200 text-rose-700 p-4 rounded-xl flex items-center gap-3 text-sm">
            <AlertCircle className="w-5 h-5 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Column: Instructions & Guidelines */}
          <div className="lg:col-span-2 bg-white rounded-2xl border border-slate-200 p-6 shadow-sm flex flex-col gap-5">
            <div className="flex items-center gap-2 border-b border-slate-200 pb-3">
              <BookOpen className="w-5 h-5 text-primary-600" />
              <h2 className="text-base font-bold text-slate-800">General Examination Instructions</h2>
            </div>

            <div className="space-y-4 text-xs text-slate-700 leading-relaxed overflow-y-auto max-h-[500px] pr-2">
              <section>
                <h3 className="font-bold text-slate-800 mb-1.5 flex items-center gap-1.5 text-xs uppercase tracking-wider text-primary-700">
                  1. Timing & Clock Enforcement
                </h3>
                <ul className="list-disc pl-5 space-y-1 text-slate-600">
                  <li>
                    The test clock will be automatically synchronized with the server clock. A countdown timer at the top right of your screen will display the remaining time available to you.
                  </li>
                  <li>
                    When the timer reaches zero, the examination will automatically conclude and submit your attempt. You are not required to terminate the test manually.
                  </li>
                </ul>
              </section>

              <section>
                <h3 className="font-bold text-slate-800 mb-1.5 flex items-center gap-1.5 text-xs uppercase tracking-wider text-primary-700">
                  2. Question Palette & Navigation (5 Canonical States)
                </h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 my-2 text-[11px]">
                  <div className="flex items-center gap-2 p-2 bg-slate-50 border border-slate-200 rounded-lg">
                    <span className="w-6 h-6 rounded bg-[#dcdcdc] text-slate-700 font-bold flex items-center justify-center text-xs">
                      1
                    </span>
                    <span><strong>Not Visited</strong>: You have not visited this question yet.</span>
                  </div>
                  <div className="flex items-center gap-2 p-2 bg-rose-50 border border-rose-200 rounded-lg">
                    <span className="w-6 h-6 rounded bg-[#FF614D] text-white font-bold flex items-center justify-center text-xs">
                      2
                    </span>
                    <span><strong>Not Answered</strong>: You have visited but not answered.</span>
                  </div>
                  <div className="flex items-center gap-2 p-2 bg-emerald-50 border border-emerald-200 rounded-lg">
                    <span className="w-6 h-6 rounded bg-[#22C969] text-white font-bold flex items-center justify-center text-xs">
                      3
                    </span>
                    <span><strong>Answered</strong>: You have selected an answer.</span>
                  </div>
                  <div className="flex items-center gap-2 p-2 bg-purple-50 border border-purple-200 rounded-lg">
                    <span className="w-6 h-6 rounded-full bg-[#9967ff] text-white font-bold flex items-center justify-center text-xs">
                      4
                    </span>
                    <span><strong>Marked for Review</strong>: Flagged for review without answer.</span>
                  </div>
                  <div className="flex items-center gap-2 p-2 bg-purple-50 border border-purple-200 rounded-lg sm:col-span-2">
                    <span className="w-6 h-6 rounded-md bg-[#9967ff] text-white font-bold flex items-center justify-center text-xs relative">
                      5
                      <span className="absolute -top-1 -right-1 w-2.5 h-2.5 bg-emerald-400 rounded-full"></span>
                    </span>
                    <span>
                      <strong>Answered & Marked for Review</strong>: Answer selected and flagged for review. <em>This question WILL be evaluated in final scoring.</em>
                    </span>
                  </div>
                </div>
              </section>

              <section>
                <h3 className="font-bold text-slate-800 mb-1.5 flex items-center gap-1.5 text-xs uppercase tracking-wider text-rose-700">
                  3. Proctoring & Anti-Cheating Protocol
                </h3>
                <ul className="list-disc pl-5 space-y-1 text-slate-600">
                  <li>
                    Navigating outside the examination tab or minimizing your browser window will log an infraction telemetry record.
                  </li>
                  <li>
                    Exceeding the allowable window switch limit (maximum 3 switches) will immediately trigger automated termination and lock your submission.
                  </li>
                  <li>
                    Periodic webcam snapshots will be captured to verify candidate identity and continuous test integrity.
                  </li>
                </ul>
              </section>
            </div>
          </div>

          {/* Right Column: Exam Details & Readiness Checklist */}
          <div className="flex flex-col gap-5">
            {/* Exam Snapshot Card */}
            <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm space-y-4">
              <h3 className="text-sm font-bold text-slate-800 border-b border-slate-200 pb-2">
                Examination Snapshot
              </h3>
              <div className="space-y-3 text-xs">
                <div className="flex items-center justify-between text-slate-600">
                  <span className="flex items-center gap-1.5">
                    <Clock className="w-4 h-4 text-primary-600" /> Duration:
                  </span>
                  <span className="font-bold text-slate-800">
                    {exam?.duration_minutes || 60} Minutes
                  </span>
                </div>
                <div className="flex items-center justify-between text-slate-600">
                  <span className="flex items-center gap-1.5">
                    <Award className="w-4 h-4 text-amber-500" /> Total Marks:
                  </span>
                  <span className="font-bold text-slate-800">
                    {exam?.total_marks ? `${exam.total_marks} Marks` : 'Configured on Test'}
                  </span>
                </div>
                <div className="flex items-center justify-between text-slate-600">
                  <span className="flex items-center gap-1.5">
                    <ShieldAlert className="w-4 h-4 text-purple-600" /> Max Tab Switches:
                  </span>
                  <span className="font-bold text-slate-800">
                    {exam?.max_window_switches || 3} Allowed
                  </span>
                </div>
              </div>
            </div>

            {/* Hardware Readiness Card */}
            <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm space-y-3">
              <h3 className="text-sm font-bold text-slate-800">System Readiness Check</h3>
              
              <div className="flex items-center justify-between p-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs">
                <div className="flex items-center gap-2">
                  <Camera className="w-4 h-4 text-slate-600" />
                  <span className="text-slate-700">Webcam Check:</span>
                </div>
                {webcamReady ? (
                  <span className="text-emerald-600 font-bold flex items-center gap-1">
                    <CheckCircle2 className="w-4 h-4" /> Ready
                  </span>
                ) : (
                  <button
                    type="button"
                    onClick={handleTestWebcam}
                    className="text-primary-600 hover:text-primary-700 font-bold underline text-xs"
                  >
                    Test Camera
                  </button>
                )}
              </div>

              <div className="flex items-center justify-between p-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs">
                <div className="flex items-center gap-2">
                  <Maximize2 className="w-4 h-4 text-slate-600" />
                  <span className="text-slate-700">Fullscreen Mode:</span>
                </div>
                <button
                  type="button"
                  onClick={handleFullscreenRequest}
                  className="text-primary-600 hover:text-primary-700 font-bold underline text-xs"
                >
                  Enable Fullscreen
                </button>
              </div>
            </div>

            {/* Declaration & Start Action */}
            <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm space-y-4">
              <label className="flex items-start gap-2.5 cursor-pointer text-xs text-slate-700 select-none">
                <input
                  type="checkbox"
                  checked={declared}
                  onChange={(e) => setDeclared(e.target.checked)}
                  className="mt-0.5 w-4 h-4 text-primary-600 rounded border-slate-300 focus:ring-primary-500"
                />
                <span className="leading-tight font-medium">
                  I have read and understood all instructions. I confirm that I will not use any unfair means during the test.
                </span>
              </label>

              <button
                type="button"
                disabled={!declared || starting || loading}
                onClick={handleStartExam}
                className="w-full py-3.5 px-4 rounded-xl bg-primary-600 hover:bg-primary-700 active:bg-primary-800 disabled:opacity-50 disabled:cursor-not-allowed text-white font-bold text-sm transition-all shadow-md flex items-center justify-center gap-2"
              >
                {starting ? (
                  <>
                    <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></span>
                    Initializing Secure Session...
                  </>
                ) : (
                  <>
                    <span>Start Examination</span>
                    <ArrowRight className="w-4 h-4" />
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
};

export default ExamLobbyPage;
