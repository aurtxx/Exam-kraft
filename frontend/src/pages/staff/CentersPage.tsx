import React, { useState, useEffect } from 'react';
import { apiService } from '../../services/api';
import { ExaminationCenter } from '../../types';
import { Plus, Search, Edit2, Trash2, Building2, Users, CheckCircle2, XCircle, AlertCircle } from 'lucide-react';

export const CentersPage: React.FC = () => {
  const [centers, setCenters] = useState<ExaminationCenter[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [search, setSearch] = useState<string>('');
  const [modalOpen, setModalOpen] = useState<boolean>(false);
  const [editingCenter, setEditingCenter] = useState<ExaminationCenter | null>(null);
  const [formData, setFormData] = useState<{
    name: string;
    code: string;
    address: string;
    capacity: number;
    is_active: boolean;
  }>({
    name: '',
    code: '',
    address: '',
    capacity: 100,
    is_active: true,
  });
  const [errorMsg, setErrorMsg] = useState<string>('');
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  const fetchCenters = async () => {
    try {
      setLoading(true);
      const data = await apiService.getCenters();
      setCenters(data);
    } catch (err) {
      console.error('Failed to load examination centers:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCenters();
  }, []);

  const openAddModal = () => {
    setEditingCenter(null);
    setFormData({
      name: '',
      code: '',
      address: '',
      capacity: 100,
      is_active: true,
    });
    setErrorMsg('');
    setModalOpen(true);
  };

  const openEditModal = (center: ExaminationCenter) => {
    setEditingCenter(center);
    setFormData({
      name: center.name,
      code: center.code,
      address: center.address || '',
      capacity: center.capacity,
      is_active: center.is_active,
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
    if (formData.capacity <= 0) {
      setErrorMsg('Capacity must be greater than zero.');
      return;
    }
    try {
      setIsSubmitting(true);
      setErrorMsg('');
      if (editingCenter) {
        await apiService.updateCenter(editingCenter.id, formData);
      } else {
        await apiService.createCenter(formData);
      }
      setModalOpen(false);
      fetchCenters();
    } catch (err: any) {
      const msg = err.response?.data?.message || err.response?.data?.code || 'Failed to save examination center.';
      setErrorMsg(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (confirm('Are you sure you want to delete this examination center?')) {
      try {
        await apiService.deleteCenter(id);
        fetchCenters();
      } catch (err) {
        console.error('Failed to delete examination center:', err);
      }
    }
  };

  const totalCapacity = centers.reduce((sum, c) => sum + (c.is_active ? c.capacity : 0), 0);

  const filteredCenters = centers.filter(
    (c) =>
      c.name.toLowerCase().includes(search.toLowerCase()) ||
      c.code.toLowerCase().includes(search.toLowerCase()) ||
      (c.address && c.address.toLowerCase().includes(search.toLowerCase()))
  );

  return (
    <div className="p-6 space-y-6">
      {/* Top Banner Stats */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Examination Centres</h1>
          <p className="text-sm text-slate-500 mt-1">Manage test venues, regional computer labs, and terminal seating capacities.</p>
        </div>
        <button
          onClick={openAddModal}
          className="flex items-center gap-2 bg-primary-500 hover:bg-primary-600 text-white px-4 py-2.5 rounded-xl font-semibold text-sm transition-colors shadow-sm"
        >
          <Plus size={18} />
          <span>Add Centre</span>
        </button>
      </div>

      {/* Summary KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-primary-50 text-primary-600 flex items-center justify-center">
            <Building2 size={24} />
          </div>
          <div>
            <p className="text-xs font-semibold text-slate-400 uppercase">Total Centres</p>
            <p className="text-xl font-bold text-slate-800">{centers.length}</p>
          </div>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center">
            <Users size={24} />
          </div>
          <div>
            <p className="text-xs font-semibold text-slate-400 uppercase">Active Seat Capacity</p>
            <p className="text-xl font-bold text-slate-800">{totalCapacity} Seats</p>
          </div>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-purple-50 text-purple-600 flex items-center justify-center">
            <CheckCircle2 size={24} />
          </div>
          <div>
            <p className="text-xs font-semibold text-slate-400 uppercase">Operational Status</p>
            <p className="text-xl font-bold text-slate-800">
              {centers.filter((c) => c.is_active).length} / {centers.length} Active
            </p>
          </div>
        </div>
      </div>

      {/* Search Bar */}
      <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex items-center justify-between gap-4">
        <div className="relative flex-1 max-w-md">
          <Search size={18} className="absolute left-3 top-2.5 text-slate-400" />
          <input
            type="text"
            placeholder="Search centres by venue name, code, or address..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-4 py-2 text-sm rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500"
          />
        </div>
        <div className="text-sm text-slate-500">
          Showing: <span className="font-semibold text-slate-700">{filteredCenters.length}</span> venues
        </div>
      </div>

      {/* Grid of Center Cards */}
      {loading ? (
        <div className="p-12 text-center text-slate-400 bg-white rounded-xl border border-slate-200">
          Loading examination centres...
        </div>
      ) : filteredCenters.length === 0 ? (
        <div className="p-12 text-center text-slate-400 bg-white rounded-xl border border-slate-200">
          No examination centres found. Click "Add Centre" to create one.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {filteredCenters.map((center) => (
            <div
              key={center.id}
              className="bg-white rounded-2xl border border-slate-200 shadow-sm hover:shadow-md transition-shadow p-5 flex flex-col justify-between"
            >
              <div>
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <h3 className="font-bold text-base text-slate-800">{center.name}</h3>
                    <span className="inline-block font-mono text-xs text-primary-600 bg-primary-50 px-2 py-0.5 rounded mt-1 font-semibold">
                      {center.code}
                    </span>
                  </div>
                  {center.is_active ? (
                    <span className="flex items-center gap-1 text-[11px] font-semibold text-emerald-600 bg-emerald-50 px-2.5 py-0.5 rounded-full">
                      <CheckCircle2 size={12} /> Active
                    </span>
                  ) : (
                    <span className="flex items-center gap-1 text-[11px] font-semibold text-slate-400 bg-slate-100 px-2.5 py-0.5 rounded-full">
                      <XCircle size={12} /> Inactive
                    </span>
                  )}
                </div>

                <p className="text-xs text-slate-500 mt-3 line-clamp-2 min-h-[32px]">
                  {center.address || 'No venue address specified.'}
                </p>

                <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between">
                  <span className="text-xs text-slate-500">Terminal Capacity</span>
                  <span className="text-sm font-bold text-slate-800 bg-slate-100 px-2.5 py-0.5 rounded-lg">
                    {center.capacity} Seats
                  </span>
                </div>
              </div>

              <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-end gap-2">
                <button
                  onClick={() => openEditModal(center)}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-slate-600 hover:text-primary-600 hover:bg-slate-50 rounded-lg transition-colors"
                >
                  <Edit2 size={14} />
                  <span>Edit</span>
                </button>
                <button
                  onClick={() => handleDelete(center.id)}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-slate-500 hover:text-danger-500 hover:bg-red-50 rounded-lg transition-colors"
                >
                  <Trash2 size={14} />
                  <span>Delete</span>
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Add / Edit Modal */}
      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-sm p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-md overflow-hidden animate-in fade-in zoom-in-95 duration-200">
            <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between">
              <h2 className="text-lg font-bold text-slate-800">
                {editingCenter ? 'Edit Examination Centre' : 'Create Examination Centre'}
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
                  Centre Name *
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. North Campus CBT Lab"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className="w-full px-3 py-2 text-sm rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-600 uppercase mb-1.5">
                  Centre Code *
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. NC01"
                  value={formData.code}
                  onChange={(e) => setFormData({ ...formData, code: e.target.value })}
                  className="w-full px-3 py-2 text-sm rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-600 uppercase mb-1.5">
                  Terminal Seat Capacity *
                </label>
                <input
                  type="number"
                  min="1"
                  required
                  placeholder="150"
                  value={formData.capacity}
                  onChange={(e) => setFormData({ ...formData, capacity: parseInt(e.target.value) || 0 })}
                  className="w-full px-3 py-2 text-sm rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-600 uppercase mb-1.5">
                  Physical Venue Address
                </label>
                <textarea
                  rows={3}
                  placeholder="Street address, building floor, city, postal code..."
                  value={formData.address}
                  onChange={(e) => setFormData({ ...formData, address: e.target.value })}
                  className="w-full px-3 py-2 text-sm rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500"
                />
              </div>

              <div className="flex items-center gap-2 pt-1">
                <input
                  type="checkbox"
                  id="center-active"
                  checked={formData.is_active}
                  onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                  className="rounded text-primary-500 focus:ring-primary-500/20 w-4 h-4"
                />
                <label htmlFor="center-active" className="text-sm text-slate-700 font-medium">
                  Active examination venue
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
                  {isSubmitting ? 'Saving...' : editingCenter ? 'Save Changes' : 'Create Centre'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default CentersPage;
