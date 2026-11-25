import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiService } from '../../services/api';
import { Examination, QuestionBank, Batch, ExaminationCenter, Question } from '../../types';
import {
  Plus,
  Search,
  CheckCircle2,
  Calendar,
  Clock,
  Users,
  Shield,
  Eye,
  Send,
  AlertCircle,
  BarChart2,
} from 'lucide-react';

export const ExaminationsPage: React.FC = () => {
  const navigate = useNavigate();
  const [exams, setExams] = useState<Examination[]>([]);
  const [papers, setPapers] = useState<QuestionBank[]>([]);
  const [batches, setBatches] = useState<Batch[]>([]);
  const [centers, setCenters] = useState<ExaminationCenter[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [search, setSearch] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('');

  // Exam Creation Modal State (#new-exam-modal)
  const [newExamModalOpen, setNewExamModalOpen] = useState<boolean>(false);
  const [step, setStep] = useState<1 | 2>(1);
  const [examForm, setExamForm] = useState({
    name: '',
    duration_minutes: 60,
    question_paper_id: '',
    start_window: '',
    end_window: '',
    max_window_switches: 5,
    shuffle_questions: true,
    camera_proctoring: false,
    allow_section_skip: true,
    pc_only: true,
    hide_results: true,
    hide_rank: true,
    practice_mode: false,
  });

  // Candidate Assignment Drawer State (#card-onex-stud)
  const [assignDrawerOpen, setAssignDrawerOpen] = useState<boolean>(false);
  const [assigningExam, setAssigningExam] = useState<Examination | null>(null);
  const [selectedBatches, setSelectedBatches] = useState<string[]>([]);
  const [selectedCenters, setSelectedCenters] = useState<string[]>([]);
  const [isAssigning, setIsAssigning] = useState<boolean>(false);

  // Publish Dialog State
  const [publishDialogOpen, setPublishDialogOpen] = useState<boolean>(false);
  const [publishingExam, setPublishingExam] = useState<Examination | null>(null);
  const [isPublishing, setIsPublishing] = useState<boolean>(false);

  // Preview State
  const [previewModalOpen, setPreviewModalOpen] = useState<boolean>(false);
  const [previewData, setPreviewData] = useState<{ exam: Examination | null; questions: Question[] }>({
    exam: null,
    questions: [],
  });
  const [loadingPreview, setLoadingPreview] = useState<boolean>(false);

  const [errorMsg, setErrorMsg] = useState<string>('');
  const [successMsg, setSuccessMsg] = useState<string>('');

  const fetchExams = async () => {
    try {
      setLoading(true);
      const data = await apiService.getExaminations();
      setExams(data);
    } catch (err) {
      console.error('Failed to load examinations:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchExams();
    const loadPrereqs = async () => {
      try {
        const [pData, bData, cData] = await Promise.all([
          apiService.getQuestionBanks(),
          apiService.getBatches(),
          apiService.getCenters(),
        ]);
        setPapers(pData);
        setBatches(bData);
        setCenters(cData);
      } catch (err) {
        console.error('Failed to load exam prereqs:', err);
      }
    };
    loadPrereqs();
  }, []);

  const openNewExamModal = () => {
    setStep(1);
    setExamForm({
      name: '',
      duration_minutes: 60,
      question_paper_id: papers[0]?.id || '',
      start_window: '',
      end_window: '',
      max_window_switches: 5,
      shuffle_questions: true,
      camera_proctoring: false,
      allow_section_skip: true,
      pc_only: true,
      hide_results: true,
      hide_rank: true,
      practice_mode: false,
    });
    setErrorMsg('');
    setNewExamModalOpen(true);
  };

  const handleCreateExam = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!examForm.name.trim()) {
      setErrorMsg('Exam title is required.');
      return;
    }
    if (examForm.duration_minutes <= 0) {
      setErrorMsg('Duration must be greater than zero.');
      return;
    }
    try {
      setErrorMsg('');
      await apiService.createExamination({
        ...examForm,
        start_window: examForm.start_window ? new Date(examForm.start_window).toISOString() : null,
        end_window: examForm.end_window ? new Date(examForm.end_window).toISOString() : null,
      });
      setNewExamModalOpen(false);
      fetchExams();
    } catch (err: any) {
      setErrorMsg(err.response?.data?.message || err.response?.data?.code || 'Failed to create examination.');
    }
  };

  const openAssignDrawer = (exam: Examination) => {
    setAssigningExam(exam);
    setSelectedBatches([]);
    setSelectedCenters([]);
    setErrorMsg('');
    setSuccessMsg('');
    setAssignDrawerOpen(true);
  };

  const handleAssignCandidates = async () => {
    if (!assigningExam) return;
    if (selectedBatches.length === 0 && selectedCenters.length === 0) {
      setErrorMsg('Please select at least one batch or examination centre.');
      return;
    }
    try {
      setIsAssigning(true);
      setErrorMsg('');
      const res = await apiService.assignCandidates(assigningExam.id, {
        batch_ids: selectedBatches,
        centre_ids: selectedCenters,
      });
      setSuccessMsg(`${res.assigned_count} new batch or centre assignments saved.`);
      setTimeout(() => {
        setAssignDrawerOpen(false);
        fetchExams();
      }, 1500);
    } catch (err: any) {
      setErrorMsg(err.response?.data?.message || 'Failed to assign candidates.');
    } finally {
      setIsAssigning(false);
    }
  };

  const openPublishDialog = (exam: Examination) => {
    setPublishingExam(exam);
    setErrorMsg('');
    setPublishDialogOpen(true);
  };

  const handlePublishExam = async () => {
    if (!publishingExam) return;
    try {
      setIsPublishing(true);
      setErrorMsg('');
      await apiService.publishExamination(publishingExam.id);
      setPublishDialogOpen(false);
      fetchExams();
    } catch (err: any) {
      const code = err.response?.data?.code;
      if (code === 'EMPTY_EXAM') {
        setErrorMsg('Cannot publish: Question paper attached has 0 questions. Please add questions first.');
      } else {
        setErrorMsg(err.response?.data?.message || 'Failed to publish examination.');
      }
    } finally {
      setIsPublishing(false);
    }
  };

  const openPreviewModal = async (exam: Examination) => {
    try {
      setLoadingPreview(true);
      setPreviewModalOpen(true);
      const res = await apiService.getExamPreview(exam.id);
      setPreviewData(res);
    } catch (err) {
      console.error('Failed to load preview:', err);
    } finally {
      setLoadingPreview(false);
    }
  };

  const filteredExams = exams.filter((ex) => {
    const q = search.toLowerCase();
    const matchesSearch = ex.name.toLowerCase().includes(q) || (ex.code && ex.code.toLowerCase().includes(q));
    const matchesStatus = !statusFilter || ex.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  return (
    <div className="p-6 space-y-6">
      {/* Top Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Online Examinations</h1>
          <p className="text-sm text-slate-500 mt-1">
            Configure examination schedules, anti-cheat proctoring, candidate allocations, and test publication.
          </p>
        </div>
        <button
          onClick={openNewExamModal}
          className="flex items-center gap-2 bg-primary-500 hover:bg-primary-600 text-white px-4 py-2.5 rounded-xl font-semibold text-sm transition-colors shadow-sm"
        >
          <Plus size={18} />
          <span>New Examination (#new-exam-modal)</span>
        </button>
      </div>

      {/* Filter Row */}
      <div className="flex flex-wrap items-center justify-between gap-4 bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
        <div className="flex items-center gap-3 flex-1 min-w-[280px]">
          <div className="relative flex-1">
            <Search size={18} className="absolute left-3 top-2.5 text-slate-400" />
            <input
              type="text"
              placeholder="Search examinations by title or code..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-9 pr-4 py-2 text-sm rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500"
            />
          </div>

          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-3 py-2 text-sm rounded-lg border border-slate-200 bg-white text-slate-700"
          >
            <option value="">All Statuses</option>
            <option value="DRAFT">Draft</option>
            <option value="PUBLISHED">Published</option>
            <option value="SCHEDULED">Scheduled</option>
            <option value="CLOSED">Closed</option>
          </select>
        </div>

        <div className="text-sm text-slate-500">
          Showing: <span className="font-semibold text-slate-700">{filteredExams.length}</span> exams
        </div>
      </div>

      {/* Examinations Cards Grid */}
      {loading ? (
        <div className="p-12 text-center text-slate-400 bg-white rounded-xl border border-slate-200">
          Loading examinations...
        </div>
      ) : filteredExams.length === 0 ? (
        <div className="p-16 text-center text-slate-400 bg-white rounded-xl border border-slate-200">
          No examinations found. Click "New Examination" to author one.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredExams.map((exam) => {
            const isDraft = exam.status === 'DRAFT';
            const isPublished = exam.status === 'PUBLISHED' || exam.status === 'SCHEDULED';
            return (
              <div
                key={exam.id}
                className="bg-white rounded-2xl border border-slate-200 shadow-sm hover:shadow-md transition-shadow p-5 flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-start justify-between gap-2">
                    <span
                      className={`inline-block px-2.5 py-0.5 rounded-full text-[11px] font-bold uppercase tracking-wider ${
                        isDraft
                          ? 'bg-slate-100 text-slate-600'
                          : isPublished
                          ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                          : 'bg-rose-50 text-rose-700'
                      }`}
                    >
                      {exam.status}
                    </span>
                    <span className="font-mono text-xs text-slate-400">{exam.code}</span>
                  </div>

                  <h3 className="text-lg font-bold text-slate-800 mt-2 line-clamp-1">{exam.name}</h3>

                  <div className="space-y-1.5 mt-4 text-xs text-slate-600">
                    <div className="flex items-center gap-2">
                      <Clock size={14} className="text-slate-400 flex-shrink-0" />
                      <span>Duration: <strong className="text-slate-700">{exam.duration_minutes} minutes</strong></span>
                    </div>

                    <div className="flex items-center gap-2">
                      <Calendar size={14} className="text-slate-400 flex-shrink-0" />
                      <span>
                        Window:{' '}
                        {exam.start_window ? (
                          <strong className="text-slate-700">
                            {new Date(exam.start_window).toLocaleDateString()}
                          </strong>
                        ) : (
                          <span className="text-slate-400">Open Anytime</span>
                        )}
                      </span>
                    </div>

                    <div className="flex items-center gap-2">
                      <Shield size={14} className="text-slate-400 flex-shrink-0" />
                      <span>
                        Security: {exam.max_window_switches} switch limit
                        {exam.camera_proctoring && ' • Webcam required'}
                      </span>
                    </div>

                    <div className="flex items-center gap-2">
                      <Users size={14} className="text-slate-400 flex-shrink-0" />
                      <span>
                        Assigned:{' '}
                        {exam.assigned_groups && exam.assigned_groups.length > 0 ? (
                          <strong className="text-slate-700">{exam.assigned_groups.join(', ')}</strong>
                        ) : (
                          <span className="text-slate-400 italic">No batches assigned</span>
                        )}
                      </span>
                    </div>
                  </div>
                </div>

                <div className="mt-5 pt-3 border-t border-slate-100 flex items-center justify-between gap-2">
                  <button
                    onClick={() => openPreviewModal(exam)}
                    className="flex items-center gap-1.5 text-xs font-semibold text-slate-600 hover:text-primary-600 py-1.5 px-2 rounded-lg hover:bg-slate-50 transition-colors"
                  >
                    <Eye size={14} />
                    <span>Preview</span>
                  </button>

                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => navigate(`/staff/exams/${exam.id}/analytics`)}
                      className="flex items-center gap-1 text-xs font-bold text-indigo-600 hover:bg-indigo-50 py-1.5 px-2.5 rounded-lg transition-colors border border-indigo-200"
                      title="View Cohort Analytics & Leaderboard"
                    >
                      <BarChart2 size={13} />
                      <span>Analytics</span>
                    </button>

                    <button
                      onClick={() => openAssignDrawer(exam)}
                      className="flex items-center gap-1 text-xs font-bold text-primary-600 hover:bg-primary-50 py-1.5 px-2.5 rounded-lg transition-colors border border-primary-200"
                    >
                      <Users size={13} />
                      <span>Assign</span>
                    </button>

                    {isDraft ? (
                      <button
                        onClick={() => openPublishDialog(exam)}
                        className="flex items-center gap-1 text-xs font-bold text-white bg-emerald-500 hover:bg-emerald-600 py-1.5 px-3 rounded-lg transition-colors shadow-xs"
                      >
                        <Send size={13} />
                        <span>Publish</span>
                      </button>
                    ) : (
                      <span className="text-xs font-bold text-emerald-600 flex items-center gap-1">
                        <CheckCircle2 size={14} /> Published
                      </span>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* New Exam Modal (#new-exam-modal) */}
      {newExamModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-sm p-4">
          <div
            id="new-exam-modal"
            className="bg-white rounded-2xl shadow-xl w-full max-w-lg overflow-hidden animate-in fade-in zoom-in-95 duration-200"
          >
            <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between bg-slate-50">
              <h2 className="text-lg font-bold text-slate-800">
                Create Online Exam {step === 1 ? '(Step 1: Details)' : '(Step 2: Configuration)'}
              </h2>
              <button
                onClick={() => setNewExamModalOpen(false)}
                className="text-slate-400 hover:text-slate-600 text-lg font-bold"
              >
                ×
              </button>
            </div>

            <form onSubmit={handleCreateExam} className="p-6 space-y-4">
              {errorMsg && (
                <div className="flex items-center gap-2 p-3 text-xs text-danger-500 bg-red-50 rounded-xl border border-red-200">
                  <AlertCircle size={16} className="flex-shrink-0" />
                  <span>{errorMsg}</span>
                </div>
              )}

              {step === 1 ? (
                <>
                  <div>
                    <label className="block text-xs font-semibold text-slate-600 uppercase mb-1.5">
                      Exam Name *
                    </label>
                    <input
                      type="text"
                      required
                      placeholder="e.g. JEE Main All-India Grand Mock Test 01"
                      value={examForm.name}
                      onChange={(e) => setExamForm({ ...examForm, name: e.target.value })}
                      className="w-full px-3 py-2 text-sm rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-600 uppercase mb-1.5">
                      Test Duration (Minutes) *
                    </label>
                    <div className="flex items-center gap-2">
                      <input
                        type="number"
                        min="1"
                        max="1440"
                        required
                        value={examForm.duration_minutes}
                        onChange={(e) =>
                          setExamForm({ ...examForm, duration_minutes: parseInt(e.target.value) || 60 })
                        }
                        className="w-32 px-3 py-2 text-sm rounded-lg border border-slate-300"
                      />
                      <div className="flex items-center gap-1 text-xs">
                        {[30, 60, 90, 120, 180].map((mins) => (
                          <button
                            key={mins}
                            type="button"
                            onClick={() => setExamForm({ ...examForm, duration_minutes: mins })}
                            className={`px-2.5 py-1.5 rounded-lg border ${
                              examForm.duration_minutes === mins
                                ? 'bg-primary-50 text-primary-700 border-primary-300 font-bold'
                                : 'bg-slate-50 text-slate-600 border-slate-200'
                            }`}
                          >
                            {mins}m
                          </button>
                        ))}
                      </div>
                    </div>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-600 uppercase mb-1.5">
                      Select Question Paper from Bank
                    </label>
                    <select
                      value={examForm.question_paper_id}
                      onChange={(e) => setExamForm({ ...examForm, question_paper_id: e.target.value })}
                      className="w-full px-3 py-2 text-sm rounded-lg border border-slate-300 bg-white"
                    >
                      <option value="">None / Custom Question Assembly</option>
                      {papers.map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.name} ({p.exam_type}) • {p.total_questions || 0} Qs
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="flex justify-end gap-3 pt-4 border-t border-slate-100">
                    <button
                      type="button"
                      onClick={() => setNewExamModalOpen(false)}
                      className="px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100 rounded-xl"
                    >
                      Cancel
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        if (!examForm.name.trim()) {
                          setErrorMsg('Exam title is required.');
                          return;
                        }
                        setErrorMsg('');
                        setStep(2);
                      }}
                      className="px-5 py-2 text-sm font-bold text-white bg-primary-500 hover:bg-primary-600 rounded-xl"
                    >
                      Next: Anti-Cheat & Windows →
                    </button>
                  </div>
                </>
              ) : (
                /* Step 2: Advanced Online Configuration (#form-add-onex) */
                <div id="form-add-onex" className="space-y-4">
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs font-semibold text-slate-600 uppercase mb-1">
                        Start Window Datetime
                      </label>
                      <input
                        type="datetime-local"
                        value={examForm.start_window}
                        onChange={(e) => setExamForm({ ...examForm, start_window: e.target.value })}
                        className="w-full px-2.5 py-1.5 text-xs rounded-lg border border-slate-300"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-semibold text-slate-600 uppercase mb-1">
                        End Window Datetime
                      </label>
                      <input
                        type="datetime-local"
                        value={examForm.end_window}
                        onChange={(e) => setExamForm({ ...examForm, end_window: e.target.value })}
                        className="w-full px-2.5 py-1.5 text-xs rounded-lg border border-slate-300"
                      />
                    </div>
                  </div>

                  {/* Anti-cheat settings */}
                  <div className="p-3.5 bg-slate-50 border border-slate-200 rounded-xl space-y-2.5 text-xs">
                    <p className="font-bold text-slate-700 uppercase tracking-wider text-[11px]">
                      Proctoring & Anti-Cheating Invariants
                    </p>

                    <div className="flex items-center justify-between">
                      <label htmlFor="check-switches" className="text-slate-700 font-medium">
                        Window Switch Limit (#check-switches)
                      </label>
                      <input
                        type="number"
                        id="num-switch"
                        min="2"
                        max="10"
                        value={examForm.max_window_switches}
                        onChange={(e) =>
                          setExamForm({ ...examForm, max_window_switches: parseInt(e.target.value) || 5 })
                        }
                        className="w-16 px-2 py-1 text-xs border border-slate-300 rounded bg-white"
                      />
                    </div>

                    <div className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        id="check-shuf"
                        checked={examForm.shuffle_questions}
                        onChange={(e) => setExamForm({ ...examForm, shuffle_questions: e.target.checked })}
                      />
                      <label htmlFor="check-shuf" className="text-slate-700 font-medium">
                        Randomize & shuffle questions per candidate
                      </label>
                    </div>

                    <div className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        id="check-cam"
                        checked={examForm.camera_proctoring}
                        onChange={(e) => setExamForm({ ...examForm, camera_proctoring: e.target.checked })}
                      />
                      <label htmlFor="check-cam" className="text-slate-700 font-medium">
                        Enforce periodic webcam snapshots
                      </label>
                    </div>

                    <div className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        id="check-sec-skip"
                        checked={examForm.allow_section_skip}
                        onChange={(e) => setExamForm({ ...examForm, allow_section_skip: e.target.checked })}
                      />
                      <label htmlFor="check-sec-skip" className="text-slate-700 font-medium">
                        Allow free section switching during test
                      </label>
                    </div>

                    <div className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        id="check-pc-only"
                        checked={examForm.pc_only}
                        onChange={(e) => setExamForm({ ...examForm, pc_only: e.target.checked })}
                      />
                      <label htmlFor="check-pc-only" className="text-slate-700 font-medium">
                        Restrict access to PC/Desktop browsers only (blocks mobile)
                      </label>
                    </div>
                  </div>

                  <div className="flex justify-between items-center pt-4 border-t border-slate-100">
                    <button
                      type="button"
                      onClick={() => setStep(1)}
                      className="px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100 rounded-xl"
                    >
                      ← Back
                    </button>
                    <button
                      type="submit"
                      className="px-5 py-2 text-sm font-bold text-white bg-primary-500 hover:bg-primary-600 rounded-xl shadow-sm"
                    >
                      Save & Create Exam
                    </button>
                  </div>
                </div>
              )}
            </form>
          </div>
        </div>
      )}

      {/* Candidate Assignment Drawer (#card-onex-stud) */}
      {assignDrawerOpen && assigningExam && (
        <div className="fixed inset-0 z-50 flex items-center justify-end bg-slate-900/50 backdrop-blur-sm">
          <div
            id="card-onex-stud"
            className="bg-white w-full max-w-md h-full shadow-2xl p-6 flex flex-col justify-between overflow-y-auto animate-in slide-in-from-right duration-300"
          >
            <div>
              <div className="flex items-center justify-between pb-4 border-b border-slate-200">
                <div>
                  <h2 className="text-lg font-bold text-slate-800">Assign Candidates</h2>
                  <p className="text-xs text-slate-500">{assigningExam.name}</p>
                </div>
                <button
                  onClick={() => setAssignDrawerOpen(false)}
                  className="text-slate-400 hover:text-slate-600 text-xl font-bold"
                >
                  ×
                </button>
              </div>

              {errorMsg && (
                <div className="mt-4 p-3 text-xs text-danger-500 bg-red-50 rounded-xl border border-red-200">
                  {errorMsg}
                </div>
              )}

              {successMsg && (
                <div className="mt-4 p-3 text-xs text-emerald-700 bg-emerald-50 rounded-xl border border-emerald-200">
                  {successMsg}
                </div>
              )}

              {/* Batches Section */}
              <div className="mt-6 space-y-3">
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-600">
                  Select Batches / Cohorts
                </label>
                <div className="space-y-2 max-h-48 overflow-y-auto custom-scrollbar border border-slate-200 rounded-xl p-3">
                  {batches.map((batch) => {
                    const isChecked = selectedBatches.includes(batch.id);
                    return (
                      <label
                        key={batch.id}
                        className="flex items-center justify-between p-2 rounded-lg hover:bg-slate-50 cursor-pointer text-xs"
                      >
                        <div className="flex items-center gap-2">
                          <input
                            type="checkbox"
                            checked={isChecked}
                            onChange={() => {
                              if (isChecked) {
                                setSelectedBatches(selectedBatches.filter((id) => id !== batch.id));
                              } else {
                                setSelectedBatches([...selectedBatches, batch.id]);
                              }
                            }}
                            className="rounded text-primary-500"
                          />
                          <span className="font-semibold text-slate-800">{batch.name}</span>
                        </div>
                        <span className="font-mono text-[11px] text-slate-400">{batch.code}</span>
                      </label>
                    );
                  })}
                </div>
              </div>

              {/* Examination Centers Section */}
              <div className="mt-6 space-y-3">
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-600">
                  Select Examination Centres
                </label>
                <div className="space-y-2 max-h-48 overflow-y-auto custom-scrollbar border border-slate-200 rounded-xl p-3">
                  {centers.map((center) => {
                    const isChecked = selectedCenters.includes(center.id);
                    return (
                      <label
                        key={center.id}
                        className="flex items-center justify-between p-2 rounded-lg hover:bg-slate-50 cursor-pointer text-xs"
                      >
                        <div className="flex items-center gap-2">
                          <input
                            type="checkbox"
                            checked={isChecked}
                            onChange={() => {
                              if (isChecked) {
                                setSelectedCenters(selectedCenters.filter((id) => id !== center.id));
                              } else {
                                setSelectedCenters([...selectedCenters, center.id]);
                              }
                            }}
                            className="rounded text-primary-500"
                          />
                          <span className="font-semibold text-slate-800">{center.name}</span>
                        </div>
                        <span className="text-[11px] text-slate-500">{center.capacity} seats</span>
                      </label>
                    );
                  })}
                </div>
              </div>
            </div>

            <div className="pt-6 border-t border-slate-100 flex items-center justify-end gap-3">
              <button
                type="button"
                onClick={() => setAssignDrawerOpen(false)}
                className="px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100 rounded-xl"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={isAssigning}
                onClick={handleAssignCandidates}
                className="px-5 py-2 text-sm font-bold text-white bg-primary-500 hover:bg-primary-600 rounded-xl disabled:opacity-50"
              >
                {isAssigning ? 'Assigning...' : 'Confirm Assignments'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Publish Dialog */}
      {publishDialogOpen && publishingExam && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-sm p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-md p-6 space-y-4 animate-in fade-in zoom-in-95 duration-200">
            <h2 className="text-lg font-bold text-slate-800">Publish Examination?</h2>
            <p className="text-sm text-slate-600">
              Publishing <strong className="text-slate-800">{publishingExam.name}</strong> will lock the linked
              question paper from further modifications and authorize assigned candidates to view the lobby.
            </p>

            {errorMsg && (
              <div className="p-3 text-xs text-danger-500 bg-red-50 rounded-xl border border-red-200">
                {errorMsg}
              </div>
            )}

            <div className="flex justify-end gap-3 pt-4 border-t border-slate-100">
              <button
                type="button"
                onClick={() => setPublishDialogOpen(false)}
                className="px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100 rounded-xl"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={isPublishing}
                onClick={handlePublishExam}
                className="px-5 py-2 text-sm font-bold text-white bg-emerald-500 hover:bg-emerald-600 rounded-xl disabled:opacity-50"
              >
                {isPublishing ? 'Publishing...' : 'Yes, Publish Exam'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Staff Preview Modal */}
      {previewModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-sm p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-3xl max-h-[90vh] flex flex-col overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between bg-slate-50">
              <h2 className="text-lg font-bold text-slate-800">Staff Examination Preview</h2>
              <button
                onClick={() => setPreviewModalOpen(false)}
                className="text-slate-400 hover:text-slate-600 text-lg font-bold"
              >
                ×
              </button>
            </div>

            <div className="p-6 overflow-y-auto space-y-4 flex-1">
              {loadingPreview ? (
                <p className="text-center text-slate-400 py-12">Generating preview...</p>
              ) : previewData.questions.length === 0 ? (
                <p className="text-center text-slate-400 py-12">No questions loaded for this examination.</p>
              ) : (
                previewData.questions.map((q, idx) => (
                  <div key={q.id} className="p-4 rounded-xl border border-slate-200 bg-slate-50/50 space-y-2 text-sm">
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-slate-700">Q#{idx + 1} ({q.section || 'General'})</span>
                      <span className="text-xs font-semibold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded">
                        Key: {q.key}
                      </span>
                    </div>
                    <div className="text-slate-800">{q.content_text}</div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ExaminationsPage;
