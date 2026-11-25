import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios';
import {
  Batch,
  ExaminationCenter,
  FacultyMember,
  StudentMember,
  BulkImportResult,
  QuestionBank,
  Question,
  Examination,
  Notice,
} from '../types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
    Accept: 'application/json',
  },
});

let isRefreshing = false;
let failedQueue: Array<{
  resolve: (token: string) => void;
  reject: (error: unknown) => void;
}> = [];

const processQueue = (error: unknown, token: string | null = null) => {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error);
    } else if (token) {
      prom.resolve(token);
    }
  });
  failedQueue = [];
};

// Request Interceptor: Attach JWT Token and Tenant ID if present
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = localStorage.getItem('access_token');
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }

    const tenantId = localStorage.getItem('tenant_id');
    if (tenantId && config.headers) {
      config.headers['X-Tenant-ID'] = tenantId;
    }

    return config;
  },
  (error) => Promise.reject(error)
);

// Response Interceptor: Handle 401 with Token Auto-Refresh
apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };

    if (error.response?.status === 401 && originalRequest && !originalRequest._retry) {
      if (originalRequest.url?.includes('/auth/login/') || originalRequest.url?.includes('/auth/token/refresh/')) {
        return Promise.reject(error);
      }

      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        })
          .then((token) => {
            if (originalRequest.headers) {
              originalRequest.headers.Authorization = `Bearer ${token}`;
            }
            return apiClient(originalRequest);
          })
          .catch((err) => Promise.reject(err));
      }

      originalRequest._retry = true;
      isRefreshing = true;

      const refreshToken = localStorage.getItem('refresh_token');
      if (!refreshToken) {
        isRefreshing = false;
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        localStorage.removeItem('current_user');
        window.location.href = '/login';
        return Promise.reject(error);
      }

      try {
        const response = await axios.post(`${API_BASE_URL}/auth/token/refresh/`, {
          refresh: refreshToken,
        });

        const newAccessToken = response.data.access;
        localStorage.setItem('access_token', newAccessToken);

        if (response.data.refresh) {
          localStorage.setItem('refresh_token', response.data.refresh);
        }

        apiClient.defaults.headers.common.Authorization = `Bearer ${newAccessToken}`;
        processQueue(null, newAccessToken);

        if (originalRequest.headers) {
          originalRequest.headers.Authorization = `Bearer ${newAccessToken}`;
        }
        return apiClient(originalRequest);
      } catch (refreshError) {
        processQueue(refreshError, null);
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        localStorage.removeItem('current_user');
        window.location.href = '/login';
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }

    return Promise.reject(error);
  }
);

// =============================================================================
// Milestone M2 API Services
// =============================================================================

export const apiService = {
  // --- Batches ---
  async getBatches(): Promise<Batch[]> {
    const res = await apiClient.get('/organizations/batches/');
    return res.data.batches || (Array.isArray(res.data) ? res.data : []);
  },
  async createBatch(data: Partial<Batch>): Promise<Batch> {
    const res = await apiClient.post('/organizations/batches/', data);
    return res.data;
  },
  async updateBatch(id: string, data: Partial<Batch>): Promise<Batch> {
    const res = await apiClient.put(`/organizations/batches/${id}/`, data);
    return res.data;
  },
  async deleteBatch(id: string): Promise<void> {
    await apiClient.delete(`/organizations/batches/${id}/`);
  },

  // --- Examination Centers ---
  async getCenters(): Promise<ExaminationCenter[]> {
    const res = await apiClient.get('/organizations/centers/');
    return res.data.centers || (Array.isArray(res.data) ? res.data : []);
  },
  async createCenter(data: Partial<ExaminationCenter>): Promise<ExaminationCenter> {
    const res = await apiClient.post('/organizations/centers/', data);
    return res.data;
  },
  async updateCenter(id: string, data: Partial<ExaminationCenter>): Promise<ExaminationCenter> {
    const res = await apiClient.put(`/organizations/centers/${id}/`, data);
    return res.data;
  },
  async deleteCenter(id: string): Promise<void> {
    await apiClient.delete(`/organizations/centers/${id}/`);
  },

  // --- Faculty ---
  async getFaculty(): Promise<FacultyMember[]> {
    const res = await apiClient.get('/users/faculty/');
    return res.data.faculties || [];
  },
  async createFaculty(data: Record<string, unknown>): Promise<FacultyMember> {
    const res = await apiClient.post('/users/faculty/', data);
    return res.data;
  },
  async deleteFaculty(id: string): Promise<void> {
    await apiClient.delete(`/users/faculty/${id}/`);
  },

  // --- Students ---
  async getStudents(params?: { page?: number; page_size?: number; search?: string; batch_id?: string; centre_id?: string }): Promise<{
    count: number;
    total_pages: number;
    current_page: number;
    students: StudentMember[];
  }> {
    const res = await apiClient.get('/users/students/', { params });
    return res.data;
  },
  async createStudent(data: Record<string, unknown>): Promise<StudentMember> {
    const res = await apiClient.post('/users/students/', data);
    return res.data.student || res.data;
  },
  async deleteStudent(id: string): Promise<void> {
    await apiClient.delete(`/users/students/${id}/`);
  },
  async bulkImportStudents(fileOrContent: File | string): Promise<BulkImportResult> {
    if (typeof fileOrContent === 'string') {
      const res = await apiClient.post('/users/students/bulk-upload/', fileOrContent, {
        headers: { 'Content-Type': 'text/csv' },
      });
      return res.data;
    } else {
      const formData = new FormData();
      formData.append('file', fileOrContent);
      const res = await apiClient.post('/users/students/bulk-upload/', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      return res.data;
    }
  },

  // --- Question Banks / Question Papers ---
  async getQuestionBanks(): Promise<QuestionBank[]> {
    const res = await apiClient.get('/question-papers/');
    return res.data.question_papers || res.data.question_banks || [];
  },
  async createQuestionBank(data: Partial<QuestionBank>): Promise<QuestionBank> {
    const res = await apiClient.post('/question-papers/', data);
    return res.data.question_paper || res.data;
  },
  async getQuestionBankQuestions(paperId: string): Promise<{ metadata: Record<string, unknown>; questions: Question[] }> {
    const res = await apiClient.get(`/question-papers/${paperId}/questions/`);
    return res.data;
  },
  async createQuestion(paperId: string, data: Record<string, unknown>): Promise<Question> {
    const res = await apiClient.post(`/question-papers/${paperId}/questions/`, data);
    return res.data.question || res.data;
  },
  async deleteQuestion(id: string): Promise<void> {
    await apiClient.delete(`/questions/${id}/`);
  },

  // --- Examinations ---
  async getExaminations(): Promise<Examination[]> {
    const res = await apiClient.get('/examinations/');
    return res.data.examinations || [];
  },
  async createExamination(data: Record<string, unknown>): Promise<Examination> {
    const res = await apiClient.post('/examinations/', data);
    return res.data.examination || res.data;
  },
  async assignCandidates(examId: string, data: { student_ids?: string[]; batch_ids?: string[]; centre_ids?: string[] }): Promise<{ assigned_count: number }> {
    const res = await apiClient.post(`/examinations/${examId}/assign-candidates/`, data);
    return res.data;
  },
  async publishExamination(examId: string): Promise<{ status: string; message: string }> {
    const res = await apiClient.post(`/examinations/${examId}/publish/`);
    return res.data;
  },
  async getExamPreview(examId: string): Promise<{ exam: Examination; questions: Question[] }> {
    const res = await apiClient.get(`/examinations/${examId}/preview/`);
    return res.data;
  },

  // --- Notices ---
  async getNotices(params?: { active?: boolean }): Promise<Notice[]> {
    const res = await apiClient.get('/notices/', { params });
    return res.data.notices || [];
  },
  async createNotice(data: Record<string, unknown>): Promise<Notice> {
    const res = await apiClient.post('/notices/', data);
    return res.data.notice || res.data;
  },
  async deleteNotice(id: string): Promise<void> {
    await apiClient.delete(`/notices/${id}/`);
  },
};

export default apiClient;
