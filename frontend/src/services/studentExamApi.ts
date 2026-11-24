import apiClient from './api';
import { CBTAttemptPayload, CBTResponseRecord } from '../types';

export interface SaveResponsePayload {
  question_id: string | number;
  selected_options?: string[];
  numerical_value?: string | null;
  status?: string;
  time_spent_seconds?: number;
}

export interface SaveResponseResult {
  status: 'SUCCESS' | 'ERROR';
  saved_at: string;
  question_id: string | number;
  remaining_seconds: number;
}

export interface HeartbeatResult {
  status: 'SUCCESS' | 'ERROR';
  server_time: string;
  server_deadline: string;
  remaining_seconds: number;
  is_terminated: boolean;
  tab_switch_count?: number;
}

export interface SubmitResult {
  status: 'SUCCESS' | 'ERROR';
  code?: string;
  attempt_id: string;
  submission_status: string;
  submitted_at: string;
  message?: string;
}

export const studentExamApi = {
  async startExam(examId: string): Promise<CBTAttemptPayload> {
    const res = await apiClient.post<CBTAttemptPayload>('/student/attempts/start/', {
      exam_id: examId,
    });
    return res.data;
  },

  async saveResponse(attemptId: string, payload: SaveResponsePayload): Promise<SaveResponseResult> {
    const res = await apiClient.post<SaveResponseResult>(
      `/student/attempts/${attemptId}/responses/`,
      payload
    );
    return res.data;
  },

  async sendHeartbeat(attemptId: string, blurCount: number): Promise<HeartbeatResult> {
    const res = await apiClient.post<HeartbeatResult>(
      `/student/attempts/${attemptId}/heartbeat/`,
      {
        window_blur_count: blurCount,
      }
    );
    return res.data;
  },

  async submitExam(
    attemptId: string,
    reason: 'MANUAL_SUBMIT' | 'AUTO_TIMER_EXPIRY' = 'MANUAL_SUBMIT'
  ): Promise<SubmitResult> {
    const res = await apiClient.post<SubmitResult>(
      `/student/attempts/${attemptId}/submit/`,
      {
        submission_reason: reason,
      }
    );
    return res.data;
  },

  async resumeAttempt(attemptId: string): Promise<CBTAttemptPayload> {
    const res = await apiClient.get<CBTAttemptPayload>(
      `/student/attempts/${attemptId}/resume/`
    );
    return res.data;
  },

  async recordProctoringEvent(
    attemptId: string,
    eventType: 'TAB_SWITCH' | 'FULLSCREEN_EXIT' | 'WINDOW_BLUR',
    details: Record<string, unknown> = {}
  ): Promise<{ status: string; tab_switch_count: number; auto_submitted: boolean }> {
    const res = await apiClient.post(
      `/student/attempts/${attemptId}/proctoring_event/`,
      {
        event_type: eventType,
        details,
      }
    );
    return res.data;
  },

  // --- Offline LocalStorage Cache Helpers ---
  getCacheKey(studentId: string, examId: string): string {
    return `cbt-${studentId}-${examId}-responses`;
  },

  saveLocalCache(key: string, responses: Record<string, CBTResponseRecord>): void {
    try {
      localStorage.setItem(key, JSON.stringify(responses));
    } catch (e) {
      console.warn('Failed to save to localStorage', e);
    }
  },

  loadLocalCache(key: string): Record<string, CBTResponseRecord> | null {
    try {
      const data = localStorage.getItem(key);
      if (data) {
        return JSON.parse(data);
      }
    } catch (e) {
      console.warn('Failed to parse localStorage cache', e);
    }
    return null;
  },

  clearLocalCache(key: string): void {
    try {
      localStorage.removeItem(key);
    } catch (e) {
      // ignore
    }
  },
};

export default studentExamApi;
