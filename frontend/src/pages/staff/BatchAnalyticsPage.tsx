import React, { useEffect, useState, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Trophy,
  Users,
  TrendingUp,
  Award,
  RefreshCw,
  Search,
  Download,
  ArrowLeft,
  AlertCircle,
  BarChart2,
  CheckCircle2,
  Eye,
} from 'lucide-react';
import analyticsApi from '../../services/analyticsApi';
import { BatchAnalyticsPayload, CohortRankingEntry } from '../../types';

export const BatchAnalyticsPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [loading, setLoading] = useState<boolean>(true);
  const [evaluating, setEvaluating] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [analytics, setAnalytics] = useState<BatchAnalyticsPayload | null>(null);
  const [searchQuery, setSearchQuery] = useState<string>('');

  const loadAnalytics = async () => {
    if (!id) return;
    try {
      setLoading(true);
      setError(null);
      const data = await analyticsApi.getExamResults(id);
      setAnalytics(data);
    } catch (err: any) {
      console.error('Failed to load batch analytics:', err);
      setError(
        err.response?.data?.detail ||
        err.response?.data?.message ||
        'Failed to load cohort analytics.'
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAnalytics();
  }, [id]);

  const handleReEvaluate = async () => {
    if (!id) return;
    try {
      setEvaluating(true);
      await analyticsApi.evaluateExam(id);
      await loadAnalytics();
    } catch (err: any) {
      console.error('Re-evaluation error:', err);
      alert('Failed to re-evaluate cohort: ' + (err.response?.data?.detail || err.message));
    } finally {
      setEvaluating(false);
    }
  };

  const rankings: CohortRankingEntry[] = useMemo(() => {
    return analytics?.rankings || analytics?.summary?.rankings || [];
  }, [analytics]);

  const filteredRankings = useMemo(() => {
    if (!searchQuery.trim()) return rankings;
    const q = searchQuery.toLowerCase();
    return rankings.filter(
      (r) =>
        r.candidate_name?.toLowerCase().includes(q) ||
        r.username?.toLowerCase().includes(q) ||
        r.student?.toLowerCase().includes(q) ||
        r.attempt_id?.toLowerCase().includes(q)
    );
  }, [rankings, searchQuery]);

  const summary = analytics?.summary;
  const totalCandidates = summary?.total_candidates ?? rankings.length;
  const avgScore = summary?.average_score ?? 0;
  const highestScore = summary?.highest_score ?? 0;
  const lowestScore = summary?.lowest_score ?? 0;

  // Passing stats
  const passingCount = useMemo(() => {
    return rankings.filter((r) => r.total_score >= 0).length; // or check passing
  }, [rankings]);
  const passingRate = totalCandidates > 0 ? Math.round((passingCount / totalCandidates) * 100) : 0;

  // Top performers
  const topPerformers = useMemo(() => {
    return rankings.slice(0, 3);
  }, [rankings]);

  // Score distribution calculations for visual histogram
  const distributionBins = useMemo(() => {
    if (analytics?.score_distribution && analytics.score_distribution.length > 0) {
      return analytics.score_distribution;
    }
    // Fallback bins
    const bins: Record<string, number> = {};
    rankings.forEach((r) => {
      const bucket = `${Math.floor(r.total_score / 10) * 10}-${Math.floor(r.total_score / 10) * 10 + 9}`;
      bins[bucket] = (bins[bucket] || 0) + 1;
    });
    return Object.entries(bins).map(([total_score, candidates]) => ({
      total_score,
      candidates,
    }));
  }, [analytics, rankings]);

  const maxBinCount = useMemo(() => {
    return Math.max(...distributionBins.map((b) => Number(b.candidates)), 1);
  }, [distributionBins]);

  const handleExportCsv = () => {
    if (!rankings.length) return;
    const headers = ['Rank', 'Candidate Name', 'Username', 'Total Score', 'Maximum Score', 'Penalty', 'Percentile'];
    const rows = rankings.map((r) => [
      r.rank,
      `"${r.candidate_name || r.student || ''}"`,
      `"${r.username || ''}"`,
      r.total_score,
      r.maximum_score,
      r.penalty,
      r.percentile,
    ]);
    const csvContent = 'data:text/csv;charset=utf-8,' + [headers.join(','), ...rows.map((e) => e.join(','))].join('\n');
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement('a');
    link.setAttribute('href', encodedUri);
    link.setAttribute('download', `cohort-rankings-${id}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center p-6">
        <div className="w-12 h-12 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin mb-4" />
        <h2 className="text-xl font-bold text-slate-800">Compiling Cohort Analytics...</h2>
        <p className="text-sm text-slate-500 mt-1">Aggregating score distribution, calculating percentiles and leaderboard.</p>
      </div>
    );
  }

  if (error || !analytics) {
    return (
      <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center p-6">
        <div className="max-w-md w-full bg-white rounded-2xl shadow-lg border border-slate-200 p-8 text-center">
          <div className="w-14 h-14 bg-rose-100 text-rose-600 rounded-full flex items-center justify-center mx-auto mb-4">
            <AlertCircle className="w-8 h-8" />
          </div>
          <h2 className="text-xl font-bold text-slate-900 mb-2">Analytics Unavailable</h2>
          <p className="text-sm text-slate-600 mb-6">{error || 'No evaluation data found for this examination.'}</p>
          <div className="flex gap-3">
            <button
              onClick={() => navigate('/staff/exams')}
              className="flex-1 px-4 py-2.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 font-medium text-sm transition"
            >
              Back to Exams
            </button>
            <button
              onClick={handleReEvaluate}
              disabled={evaluating}
              className="flex-1 px-4 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-medium text-sm transition"
            >
              {evaluating ? 'Evaluating...' : 'Evaluate Now'}
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8 pb-16">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-200">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate('/staff/exams')}
            className="p-2 rounded-xl text-slate-500 hover:text-slate-800 hover:bg-slate-100 transition"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div>
            <h1 className="text-2xl font-extrabold text-slate-900">Cohort Batch Analytics</h1>
            <p className="text-xs text-slate-500">
              Exam ID: <span className="font-mono text-slate-700">{id}</span> • Evaluated:{' '}
              {summary?.evaluated_at ? new Date(summary.evaluated_at).toLocaleString() : 'Recent'}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={handleReEvaluate}
            disabled={evaluating}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-indigo-50 text-indigo-700 hover:bg-indigo-100 border border-indigo-200 text-xs font-semibold transition"
          >
            <RefreshCw className={`w-4 h-4 ${evaluating ? 'animate-spin' : ''}`} />
            {evaluating ? 'Recalculating...' : 'Re-Evaluate Cohort'}
          </button>
          <button
            onClick={handleExportCsv}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-900 text-white text-xs font-semibold shadow-sm transition"
          >
            <Download className="w-4 h-4" /> Export Leaderboard
          </button>
        </div>
      </div>

      {/* Metric Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        {/* Total Candidates */}
        <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm">
          <div className="flex items-center justify-between text-slate-500 text-xs font-medium mb-1">
            <span>Candidates Tested</span>
            <Users className="w-4 h-4 text-indigo-500" />
          </div>
          <div className="text-3xl font-extrabold text-slate-900">{totalCandidates}</div>
          <span className="text-xs text-slate-400 mt-1 block">Final submitted attempts</span>
        </div>

        {/* Batch Average */}
        <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm">
          <div className="flex items-center justify-between text-slate-500 text-xs font-medium mb-1">
            <span>Cohort Average</span>
            <TrendingUp className="w-4 h-4 text-emerald-500" />
          </div>
          <div className="text-3xl font-extrabold text-emerald-600">{avgScore}</div>
          <span className="text-xs text-slate-400 mt-1 block">Mean score of cohort</span>
        </div>

        {/* Highest Score */}
        <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm">
          <div className="flex items-center justify-between text-slate-500 text-xs font-medium mb-1">
            <span>Highest Score</span>
            <Trophy className="w-4 h-4 text-amber-500" />
          </div>
          <div className="text-3xl font-extrabold text-amber-600">{highestScore}</div>
          <span className="text-xs text-slate-400 mt-1 block">Top candidate score</span>
        </div>

        {/* Lowest Score */}
        <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm">
          <div className="flex items-center justify-between text-slate-500 text-xs font-medium mb-1">
            <span>Lowest Score</span>
            <BarChart2 className="w-4 h-4 text-slate-400" />
          </div>
          <div className="text-3xl font-extrabold text-slate-700">{lowestScore}</div>
          <span className="text-xs text-slate-400 mt-1 block">Baseline attempt score</span>
        </div>

        {/* Passing Rate */}
        <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm">
          <div className="flex items-center justify-between text-slate-500 text-xs font-medium mb-1">
            <span>Passing Rate</span>
            <CheckCircle2 className="w-4 h-4 text-cyan-500" />
          </div>
          <div className="text-3xl font-extrabold text-cyan-600">{passingRate}%</div>
          <span className="text-xs text-slate-400 mt-1 block">{passingCount} candidates passing</span>
        </div>
      </div>

      {/* Score Distribution & Top Performers Section */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Score Distribution Histogram */}
        <div className="lg:col-span-2 bg-white rounded-3xl border border-slate-200 p-6 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-lg font-bold text-slate-900">Score Distribution Histogram</h2>
              <p className="text-xs text-slate-500">Frequency of candidate net scores across the cohort</p>
            </div>
            <BarChart2 className="w-5 h-5 text-indigo-500" />
          </div>

          <div className="h-48 flex items-end gap-3 pt-6 border-b border-slate-200 pb-2">
            {distributionBins.map((bin, idx) => {
              const count = Number(bin.candidates);
              const heightPct = Math.round((count / maxBinCount) * 100);
              return (
                <div key={idx} className="flex-1 flex flex-col items-center h-full justify-end group">
                  <span className="text-xs font-bold text-slate-700 opacity-0 group-hover:opacity-100 transition-opacity mb-1">
                    {count}
                  </span>
                  <div
                    className="w-full bg-indigo-500 hover:bg-indigo-600 rounded-t-lg transition-all duration-300 min-h-[4px]"
                    style={{ height: `${Math.max(heightPct, 6)}%` }}
                  />
                  <span className="text-[10px] text-slate-500 mt-2 rotate-[-45deg] origin-top-left font-mono">
                    {bin.total_score}
                  </span>
                </div>
              );
            })}
          </div>
        </div>

        {/* Top Performers Podium */}
        <div className="bg-white rounded-3xl border border-slate-200 p-6 shadow-sm flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-bold text-slate-900">Top Performers</h2>
              <Award className="w-5 h-5 text-amber-500" />
            </div>

            <div className="space-y-3">
              {topPerformers.map((cand, idx) => (
                <div
                  key={cand.attempt_id}
                  className="flex items-center justify-between p-3 rounded-2xl bg-slate-50 border border-slate-200"
                >
                  <div className="flex items-center gap-3">
                    <span
                      className={`w-7 h-7 rounded-full flex items-center justify-center font-bold text-xs ${
                        idx === 0
                          ? 'bg-amber-400 text-white'
                          : idx === 1
                          ? 'bg-slate-300 text-slate-800'
                          : 'bg-amber-700/60 text-white'
                      }`}
                    >
                      #{cand.rank}
                    </span>
                    <div>
                      <h4 className="font-bold text-slate-900 text-xs">
                        {cand.candidate_name || cand.student || cand.username}
                      </h4>
                      <span className="text-[10px] text-slate-400 font-mono">@{cand.username}</span>
                    </div>
                  </div>
                  <div className="text-right">
                    <span className="font-extrabold text-sm text-indigo-600">{cand.total_score} pts</span>
                    <span className="block text-[10px] text-emerald-600 font-semibold">
                      {cand.percentile?.toFixed(2)}%ile
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="mt-4 pt-4 border-t border-slate-100 text-xs text-slate-400 text-center">
            Rankings determined with standard tie-break order
          </div>
        </div>
      </div>

      {/* Cohort Leaderboard Table */}
      <div className="bg-white rounded-3xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="p-6 border-b border-slate-200 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h2 className="text-xl font-bold text-slate-900">Cohort Leaderboard</h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Deterministic rankings with section breakdown, penalties, and percentile scores
            </p>
          </div>

          <div className="relative w-full sm:w-72">
            <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search candidate name or username..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 text-xs rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500 bg-slate-50"
            />
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 border-b border-slate-200 text-slate-500 font-semibold uppercase tracking-wider">
              <tr>
                <th className="py-3.5 px-6">Rank</th>
                <th className="py-3.5 px-6">Candidate</th>
                <th className="py-3.5 px-6">Net Score</th>
                <th className="py-3.5 px-6">Penalty</th>
                <th className="py-3.5 px-6">Correct / Incorrect</th>
                <th className="py-3.5 px-6">Percentile</th>
                <th className="py-3.5 px-6 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filteredRankings.length > 0 ? (
                filteredRankings.map((cand) => (
                  <tr key={cand.attempt_id} className="hover:bg-slate-50/80 transition">
                    <td className="py-4 px-6 font-bold text-slate-900">
                      <span
                        className={`inline-flex items-center justify-center w-6 h-6 rounded-full text-xs font-bold ${
                          cand.rank === 1
                            ? 'bg-amber-100 text-amber-800 border border-amber-300'
                            : cand.rank === 2
                            ? 'bg-slate-100 text-slate-700 border border-slate-300'
                            : cand.rank === 3
                            ? 'bg-orange-100 text-orange-800 border border-orange-300'
                            : 'text-slate-600'
                        }`}
                      >
                        {cand.rank}
                      </span>
                    </td>
                    <td className="py-4 px-6">
                      <div className="font-bold text-slate-900">
                        {cand.candidate_name || cand.student || cand.username}
                      </div>
                      <div className="text-[11px] text-slate-400 font-mono">@{cand.username}</div>
                    </td>
                    <td className="py-4 px-6">
                      <span className="font-extrabold text-sm text-slate-900">{cand.total_score}</span>
                      <span className="text-slate-400 font-normal"> / {cand.maximum_score}</span>
                    </td>
                    <td className="py-4 px-6">
                      {cand.penalty > 0 ? (
                        <span className="text-rose-600 font-semibold">-{cand.penalty} pts</span>
                      ) : (
                        <span className="text-slate-400">0 pts</span>
                      )}
                    </td>
                    <td className="py-4 px-6">
                      <span className="text-emerald-600 font-semibold">{cand.total_correct}</span> /{' '}
                      <span className="text-rose-600 font-semibold">{cand.total_incorrect}</span>
                    </td>
                    <td className="py-4 px-6">
                      <span className="px-2.5 py-1 rounded-md bg-indigo-50 text-indigo-700 font-bold border border-indigo-200">
                        {cand.percentile?.toFixed(3)}%
                      </span>
                    </td>
                    <td className="py-4 px-6 text-right">
                      <button
                        onClick={() => navigate(`/student/exam/${cand.attempt_id}/report`)}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold text-xs transition"
                        title="View Detailed Student Report"
                      >
                        <Eye className="w-3.5 h-3.5" /> View Report
                      </button>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-slate-400">
                    No candidates found matching the query.
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

export default BatchAnalyticsPage;
