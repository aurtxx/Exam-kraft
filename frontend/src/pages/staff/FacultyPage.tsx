import React, { useState, useEffect } from 'react';
import { apiService } from '../../services/api';
import { FacultyMember } from '../../types';
import { Plus, Search, Trash2, Mail, Phone, BookOpen, AlertCircle, CheckCircle2, XCircle } from 'lucide-react';

export const FacultyPage: React.FC = () => {
  const [faculties, setFaculties] = useState<FacultyMember[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [search, setSearch] = useState<string>('');
  const [modalOpen, setModalOpen] = useState<boolean>(false);
  const [formData, setFormData] = useState<{
    name: string;
    email: string;
    phone: string;
    department: string;
    subjects: string;
    password?: string;
    is_active: boolean;
  }>({
    name: '',
    email: '',
    phone: '',
    department: '',
    subjects: '',
    password: '',
    is_active: true,
  });
  const [errorMsg, setErrorMsg] = useState<string>('');
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  const fetchFaculty = async () => {
    try {
      setLoading(true);
      const data = await apiService.getFaculty();
      setFaculties(data);
    } catch (err) {
      console.error('Failed to load faculty roster:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchFaculty();
  }, []);

  const openAddModal = () => {
    setFormData({
      name: '',
      email: '',
      phone: '',
      department: '',
      subjects: '',
      password: '',
      is_active: true,
    });
    setErrorMsg('');
    setModalOpen(true);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.name.trim() || !formData.email.trim()) {
      setErrorMsg('Name and Email are required.');
      return;
    }
    try {
      setIsSubmitting(true);
      setErrorMsg('');
      const subjectsArray = formData.subjects
        .split(',')
        .map((s) => s.strip ? s.trim() : s.trim())
        .filter((s) => s.length > 0);

      await apiService.createFaculty({
        ...formData,
        subjects: subjectsArray,
        subject_ids: subjectsArray,
      });
      setModalOpen(false);
      fetchFaculty();
    } catch (err: any) {
      const msg = err.response?.data?.message || err.response?.data?.code || 'Failed to save faculty.';
      setErrorMsg(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (confirm('Are you sure you want to delete this faculty member?')) {
      try {
        await apiService.deleteFaculty(id);
        fetchFaculty();
      } catch (err) {
        console.error('Failed to delete faculty:', err);
      }
    }
  };

  const filteredFaculties = faculties.filter((f) => {
    const q = search.toLowerCase();
    return (
      f.name?.toLowerCase().includes(q) ||
      f.email?.toLowerCase().includes(q) ||
      f.department?.toLowerCase().includes(q) ||
      (f.subjects && f.subjects.some((s) => s.toLowerCase().includes(q)))
    );
  });

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Faculty Roster</h1>
          <p className="text-sm text-slate-500 mt-1">Manage teaching staff, subject authorizations, and exam authoring access.</p>
        </div>
        <button
          onClick={openAddModal}
          className="flex items-center gap-2 bg-primary-500 hover:bg-primary-600 text-white px-4 py-2.5 rounded-xl font-semibold text-sm transition-colors shadow-sm"
        >
          <Plus size={18} />
          <span>Add Faculty</span>
        </button>
      </div>

      {/* Filter Bar */}
      <div className="flex items-center justify-between gap-4 bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
        <div className="relative flex-1 max-w-md">
          <Search size={18} className="absolute left-3 top-2.5 text-slate-400" />
          <input
            type="text"
            placeholder="Search faculty by name, email, department, or subject tag..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-4 py-2 text-sm rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500"
          />
        </div>
        <div className="text-sm text-slate-500">
          Total Faculty: <span className="font-semibold text-slate-700">{filteredFaculties.length}</span>
        </div>
      </div>

      {/* Faculty Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-slate-400">Loading faculty members...</div>
        ) : filteredFaculties.length === 0 ? (
          <div className="p-12 text-center text-slate-400">No faculty members found.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-50 text-slate-600 uppercase text-xs font-semibold border-b border-slate-200">
                <tr>
                  <th className="px-6 py-3.5">Faculty Name</th>
                  <th className="px-6 py-3.5">Contact Details</th>
                  <th className="px-6 py-3.5">Department</th>
                  <th className="px-6 py-3.5">Subject Tags</th>
                  <th className="px-6 py-3.5">Status</th>
                  <th className="px-6 py-3.5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-slate-700">
                {filteredFaculties.map((fac) => (
                  <tr key={fac.id} className="hover:bg-slate-50/80 transition-colors">
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-3">
                        <div className="w-9 h-9 rounded-full bg-primary-100 text-primary-600 font-bold flex items-center justify-center text-sm">
                          {fac.name?.charAt(0).toUpperCase() || 'F'}
                        </div>
                        <div>
                          <p className="font-semibold text-slate-800">{fac.name}</p>
                          <p className="text-xs text-slate-400">{fac.username}</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="space-y-0.5 text-xs">
                        {fac.email && (
                          <div className="flex items-center gap-1.5 text-slate-600">
                            <Mail size={12} className="text-slate-400" />
                            <span>{fac.email}</span>
                          </div>
                        )}
                        {fac.phone && (
                          <div className="flex items-center gap-1.5 text-slate-500">
                            <Phone size={12} className="text-slate-400" />
                            <span>{fac.phone}</span>
                          </div>
                        )}
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <span className="text-xs font-medium text-slate-700 bg-slate-100 px-2.5 py-1 rounded-lg">
                        {fac.department || 'General'}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex flex-wrap gap-1.5 max-w-xs">
                        {fac.subjects && fac.subjects.length > 0 ? (
                          fac.subjects.map((subj, idx) => (
                            <span
                              key={idx}
                              className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-50 text-emerald-700"
                            >
                              <BookOpen size={10} />
                              {subj}
                            </span>
                          ))
                        ) : (
                          <span className="text-xs text-slate-400 italic">No subjects assigned</span>
                        )}
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      {fac.is_active ? (
                        <span className="flex items-center gap-1 text-xs text-emerald-600 font-medium">
                          <CheckCircle2 size={15} /> Active
                        </span>
                      ) : (
                        <span className="flex items-center gap-1 text-xs text-slate-400 font-medium">
                          <XCircle size={15} /> Inactive
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-4 text-right">
                      <button
                        onClick={() => handleDelete(fac.id)}
                        className="p-1.5 text-slate-500 hover:text-danger-500 rounded-lg hover:bg-slate-100 transition-colors"
                        title="Delete Faculty"
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

      {/* Add Faculty Modal */}
      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-sm p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-md overflow-hidden animate-in fade-in zoom-in-95 duration-200">
            <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between">
              <h2 className="text-lg font-bold text-slate-800">Add Faculty Member</h2>
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
                  Full Name *
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Dr. Richard Feynman"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className="w-full px-3 py-2 text-sm rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-600 uppercase mb-1.5">
                  Email Address *
                </label>
                <input
                  type="email"
                  required
                  placeholder="feynman@apex.edu"
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

              <div>
                <label className="block text-xs font-semibold text-slate-600 uppercase mb-1.5">
                  Department
                </label>
                <input
                  type="text"
                  placeholder="e.g. Physics / Mathematics"
                  value={formData.department}
                  onChange={(e) => setFormData({ ...formData, department: e.target.value })}
                  className="w-full px-3 py-2 text-sm rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-600 uppercase mb-1.5">
                  Subject Tags (Comma Separated)
                </label>
                <input
                  type="text"
                  placeholder="e.g. Mechanics, Thermodynamics, Quantum"
                  value={formData.subjects}
                  onChange={(e) => setFormData({ ...formData, subjects: e.target.value })}
                  className="w-full px-3 py-2 text-sm rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-600 uppercase mb-1.5">
                  Initial Password
                </label>
                <input
                  type="password"
                  placeholder="FacultyPass#2026 (Leave blank for default)"
                  value={formData.password}
                  onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                  className="w-full px-3 py-2 text-sm rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500"
                />
              </div>

              <div className="flex items-center gap-2 pt-1">
                <input
                  type="checkbox"
                  id="faculty-active"
                  checked={formData.is_active}
                  onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                  className="rounded text-primary-500 focus:ring-primary-500/20 w-4 h-4"
                />
                <label htmlFor="faculty-active" className="text-sm text-slate-700 font-medium">
                  Active faculty account
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
                  {isSubmitting ? 'Creating...' : 'Create Faculty'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default FacultyPage;
