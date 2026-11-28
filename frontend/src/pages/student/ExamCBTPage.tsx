import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import {
  Clock,
  Maximize,
  Minimize,
  AlertTriangle,
  ChevronLeft,
  ChevronRight,
  Bookmark,
  CheckCircle,
  RotateCcw,
  Send,
  Camera,
  ShieldAlert,
} from 'lucide-react';
import studentExamApi, { SaveResponseResult } from '../../services/studentExamApi';
import {
  CBTAttemptPayload,
  CBTSection,
  CBTQuestion,
  CBTResponseRecord,
  ResponseStatusType,
} from '../../types';
import QuestionPalette from '../../components/QuestionPalette';
import VirtualNumpad from '../../components/VirtualNumpad';
import FinishConfirmationModal from '../../components/FinishConfirmationModal';
import { useAuth } from '../../context/AuthContext';
import MathRenderer from '../../components/MathRenderer';
import {
  reconcileResponses,
  hasPendingResponses,
  createResponseFlushRunner,
  submitAttemptWithFlush,
} from '../../utils/offlineResponseQueue';
import {
  ClockAnchor,
  getMonotonicNowMs,
  normalizeRemainingSeconds,
  createClockAnchor,
  computeClockRemaining,
  shouldAutoSubmitOnTick,
} from '../../utils/examClock';

const TEXT_INPUT_TYPES = new Set(['NUMERICAL', 'SINGLE_DIGIT', 'ONE_WORD', 'SUBJECTIVE', 'CODING']);
const NUMERIC_INPUT_TYPES = new Set(['NUMERICAL', 'SINGLE_DIGIT']);
const VALID_NUMBER_PATTERN = /^-?(?:\d+\.?\d*|\.\d+)$/;

function isValidTextInput(questionType: string | undefined, value: string): boolean {
  const qType = questionType ?? '';
  if (!TEXT_INPUT_TYPES.has(qType)) return false;
  const trimmed = value.trim();
  if (NUMERIC_INPUT_TYPES.has(qType)) {
    return VALID_NUMBER_PATTERN.test(trimmed);
  }
  return trimmed.length > 0;
}

function formatTextPayloadValue(questionType: string | undefined, value: string): string | null {
  if (!isValidTextInput(questionType, value)) return null;
  if (questionType === 'SUBJECTIVE' || questionType === 'CODING') {
    return value;
  }
  return value.trim();
}

export const ExamCBTPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const { user } = useAuth();

  // Attempt Data
  const [attempt, setAttempt] = useState<CBTAttemptPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Active navigation state
  const [activeSectionIndex, setActiveSectionIndex] = useState(0);
  const [activeQuestionIndex, setActiveQuestionIndex] = useState(0);
  const [isPaletteOpen, setIsPaletteOpen] = useState(false);
  const [showCalculator, setShowCalculator] = useState(false);
  const [calcDisplay, setCalcDisplay] = useState("0");
  const [calcPrev, setCalcPrev] = useState<number | null>(null);
  const [calcOp, setCalcOp] = useState<string | null>(null);
  const [calcClearNext, setCalcClearNext] = useState(false);

  // In-memory responses & visited tracker
  const [responses, setResponses] = useState<Record<string, CBTResponseRecord>>({});
  const [visitedQuestionIds, setVisitedQuestionIds] = useState<Set<string | number>>(new Set());

  // Current question inputs
  const [selectedOptions, setSelectedOptions] = useState<string[]>([]);
  const [numericalValue, setNumericalValue] = useState<string>('');
  const questionStartTimeRef = useRef<number>(getMonotonicNowMs());

  // Timer & Heartbeat state
  const [remainingSeconds, setRemainingSeconds] = useState<number>(3600);
  const timerIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const heartbeatIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // Proctoring state
  const [blurCount, setBlurCount] = useState<number>(0);
  const blurCountRef = useRef<number>(0);
  const [showBlurWarning, setShowBlurWarning] = useState<boolean>(false);
  const maxBlurSwitches = attempt?.exam?.max_window_switches || 3;

  // Modals & UI controls
  const [showFinishModal, setShowFinishModal] = useState<boolean>(false);
  const submittingRef = useRef(false);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [isFullscreen, setIsFullscreen] = useState<boolean>(false);
  const pendingResponses = useRef<Record<string, CBTResponseRecord>>({});
  const attemptRef = useRef<CBTAttemptPayload | null>(null);
  const examIdRef = useRef<string | undefined>(id);
  examIdRef.current = id;
  const flushRunnerRef = useRef<ReturnType<typeof createResponseFlushRunner> | null>(null);
  const [pendingCount, setPendingCount] = useState<number>(0);
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle');
  const clockRef = useRef<ClockAnchor>(createClockAnchor(0, getMonotonicNowMs()));

  const applyServerClock = useCallback((remainingSecondsRaw: unknown) => {
    const nowMs = getMonotonicNowMs();
    clockRef.current = createClockAnchor(remainingSecondsRaw, nowMs);
    setRemainingSeconds(normalizeRemainingSeconds(remainingSecondsRaw));
  }, []);

  const getFlushRunner = useCallback(() => {
    if (!flushRunnerRef.current) {
      flushRunnerRef.current = createResponseFlushRunner(() => {
        const activeAttempt = attemptRef.current;
        const cacheKey = activeAttempt
          ? studentExamApi.getCacheKey(activeAttempt.attempt_id, examIdRef.current || 'exam')
          : '';
        return {
          attemptId: activeAttempt?.attempt_id || '',
          pending: pendingResponses.current,
          saveResponse: (attemptId, record) => studentExamApi.saveResponse(attemptId, record),
          persistCache: (map) => {
            if (cacheKey) studentExamApi.saveLocalCache(cacheKey, map);
          },
          onSaveResult: (res: SaveResponseResult) => {
            if (
              typeof res.remaining_seconds === 'number' &&
              Number.isFinite(res.remaining_seconds)
            ) {
              applyServerClock(res.remaining_seconds);
            }
          },
        };
      });
    }
    return flushRunnerRef.current;
  }, [applyServerClock]);

  const triggerPendingFlush = useCallback(async () => {
    if (
      !attemptRef.current ||
      submittingRef.current ||
      !hasPendingResponses(pendingResponses.current)
    ) {
      setPendingCount(Object.keys(pendingResponses.current).length);
      return;
    }
    setSaveStatus('saving');
    const result = await getFlushRunner().flush();
    setPendingCount(result.remainingCount);
    setSaveStatus(result.status);
  }, [getFlushRunner]);

  // Candidate info
  const candidateName = user?.profile?.full_name || user?.username;
  const rollNumber = attempt?.candidate?.roll_number || '—';

  // 1. Initial Load / Session Recovery
  useEffect(() => {
    const initializeAttempt = async () => {
      if (!id) return;
      try {
        setLoading(true);
        setError(null);

        let payload: CBTAttemptPayload | null = null;
        const routerState = location.state as { attemptPayload?: CBTAttemptPayload } | undefined;

        if (routerState?.attemptPayload?.exam?.id === id) {
          payload = routerState.attemptPayload;
        } else {
          // Recover via start/resume endpoint
          payload = await studentExamApi.startExam(id);
        }

        if (payload && payload.status === 'SUCCESS') {
          attemptRef.current = payload;
          setAttempt(payload);
          applyServerClock(payload.remaining_seconds);

          // Reconcile server responses with localStorage cache (local wins on conflict)
          const cacheKey = studentExamApi.getCacheKey(payload.attempt_id, id);
          const cachedPending = studentExamApi.loadLocalCache(cacheKey) ?? {};
          pendingResponses.current = cachedPending;
          const initialResponses = reconcileResponses(
            payload.existing_responses,
            cachedPending
          );
          setResponses(initialResponses);
          setPendingCount(Object.keys(cachedPending).length);

          // Mark already answered questions as visited
          const visited = new Set<string | number>();
          Object.keys(initialResponses).forEach((qid) => {
            visited.add(qid);
          });
          setVisitedQuestionIds(visited);

          if (hasPendingResponses(cachedPending)) {
            void triggerPendingFlush();
          }
        } else {
          setError('Failed to initialize examination session.');
        }
      } catch (err: unknown) {
        const e = err as { response?: { data?: { message?: string; code?: string } } };
        setError(e.response?.data?.message || 'Could not load examination.');
      } finally {
        setLoading(false);
      }
    };

    initializeAttempt();
  }, [id, location.state]);

  // Derived active section and question
  const currentSection: CBTSection | undefined = attempt?.sections?.[activeSectionIndex];
  const currentQuestion: CBTQuestion | undefined = currentSection?.questions?.[activeQuestionIndex];

  // 2. Mark current question visited and load response inputs
  useEffect(() => {
    if (!currentQuestion) return;

    questionStartTimeRef.current = getMonotonicNowMs();
    const qidKey = String(currentQuestion.id);

    // Mark visited
    setVisitedQuestionIds((prev) => {
      const next = new Set(prev);
      next.add(currentQuestion.id);
      next.add(qidKey);
      return next;
    });

    // Populate current question inputs from stored responses
    const existing = responses[qidKey];
    if (existing) {
      setSelectedOptions(existing.selected_options || []);
      setNumericalValue(existing.numerical_value || '');
    } else {
      setSelectedOptions([]);
      setNumericalValue('');
    }
  }, [currentQuestion, activeSectionIndex, activeQuestionIndex]);

  // Countdown uses monotonic performance.now() elapsed time so OS clock jumps cannot tamper with the timer, while throttled tabs / sleep still catch up on tick.
  useEffect(() => {
    if (loading || !attempt) return;
    clockRef.current = createClockAnchor(attempt.remaining_seconds, getMonotonicNowMs());
    const recomputeTick = () => {
      setRemainingSeconds(computeClockRemaining(clockRef.current, getMonotonicNowMs()));
    };
    recomputeTick();
    timerIntervalRef.current = setInterval(recomputeTick, 1000);

    return () => {
      if (timerIntervalRef.current) clearInterval(timerIntervalRef.current);
    };
  }, [loading, attempt]);

  useEffect(() => {
    if (!loading && attempt && shouldAutoSubmitOnTick(remainingSeconds)) {
      void handleFinalSubmitRef.current('AUTO_TIMER_EXPIRY');
    }
  }, [loading, attempt, remainingSeconds]);

  // 4. Server-Authoritative Heartbeat Sync (every 20s + wake/online resync)
  useEffect(() => {
    if (loading || !attempt || !attempt.attempt_id) return;

    const syncHeartbeat = async () => {
      try {
        const hb = await studentExamApi.sendHeartbeat(
          attempt.attempt_id,
          blurCountRef.current
        );
        if (hb.status === 'SUCCESS') {
          applyServerClock(hb.remaining_seconds);
          if (hasPendingResponses(pendingResponses.current)) {
            void triggerPendingFlush();
          }
          if (
            shouldAutoSubmitOnTick(
              normalizeRemainingSeconds(hb.remaining_seconds),
              hb.is_terminated
            )
          ) {
            void handleFinalSubmitRef.current('AUTO_TIMER_EXPIRY');
          }
        }
      } catch (err) {
        console.warn('Heartbeat synchronization failed (offline/retry)', err);
      }
    };

    const onOnline = () => {
      if (hasPendingResponses(pendingResponses.current)) {
        void triggerPendingFlush();
      }
      void syncHeartbeat();
      if (shouldAutoSubmitOnTick(computeClockRemaining(clockRef.current, getMonotonicNowMs()))) {
        void handleFinalSubmitRef.current('AUTO_TIMER_EXPIRY');
      }
    };

    const onVisibilityWake = () => {
      if (document.visibilityState === 'visible') {
        setRemainingSeconds(computeClockRemaining(clockRef.current, getMonotonicNowMs()));
        void syncHeartbeat();
      }
    };

    heartbeatIntervalRef.current = setInterval(syncHeartbeat, 20000);
    window.addEventListener('online', onOnline);
    document.addEventListener('visibilitychange', onVisibilityWake);

    return () => {
      if (heartbeatIntervalRef.current) clearInterval(heartbeatIntervalRef.current);
      window.removeEventListener('online', onOnline);
      document.removeEventListener('visibilitychange', onVisibilityWake);
    };
  }, [loading, attempt, applyServerClock, triggerPendingFlush]);

  // Warn before unloading tab while local answers are still pending sync
  useEffect(() => {
    if (!attempt) return;
    const onBeforeUnload = (e: BeforeUnloadEvent) => {
      if (hasPendingResponses(pendingResponses.current)) {
        e.preventDefault();
        e.returnValue = '';
      }
    };
    window.addEventListener('beforeunload', onBeforeUnload);
    return () => {
      window.removeEventListener('beforeunload', onBeforeUnload);
    };
  }, [attempt]);

  // 5. Anti-Cheating & Proctoring Window Switch / Blur Listener
  useEffect(() => {
    const handleVisibilityOrBlur = async () => {
      if (loading || !attempt || isSubmitting) return;

      const newCount = blurCountRef.current + 1;
      blurCountRef.current = newCount;
      setBlurCount(newCount);
      setShowBlurWarning(true);

      // Report event to backend proctoring log
      try {
        await studentExamApi.recordProctoringEvent(attempt.attempt_id, 'WINDOW_BLUR', {
          switch_index: newCount,
          timestamp: new Date().toISOString(),
        });
      } catch (e) {
        console.warn('Failed to record proctoring telemetry', e);
      }

      // Check max allowed switches
      if (newCount > maxBlurSwitches) {
        alert(`You have switched away ${newCount} times, exceeding the allowable limit (${maxBlurSwitches}). Your exam is now being auto-submitted.`);
        void handleFinalSubmitRef.current('AUTO_TIMER_EXPIRY');
      }
    };

    const onVisibilityChange = () => {
      if (document.visibilityState === 'hidden') {
        handleVisibilityOrBlur();
      }
    };

    document.addEventListener('visibilitychange', onVisibilityChange);

    return () => {
      document.removeEventListener('visibilitychange', onVisibilityChange);
    };
  }, [loading, attempt, blurCount, isSubmitting, maxBlurSwitches]);

  // Format Remaining Time in HH:MM:SS
  const formatTime = (totalSeconds: number): string => {
    const hrs = Math.floor(totalSeconds / 3600);
    const mins = Math.floor((totalSeconds % 3600) / 60);
    const secs = totalSeconds % 60;
    const pad = (n: number) => String(n).padStart(2, '0');
    return `${pad(hrs)}:${pad(mins)}:${pad(secs)}`;
  };

  // 6. Option Toggle Handlers
  const handleOptionSelect = (optionKey: string) => {
    if (!currentQuestion) return;
    const isMulti = currentQuestion.question_type === 'MCQ_MULTI';

    if (isMulti) {
      setSelectedOptions((prev) =>
        prev.includes(optionKey) ? prev.filter((k) => k !== optionKey) : [...prev, optionKey]
      );
    } else {
      setSelectedOptions([optionKey]);
    }
  };

  // 7. Save Response Core Function
  const saveCurrentResponse = useCallback(
    async (targetStatus: ResponseStatusType): Promise<boolean> => {
      if (!attempt || !currentQuestion || submittingRef.current) return false;

      const qid = currentQuestion.id;
      const qidKey = String(qid);
      const timeSpent = Math.max(0, Math.round((getMonotonicNowMs() - questionStartTimeRef.current) / 1000));

      const qType = currentQuestion.question_type as string;
      const isTextType = TEXT_INPUT_TYPES.has(qType);
      const formattedTextValue = isTextType ? formatTextPayloadValue(qType, numericalValue) : null;
      const record: CBTResponseRecord = {
        question_id: qid,
        selected_options: targetStatus === 'UNANSWERED' ? [] : (isTextType ? [] : selectedOptions),
        numerical_value: targetStatus === 'UNANSWERED' ? null : formattedTextValue,
        status: targetStatus,
        time_spent_seconds: timeSpent,
        saved_at: new Date().toISOString(),
      };

      setResponses((prev) => ({ ...prev, [qidKey]: record }));
      const cacheKey = studentExamApi.getCacheKey(attempt.attempt_id, id || 'exam');
      pendingResponses.current[qidKey] = record;
      studentExamApi.saveLocalCache(cacheKey, pendingResponses.current);
      setPendingCount(Object.keys(pendingResponses.current).length);

      void triggerPendingFlush();
      return true;
    },
    [attempt, currentQuestion, selectedOptions, numericalValue, id, triggerPendingFlush]
  );

  // Navigation: Advance to next question or section
  const advanceToNextQuestion = () => {
    if (!currentSection) return;
    if (activeQuestionIndex < currentSection.questions.length - 1) {
      setActiveQuestionIndex((prev) => prev + 1);
    } else if (attempt?.sections && activeSectionIndex < attempt.sections.length - 1) {
      setActiveSectionIndex((prev) => prev + 1);
      setActiveQuestionIndex(0);
    } else {
      // Reached end of entire paper -> show submission modal
      setShowFinishModal(true);
    }
  };

  // Navigation: Move to previous question
  const moveToPreviousQuestion = () => {
    if (activeQuestionIndex > 0) {
      setActiveQuestionIndex((prev) => prev - 1);
    } else if (activeSectionIndex > 0 && attempt?.sections) {
      const prevSec = attempt.sections[activeSectionIndex - 1];
      setActiveSectionIndex((prev) => prev - 1);
      setActiveQuestionIndex(prevSec.questions.length - 1);
    }
  };

  // Action Button: Save & Next
  const handleSaveAndNext = async () => {
    const qType = currentQuestion?.question_type as string | undefined;
    const isTextType = qType ? TEXT_INPUT_TYPES.has(qType) : false;
    const hasSelection = isTextType
      ? isValidTextInput(qType, numericalValue)
      : selectedOptions.length > 0;
    const targetStatus: ResponseStatusType = hasSelection ? 'ANSWERED' : 'UNANSWERED';
    if (await saveCurrentResponse(targetStatus)) advanceToNextQuestion();
  };

  // Action Button: Mark for Review & Next
  const handleMarkForReviewAndNext = async () => {
    const qType = currentQuestion?.question_type as string | undefined;
    const isTextType = qType ? TEXT_INPUT_TYPES.has(qType) : false;
    const hasSelection = isTextType
      ? isValidTextInput(qType, numericalValue)
      : selectedOptions.length > 0;
    const targetStatus: ResponseStatusType = hasSelection
      ? 'ANSWERED_AND_MARKED'
      : 'MARKED_FOR_REVIEW';
    if (await saveCurrentResponse(targetStatus)) advanceToNextQuestion();
  };

  // Action Button: Clear Response
  const handleClearResponse = async () => {
    if (submittingRef.current) return;
    setSelectedOptions([]);
    setNumericalValue('');
    await saveCurrentResponse('UNANSWERED');
  };

  // Final Submission
  const handleFinalSubmit = async (
    reason: 'MANUAL_SUBMIT' | 'AUTO_TIMER_EXPIRY' = 'MANUAL_SUBMIT'
  ) => {
    if (!attempt || submittingRef.current) return;
    submittingRef.current = true;
    try {
      setIsSubmitting(true);
      const cacheKey = studentExamApi.getCacheKey(attempt.attempt_id, id || 'exam');
      const res = await submitAttemptWithFlush({
        attemptId: attempt.attempt_id,
        reason,
        pending: pendingResponses.current,
        waitForInFlight: () => getFlushRunner().waitForIdle(),
        saveResponse: (attemptId, record) => studentExamApi.saveResponse(attemptId, record),
        submitExam: (attemptId, submitReason) =>
          studentExamApi.submitExam(attemptId, submitReason),
        persistCache: (map) => studentExamApi.saveLocalCache(cacheKey, map),
        clearCache: () => {
          if (id) {
            studentExamApi.clearLocalCache(cacheKey);
          }
        },
        onSaveResult: (saveRes) => {
          if (
            typeof saveRes.remaining_seconds === 'number' &&
            Number.isFinite(saveRes.remaining_seconds)
          ) {
            applyServerClock(saveRes.remaining_seconds);
          }
        },
      });
      setPendingCount(Object.keys(pendingResponses.current).length);
      navigate(`/student/exam/${id}/finish`, {
        replace: true,
        state: { submitResult: res, examName: attempt.exam?.name },
      });
    } catch (err: unknown) {
      setPendingCount(Object.keys(pendingResponses.current).length);
      if (hasPendingResponses(pendingResponses.current)) {
        setSaveStatus('error');
      }
      if (reason === 'MANUAL_SUBMIT') {
        const e = err as { response?: { data?: { message?: string } } };
        alert(e.response?.data?.message || 'Submission failed. Please try again.');
      } else {
        console.warn('Auto-submit deferred (offline/retry)', err);
      }
      submittingRef.current = false;
      setIsSubmitting(false);
    }
  };
  const handleFinalSubmitRef = useRef(handleFinalSubmit);
  handleFinalSubmitRef.current = handleFinalSubmit;

  // Sync fullscreen indicator when user presses Escape or browser exits fullscreen
  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(Boolean(document.fullscreenElement));
    };
    document.addEventListener('fullscreenchange', handleFullscreenChange);
    return () => {
      document.removeEventListener('fullscreenchange', handleFullscreenChange);
    };
  }, []);

  // Fullscreen toggle
  const toggleFullscreen = () => {
    if (!document.fullscreenElement) {
      document.documentElement
        .requestFullscreen()
        .then(() => setIsFullscreen(true))
        .catch(() => {});
    } else {
      document
        .exitFullscreen()
        .then(() => setIsFullscreen(false))
        .catch(() => {});
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-100 flex items-center justify-center p-6">
        <div className="bg-white p-8 rounded-2xl shadow-md border border-slate-200 flex flex-col items-center gap-4 text-center">
          <div className="w-12 h-12 border-4 border-primary-600 border-t-transparent rounded-full animate-spin"></div>
          <div>
            <h2 className="text-base font-bold text-slate-800">Loading Examination Interface...</h2>
            <p className="text-xs text-slate-500 mt-1">Establishing secure server session & syncing timer</p>
          </div>
        </div>
      </div>
    );
  }

  if (error || !attempt) {
    return (
      <div className="min-h-screen bg-slate-100 flex items-center justify-center p-6">
        <div className="bg-white p-8 rounded-2xl shadow-md border border-rose-200 max-w-md w-full text-center space-y-4">
          <div className="w-12 h-12 rounded-full bg-rose-100 text-rose-600 mx-auto flex items-center justify-center">
            <AlertTriangle className="w-6 h-6" />
          </div>
          <h2 className="text-lg font-bold text-slate-800">Examination Error</h2>
          <p className="text-xs text-slate-600">{error || 'Could not load examination.'}</p>
          <button
            type="button"
            onClick={() => navigate('/student')}
            className="px-5 py-2.5 rounded-xl bg-primary-600 text-white font-bold text-xs hover:bg-primary-700 transition-colors"
          >
            Return to Dashboard
          </button>
        </div>
      </div>
    );
  }

  // Timer Warning styling
  const isTimerCritical = remainingSeconds < 300; // <5 mins: pulsing red
  const isTimerWarning = remainingSeconds < 600 && !isTimerCritical; // <10 mins: amber

  return (
    <div className="min-h-screen bg-slate-100 flex flex-col select-none font-sans overflow-hidden h-screen">
      {/* 1. TOP HEADER BAR */}
      <header className="bg-white border-b border-slate-200 px-5 py-2.5 shadow-xs flex items-center justify-between z-20">
        {/* Left: Brand & Exam Title */}
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-primary-600 flex items-center justify-center text-white font-bold text-sm shadow-xs">
            EK
          </div>
          <div>
            <h1 className="text-sm font-bold text-slate-800 leading-tight truncate max-w-md">
              {attempt.exam?.name || 'Examination CBT'}
            </h1>
            <div className="text-[11px] text-slate-500 flex items-center gap-2">
              <span>Section: <strong>{currentSection?.name || 'General'}</strong></span>
              <span>•</span>
              <span>Q {activeQuestionIndex + 1} of {currentSection?.questions?.length || 0}</span>
            </div>
          </div>
        </div>

        {/* Center: Save Status & Webcam Indicator */}
        <div className="hidden md:flex items-center gap-3">
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-700 text-xs font-semibold">
            <Camera className="w-3.5 h-3.5" />
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
            Proctored Session
          </div>

          {saveStatus === 'saving' && (
            <span className="text-[11px] text-slate-400 flex items-center gap-1">
              <span className="w-2 h-2 border border-primary-500 border-t-transparent rounded-full animate-spin"></span>
              Autosaving...
            </span>
          )}
          {saveStatus === 'saved' && pendingCount === 0 && (
            <span className="text-[11px] text-emerald-600 font-medium flex items-center gap-1">
              <CheckCircle className="w-3 h-3" /> Saved
            </span>
          )}
          {(saveStatus === 'error' || (saveStatus !== 'saving' && pendingCount > 0)) && (
            <button
              type="button"
              onClick={() => void triggerPendingFlush()}
              className="text-[11px] text-amber-700 bg-amber-50 border border-amber-200 hover:bg-amber-100 px-2 py-0.5 rounded-full font-semibold flex items-center gap-1 transition-colors"
              title="Some answers are saved locally and waiting to sync. Click to retry now."
            >
              <AlertTriangle className="w-3 h-3 text-amber-600" />
              <span>
                Offline / Sync Pending{pendingCount > 0 ? ` (${pendingCount})` : ''} — Retry
              </span>
            </button>
          )}
        </div>

        {/* Right: High-Visibility Timer & Fullscreen */}
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={toggleFullscreen}
            className="p-1.5 rounded-lg border border-slate-200 hover:bg-slate-100 text-slate-600 transition-colors"
            title="Toggle Fullscreen"
          >
            {isFullscreen ? <Minimize className="w-4 h-4" /> : <Maximize className="w-4 h-4" />}
          </button>

          {/* Countdown Clock Display */}
          <div
            className={`flex items-center gap-2 px-3.5 py-1.5 rounded-xl border font-mono font-bold text-sm shadow-inner transition-all ${
              isTimerCritical
                ? 'bg-rose-50 border-rose-300 text-rose-700 animate-pulse'
                : isTimerWarning
                ? 'bg-amber-50 border-amber-300 text-amber-700'
                : 'bg-slate-50 border-slate-300 text-slate-800'
            }`}
          >
            <Clock className={`w-4 h-4 ${isTimerCritical ? 'text-rose-600' : 'text-primary-600'}`} />
            <span>{formatTime(remainingSeconds)}</span>
          </div>

          <button
            type="button"
            onClick={() => setShowFinishModal(true)}
            className="px-4 py-1.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs transition-colors shadow-xs flex items-center gap-1.5"
          >
            <Send className="w-3.5 h-3.5" />
            <span>Submit</span>
          </button>
        </div>
      </header>

      {/* 2. SECTION NAVIGATION TABS */}
      <div className="bg-white border-b border-slate-200 px-5 py-1 flex items-center gap-2 overflow-x-auto shadow-xs">
        <span className="text-xs font-bold text-slate-500 uppercase tracking-wider mr-1">Sections:</span>
        {attempt.sections?.map((sec, idx) => {
          const isActive = idx === activeSectionIndex;
          return (
            <button
              key={sec.id || idx}
              type="button"
              onClick={() => {
                setActiveSectionIndex(idx);
                setActiveQuestionIndex(0);
              }}
              className={`px-4 py-1.5 rounded-lg text-xs font-bold transition-all flex items-center gap-2 ${
                isActive
                  ? 'bg-primary-600 text-white shadow-xs'
                  : 'bg-slate-100 hover:bg-slate-200 text-slate-700'
              }`}
            >
              <span>{sec.name || sec.title}</span>
              <span
                className={`text-[10px] px-1.5 py-0.2 rounded-full ${
                  isActive ? 'bg-white/20 text-white' : 'bg-slate-200 text-slate-600'
                }`}
              >
                {sec.questions?.length || sec.total_questions || 0}
              </span>
            </button>
          );
        })}
      </div>

      {/* 3. MAIN WORKSPACE: QUESTION AREA + QUESTION PALETTE */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left: Question Canvas */}
        <div className="flex-1 flex flex-col bg-white overflow-hidden border-r border-slate-200">
          {/* Question Subheader */}
          <div className="px-6 py-2.5 border-b border-slate-200 bg-slate-50 flex items-center justify-between text-xs">
            <div className="flex items-center gap-3">
              <span className="font-extrabold text-slate-800 text-sm">
                Question No. {currentQuestion?.question_number || activeQuestionIndex + 1}
              </span>
              <span className="px-2 py-0.5 rounded bg-slate-200 text-slate-700 text-[11px] font-semibold">
                {currentQuestion?.question_type === 'NUMERICAL'
                  ? 'Numerical Value Answer'
                  : currentQuestion?.question_type === 'SINGLE_DIGIT'
                  ? 'Single Digit (0–9)'
                  : currentQuestion?.question_type === 'MCQ_MULTI'
                  ? 'Multiple Correct Options'
                  : currentQuestion?.question_type === 'TRUE_FALSE'
                  ? 'True / False'
                  : currentQuestion?.question_type === 'ONE_WORD'
                  ? 'One Word Answer'
                  : currentQuestion?.question_type === 'SUBJECTIVE'
                  ? 'Descriptive / Subjective'
                  : currentQuestion?.question_type === 'CODING'
                  ? 'Coding Problem'
                  : 'Single Correct Option'}
              </span>
            </div>
            <div className="flex items-center gap-3 text-slate-600 font-semibold text-[11px]">
              <span className="text-emerald-600 font-bold">
                Marks: +{currentQuestion?.positive_marks || 4.0}
              </span>
              <span className="text-rose-600 font-bold">
                Negative: -{currentQuestion?.negative_marks || 1.0}
              </span>
            </div>
          </div>

          {/* Question Body Scroll Area */}
          <div className="flex-1 overflow-y-auto p-6 space-y-6">
            {currentQuestion ? (
              <>
                {/* Question Text with Math/LaTeX Rendering */}
                <div className="text-sm font-medium text-slate-800 leading-relaxed bg-slate-50/50 p-4 rounded-xl border border-slate-200">
                  <MathRenderer content={currentQuestion.content_text} />
                  {currentQuestion.image_url && (
                    <div className="mt-4 max-w-lg rounded-xl overflow-hidden border border-slate-200">
                      <img
                        src={currentQuestion.image_url}
                        alt="Question Diagram"
                        className="w-full object-contain max-h-72"
                      />
                    </div>
                  )}
                </div>

                {/* Option Inputs by Question Type */}
                {currentQuestion.question_type === 'NUMERICAL' || currentQuestion.question_type === 'SINGLE_DIGIT' ? (
                  <div className="pt-2 space-y-3">
                    <div className="text-xs font-bold text-slate-500 uppercase tracking-wider">
                      {currentQuestion.question_type === 'SINGLE_DIGIT' ? 'Enter a single digit (0–9):' : 'Enter numerical value:'}
                    </div>
                    <VirtualNumpad
                      key={currentQuestion.id}
                      value={numericalValue}
                      onChange={(val) => setNumericalValue(val)}
                      singleDigit={currentQuestion.question_type === 'SINGLE_DIGIT'}
                    />
                    {numericalValue.trim().length > 0 && !VALID_NUMBER_PATTERN.test(numericalValue.trim()) && (
                      <p className="text-xs text-amber-600 font-medium">
                        Enter at least one digit (incomplete input like &ldquo;-&rdquo; or &ldquo;.&rdquo; will not be saved as an answer).
                      </p>
                    )}
                  </div>
                ) : currentQuestion.question_type === 'ONE_WORD' ? (
                  <div className="pt-2 space-y-3 max-w-2xl">
                    <div className="flex items-center justify-between">
                      <div className="text-xs font-bold text-slate-500 uppercase tracking-wider">
                        Enter one-word answer:
                      </div>
                      <span className="text-[11px] font-mono text-slate-400">
                        {numericalValue.length}/100
                      </span>
                    </div>
                    <input
                      type="text"
                      maxLength={100}
                      value={numericalValue}
                      onChange={(e) => setNumericalValue(e.target.value)}
                      className="w-full px-4 py-3 rounded-xl border-2 border-primary-400 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-primary-500/30 min-h-[48px] placeholder:text-slate-400 text-slate-800"
                      placeholder="Type one word..."
                      autoComplete="off"
                      spellCheck={false}
                    />
                    {numericalValue.trim().length > 0 && (
                      <div className="text-xs text-emerald-600 font-semibold flex items-center gap-1">
                        <span className="w-2 h-2 rounded-full bg-emerald-500 inline-block" />
                        Answer recorded — click Save &amp; Next to confirm
                      </div>
                    )}
                  </div>
                ) : currentQuestion.question_type === 'SUBJECTIVE' ? (
                  <div className="pt-2 space-y-3 max-w-2xl">
                    <div className="flex items-center justify-between">
                      <div className="text-xs font-bold text-slate-500 uppercase tracking-wider">
                        Write your answer below:
                      </div>
                      <span className="text-[11px] font-mono text-slate-400">
                        {numericalValue.length}/10,000
                      </span>
                    </div>
                    <textarea
                      value={numericalValue}
                      onChange={(e) => setNumericalValue(e.target.value)}
                      rows={5}
                      maxLength={10000}
                      className="w-full px-4 py-3 rounded-xl border-2 border-primary-400 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-primary-500/30 resize-y min-h-[48px] placeholder:text-slate-400 text-slate-800"
                      placeholder="Write your detailed answer here..."
                      autoComplete="off"
                      spellCheck={true}
                    />
                    {numericalValue.trim().length > 0 && (
                      <div className="text-xs text-emerald-600 font-semibold flex items-center gap-1">
                        <span className="w-2 h-2 rounded-full bg-emerald-500 inline-block" />
                        Answer recorded — click Save &amp; Next to confirm
                      </div>
                    )}
                  </div>
                ) : currentQuestion.question_type === 'CODING' ? (
                  <div className="pt-2 space-y-3 max-w-2xl">
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">
                          Write your solution:
                        </span>
                        {currentQuestion.coding_language && (
                          <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-100 text-[11px] font-mono font-semibold">
                            {currentQuestion.coding_language}
                          </span>
                        )}
                      </div>
                      <span className="text-[11px] font-mono text-slate-400">
                        {numericalValue.length}/50,000
                      </span>
                    </div>
                    {currentQuestion.code_boilerplate && (
                      <div className="space-y-1">
                        <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
                          Boilerplate / Starter Reference
                        </div>
                        <pre className="p-3 rounded-xl bg-slate-900 text-slate-100 text-xs font-mono overflow-x-auto border border-slate-700 select-text">
                          <code>{currentQuestion.code_boilerplate}</code>
                        </pre>
                      </div>
                    )}
                    <textarea
                      value={numericalValue}
                      onChange={(e) => setNumericalValue(e.target.value)}
                      rows={6}
                      maxLength={50000}
                      className="w-full px-4 py-3 rounded-xl border-2 border-primary-400 text-sm font-mono bg-slate-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-primary-500/30 resize-y min-h-[48px] placeholder:text-slate-400 text-slate-800"
                      placeholder="Enter your code or answer here..."
                      autoComplete="off"
                      spellCheck={false}
                    />
                    {numericalValue.trim().length > 0 && (
                      <div className="text-xs text-emerald-600 font-semibold flex items-center gap-1">
                        <span className="w-2 h-2 rounded-full bg-emerald-500 inline-block" />
                        Answer recorded — click Save &amp; Next to confirm
                      </div>
                    )}
                  </div>
                ) : currentQuestion.question_type === 'TRUE_FALSE' ? (
                  <div className="space-y-3 max-w-xs">
                    <div className="text-xs font-bold text-slate-500 uppercase tracking-wider">Select true or false:</div>
                    {(currentQuestion.options && currentQuestion.options.length > 0
                      ? currentQuestion.options.map((opt) => ({
                          key: opt.key,
                          label: opt.text || opt.content_text || opt.key,
                        }))
                      : [
                          { key: 'TRUE', label: 'True' },
                          { key: 'FALSE', label: 'False' },
                        ]
                    ).map((opt) => {
                      const isSelected = selectedOptions.includes(opt.key);
                      return (
                        <button
                          type="button"
                          key={opt.key}
                          onClick={() => handleOptionSelect(opt.key)}
                          className={`w-full text-left flex items-center gap-3 p-4 rounded-xl border-2 cursor-pointer transition-all font-semibold text-sm select-none ${
                            isSelected
                              ? 'border-[#2d8df1] bg-[#2d8df1]/10 text-primary-700 shadow-xs'
                              : 'border-slate-200 hover:border-slate-300 hover:bg-slate-50/80 text-slate-700'
                          }`}
                        >
                          <div className={`w-5 h-5 rounded-full border-2 flex items-center justify-center flex-shrink-0 ${isSelected ? 'border-[#2d8df1] bg-[#2d8df1]' : 'border-slate-300'}`}>
                            {isSelected && <div className="w-2 h-2 rounded-full bg-white" />}
                          </div>
                          {opt.label}
                        </button>
                      );
                    })}
                  </div>
                ) : (
                  <div className="space-y-3 max-w-2xl">
                    <div className="text-xs font-bold text-slate-500 uppercase tracking-wider">
                      {currentQuestion.question_type === 'MCQ_MULTI'
                        ? 'Select all correct options:'
                        : 'Select one option:'}
                    </div>
                    {currentQuestion.options?.map((opt) => {
                      const isSelected = selectedOptions.includes(opt.key);
                      return (
                        <button
                          type="button"
                          key={opt.key}
                          onClick={() => handleOptionSelect(opt.key)}
                          className={`w-full text-left flex items-start gap-3 p-3.5 rounded-xl border cursor-pointer transition-all select-none ${
                            isSelected
                              ? 'border-[#2d8df1] bg-[#2d8df1]/10 text-slate-900 shadow-xs'
                              : 'border-slate-200 hover:border-slate-300 hover:bg-slate-50/80 text-slate-700'
                          }`}
                        >
                          <div
                            className={`w-5 h-5 ${currentQuestion.question_type === 'MCQ_MULTI' ? 'rounded-sm' : 'rounded-full'} flex items-center justify-center font-bold text-xs mt-0.5 flex-shrink-0 transition-colors ${
                              isSelected
                                ? 'bg-[#2d8df1] text-white ring-2 ring-[#2d8df1]/30'
                                : 'border border-slate-300 text-slate-600 bg-white'
                            }`}
                          >
                            {opt.key}
                          </div>
                          <div className="text-xs font-medium leading-relaxed pt-0.5">
                            <MathRenderer content={opt.text || opt.content_text || ''} />
                          </div>
                        </button>
                      );
                    })}
                  </div>
                )}
              </>
            ) : (
              <div className="text-center py-12 text-slate-400 text-xs">No question selected</div>
            )}
          </div>

          {/* 4. BOTTOM ACTION BAR */}
          <footer className="px-6 py-3 border-t border-slate-200 bg-slate-50 flex items-center justify-between z-10">
            {/* Left Actions: Review & Clear */}
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={handleMarkForReviewAndNext}
                className="px-3.5 py-2 rounded-xl border border-purple-300 bg-purple-50 hover:bg-purple-100 text-purple-700 font-bold text-xs flex items-center gap-1.5 transition-colors shadow-xs"
              >
                <Bookmark className="w-3.5 h-3.5" />
                <span>Mark for Review & Next</span>
              </button>

              <button
                type="button"
                onClick={handleClearResponse}
                className="px-3.5 py-2 rounded-xl border border-slate-300 bg-white hover:bg-slate-100 text-slate-700 font-semibold text-xs flex items-center gap-1.5 transition-colors shadow-xs"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                <span>Clear Response</span>
              </button>
            </div>

            {/* Right Actions: Previous, Save & Next */}
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={moveToPreviousQuestion}
                disabled={activeQuestionIndex === 0 && activeSectionIndex === 0}
                className="px-4 py-2 rounded-xl border border-slate-300 bg-white hover:bg-slate-100 disabled:opacity-40 disabled:cursor-not-allowed text-slate-700 font-bold text-xs flex items-center gap-1.5 transition-colors shadow-xs"
              >
                <ChevronLeft className="w-4 h-4" />
                <span>Previous</span>
              </button>

              <button
                type="button"
                onClick={handleSaveAndNext}
                className="px-5 py-2 rounded-xl bg-primary-600 hover:bg-primary-700 text-white font-bold text-xs flex items-center gap-1.5 transition-colors shadow-sm"
              >
                <span>Save & Next</span>
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </footer>
        </div>

        {/* Backdrop for mobile drawer */}
        {isPaletteOpen && (
          <div
            className="fixed inset-0 bg-slate-900/50 backdrop-blur-xs z-40 lg:hidden"
            onClick={() => setIsPaletteOpen(false)}
          />
        )}

        {/* Right: Question Palette - Slide-over drawer on mobile/tablet, pinned on lg+ */}
        {currentSection && (
          <aside
            className={`fixed inset-y-0 right-0 z-50 w-80 bg-white shadow-2xl transition-transform duration-300 ease-in-out lg:static lg:translate-x-0 lg:z-auto lg:shadow-sm lg:border-l lg:border-slate-200 flex flex-col flex-shrink-0 overflow-hidden ${
              isPaletteOpen ? "translate-x-0" : "translate-x-full lg:translate-x-0"
            }`}
          >
            {/* Mobile drawer header */}
            <div className="lg:hidden flex items-center justify-between p-3 border-b border-slate-200 bg-slate-50">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-700">Question Palette</span>
              <button
                onClick={() => setIsPaletteOpen(false)}
                className="px-2 py-1 rounded bg-slate-200 hover:bg-slate-300 text-slate-700 text-xs font-bold"
              >
                ✕ Close
              </button>
            </div>
            <QuestionPalette
              questions={currentSection.questions || []}
              currentQuestionIndex={activeQuestionIndex}
              responses={responses}
              visitedQuestionIds={visitedQuestionIds}
              onSelectQuestion={(idx) => {
                setActiveQuestionIndex(idx);
                setIsPaletteOpen(false);
              }}
              candidateName={candidateName}
              rollNumber={rollNumber}
            />
          </aside>
        )}
      </div>

            {/* VIRTUAL CALCULATOR POPUP */}
      {showCalculator && (
        <div className="fixed bottom-20 right-8 z-50 w-72 bg-white rounded-2xl shadow-2xl border border-slate-300 overflow-hidden animate-in fade-in zoom-in-95 duration-150">
          <div className="flex items-center justify-between px-4 py-2.5 bg-slate-800 text-white select-none">
            <span className="text-xs font-bold tracking-wider uppercase flex items-center gap-1.5">
              <span>🧮</span> Scientific Calculator
            </span>
            <button
              onClick={() => setShowCalculator(false)}
              className="text-slate-400 hover:text-white text-sm font-bold p-1"
            >
              ✕
            </button>
          </div>
          <div className="p-3 bg-slate-900">
            <div className="bg-slate-950 rounded-xl px-3 py-2 text-right text-white font-mono text-xl tracking-wider overflow-x-auto min-h-[44px] flex items-center justify-end">
              {calcDisplay}
            </div>
          </div>
          <div className="p-3 grid grid-cols-4 gap-2 bg-slate-100 select-none">
            {["C", "±", "%", "÷", "7", "8", "9", "×", "4", "5", "6", "-", "1", "2", "3", "+", "0", ".", "⌫", "="].map((btn) => (
              <button
                key={btn}
                onClick={() => {
                  if (btn === "C") {
                    setCalcDisplay("0");
                    setCalcPrev(null);
                    setCalcOp(null);
                    setCalcClearNext(false);
                  } else if (btn === "⌫") {
                    setCalcDisplay((prev) => (prev.length > 1 ? prev.slice(0, -1) : "0"));
                  } else if (btn === "±") {
                    setCalcDisplay((prev) => (prev.startsWith("-") ? prev.slice(1) : "-" + prev));
                  } else if (["+", "-", "×", "÷"].includes(btn)) {
                    setCalcPrev(parseFloat(calcDisplay));
                    setCalcOp(btn);
                    setCalcClearNext(true);
                  } else if (btn === "=") {
                    if (calcOp && calcPrev !== null) {
                      const cur = parseFloat(calcDisplay);
                      let res = 0;
                      if (calcOp === "+") res = calcPrev + cur;
                      if (calcOp === "-") res = calcPrev - cur;
                      if (calcOp === "×") res = calcPrev * cur;
                      if (calcOp === "÷") res = cur !== 0 ? calcPrev / cur : 0;
                      setCalcDisplay(String(Number(res.toFixed(8))));
                      setCalcPrev(null);
                      setCalcOp(null);
                      setCalcClearNext(true);
                    }
                  } else if (btn === ".") {
                    if (!calcDisplay.includes(".")) setCalcDisplay((prev) => prev + ".");
                  } else {
                    if (calcDisplay === "0" || calcClearNext) {
                      setCalcDisplay(btn);
                      setCalcClearNext(false);
                    } else {
                      setCalcDisplay((prev) => prev + btn);
                    }
                  }
                }}
                className={`py-2 rounded-xl text-xs font-bold transition-all active:scale-95 shadow-xs ${
                  ["+", "-", "×", "÷", "="].includes(btn)
                    ? "bg-primary-600 text-white hover:bg-primary-700"
                    : btn === "C"
                    ? "bg-rose-500 text-white hover:bg-rose-600"
                    : "bg-white text-slate-800 hover:bg-slate-200 border border-slate-200"
                }`}
              >
                {btn}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* 5. FINISH CONFIRMATION MODAL */}
      <FinishConfirmationModal
        isOpen={showFinishModal}
        sections={attempt.sections || []}
        responses={responses}
        visitedQuestionIds={visitedQuestionIds}
        onClose={() => setShowFinishModal(false)}
        onConfirmSubmit={() => handleFinalSubmit('MANUAL_SUBMIT')}
        isSubmitting={isSubmitting}
      />

      {/* 6. TAB SWITCH / BLUR PROCTORING WARNING MODAL */}
      {showBlurWarning && (
        <div 
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/70 backdrop-blur-xs"
          role="dialog"
          aria-modal="true"
          aria-labelledby="proctoring-modal-title"
          aria-describedby="proctoring-modal-desc"
        >
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-rose-200 text-center space-y-4 animate-in zoom-in-95 duration-150">
            <div className="w-14 h-14 rounded-full bg-rose-100 text-rose-600 mx-auto flex items-center justify-center">
              <ShieldAlert className="w-8 h-8" />
            </div>
            <div>
              <h3 className="text-base font-extrabold text-slate-900">
                Warning: Window Switch Detected!
              </h3>
              <p className="text-xs text-rose-700 font-bold mt-1">
                You have switched outside the exam screen {blurCount} of {maxBlurSwitches} allowable times!
              </p>
              <p className="text-xs text-slate-500 mt-2 leading-relaxed">
                Navigating away from the examination window is strictly tracked by window-focus proctoring telemetry. Exceeding the allowable switches will immediately terminate and submit your examination.
              </p>
            </div>
            <button
              type="button"
              onClick={() => setShowBlurWarning(false)}
              className="w-full py-2.5 rounded-xl bg-primary-600 hover:bg-primary-700 text-white font-bold text-xs transition-colors shadow-sm"
            >
              I Understand & Return to Exam
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default ExamCBTPage;
