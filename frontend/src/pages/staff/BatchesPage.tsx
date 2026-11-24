import React, { useState, useEffect } from 'react';
import { apiService } from '../../services/api';
import { Batch } from '../../types';
import { Plus, Search, Edit2, Trash2, CheckCircle2, XCircle, AlertCircle } from 'lucide-react';

export const BatchesPage: React.FC = () => {
  const [batches, setBatches] = useState<Batch[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [search, setSearch] = useState<string>('');
  const [modalOpen, setModalOpen] = useState<boolean>(false);
  const [editingBatch, setEditingBatch] = useState<Batch | null>(null);
  const [formData, setFormData] = useState<{
    name: string;
    code: string;
    stream: 'JEE_MAIN' | 'JEE_ADVANCED' | 'NEET' | 'OTHER';
    description: string;
    is_active: boolean;
  }>({
    name: '',
    code: '',
    stream: 'JEE_MAIN',
    description: '',
    is_active: true,
  });
  const [errorMsg, setErrorMsg] = useState<string>('');
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  const fetchBatches = async () => {
    try {
      setLoading(true);
      const data = await apiService.getBatches();
      setBatches(data);
    } catch (err: unknown) {
      console.error('Failed to load batches:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchBatches();
  }, []);

  const openAddModal = () => {
    setEditingBatch(null);
    setFormData({
      name: '',
      code: '',
      stream: 'JEE_MAIN',
      description: '',
      is_active: true,
    });
    setErrorMsg('');
    setModalOpen(true);
  };

  const openEditModal = (batch: Batch) => {
    setEditingBatch(batch);
    setFormData({
      name: batch.name,
      code: batch.code,
      stream: batch.stream,
      description: batch.description || '',
      is_active: batch.is_active,
    });
    setErrorMsg('');
    setModalOpen(true);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.name.trim() || !formData.code.trim()) {
      setErrorMsg('Name and Code are required.');
      return;
    }
    try {
      setIsSubmitting(true);
      setErrorMsg('');
      if (editingBatch) {
        await apiService.updateBatch(editingBatch.id, formData);
      } else {
        await apiService.createBatch(formData);
      }
      setModalOpen(false);
      fetchBatches();
    } catch (err: any) {
      const msg = err.response?.data?.message || err.response?.data?.code || 'Failed to save batch.';
      setErrorMsg(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (confirm('Are you sure you want to delete this batch?')) {
      try {
        await apiService.deleteBatch(id);
        fetchBatches();
      } catch (err) {
        console.error('Failed to delete batch:', err);
      }
    }
  };

  const filteredBatches = batches.filter(
    (b) =>
      b.name.toLowerCase().includes(search.toLowerCase()) ||
      b.code.toLowerCase().includes(search.toLowerCase()) ||
      b.stream.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="p-6 space-y-6">
      {/* Header Bar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Batches & Cohorts</h1>
          <p className="text-sm text-slate-500 mt-1">Manage academic streams, cohort classes, and candidate groups.</p>
        </div>
        <button
          onClick={openAddModal}
          className="flex items-center gap-2 bg-primary-500 hover:bg-primary-600 text-white px-4 py-2.5 rounded-xl font-semibold text-sm transition-colors shadow-sm"
        >
          <Plus size={18} />
          <span>Add Batch</span>
        </button>
      </div>

      {/* Filter / Search Bar */}
      <div className="flex items-center justify-between gap-4 bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
        <div className="relative flex-1 max-w-md">
          <Search size={18} className="absolute left-3 top-2.5 text-slate-400" />
          <input
            type="text"
            placeholder="Search batches by name, code, or stream..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-4 py-2 text-sm rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500"
          />
        </div>
        <div className="text-sm text-slate-500">
          Total Batches: <span className="font-semibold text-slate-700">{filteredBatches.length}</span>
        </div>
      </div>

      {/* Data Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-slate-400">Loading batches...</div>
        ) : filteredBatches.length === 0 ? (
          <div className="p-12 text-center text-slate-400">No batches found matching your search.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-50 text-slate-600 uppercase text-xs font-semibold border-b border-slate-200">
                <tr>
                  <th className="px-6 py-3.5">Batch Name</th>
                  <th className="px-6 py-3.5">Code</th>
                  <th className="px-6 py-3.5">Stream</th>
                  <th className="px-6 py-3.5">Description</th>
                  <th className="px-6 py-3.5">Status</th>
                  <th className="px-6 py-3.5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-slate-700">
                {filteredBatches.map((batch) => (
                  <tr key={batch.id} className="hover:bg-slate-50/80 transition-colors">
                    <td className="px-6 py-4 font-semibold text-slate-800">{batch.name}</td>
                    <td className="px-6 py-4 font-mono text-xs text-primary-600 bg-primary-50/50 px-2 py-0.5 rounded w-max inline-block my-3">
                      {batch.code}
                    </td>
                    <td className="px-6 py-4">
                      <span className="inline-block px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-100 text-slate-700">
                        {batch.stream}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-slate-500 max-w-xs truncate">{batch.description || '—'}</td>
                    <td className="px-6 py-4">
                      {batch.is_active ? (
                        <span className="flex items-center gap-1.5 text-xs text-emerald-600 font-medium">
                          <CheckCircle2 size={16} /> Active
                        </span>
                      ) : (
                        <span className="flex items-center gap-1.5 text-xs text-slate-400 font-medium">
                          <XCircle size={16} /> Inactive
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-4 text-right space-x-2">
                      <button
                        onClick={() => openEditModal(batch)}
                        className="p-1.5 text-slate-500 hover:text-primary-600 rounded-lg hover:bg-slate-100 transition-colors"
                        title="Edit Batch"
                      >
                        <Edit2 size={16} />
                      </button>
                      <button
                        onClick={() => handleDelete(batch.id)}
                        className="p-1.5 text-slate-500 hover:text-danger-500 rounded-lg hover:bg-slate-100 transition-colors"
                        title="Delete Batch"
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
      </div>

      {/* Add / Edit Modal */}
      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-sm p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-md overflow-hidden animate-in fade-in zoom-in-95 duration-200">
            <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between">
              <h2 className="text-lg font-bold text-slate-800">
                {editingBatch ? 'Edit Batch' : 'Create New Batch'}
              </h2>
              <button
                onClick={() => setModalOpen(false)}
                className="text-slate-400 hover:text-slate-600 text-lg font-bold"
              >
                ×
              </button>
            </div>

            <form onSubmit={handleSubmit} className="p-6 space-y-4">
              {errorMsg && (
                <div className="flex items-center gap-2 p-3 text-xs text-danger-500 bg-red-50 rounded-xl border border-red-200">
                  <AlertCircle size={16} className="flex-shrink-0" />
                  <span>{errorMsg}</span>
                </div>
              )}

              <div>
                <label className="block text-xs font-semibold text-slate-600 uppercase mb-1.5">
                  Batch Name *
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Class 12 Physics Elite"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className="w-full px-3 py-2 text-sm rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-600 uppercase mb-1.5">
                  Batch Code *
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. C12PE"
                  value={formData.code}
                  onChange={(e) => setFormData({ ...formData, code: e.target.value })}
                  className="w-full px-3 py-2 text-sm rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-600 uppercase mb-1.5">
                  Academic Stream
                </label>
                <select
                  value={formData.stream}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      stream: e.target.value as 'JEE_MAIN' | 'JEE_ADVANCED' | 'NEET' | 'OTHER',
                    })
                  }
                  className="w-full px-3 py-2 text-sm rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500 bg-white"
                >
                  <option value="JEE_MAIN">JEE Main</option>
                  <option value="JEE_ADVANCED">JEE Advanced</option>
                  <option value="NEET">NEET</option>
                  <option value="OTHER">Other / General</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-600 uppercase mb-1.5">
                  Description
                </label>
                <textarea
                  rows={3}
                  placeholder="Cohort goals, syllabus target, schedule details..."
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  className="w-full px-3 py-2 text-sm rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500"
                />
              </div>

              <div className="flex items-center gap-2 pt-1">
                <input
                  type="checkbox"
                  id="batch-active"
                  checked={formData.is_active}
                  onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                  className="rounded text-primary-500 focus:ring-primary-500/20 w-4 h-4"
                />
                <label htmlFor="batch-active" className="text-sm text-slate-700 font-medium">
                  Active academic cohort
                </label>
              </div>

              <div className="flex justify-end gap-3 pt-4 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setModalOpen(false)}
                  className="px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100 rounded-xl transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="px-5 py-2 text-sm font-bold text-white bg-primary-500 hover:bg-primary-600 rounded-xl transition-colors disabled:opacity-50"
                >
                  {isSubmitting ? 'Saving...' : editingBatch ? 'Save Changes' : 'Create Batch'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default BatchesPage;
