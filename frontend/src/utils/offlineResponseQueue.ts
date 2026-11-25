import type { CBTResponseRecord } from '../types';
import type { SaveResponseResult, SubmitResult } from '../services/studentExamApi';

export type FlushMode = 'SYNC' | 'MANUAL_SUBMIT' | 'AUTO_TIMER_EXPIRY';

export interface FlushPendingQueueOptions {
  attemptId: string;
  pending: Record<string, CBTResponseRecord>;
  saveResponse: (
    attemptId: string,
    record: CBTResponseRecord
  ) => Promise<SaveResponseResult | unknown>;
  persistCache: (pending: Record<string, CBTResponseRecord>) => void;
  mode?: FlushMode;
  onSaveResult?: (result: SaveResponseResult) => void;
}

export interface FlushPendingQueueResult {
  status: 'saved' | 'error';
  remainingCount: number;
  skippedExpired: boolean;
  lastError?: unknown;
}

export interface SubmitAttemptWithFlushOptions {
  attemptId: string;
  reason: 'MANUAL_SUBMIT' | 'AUTO_TIMER_EXPIRY';
  pending: Record<string, CBTResponseRecord>;
  waitForInFlight?: () => Promise<unknown>;
  saveResponse: (
    attemptId: string,
    record: CBTResponseRecord
  ) => Promise<SaveResponseResult | unknown>;
  submitExam: (
    attemptId: string,
    reason: 'MANUAL_SUBMIT' | 'AUTO_TIMER_EXPIRY'
  ) => Promise<SubmitResult>;
  persistCache: (pending: Record<string, CBTResponseRecord>) => void;
  clearCache: () => void;
  onSaveResult?: (result: SaveResponseResult) => void;
}

export function reconcileResponses(
  serverResponses: Record<string, CBTResponseRecord> | null | undefined,
  pendingResponses: Record<string, CBTResponseRecord> | null | undefined
): Record<string, CBTResponseRecord> {
  return {
    ...(serverResponses || {}),
    ...(pendingResponses || {}),
  };
}

export function markSyncedIfUnchanged(
  pending: Record<string, CBTResponseRecord>,
  qidKey: string,
  record: CBTResponseRecord
): boolean {
  if (pending[qidKey] === record) {
    delete pending[qidKey];
    return true;
  }
  return false;
}

export function hasPendingResponses(
  pending: Record<string, CBTResponseRecord> | null | undefined
): boolean {
  if (!pending) return false;
  return Object.keys(pending).length > 0;
}

export function isExpiredOrLockedError(err: unknown): boolean {
  const e = err as {
    status?: number;
    response?: { status?: number; data?: { code?: string } };
  } | null;
  const status = e?.response?.status ?? e?.status;
  if (status !== 403) return false;
  const code = e?.response?.data?.code;
  return !code || code === 'DEADLINE_EXPIRED' || code === 'ATTEMPT_LOCKED';
}

export async function flushPendingQueue(
  options: FlushPendingQueueOptions
): Promise<FlushPendingQueueResult> {
  const {
    attemptId,
    pending,
    saveResponse,
    persistCache,
    mode = 'SYNC',
    onSaveResult,
  } = options;

  const attemptedFailed = new Map<string, CBTResponseRecord>();
  let skippedExpired = false;
  let lastError: unknown = undefined;

  while (true) {
    const entries = Object.entries(pending).filter(
      ([qid, record]) => attemptedFailed.get(qid) !== record
    );
    if (entries.length === 0) {
      break;
    }

    for (const [qid, record] of entries) {
      try {
        const res = await saveResponse(attemptId, record);
        if (
          onSaveResult &&
          res &&
          typeof res === 'object' &&
          'remaining_seconds' in res
        ) {
          onSaveResult(res as SaveResponseResult);
        }
        if (markSyncedIfUnchanged(pending, qid, record)) {
          persistCache(pending);
        }
      } catch (err) {
        if (mode === 'MANUAL_SUBMIT') {
          throw err;
        }
        if (mode === 'AUTO_TIMER_EXPIRY') {
          if (isExpiredOrLockedError(err)) {
            skippedExpired = true;
            const remainingCount = Object.keys(pending).length;
            return {
              status: remainingCount === 0 ? 'saved' : 'error',
              remainingCount,
              skippedExpired,
              lastError: err,
            };
          }
          throw err;
        }
        attemptedFailed.set(qid, record);
        lastError = err;
      }
    }
  }

  const remainingCount = Object.keys(pending).length;
  return {
    status: remainingCount === 0 ? 'saved' : 'error',
    remainingCount,
    skippedExpired,
    lastError,
  };
}

export function createResponseFlushRunner(
  getOptions: () => Omit<FlushPendingQueueOptions, 'mode'>
) {
  let activePromise: Promise<FlushPendingQueueResult> | null = null;
  let rerunRequested = false;

  const runLoop = async (): Promise<FlushPendingQueueResult> => {
    let lastResult: FlushPendingQueueResult = {
      status: 'saved',
      remainingCount: 0,
      skippedExpired: false,
    };
    do {
      rerunRequested = false;
      const opts = getOptions();
      lastResult = await flushPendingQueue({ ...opts, mode: 'SYNC' });
    } while (rerunRequested);
    return lastResult;
  };

  const flush = (): Promise<FlushPendingQueueResult> => {
    if (activePromise) {
      rerunRequested = true;
      return activePromise;
    }
    activePromise = runLoop().finally(() => {
      activePromise = null;
    });
    return activePromise;
  };

  const waitForIdle = async (): Promise<void> => {
    if (activePromise) {
      await activePromise.catch(() => {});
    }
  };

  return { flush, waitForIdle };
}

export async function submitAttemptWithFlush(
  options: SubmitAttemptWithFlushOptions
): Promise<SubmitResult> {
  const {
    attemptId,
    reason,
    pending,
    waitForInFlight,
    saveResponse,
    submitExam,
    persistCache,
    clearCache,
    onSaveResult,
  } = options;

  if (waitForInFlight) {
    await waitForInFlight();
  }

  await flushPendingQueue({
    attemptId,
    pending,
    saveResponse,
    persistCache,
    mode: reason,
    onSaveResult,
  });

  const result = await submitExam(attemptId, reason);
  clearCache();
  return result;
}
