import MathRenderer from '../../components/MathRenderer';
import React, { useState, useEffect } from 'react';
import { apiService } from '../../services/api';
import { QuestionBank, Question, QuestionOption } from '../../types';
import {
  Plus,
  BookOpen,
  Trash2,
  Lock,
  FileQuestion,
  AlertCircle,
  ChevronRight,
} from 'lucide-react';

export const QuestionBankPage: React.FC = () => {
  const [papers, setPapers] = useState<QuestionBank[]>([]);
  const [selectedPaper, setSelectedPaper] = useState<QuestionBank | null>(null);
  const [questions, setQuestions] = useState<Question[]>([]);
  const [loadingPapers, setLoadingPapers] = useState<boolean>(true);
  const [loadingQuestions, setLoadingQuestions] = useState<boolean>(false);

  // New Paper Modal State
  const [newPaperModalOpen, setNewPaperModalOpen] = useState<boolean>(false);
  const [paperForm, setPaperForm] = useState({
    name: '',
    exam_type: 'JEE-Main',
    duration_minutes: 60,
    instructions: '',
  });

  // Question Authoring Modal State (#form-addq)
  const [qModalOpen, setQModalOpen] = useState<boolean>(false);
  const [qForm, setQForm] = useState<{
    section: string;
    question_type: string;
    content_text: string;
    explanation: string;
    key: string;
    positive_marks: number;
    negative_marks: number;
    partial_marks: number;
    coding_language: string;
    code_boilerplate: string;
    options: QuestionOption[];
  }>({
    section: 'Physics',
    question_type: 'MCQ_SINGLE',
    content_text: '',
    explanation: '',
    key: 'A',
    positive_marks: 4.0,
    negative_marks: 1.0,
    partial_marks: 0.0,
    coding_language: 'python',
    code_boilerplate: 'def solve():\n    pass',
    options: [
      { key: 'A', text: '', is_correct: true },
      { key: 'B', text: '', is_correct: false },
      { key: 'C', text: '', is_correct: false },
      { key: 'D', text: '', is_correct: false },
    ],
  });

  const [previewTab, setPreviewTab] = useState<'editor' | 'preview'>('editor');
  const [errorMsg, setErrorMsg] = useState<string>('');
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  const fetchPapers = async () => {
    try {
      setLoadingPapers(true);
      const data = await apiService.getQuestionBanks();
      setPapers(data);
      if (data.length > 0 && !selectedPaper) {
        setSelectedPaper(data[0]);
      }
    } catch (err) {
      console.error('Failed to load question papers:', err);
    } finally {
      setLoadingPapers(false);
    }
  };

  useEffect(() => {
    fetchPapers();
  }, []);

  const fetchQuestions = async (paperId: string) => {
    try {
      setLoadingQuestions(true);
      const res = await apiService.getQuestionBankQuestions(paperId);
      setQuestions(res.questions || []);
    } catch (err) {
      console.error('Failed to load questions:', err);
    } finally {
      setLoadingQuestions(false);
    }
  };

  useEffect(() => {
    if (selectedPaper) {
      fetchQuestions(selectedPaper.id);
    }
  }, [selectedPaper]);

  const handleCreatePaper = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!paperForm.name.trim()) return;
    try {
      setIsSubmitting(true);
      const newP = await apiService.createQuestionBank(paperForm);
      setNewPaperModalOpen(false);
      await fetchPapers();
      setSelectedPaper(newP);
    } catch (err: any) {
      setErrorMsg(err.response?.data?.message || 'Failed to create question paper.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const openAddQuestionModal = () => {
    setQForm({
      section: selectedPaper?.subjects?.[0] || 'Physics',
      question_type: 'MCQ_SINGLE',
      content_text: '',
      explanation: '',
      key: 'A',
      positive_marks: 4.0,
      negative_marks: 1.0,
      partial_marks: 0.0,
      coding_language: 'python',
      code_boilerplate: 'def solve():\n    pass',
      options: [
        { key: 'A', text: '', is_correct: true },
        { key: 'B', text: '', is_correct: false },
        { key: 'C', text: '', is_correct: false },
        { key: 'D', text: '', is_correct: false },
      ],
    });
    setErrorMsg('');
    setPreviewTab('editor');
    setQModalOpen(true);
  };

  const handleOptionChange = (idx: number, text: string) => {
    const updated = [...qForm.options];
    updated[idx].text = text;
    setQForm({ ...qForm, options: updated });
  };

  const handleOptionSelectSingle = (key: string) => {
    const updated = qForm.options.map((opt) => ({
      ...opt,
      is_correct: opt.key === key,
    }));
    setQForm({ ...qForm, options: updated, key });
  };

  const handleOptionToggleMulti = (key: string) => {
    const updated = qForm.options.map((opt) =>
      opt.key === key ? { ...opt, is_correct: !opt.is_correct } : opt
    );
    const correctKeys = updated.filter((o) => o.is_correct).map((o) => o.key).join(',');
    setQForm({ ...qForm, options: updated, key: correctKeys });
  };

  const handleQuestionSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedPaper) return;
    if (!qForm.content_text.trim()) {
      setErrorMsg('Question statement cannot be empty.');
      return;
    }
    if (qForm.negative_marks > qForm.positive_marks) {
      setErrorMsg('Negative marks penalty cannot exceed positive marks.');
      return;
    }

    try {
      setIsSubmitting(true);
      setErrorMsg('');

      let finalKey = qForm.key;
      let finalOptions = qForm.options;

      if (qForm.question_type === 'TRUE_FALSE') {
        finalOptions = [
          { key: 'A', text: 'True', is_correct: qForm.key === 'A' },
          { key: 'B', text: 'False', is_correct: qForm.key === 'B' },
        ];
      } else if (['NUMERICAL', 'SUBJECTIVE', 'CODING'].includes(qForm.question_type)) {
        finalOptions = [];
      }

      await apiService.createQuestion(selectedPaper.id, {
        ...qForm,
        key: finalKey,
        options: finalOptions,
      });

      setQModalOpen(false);
      fetchQuestions(selectedPaper.id);
      fetchPapers();
    } catch (err: any) {
      const msg = err.response?.data?.message || err.response?.data?.code || 'Failed to author question.';
      setErrorMsg(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDeleteQuestion = async (id: string) => {
    if (confirm('Are you sure you want to delete this question?')) {
      try {
        await apiService.deleteQuestion(id);
        if (selectedPaper) {
          fetchQuestions(selectedPaper.id);
        }
      } catch (err) {
        console.error('Failed to delete question:', err);
      }
    }
  };

  return (
    <div className="p-6 space-y-6">
      {/* Top Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Question Bank & Authoring</h1>
          <p className="text-sm text-slate-500 mt-1">
            Author multi-type question papers with LaTeX formulas, 3-tier marking schemes, and subject sections.
          </p>
        </div>
        <button
          onClick={() => {
            setPaperForm({
              name: '',
              exam_type: 'JEE-Main',
              duration_minutes: 60,
              instructions: '',
            });
            setErrorMsg('');
            setNewPaperModalOpen(true);
          }}
          className="flex items-center gap-2 bg-primary-500 hover:bg-primary-600 text-white px-4 py-2.5 rounded-xl font-semibold text-sm transition-colors shadow-sm"
        >
          <Plus size={18} />
          <span>New Question Paper</span>
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 items-start">
        {/* Left Column: Question Papers List */}
        <div className="lg:col-span-1 bg-white rounded-2xl border border-slate-200 shadow-sm p-4 space-y-3">
          <div className="flex items-center justify-between px-2 pb-2 border-b border-slate-100">
            <h2 className="text-xs font-bold uppercase tracking-wider text-slate-400">Question Papers</h2>
            <span className="text-xs font-bold text-primary-600 bg-primary-50 px-2 py-0.5 rounded-full">
              {papers.length}
            </span>
          </div>

          {loadingPapers ? (
            <p className="text-xs text-slate-400 p-4 text-center">Loading papers...</p>
          ) : papers.length === 0 ? (
            <p className="text-xs text-slate-400 p-4 text-center">No papers found. Create one above.</p>
          ) : (
            <div className="space-y-1.5 max-h-[600px] overflow-y-auto custom-scrollbar">
              {papers.map((paper) => {
                const isSelected = selectedPaper?.id === paper.id;
                return (
                  <button
                    key={paper.id}
                    onClick={() => setSelectedPaper(paper)}
                    className={`w-full text-left p-3 rounded-xl transition-all flex items-center justify-between ${
                      isSelected
                        ? 'bg-primary-50 text-primary-700 border border-primary-200 shadow-sm'
                        : 'hover:bg-slate-50 text-slate-700'
                    }`}
                  >
                    <div className="overflow-hidden pr-2">
                      <p className="font-semibold text-sm truncate">{paper.name}</p>
                      <div className="flex items-center gap-2 mt-1">
                        <span className="text-[10px] font-bold uppercase bg-slate-200 text-slate-700 px-1.5 py-0.5 rounded">
                          {paper.exam_type}
                        </span>
                        <span className="text-[11px] text-slate-500">
                          {paper.total_questions || 0} Qs
                        </span>
                      </div>
                    </div>
                    {paper.is_locked ? (
                      <Lock size={14} className="text-amber-500 flex-shrink-0" />
                    ) : (
                      <ChevronRight size={16} className="text-slate-400 flex-shrink-0" />
                    )}
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* Right Column: Questions in Selected Paper */}
        <div className="lg:col-span-3 bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
          {selectedPaper ? (
            <div>
              {/* Paper Details Header */}
              <div className="p-6 border-b border-slate-100 flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-slate-50/50">
                <div>
                  <div className="flex items-center gap-2">
                    <h2 className="text-xl font-bold text-slate-800">{selectedPaper.name}</h2>
                    {selectedPaper.is_locked && (
                      <span className="flex items-center gap-1 text-[11px] font-bold text-amber-700 bg-amber-100 px-2.5 py-0.5 rounded-full">
                        <Lock size={12} /> Locked
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-3 text-xs text-slate-500 mt-1">
                    <span>Type: <strong className="text-slate-700">{selectedPaper.exam_type}</strong></span>
                    <span>•</span>
                    <span>Duration: <strong className="text-slate-700">{selectedPaper.duration_minutes} mins</strong></span>
                    <span>•</span>
                    <span>Total Questions: <strong className="text-slate-700">{questions.length}</strong></span>
                  </div>
                </div>

                {!selectedPaper.is_locked && (
                  <button
                    onClick={openAddQuestionModal}
                    className="flex items-center gap-2 bg-emerald-500 hover:bg-emerald-600 text-white px-4 py-2 rounded-xl font-bold text-xs transition-colors shadow-sm"
                  >
                    <Plus size={16} />
                    <span>Add Question (#form-addq)</span>
                  </button>
                )}
              </div>

              {/* Questions List */}
              <div className="p-6">
                {loadingQuestions ? (
                  <p className="text-center text-slate-400 py-12">Loading questions...</p>
                ) : questions.length === 0 ? (
                  <div className="text-center py-16 text-slate-400">
                    <FileQuestion size={40} className="mx-auto mb-2 text-slate-300" />
                    <p className="font-semibold text-slate-600">No questions in this paper yet.</p>
                    <p className="text-xs text-slate-400 mt-1">Click "Add Question" above to start authoring.</p>
                  </div>
                ) : (
                  <div className="space-y-4">
                    {questions.map((q, idx) => (
                      <div
                        key={q.id}
                        className="p-5 rounded-xl border border-slate-200 hover:border-slate-300 transition-colors bg-white space-y-3"
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div className="flex items-center gap-2">
                            <span className="w-7 h-7 rounded-lg bg-slate-100 text-slate-700 font-bold text-xs flex items-center justify-center">
                              #{q.question_number || idx + 1}
                            </span>
                            <span className="text-xs font-bold text-primary-700 bg-primary-50 px-2 py-0.5 rounded">
                              {q.section || q.section_name || 'General'}
                            </span>
                            <span className="text-xs font-semibold text-purple-700 bg-purple-50 px-2 py-0.5 rounded">
                              {q.question_type}
                            </span>
                          </div>

                          <div className="flex items-center gap-3">
                            <span className="text-xs font-bold text-slate-600">
                              +{q.positive_marks} / -{q.negative_marks}
                            </span>
                            {!selectedPaper.is_locked && (
                              <button
                                onClick={() => handleDeleteQuestion(q.id)}
                                className="text-slate-400 hover:text-danger-500 p-1 rounded transition-colors"
                              >
                                <Trash2 size={16} />
                              </button>
                            )}
                          </div>
                        </div>

                        {/* Question Text */}
                        <div className="text-sm text-slate-800 whitespace-pre-wrap font-sans leading-relaxed">
                          <MathRenderer content={q.content_text} />
                        </div>

                        {/* Options if MCQ */}
                        {q.options && q.options.length > 0 && (
                          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-2">
                            {q.options.map((opt, oIdx) => {
                              const isCorrect =
                                opt.is_correct ||
                                (q.key && q.key.split(',').includes(opt.key || opt.option_key || ''));
                              return (
                                <div
                                  key={oIdx}
                                  className={`p-2.5 rounded-lg border text-xs flex items-center gap-2.5 ${
                                    isCorrect
                                      ? 'bg-emerald-50/70 border-emerald-300 text-emerald-900 font-semibold'
                                      : 'bg-slate-50 border-slate-200 text-slate-700'
                                  }`}
                                >
                                  <span className="w-5 h-5 rounded-full bg-white border border-slate-300 flex items-center justify-center font-bold text-[10px]">
                                    {opt.key || opt.option_key || chr(65 + oIdx)}
                                  </span>
                                  <MathRenderer content={opt.text || opt.content_text || ''} />
                                </div>
                              );
                            })}
                          </div>
                        )}

                        {/* Key & Explanation */}
                        <div className="pt-2 flex flex-wrap items-center gap-4 text-xs text-slate-500 border-t border-slate-100">
                          <div>
                            Answer Key: <strong className="text-slate-800">{q.key || '—'}</strong>
                          </div>
                          {q.explanation && (
                            <div>
                              Explanation: <span className="text-slate-600 italic">{q.explanation}</span>
                            </div>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="p-16 text-center text-slate-400">
              Select or create a question paper from the left panel.
            </div>
          )}
        </div>
      </div>

      {/* New Question Paper Modal */}
      {newPaperModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-sm p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-md overflow-hidden animate-in fade-in zoom-in-95 duration-200">
            <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between">
              <h2 className="text-lg font-bold text-slate-800">New Question Paper</h2>
              <button
                onClick={() => setNewPaperModalOpen(false)}
                className="text-slate-400 hover:text-slate-600 text-lg font-bold"
              >
                ×
              </button>
            </div>

            <form onSubmit={handleCreatePaper} className="p-6 space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-600 uppercase mb-1.5">
                  Paper Name *
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. JEE Main Mock Grand Test 01"
                  value={paperForm.name}
                  onChange={(e) => setPaperForm({ ...paperForm, name: e.target.value })}
                  className="w-full px-3 py-2 text-sm rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-600 uppercase mb-1.5">
                  Exam Type / Curriculum
                </label>
                <select
                  value={paperForm.exam_type}
                  onChange={(e) => setPaperForm({ ...paperForm, exam_type: e.target.value })}
                  className="w-full px-3 py-2 text-sm rounded-lg border border-slate-300 bg-white"
                >
                  <option value="JEE-Main">JEE Main</option>
                  <option value="JEE-Advanced">JEE Advanced</option>
                  <option value="NEET">NEET</option>
                  <option value="GATE">GATE</option>
                  <option value="GENERAL">General / Assessment</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-600 uppercase mb-1.5">
                  Duration (Minutes)
                </label>
                <input
                  type="number"
                  min="5"
                  value={paperForm.duration_minutes}
                  onChange={(e) =>
                    setPaperForm({ ...paperForm, duration_minutes: parseInt(e.target.value) || 60 })
                  }
                  className="w-full px-3 py-2 text-sm rounded-lg border border-slate-300"
                />
              </div>

              <div className="flex justify-end gap-3 pt-4 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setNewPaperModalOpen(false)}
                  className="px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100 rounded-xl"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="px-5 py-2 text-sm font-bold text-white bg-primary-500 hover:bg-primary-600 rounded-xl disabled:opacity-50"
                >
                  {isSubmitting ? 'Creating...' : 'Create Paper'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Multi-Type Question Authoring Modal (#form-addq) */}
      {qModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-sm p-4">
          <div
            id="form-addq"
            className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-200"
          >
            {/* Header */}
            <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between bg-slate-50">
              <div className="flex items-center gap-2">
                <BookOpen size={20} className="text-primary-600" />
                <h2 className="text-lg font-bold text-slate-800">Author Question (#form-addq)</h2>
              </div>
              <button
                onClick={() => setQModalOpen(false)}
                className="text-slate-400 hover:text-slate-600 text-lg font-bold"
              >
                ×
              </button>
            </div>

            {/* Form Body */}
            <form onSubmit={handleQuestionSubmit} className="p-6 space-y-4 overflow-y-auto flex-1">
              {errorMsg && (
                <div className="flex items-center gap-2 p-3 text-xs text-danger-500 bg-red-50 rounded-xl border border-red-200">
                  <AlertCircle size={16} className="flex-shrink-0" />
                  <span>{errorMsg}</span>
                </div>
              )}

              {/* Section & Question Type Row */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-600 uppercase mb-1.5">
                    Section / Subject
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Physics / Maths / Chemistry"
                    value={qForm.section}
                    onChange={(e) => setQForm({ ...qForm, section: e.target.value })}
                    className="w-full px-3 py-2 text-sm rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-600 uppercase mb-1.5">
                    Question Type (qtype)
                  </label>
                  <select
                    value={qForm.question_type}
                    onChange={(e) => setQForm({ ...qForm, question_type: e.target.value })}
                    className="w-full px-3 py-2 text-sm rounded-lg border border-slate-300 bg-white"
                  >
                    <option value="MCQ_SINGLE">MCQ Single Correct (1)</option>
                    <option value="MCQ_MULTI">MCQ Multi Correct (2)</option>
                    <option value="NUMERICAL">Numerical Value (3)</option>
                    <option value="TRUE_FALSE">True / False (21)</option>
                    <option value="SUBJECTIVE">Text Subjective (71)</option>
                    <option value="CODING">Code Execution (721)</option>
                  </select>
                </div>
              </div>

              {/* Question Statement with Preview Toggle */}
              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label className="text-xs font-semibold text-slate-600 uppercase">
                    Question Statement (Markdown & LaTeX supported) *
                  </label>
                  <div className="flex items-center gap-1 bg-slate-100 p-0.5 rounded-lg text-xs">
                    <button
                      type="button"
                      onClick={() => setPreviewTab('editor')}
                      className={`px-2 py-0.5 rounded-md font-medium transition-colors ${
                        previewTab === 'editor' ? 'bg-white shadow-xs text-slate-800' : 'text-slate-500'
                      }`}
                    >
                      Editor
                    </button>
                    <button
                      type="button"
                      onClick={() => setPreviewTab('preview')}
                      className={`px-2 py-0.5 rounded-md font-medium transition-colors ${
                        previewTab === 'preview' ? 'bg-white shadow-xs text-slate-800' : 'text-slate-500'
                      }`}
                    >
                      Preview
                    </button>
                  </div>
                </div>

                {previewTab === 'editor' ? (
                  <textarea
                    rows={4}
                    required
                    placeholder="e.g. Calculate the determinant of matrix $A$ where $\det(A) = 4$..."
                    value={qForm.content_text}
                    onChange={(e) => setQForm({ ...qForm, content_text: e.target.value })}
                    className="w-full px-3 py-2 text-sm rounded-lg border border-slate-300 font-mono focus:outline-none focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500"
                  />
                ) : (
                  <div className="min-h-[96px] p-3 rounded-lg border border-slate-200 bg-slate-50 text-sm whitespace-pre-wrap text-slate-800">
                    {qForm.content_text ? <MathRenderer content={qForm.content_text} /> : <span className="text-slate-400 italic">No content typed yet.</span>}
                  </div>
                )}
              </div>

              {/* Dynamic Option Inputs for MCQs */}
              {['MCQ_SINGLE', 'MCQ_MULTI'].includes(qForm.question_type) && (
                <div className="space-y-2 pt-2 border-t border-slate-100">
                  <label className="block text-xs font-semibold text-slate-600 uppercase">
                    Options & Correct Answer Choice
                  </label>
                  <div className="space-y-2">
                    {qForm.options.map((opt, idx) => (
                      <div key={idx} className="flex items-center gap-2">
                        {qForm.question_type === 'MCQ_SINGLE' ? (
                          <input
                            type="radio"
                            name="single_correct_radio"
                            checked={opt.is_correct}
                            onChange={() => handleOptionSelectSingle(opt.key || chr(65 + idx))}
                            className="w-4 h-4 text-primary-600 focus:ring-primary-500"
                          />
                        ) : (
                          <input
                            type="checkbox"
                            checked={opt.is_correct}
                            onChange={() => handleOptionToggleMulti(opt.key || chr(65 + idx))}
                            className="w-4 h-4 text-primary-600 rounded focus:ring-primary-500"
                          />
                        )}
                        <span className="w-6 h-6 rounded bg-slate-200 font-bold text-xs flex items-center justify-center flex-shrink-0">
                          {opt.key || chr(65 + idx)}
                        </span>
                        <input
                          type="text"
                          required
                          placeholder={`Option ${opt.key} text`}
                          value={opt.text}
                          onChange={(e) => handleOptionChange(idx, e.target.value)}
                          className="flex-1 px-3 py-1.5 text-sm rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-primary-500/20"
                        />
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Numerical Answer Key */}
              {qForm.question_type === 'NUMERICAL' && (
                <div className="pt-2 border-t border-slate-100">
                  <label className="block text-xs font-semibold text-slate-600 uppercase mb-1.5">
                    Numerical Correct Answer *
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. 1024 or 3.1415"
                    value={qForm.key}
                    onChange={(e) => setQForm({ ...qForm, key: e.target.value })}
                    className="w-full px-3 py-2 text-sm rounded-lg border border-slate-300 font-mono"
                  />
                </div>
              )}

              {/* True/False Selector */}
              {qForm.question_type === 'TRUE_FALSE' && (
                <div className="pt-2 border-t border-slate-100">
                  <label className="block text-xs font-semibold text-slate-600 uppercase mb-1.5">
                    Correct Option
                  </label>
                  <div className="flex items-center gap-4">
                    <label className="flex items-center gap-2 text-sm">
                      <input
                        type="radio"
                        name="tf_radio"
                        checked={qForm.key === 'A'}
                        onChange={() => setQForm({ ...qForm, key: 'A' })}
                      />
                      <span>True (A)</span>
                    </label>
                    <label className="flex items-center gap-2 text-sm">
                      <input
                        type="radio"
                        name="tf_radio"
                        checked={qForm.key === 'B'}
                        onChange={() => setQForm({ ...qForm, key: 'B' })}
                      />
                      <span>False (B)</span>
                    </label>
                  </div>
                </div>
              )}

              {/* Coding Box Details */}
              {qForm.question_type === 'CODING' && (
                <div className="space-y-3 pt-2 border-t border-slate-100">
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs font-semibold text-slate-600 uppercase mb-1">
                        Language
                      </label>
                      <select
                        value={qForm.coding_language}
                        onChange={(e) => setQForm({ ...qForm, coding_language: e.target.value })}
                        className="w-full px-3 py-1.5 text-xs rounded-lg border border-slate-300"
                      >
                        <option value="python">Python 3</option>
                        <option value="cpp">C++ (GCC)</option>
                        <option value="java">Java 17</option>
                        <option value="javascript">JavaScript (Node)</option>
                      </select>
                    </div>
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-slate-600 uppercase mb-1">
                      Starter Code / Boilerplate
                    </label>
                    <textarea
                      rows={3}
                      value={qForm.code_boilerplate}
                      onChange={(e) => setQForm({ ...qForm, code_boilerplate: e.target.value })}
                      className="w-full px-3 py-1.5 text-xs font-mono rounded-lg border border-slate-300"
                    />
                  </div>
                </div>
              )}

              {/* 3-Tier Marking Scheme Inputs (.markings-inputs) */}
              <div className="markings-inputs p-4 rounded-xl bg-slate-50 border border-slate-200 grid grid-cols-3 gap-3">
                <div>
                  <label className="block text-[11px] font-bold text-slate-600 uppercase mb-1">
                    Correct (cmk) *
                  </label>
                  <input
                    type="number"
                    step="0.25"
                    min="0"
                    required
                    value={qForm.positive_marks}
                    onChange={(e) =>
                      setQForm({ ...qForm, positive_marks: parseFloat(e.target.value) || 0 })
                    }
                    className="w-full px-2.5 py-1.5 text-xs rounded-lg border border-slate-300 bg-white"
                  />
                </div>
                <div>
                  <label className="block text-[11px] font-bold text-slate-600 uppercase mb-1">
                    Penalty (imk)
                  </label>
                  <input
                    type="number"
                    step="0.25"
                    min="0"
                    value={qForm.negative_marks}
                    onChange={(e) =>
                      setQForm({ ...qForm, negative_marks: parseFloat(e.target.value) || 0 })
                    }
                    className="w-full px-2.5 py-1.5 text-xs rounded-lg border border-slate-300 bg-white"
                  />
                </div>
                <div>
                  <label className="block text-[11px] font-bold text-slate-600 uppercase mb-1">
                    Partial (pmk)
                  </label>
                  <input
                    type="number"
                    step="0.25"
                    min="0"
                    value={qForm.partial_marks}
                    onChange={(e) =>
                      setQForm({ ...qForm, partial_marks: parseFloat(e.target.value) || 0 })
                    }
                    className="w-full px-2.5 py-1.5 text-xs rounded-lg border border-slate-300 bg-white"
                  />
                </div>
              </div>

              {/* Explanation */}
              <div>
                <label className="block text-xs font-semibold text-slate-600 uppercase mb-1.5">
                  Detailed Explanation / Solution Note
                </label>
                <textarea
                  rows={2}
                  placeholder="Step-by-step reasoning or formula rationale..."
                  value={qForm.explanation}
                  onChange={(e) => setQForm({ ...qForm, explanation: e.target.value })}
                  className="w-full px-3 py-2 text-xs rounded-lg border border-slate-300"
                />
              </div>

              {/* Actions */}
              <div className="flex justify-end gap-3 pt-4 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setQModalOpen(false)}
                  className="px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100 rounded-xl"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="px-5 py-2 text-sm font-bold text-white bg-primary-500 hover:bg-primary-600 rounded-xl disabled:opacity-50"
                >
                  {isSubmitting ? 'Saving Question...' : 'Save & Add Question'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

function chr(code: number): string {
  return String.fromCharCode(code);
}

export default QuestionBankPage;
