import React, { useEffect, useState, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Trophy,
  Award,
  CheckCircle2,
  XCircle,
  AlertCircle,
  HelpCircle,
  Clock,
  ArrowLeft,
  Download,
  BarChart3,
  MinusCircle,
  Sparkles,
} from 'lucide-react';
import analyticsApi from '../../services/analyticsApi';
import { ExamReportPayload, QuestionReviewItem, ReviewOutcome } from '../../types';
import MathRenderer from '../../components/MathRenderer';

export const ExamResultReportPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [reportData, setReportData] = useState<ExamReportPayload | null>(null);

  // Filters for questions pane
  const [selectedSection, setSelectedSection] = useState<string>('ALL');
  const [selectedOutcome, setSelectedOutcome] = useState<string>('ALL');

  useEffect(() => {
    if (!id) {
      setError('Attempt ID is missing.');
      setLoading(false);
      return;
    }

    const fetchReport = async () => {
      try {
        setLoading(true);
        setError(null);
        const data = await analyticsApi.getAttemptReport(id);
        setReportData(data);
      } catch (err: any) {
        console.error('Failed to load exam report:', err);
        setError(
          err.response?.data?.detail ||
          err.response?.data?.message ||
          'Failed to load examination report. The results may still be evaluating or withheld.'
        );
      } finally {
        setLoading(false);
      }
    };

    fetchReport();
  }, [id]);

  const report = reportData?.report;
  const sections = reportData?.sections || [];
  const reviews: QuestionReviewItem[] = useMemo(() => {
    if (reportData?.reviews && reportData.reviews.length > 0) {
      return reportData.reviews;
    }
    // Fallback: extract reviews from sections
    const items: QuestionReviewItem[] = [];
    sections.forEach((sec) => {
      if (sec.reviews) {
        sec.reviews.forEach((r) => items.push({ ...r, section: sec.title }));
      }
    });
    return items;
  }, [reportData, sections]);

  // Unique sections list
  const sectionTitles = useMemo(() => {
    const titles = new Set<string>();
    reviews.forEach((r) => {
      if (r.section) titles.add(r.section);
    });
    return Array.from(titles);
  }, [reviews]);

  // Filtered reviews
  const filteredReviews = useMemo(() => {
    return reviews.filter((r) => {
      if (selectedSection !== 'ALL' && r.section !== selectedSection) {
        return false;
      }
      if (selectedOutcome !== 'ALL' && r.outcome !== selectedOutcome) {
        return false;
      }
      return true;
    });
  }, [reviews, selectedSection, selectedOutcome]);

  const handleDownloadCsv = async () => {
    if (!reportData?.result?.id) return;
    try {
      const blob = await analyticsApi.downloadScorecardCsv(reportData.result.id);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `Scorecard-${reportData.exam_name || 'Exam'}.csv`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err) {
      console.error('Failed to download CSV:', err);
    }
  };

  const getOutcomeBadge = (outcome: ReviewOutcome) => {
    switch (outcome) {
      case 'CORRECT':
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800 border border-emerald-300">
            <CheckCircle2 className="w-3.5 h-3.5" /> Correct
          </span>
        );
      case 'PARTIAL':
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-amber-100 text-amber-800 border border-amber-300">
            <Sparkles className="w-3.5 h-3.5" /> Partial Credit
          </span>
        );
      case 'INCORRECT':
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-rose-100 text-rose-800 border border-rose-300">
            <XCircle className="w-3.5 h-3.5" /> Incorrect
          </span>
        );
      case 'CANCELLED':
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-purple-100 text-purple-800 border border-purple-300">
            <Award className="w-3.5 h-3.5" /> Cancelled (Bonus)
          </span>
        );
      case 'UNANSWERED':
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-slate-100 text-slate-700 border border-slate-300">
            <MinusCircle className="w-3.5 h-3.5" /> Unattempted
          </span>
        );
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center p-6">
        <div className="w-12 h-12 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin mb-4" />
        <h2 className="text-xl font-bold text-slate-800">Generating Performance Report...</h2>
        <p className="text-sm text-slate-500 mt-1">Evaluating marking scheme, calculating cohort percentiles and rankings.</p>
      </div>
    );
  }

  if (error || !reportData || !report) {
    return (
      <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center p-6">
        <div className="max-w-md w-full bg-white rounded-2xl shadow-lg border border-slate-200 p-8 text-center">
          <div className="w-14 h-14 bg-rose-100 text-rose-600 rounded-full flex items-center justify-center mx-auto mb-4">
            <AlertCircle className="w-8 h-8" />
          </div>
          <h2 className="text-xl font-bold text-slate-900 mb-2">Report Not Available</h2>
          <p className="text-sm text-slate-600 mb-6">{error || 'Unable to retrieve exam evaluation.'}</p>
          <button
            onClick={() => navigate('/student')}
            className="w-full inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-900 text-white font-medium text-sm transition"
          >
            <ArrowLeft className="w-4 h-4" /> Back to Dashboard
          </button>
        </div>
      </div>
    );
  }

  const isPassed = report.passed ?? (report.score_percentage >= 40);

  return (
    <div className="min-h-screen bg-slate-50 text-slate-800 pb-16">
      {/* Top Navigation Bar */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-30 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button
              onClick={() => navigate(-1)}
              className="p-2 rounded-xl text-slate-500 hover:text-slate-800 hover:bg-slate-100 transition"
              title="Go back"
            >
              <ArrowLeft className="w-5 h-5" />
            </button>
            <div>
              <h1 className="text-lg font-bold text-slate-900 leading-tight">
                {reportData.exam_name || 'Examination Performance Report'}
              </h1>
              <p className="text-xs text-slate-500">
                Candidate: <span className="font-semibold text-slate-700">{report.candidate_name || 'Student'}</span> • Attempt #{report.attempt_id.slice(0, 8)}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {reportData.result?.id && (
              <button
                onClick={handleDownloadCsv}
                className="inline-flex items-center gap-2 px-3.5 py-2 rounded-xl bg-indigo-50 text-indigo-700 hover:bg-indigo-100 border border-indigo-200 text-xs font-semibold transition"
              >
                <Download className="w-4 h-4" /> Export CSV
              </button>
            )}
            <button
              onClick={() => window.print()}
              className="inline-flex items-center gap-2 px-3.5 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold transition"
            >
              Print Report
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-8 space-y-8">
        {/* Candidate Scorecard Summary Banner */}
        <section className="bg-gradient-to-br from-slate-900 via-indigo-950 to-slate-900 text-white rounded-3xl p-6 sm:p-8 shadow-xl relative overflow-hidden">
          <div className="absolute right-0 top-0 translate-x-12 -translate-y-12 w-96 h-96 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none" />

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 items-center">
            {/* Score & Percentage */}
            <div className="bg-white/10 backdrop-blur-md rounded-2xl p-5 border border-white/15">
              <span className="text-xs font-medium text-slate-300 uppercase tracking-wider block mb-1">
                Total Score
              </span>
              <div className="flex items-baseline gap-2">
                <span className="text-4xl font-extrabold text-white">
                  {report.total_score}
                </span>
                <span className="text-lg text-slate-300 font-medium">
                  / {report.maximum_score}
                </span>
              </div>
              <div className="mt-3 flex items-center justify-between text-xs">
                <span className="text-slate-300">Score Percentage:</span>
                <span className="font-bold text-emerald-400 text-sm">
                  {report.score_percentage.toFixed(2)}%
                </span>
              </div>
            </div>

            {/* Cohort Rank */}
            <div className="bg-white/10 backdrop-blur-md rounded-2xl p-5 border border-white/15">
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-medium text-slate-300 uppercase tracking-wider">
                  Cohort Rank
                </span>
                <Trophy className="w-5 h-5 text-amber-400" />
              </div>
              <div className="text-4xl font-extrabold text-amber-300">
                {report.rank !== null && report.rank !== undefined ? `#${report.rank}` : 'N/A'}
              </div>
              <p className="mt-3 text-xs text-slate-300">
                Official deterministic tie-break rank
              </p>
            </div>

            {/* Percentile */}
            <div className="bg-white/10 backdrop-blur-md rounded-2xl p-5 border border-white/15">
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-medium text-slate-300 uppercase tracking-wider">
                  Percentile
                </span>
                <BarChart3 className="w-5 h-5 text-cyan-400" />
              </div>
              <div className="text-4xl font-extrabold text-cyan-300">
                {report.percentile !== null && report.percentile !== undefined
                  ? `${report.percentile.toFixed(3)}%`
                  : 'N/A'}
              </div>
              <p className="mt-3 text-xs text-slate-300">
                Better than or equal to cohort
              </p>
            </div>

            {/* Status & Penalty */}
            <div className="bg-white/10 backdrop-blur-md rounded-2xl p-5 border border-white/15">
              <span className="text-xs font-medium text-slate-300 uppercase tracking-wider block mb-2">
                Assessment Outcome
              </span>
              <div>
                {isPassed ? (
                  <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                    <CheckCircle2 className="w-4 h-4" /> PASSED
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-rose-500/20 text-rose-300 border border-rose-500/30">
                    <XCircle className="w-4 h-4" /> NEEDS REVIEW
                  </span>
                )}
              </div>
              <div className="mt-4 pt-3 border-t border-white/10 flex items-center justify-between text-xs text-slate-300">
                <span>Negative Deduction:</span>
                <span className="font-semibold text-rose-300">-{report.penalty} pts</span>
              </div>
            </div>
          </div>

          {/* Quick Metrics Strip */}
          <div className="mt-6 pt-6 border-t border-white/15 grid grid-cols-3 gap-4 text-center">
            <div className="bg-white/5 rounded-xl py-2 px-3">
              <span className="text-xs text-slate-400 block">Correct Answers</span>
              <span className="text-lg font-bold text-emerald-400">{report.total_correct}</span>
            </div>
            <div className="bg-white/5 rounded-xl py-2 px-3">
              <span className="text-xs text-slate-400 block">Incorrect Answers</span>
              <span className="text-lg font-bold text-rose-400">{report.total_incorrect}</span>
            </div>
            <div className="bg-white/5 rounded-xl py-2 px-3">
              <span className="text-xs text-slate-400 block">Unattempted</span>
              <span className="text-lg font-bold text-slate-300">{report.total_unanswered}</span>
            </div>
          </div>
        </section>

        {/* Section-wise Performance Cards */}
        <section>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
              <BarChart3 className="w-5 h-5 text-indigo-600" />
              Section Breakdown & Accuracy
            </h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {sections.length > 0 ? (
              sections.map((sec, idx) => {
                const secScore = Number(sec.score);
                const secMax = Number(sec.maximum_score);
                const pct = secMax > 0 ? Math.round((secScore / secMax) * 100) : 0;
                return (
                  <div
                    key={sec.title || idx}
                    className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm hover:shadow-md transition"
                  >
                    <div className="flex items-center justify-between mb-3">
                      <h3 className="font-bold text-slate-900 text-base">{sec.title}</h3>
                      <span className="text-xs font-semibold px-2 py-0.5 rounded-md bg-indigo-50 text-indigo-700 border border-indigo-200">
                        Section #{sec.order}
                      </span>
                    </div>

                    <div className="flex items-baseline justify-between mb-2">
                      <span className="text-2xl font-extrabold text-slate-900">
                        {secScore} <span className="text-sm font-normal text-slate-500">/ {secMax}</span>
                      </span>
                      <span className={`text-sm font-bold ${pct >= 50 ? 'text-emerald-600' : 'text-amber-600'}`}>
                        {pct}% Accuracy
                      </span>
                    </div>

                    <div className="w-full bg-slate-100 rounded-full h-2.5 overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all duration-500 ${
                          pct >= 70 ? 'bg-emerald-500' : pct >= 40 ? 'bg-indigo-600' : 'bg-rose-500'
                        }`}
                        style={{ width: `${Math.min(100, Math.max(0, pct))}%` }}
                      />
                    </div>
                  </div>
                );
              })
            ) : (
              <div className="col-span-full bg-white rounded-2xl border border-slate-200 p-8 text-center text-slate-500">
                No section details configured for this examination.
              </div>
            )}
          </div>
        </section>

        {/* Detailed Question Review Pane */}
        <section className="bg-white rounded-3xl border border-slate-200 shadow-sm p-6 sm:p-8">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 pb-6 border-b border-slate-200">
            <div>
              <h2 className="text-xl font-bold text-slate-900">Question-by-Question Review</h2>
              <p className="text-xs text-slate-500 mt-1">
                Showing {filteredReviews.length} of {reviews.length} total questions
              </p>
            </div>

            {/* Filter Controls */}
            <div className="flex flex-wrap items-center gap-3">
              {/* Section Filter */}
              {sectionTitles.length > 1 && (
                <div className="flex items-center gap-1.5 bg-slate-100 rounded-xl p-1 text-xs">
                  <button
                    onClick={() => setSelectedSection('ALL')}
                    className={`px-3 py-1.5 rounded-lg font-medium transition ${
                      selectedSection === 'ALL'
                        ? 'bg-white text-slate-900 shadow-sm font-semibold'
                        : 'text-slate-600 hover:text-slate-900'
                    }`}
                  >
                    All Sections
                  </button>
                  {sectionTitles.map((title) => (
                    <button
                      key={title}
                      onClick={() => setSelectedSection(title)}
                      className={`px-3 py-1.5 rounded-lg font-medium transition ${
                        selectedSection === title
                          ? 'bg-white text-slate-900 shadow-sm font-semibold'
                          : 'text-slate-600 hover:text-slate-900'
                      }`}
                    >
                      {title}
                    </button>
                  ))}
                </div>
              )}

              {/* Outcome Filter */}
              <div className="flex items-center gap-1.5 bg-slate-100 rounded-xl p-1 text-xs">
                {(['ALL', 'CORRECT', 'PARTIAL', 'INCORRECT', 'UNANSWERED'] as const).map((outc) => (
                  <button
                    key={outc}
                    onClick={() => setSelectedOutcome(outc)}
                    className={`px-2.5 py-1.5 rounded-lg font-medium transition ${
                      selectedOutcome === outc
                        ? 'bg-white text-slate-900 shadow-sm font-semibold'
                        : 'text-slate-600 hover:text-slate-900'
                    }`}
                  >
                    {outc === 'ALL' ? 'All Outcomes' : outc.charAt(0) + outc.slice(1).toLowerCase()}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Question List */}
          <div className="divide-y divide-slate-100 mt-6 space-y-6">
            {filteredReviews.length > 0 ? (
              filteredReviews.map((rev, index) => {
                const marksAwarded = Number(rev.marks_awarded ?? rev.marks ?? 0);
                const isPositive = marksAwarded > 0;
                const isNegative = marksAwarded < 0;

                return (
                  <div key={rev.question_id || index} className="pt-6 first:pt-0">
                    <div className="flex items-start justify-between gap-4 mb-3">
                      <div className="flex items-center gap-3">
                        <span className="w-8 h-8 rounded-full bg-slate-100 text-slate-700 font-bold text-sm flex items-center justify-center">
                          {index + 1}
                        </span>
                        {getOutcomeBadge(rev.outcome)}
                        {rev.section && (
                          <span className="text-xs text-slate-400 font-medium">
                            • Section: {rev.section}
                          </span>
                        )}
                      </div>

                      <div className="flex items-center gap-3 text-xs">
                        <div
                          className={`font-bold px-2.5 py-1 rounded-lg ${
                            isPositive
                              ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                              : isNegative
                              ? 'bg-rose-50 text-rose-700 border border-rose-200'
                              : 'bg-slate-50 text-slate-600 border border-slate-200'
                          }`}
                        >
                          {isPositive ? `+${marksAwarded.toFixed(2)}` : marksAwarded.toFixed(2)} marks
                        </div>
                        {rev.time_spent_seconds !== undefined && (
                          <span className="flex items-center gap-1 text-slate-400 font-mono">
                            <Clock className="w-3.5 h-3.5" /> {rev.time_spent_seconds}s
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Question Content */}
                    <div className="bg-slate-50 rounded-2xl p-4 sm:p-5 border border-slate-200/80 mb-4 text-sm font-medium">
                      <MathRenderer content={rev.question_text || rev.content_text || `Question ${index + 1}`} />
                    </div>

                    {/* Choices / Responses Comparison */}
                    <div className="space-y-2 mb-4">
                      {rev.selected_options && rev.selected_options.length > 0 && (
                        <div className="flex items-center gap-2 text-xs">
                          <span className="font-semibold text-slate-600">Your Chosen Option(s):</span>
                          <span className="px-2 py-0.5 rounded font-mono font-bold bg-indigo-50 text-indigo-700 border border-indigo-200">
                            {rev.selected_options.join(', ')}
                          </span>
                        </div>
                      )}

                      {rev.submitted_value && (
                        <div className="flex items-center gap-2 text-xs">
                          <span className="font-semibold text-slate-600">Your Submitted Value:</span>
                          <span className="px-2 py-0.5 rounded font-mono font-bold bg-indigo-50 text-indigo-700 border border-indigo-200">
                            {rev.submitted_value}
                          </span>
                        </div>
                      )}

                      {/* Correct Answer (if revealed under policy) */}
                      {rev.answer && rev.answer.length > 0 ? (
                        <div className="flex items-center gap-2 text-xs">
                          <span className="font-semibold text-emerald-700">Authoritative Answer:</span>
                          <span className="px-2 py-0.5 rounded font-mono font-bold bg-emerald-50 text-emerald-800 border border-emerald-300">
                            {rev.answer.join(', ')}
                          </span>
                        </div>
                      ) : (
                        <div className="text-xs text-slate-400 italic">
                          Detailed answers and explanations are protected by examination reveal policy.
                        </div>
                      )}
                    </div>

                    {/* Explanation */}
                    {rev.explanation && (
                      <div className="bg-indigo-50/60 rounded-xl p-4 border border-indigo-100 text-xs">
                        <div className="font-bold text-indigo-900 mb-1 flex items-center gap-1.5">
                          <HelpCircle className="w-3.5 h-3.5" /> Solution & Explanation:
                        </div>
                        <div className="text-indigo-950/80">
                          <MathRenderer content={rev.explanation} />
                        </div>
                      </div>
                    )}
                  </div>
                );
              })
            ) : (
              <div className="py-12 text-center text-slate-500">
                No questions match the selected filter criteria.
              </div>
            )}
          </div>
        </section>
      </main>
    </div>
  );
};

export default ExamResultReportPage;
