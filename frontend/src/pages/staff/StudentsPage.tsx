import React, { useState, useEffect } from 'react';
import { apiService } from '../../services/api';
import { StudentMember, Batch, ExaminationCenter, BulkImportResult } from '../../types';
import {
  Plus,
  Upload,
  Search,
  Trash2,
  Download,
  AlertCircle,
  CheckCircle2,
  XCircle,
  ChevronLeft,
  ChevronRight,
  FileText,
} from 'lucide-react';

export const StudentsPage: React.FC = () => {
  const [students, setStudents] = useState<StudentMember[]>([]);
  const [batches, setBatches] = useState<Batch[]>([]);
  const [centers, setCenters] = useState<ExaminationCenter[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [search, setSearch] = useState<string>('');
  const [selectedBatch, setSelectedBatch] = useState<string>('');
  const [page, setPage] = useState<number>(1);
  const [totalPages, setTotalPages] = useState<number>(1);
  const [totalCount, setTotalCount] = useState<number>(0);

  // Add Student Modal State
  const [addModalOpen, setAddModalOpen] = useState<boolean>(false);
  const [formData, setFormData] = useState({
    roll_number: '',
    name: '',
    email: '',
    phone: '',
    batch_id: '',
    centre_id: '',
    password: '',
    is_active: true,
  });

  // Bulk Import Modal State
  const [bulkModalOpen, setBulkModalOpen] = useState<boolean>(false);
  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [csvText, setCsvText] = useState<string>('');
  const [importResult, setImportResult] = useState<BulkImportResult | null>(null);
  const [isImporting, setIsImporting] = useState<boolean>(false);

  const [errorMsg, setErrorMsg] = useState<string>('');
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  const fetchStudents = async () => {
    try {
      setLoading(true);
      const res = await apiService.getStudents({
        page,
        page_size: 20,
        search: search || undefined,
        batch_id: selectedBatch || undefined,
      });
      setStudents(res.students || []);
      setTotalPages(res.total_pages || 1);
      setTotalCount(res.count || 0);
    } catch (err) {
      console.error('Failed to load students:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStudents();
  }, [page, search, selectedBatch]);

  useEffect(() => {
    const fetchMetadata = async () => {
      try {
        const [bData, cData] = await Promise.all([apiService.getBatches(), apiService.getCenters()]);
        setBatches(bData);
        setCenters(cData);
      } catch (err) {
        console.error('Failed to load master metadata:', err);
      }
    };
    fetchMetadata();
  }, []);

  const openAddModal = () => {
    setFormData({
      roll_number: '',
      name: '',
      email: '',
      phone: '',
      batch_id: batches[0]?.id || '',
      centre_id: centers[0]?.id || '',
      password: '',
      is_active: true,
    });
    setErrorMsg('');
    setAddModalOpen(true);
  };

  const handleAddSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.roll_number.trim() || !formData.name.trim()) {
      setErrorMsg('Roll Number and Name are required.');
      return;
    }
    try {
      setIsSubmitting(true);
      setErrorMsg('');
      await apiService.createStudent(formData);
      setAddModalOpen(false);
      fetchStudents();
    } catch (err: any) {
      const msg = err.response?.data?.message || err.response?.data?.code || 'Failed to save student.';
      setErrorMsg(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (confirm('Are you sure you want to delete this student record?')) {
      try {
        await apiService.deleteStudent(id);
        fetchStudents();
      } catch (err) {
        console.error('Failed to delete student:', err);
      }
    }
  };

  const handleDownloadSampleCsv = () => {
    const sample =
      'RollNumber,Name,Phone,Email,BatchCode,CentreCode\n' +
      '2026101,Ada Lovelace,+919999900001,ada@lovelace.org,C12B,NC01\n' +
      '2026102,Charles Babbage,+919999900002,charles@babbage.org,C12B,NC01\n' +
      '2026103,Alan Turing,+919999900003,turing@cs.org,C12B,NC01\n';
    const blob = new Blob([sample], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'students_sample_import.csv';
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleBulkUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!csvFile && !csvText.trim()) {
      setErrorMsg('Please select a CSV file or paste CSV content.');
      return;
    }
    try {
      setIsImporting(true);
      setErrorMsg('');
      setImportResult(null);

      const payload = csvFile ? csvFile : csvText;
      const res = await apiService.bulkImportStudents(payload);
      setImportResult(res);

      if (res.status === 'SUCCESS' && (!res.errors || res.errors.length === 0)) {
        setTimeout(() => {
          setBulkModalOpen(false);
          setCsvFile(null);
          setCsvText('');
          fetchStudents();
        }, 1500);
      }
    } catch (err: any) {
      const res = err.response?.data;
      if (res) {
        setImportResult(res);
      } else {
        setErrorMsg('Failed to process bulk student CSV.');
      }
    } finally {
      setIsImporting(false);
    }
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Student Roster</h1>
          <p className="text-sm text-slate-500 mt-1">
            Enrolled candidates, institutional roll numbers, batch groupings, and bulk CSV ingestion.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => {
              setBulkModalOpen(true);
              setImportResult(null);
              setErrorMsg('');
            }}
            className="flex items-center gap-2 bg-slate-100 hover:bg-slate-200 text-slate-700 px-4 py-2.5 rounded-xl font-semibold text-sm transition-colors border border-slate-200"
          >
            <Upload size={18} />
            <span>Bulk CSV Import</span>
          </button>
          <button
            onClick={openAddModal}
            className="flex items-center gap-2 bg-primary-500 hover:bg-primary-600 text-white px-4 py-2.5 rounded-xl font-semibold text-sm transition-colors shadow-sm"
          >
            <Plus size={18} />
            <span>Add Student</span>
          </button>
        </div>
      </div>

      {/* Filter / Search Bar */}
      <div className="flex flex-wrap items-center justify-between gap-4 bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
        <div className="flex items-center gap-3 flex-1 min-w-[280px]">
          <div className="relative flex-1">
            <Search size={18} className="absolute left-3 top-2.5 text-slate-400" />
            <input
              type="text"
              placeholder="Search by student name, roll number, email..."
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
              className="w-full pl-9 pr-4 py-2 text-sm rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500"
            />
          </div>

          <select
            value={selectedBatch}
            onChange={(e) => {
              setSelectedBatch(e.target.value);
              setPage(1);
            }}
            className="px-3 py-2 text-sm rounded-lg border border-slate-200 bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500"
          >
            <option value="">All Batches</option>
            {batches.map((b) => (
              <option key={b.id} value={b.id}>
                {b.name} ({b.code})
              </option>
            ))}
          </select>
        </div>

        <div className="text-sm text-slate-500">
          Total Candidates: <span className="font-semibold text-slate-700">{totalCount}</span>
        </div>
      </div>

      {/* Students Data Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-slate-400">Loading student roster...</div>
        ) : students.length === 0 ? (
          <div className="p-12 text-center text-slate-400">No students found matching your search.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-50 text-slate-600 uppercase text-xs font-semibold border-b border-slate-200">
                <tr>
                  <th className="px-6 py-3.5">Roll Number</th>
                  <th className="px-6 py-3.5">Candidate Name</th>
                  <th className="px-6 py-3.5">Batch / Cohort</th>
                  <th className="px-6 py-3.5">Assigned Centre</th>
                  <th className="px-6 py-3.5">Contact</th>
                  <th className="px-6 py-3.5">Status</th>
                  <th className="px-6 py-3.5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-slate-700">
                {students.map((stud) => (
                  <tr key={stud.id} className="hover:bg-slate-50/80 transition-colors">
                    <td className="px-6 py-4 font-mono font-bold text-xs text-primary-600 bg-primary-50/60 px-2.5 py-1 rounded-md w-max inline-block my-3">
                      {stud.roll_number || '—'}
                    </td>
                    <td className="px-6 py-4">
                      <p className="font-semibold text-slate-800">{stud.name}</p>
                      <p className="text-xs text-slate-400">{stud.username}</p>
                    </td>
                    <td className="px-6 py-4">
                      <span className="inline-block px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-50 text-blue-700">
                        {stud.batch_name || 'General'}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-xs text-slate-600">{stud.centre_name || '—'}</td>
                    <td className="px-6 py-4 text-xs text-slate-500">{stud.email || stud.phone || '—'}</td>
                    <td className="px-6 py-4">
                      {stud.is_active ? (
                        <span className="flex items-center gap-1 text-xs text-emerald-600 font-medium">
                          <CheckCircle2 size={15} /> Enrolled
                        </span>
                      ) : (
                        <span className="flex items-center gap-1 text-xs text-slate-400 font-medium">
                          <XCircle size={15} /> Inactive
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-4 text-right">
                      <button
                        onClick={() => handleDelete(stud.id)}
                        className="p-1.5 text-slate-500 hover:text-danger-500 rounded-lg hover:bg-slate-100 transition-colors"
                        title="Delete Student"
                      >
                        <Trash2 size={16} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination Bar */}
        <div className="flex items-center justify-between px-6 py-4 border-t border-slate-100 bg-slate-50 text-sm">
          <div className="text-slate-500 text-xs">
            Page <span className="font-semibold text-slate-700">{page}</span> of{' '}
            <span className="font-semibold text-slate-700">{totalPages}</span>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage(Math.max(1, page - 1))}
              disabled={page <= 1}
              className="p-1.5 rounded-lg border border-slate-200 bg-white text-slate-600 hover:bg-slate-100 disabled:opacity-40"
            >
              <ChevronLeft size={16} />
            </button>
            <button
              onClick={() => setPage(Math.min(totalPages, page + 1))}
              disabled={page >= totalPages}
              className="p-1.5 rounded-lg border border-slate-200 bg-white text-slate-600 hover:bg-slate-100 disabled:opacity-40"
            >
              <ChevronRight size={16} />
            </button>
          </div>
        </div>
      </div>

      {/* Add Single Student Modal */}
      {addModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-sm p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-md overflow-hidden animate-in fade-in zoom-in-95 duration-200">
            <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between">
              <h2 className="text-lg font-bold text-slate-800">Enroll Single Student</h2>
              <button
                onClick={() => setAddModalOpen(false)}
                className="text-slate-400 hover:text-slate-600 text-lg font-bold"
              >
                ×
              </button>
            </div>

            <form onSubmit={handleAddSubmit} className="p-6 space-y-4">
              {errorMsg && (
                <div className="flex items-center gap-2 p-3 text-xs text-danger-500 bg-red-50 rounded-xl border border-red-200">
                  <AlertCircle size={16} className="flex-shrink-0" />
                  <span>{errorMsg}</span>
                </div>
              )}

              <div>
                <label className="block text-xs font-semibold text-slate-600 uppercase mb-1.5">
                  Roll Number *
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. 2026101"
                  value={formData.roll_number}
                  onChange={(e) => setFormData({ ...formData, roll_number: e.target.value })}
                  className="w-full px-3 py-2 text-sm rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500 font-mono"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-600 uppercase mb-1.5">
                  Full Name *
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Aryabhata Sharma"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className="w-full px-3 py-2 text-sm rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-600 uppercase mb-1.5">
                    Batch
                  </label>
                  <select
                    value={formData.batch_id}
                    onChange={(e) => setFormData({ ...formData, batch_id: e.target.value })}
                    className="w-full px-3 py-2 text-sm rounded-lg border border-slate-300 bg-white"
                  >
                    <option value="">Select Batch</option>
                    {batches.map((b) => (
                      <option key={b.id} value={b.id}>
                        {b.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-600 uppercase mb-1.5">
                    Test Centre
                  </label>
                  <select
                    value={formData.centre_id}
                    onChange={(e) => setFormData({ ...formData, centre_id: e.target.value })}
                    className="w-full px-3 py-2 text-sm rounded-lg border border-slate-300 bg-white"
                  >
                    <option value="">Select Centre</option>
                    {centers.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-600 uppercase mb-1.5">
                  Email Address
                </label>
                <input
                  type="email"
                  placeholder="student@institution.edu"
                  value={formData.email}
                  onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                  className="w-full px-3 py-2 text-sm rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-600 uppercase mb-1.5">
                  Phone Number
                </label>
                <input
                  type="text"
                  placeholder="+919876543210"
                  value={formData.phone}
                  onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                  className="w-full px-3 py-2 text-sm rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500"
                />
              </div>

              <div className="flex justify-end gap-3 pt-4 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setAddModalOpen(false)}
                  className="px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100 rounded-xl transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="px-5 py-2 text-sm font-bold text-white bg-primary-500 hover:bg-primary-600 rounded-xl transition-colors disabled:opacity-50"
                >
                  {isSubmitting ? 'Enrolling...' : 'Enroll Student'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Bulk CSV Upload Modal */}
      {bulkModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-sm p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg overflow-hidden animate-in fade-in zoom-in-95 duration-200">
            <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Upload size={20} className="text-primary-500" />
                <h2 className="text-lg font-bold text-slate-800">Bulk Ingestion (CSV / Excel)</h2>
              </div>
              <button
                onClick={() => setBulkModalOpen(false)}
                className="text-slate-400 hover:text-slate-600 text-lg font-bold"
              >
                ×
              </button>
            </div>

            <form onSubmit={handleBulkUpload} className="p-6 space-y-4">
              <div className="flex items-center justify-between bg-blue-50/60 border border-blue-200/80 p-3.5 rounded-xl">
                <div>
                  <p className="text-xs font-bold text-blue-900">Need the correct column structure?</p>
                  <p className="text-[11px] text-blue-700 mt-0.5">
                    Download sample CSV with RollNumber, Name, Email, BatchCode, CentreCode.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={handleDownloadSampleCsv}
                  className="flex items-center gap-1.5 bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold px-3 py-1.5 rounded-lg transition-colors flex-shrink-0"
                >
                  <Download size={14} />
                  <span>Sample CSV</span>
                </button>
              </div>

              {errorMsg && (
                <div className="flex items-center gap-2 p-3 text-xs text-danger-500 bg-red-50 rounded-xl border border-red-200">
                  <AlertCircle size={16} className="flex-shrink-0" />
                  <span>{errorMsg}</span>
                </div>
              )}

              {importResult && (
                <div
                  className={`p-3.5 rounded-xl border text-xs ${
                    importResult.status === 'SUCCESS' && (!importResult.errors || importResult.errors.length === 0)
                      ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
                      : 'bg-red-50 text-red-800 border-red-200'
                  }`}
                >
                  <p className="font-bold">
                    {importResult.status === 'SUCCESS'
                      ? `Successfully imported ${importResult.created_count || importResult.created} students!`
                      : 'Validation Failed — Transaction Rolled Back'}
                  </p>
                  {importResult.errors && importResult.errors.length > 0 && (
                    <ul className="list-disc list-inside mt-2 space-y-1 text-[11px] max-h-32 overflow-y-auto">
                      {importResult.errors.map((err, idx) => (
                        <li key={idx}>{err}</li>
                      ))}
                    </ul>
                  )}
                </div>
              )}

              {/* File Dropzone */}
              <div>
                <label className="block text-xs font-semibold text-slate-600 uppercase mb-1.5">
                  Select CSV File
                </label>
                <div className="border-2 border-dashed border-slate-300 rounded-xl p-4 text-center hover:border-primary-500 transition-colors">
                  <input
                    type="file"
                    accept=".csv,.txt"
                    onChange={(e) => setCsvFile(e.target.files?.[0] || null)}
                    className="block w-full text-xs text-slate-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-primary-50 file:text-primary-600 hover:file:bg-primary-100"
                  />
                  {csvFile && (
                    <p className="text-xs text-emerald-600 font-medium mt-2 flex items-center justify-center gap-1">
                      <FileText size={14} /> Selected: {csvFile.name}
                    </p>
                  )}
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-600 uppercase mb-1.5">
                  Or Paste Raw CSV Content
                </label>
                <textarea
                  rows={4}
                  placeholder="RollNumber,Name,Phone,Email,BatchCode,CentreCode..."
                  value={csvText}
                  onChange={(e) => setCsvText(e.target.value)}
                  className="w-full px-3 py-2 text-xs font-mono rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500"
                />
              </div>

              <div className="flex justify-end gap-3 pt-4 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setBulkModalOpen(false)}
                  className="px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100 rounded-xl transition-colors"
                >
                  Close
                </button>
                <button
                  type="submit"
                  disabled={isImporting}
                  className="px-5 py-2 text-sm font-bold text-white bg-primary-500 hover:bg-primary-600 rounded-xl transition-colors disabled:opacity-50 flex items-center gap-2"
                >
                  {isImporting ? 'Processing & Validating...' : 'Upload & Import'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default StudentsPage;
