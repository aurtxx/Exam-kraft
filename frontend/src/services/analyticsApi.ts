import apiClient from './api';
import { BatchAnalyticsPayload, ExamReportPayload } from '../types';

export const analyticsApi = {
  /**
   * Fetch detailed student scorecard and question reviews for an attempt
   */
  async getAttemptReport(attemptId: string): Promise<ExamReportPayload> {
    const res = await apiClient.get<ExamReportPayload>(`/attempts/${attemptId}/report/`);
    return res.data;
  },

  /**
   * Fetch cohort batch analytics, leaderboard, score distributions
   */
  async getExamResults(examId: string): Promise<BatchAnalyticsPayload> {
    const res = await apiClient.get<BatchAnalyticsPayload>(`/examinations/${examId}/results/`);
    return res.data;
  },

  /**
   * Trigger evaluation / re-evaluation of submitted attempts
   */
  async evaluateExam(examId: string): Promise<{ status: string; evaluated_count: number; summary: any }> {
    const res = await apiClient.post<{ status: string; evaluated_count: number; summary: any }>(
      `/examinations/${examId}/evaluate/`
    );
    return res.data;
  },

  /**
   * Download scorecard CSV
   */
  async downloadScorecardCsv(resultId: string): Promise<Blob> {
    const res = await apiClient.get(`/analytics/results/${resultId}/scorecard/download/`, {
      responseType: 'blob',
    });
    return res.data;
  },
};

export default analyticsApi;
