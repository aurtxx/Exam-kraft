import React, { useState, useEffect } from 'react';
import { apiService } from '../../services/api';
import { Notice, Batch, ExaminationCenter } from '../../types';
import { Plus, Bell, Trash2, CheckCircle2, XCircle, Users, Building2, AlertCircle } from 'lucide-react';

export const NoticesPage: React.FC = () => {
  const [notices, setNotices] = useState<Notice[]>([]);
  const [batches, setBatches] = useState<Batch[]>([]);
  const [centers, setCenters] = useState<ExaminationCenter[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [modalOpen, setModalOpen] = useState<boolean>(false);
  const [formData, setFormData] = useState<{
    title: string;
    content: string;
    target_batch_ids: string[];
    target_center_ids: string[];
    is_active: boolean;
    start_time: string;
    end_time: string;
  }>({
    title: '',
    content: '',
    target_batch_ids: [],
    target_center_ids: [],
    is_active: true,
    start_time: '',
    end_time: '',
  });

  const [errorMsg, setErrorMsg] = useState<string>('');
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  const fetchNotices = async () => {
    try {
      setLoading(true);
      const data = await apiService.getNotices();
      setNotices(data);
    } catch (err) {
      console.error('Failed to load notices:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchNotices();
    const loadTargets = async () => {
      try {
        const [bData, cData] = await Promise.all([apiService.getBatches(), apiService.getCenters()]);
        setBatches(bData);
        setCenters(cData);
      } catch (err) {
        console.error('Failed to load target master data:', err);
      }
    };
    loadTargets();
  }, []);

  const openAddModal = () => {
    setFormData({
      title: '',
      content: '',
      target_batch_ids: [],
      target_center_ids: [],
      is_active: true,
      start_time: '',
      end_time: '',
    });
    setErrorMsg('');
    setModalOpen(true);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.title.trim() || !formData.content.trim()) {
      setErrorMsg('Title and Content are required.');
      return;
    }
    try {
      setIsSubmitting(true);
      setErrorMsg('');
      await apiService.createNotice(formData);
      setModalOpen(false);
      fetchNotices();
    } catch (err: any) {
      setErrorMsg(err.response?.data?.message || 'Failed to publish notice.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (confirm('Are you sure you want to delete this notice?')) {
      try {
        await apiService.deleteNotice(id);
        fetchNotices();
      } catch (err) {
        console.error('Failed to delete notice:', err);
      }
    }
  };

  return (
    <div className="p-6 space-y-6">
      {/* Top Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Notices & Announcements</h1>
          <p className="text-sm text-slate-500 mt-1">
            Broadcast institutional notifications, admit card alerts, and venue guidelines.
          </p>
        </div>
        <button
          onClick={openAddModal}
          className="flex items-center gap-2 bg-primary-500 hover:bg-primary-600 text-white px-4 py-2.5 rounded-xl font-semibold text-sm transition-colors shadow-sm"
        >
          <Plus size={18} />
          <span>New Notice</span>
        </button>
      </div>

      {/* Notices List */}
      <div className="space-y-4">
        {loading ? (
          <div className="p-12 text-center text-slate-400 bg-white rounded-xl border border-slate-200">
            Loading announcements...
          </div>
        ) : notices.length === 0 ? (
          <div className="p-16 text-center text-slate-400 bg-white rounded-xl border border-slate-200">
            <Bell size={40} className="mx-auto mb-2 text-slate-300" />
            <p className="font-semibold text-slate-600">No broadcast notices published yet.</p>
            <p className="text-xs text-slate-400 mt-1">Click "New Notice" above to publish an announcement.</p>
          </div>
        ) : (
          notices.map((notice) => (
            <div
              key={notice.id}
              className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm hover:shadow-md transition-shadow flex flex-col justify-between space-y-3"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <h3 className="font-bold text-base text-slate-800">{notice.title}</h3>
                    {notice.is_active ? (
                      <span className="flex items-center gap-1 text-[11px] font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full">
                        <CheckCircle2 size={12} /> Active
                      </span>
                    ) : (
                      <span className="flex items-center gap-1 text-[11px] font-bold text-slate-400 bg-slate-100 px-2 py-0.5 rounded-full">
                        <XCircle size={12} /> Inactive
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-slate-400">
                    Posted on {notice.created_at ? new Date(notice.created_at).toLocaleDateString() : 'Today'}
                  </p>
                </div>

                <button
                  onClick={() => handleDelete(notice.id)}
                  className="text-slate-400 hover:text-danger-500 p-1.5 rounded-lg hover:bg-slate-50 transition-colors"
                >
                  <Trash2 size={16} />
                </button>
              </div>

              <div className="text-sm text-slate-700 whitespace-pre-wrap leading-relaxed">
                {notice.content}
              </div>

              {/* Target Audience Badges */}
              <div className="pt-3 border-t border-slate-100 flex flex-wrap items-center gap-3 text-xs text-slate-500">
                <div className="flex items-center gap-1.5">
                  <Users size={14} className="text-slate-400" />
                  <span>
                    Target Batches:{' '}
                    {notice.target_batch_names && notice.target_batch_names.length > 0 ? (
                      <strong className="text-slate-700">{notice.target_batch_names.join(', ')}</strong>
                    ) : (
                      <span className="text-slate-400">All Institution</span>
                    )}
                  </span>
                </div>

                <div className="flex items-center gap-1.5">
                  <Building2 size={14} className="text-slate-400" />
                  <span>
                    Target Centres:{' '}
                    {notice.target_center_names && notice.target_center_names.length > 0 ? (
                      <strong className="text-slate-700">{notice.target_center_names.join(', ')}</strong>
                    ) : (
                      <span className="text-slate-400">All Centres</span>
                    )}
                  </span>
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Add Notice Modal */}
      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-sm p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg overflow-hidden animate-in fade-in zoom-in-95 duration-200">
            <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between">
              <h2 className="text-lg font-bold text-slate-800">Publish New Notice</h2>
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
                  Notice Title *
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Schedule for Phase 1 JEE Mock Examinations"
                  value={formData.title}
                  onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                  className="w-full px-3 py-2 text-sm rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-600 uppercase mb-1.5">
                  Announcement Content *
                </label>
                <textarea
                  rows={4}
                  required
                  placeholder="Type announcement details, venue guidelines, or reporting instructions..."
                  value={formData.content}
                  onChange={(e) => setFormData({ ...formData, content: e.target.value })}
                  className="w-full px-3 py-2 text-sm rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500"
                />
              </div>

              {/* Target Batches */}
              <div>
                <label className="block text-xs font-semibold text-slate-600 uppercase mb-1.5">
                  Target Batches (Select multiple or leave empty for all)
                </label>
                <div className="max-h-32 overflow-y-auto border border-slate-200 rounded-lg p-2 space-y-1">
                  {batches.map((b) => {
                    const isChecked = formData.target_batch_ids.includes(b.id);
                    return (
                      <label key={b.id} className="flex items-center gap-2 text-xs p-1 hover:bg-slate-50 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={isChecked}
                          onChange={() => {
                            if (isChecked) {
                              setFormData({
                                ...formData,
                                target_batch_ids: formData.target_batch_ids.filter((id) => id !== b.id),
                              });
                            } else {
                              setFormData({
                                ...formData,
                                target_batch_ids: [...formData.target_batch_ids, b.id],
                              });
                            }
                          }}
                        />
                        <span>{b.name} ({b.code})</span>
                      </label>
                    );
                  })}
                </div>
              </div>

              {/* Target Centers */}
              <div>
                <label className="block text-xs font-semibold text-slate-600 uppercase mb-1.5">
                  Target Centers (Select multiple or leave empty for all)
                </label>
                <div className="max-h-32 overflow-y-auto border border-slate-200 rounded-lg p-2 space-y-1">
                  {centers.map((c) => {
                    const isChecked = formData.target_center_ids.includes(c.id);
                    return (
                      <label key={c.id} className="flex items-center gap-2 text-xs p-1 hover:bg-slate-50 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={isChecked}
                          onChange={() => {
                            if (isChecked) {
                              setFormData({
                                ...formData,
                                target_center_ids: formData.target_center_ids.filter((id) => id !== c.id),
                              });
                            } else {
                              setFormData({
                                ...formData,
                                target_center_ids: [...formData.target_center_ids, c.id],
                              });
                            }
                          }}
                        />
                        <span>{c.name} ({c.code})</span>
                      </label>
                    );
                  })}
                </div>
              </div>

              <div className="flex items-center gap-2 pt-1">
                <input
                  type="checkbox"
                  id="notice-active"
                  checked={formData.is_active}
                  onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                  className="rounded text-primary-500 focus:ring-primary-500/20 w-4 h-4"
                />
                <label htmlFor="notice-active" className="text-sm text-slate-700 font-medium">
                  Active announcement
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
                  {isSubmitting ? 'Publishing...' : 'Publish Notice'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default NoticesPage;
