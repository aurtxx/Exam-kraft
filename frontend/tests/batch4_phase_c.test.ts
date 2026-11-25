import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

import {
  reconcileResponses,
  markSyncedIfUnchanged,
  hasPendingResponses,
  flushPendingQueue,
  createResponseFlushRunner,
  submitAttemptWithFlush,
} from '../src/utils/offlineResponseQueue';
import {
  normalizeRemainingSeconds,
  createClockAnchor,
  computeClockRemaining,
  shouldAutoSubmitOnTick,
} from '../src/utils/examClock';
import { getFocusableElements, trapFocusKeyDown } from '../src/hooks/useFocusTrap';
import FinishConfirmationModal from '../src/components/FinishConfirmationModal';
import type { CBTResponseRecord, CBTSection } from '../src/types';

function makeRecord(
  questionId: string,
  selectedOptions: string[],
  status: CBTResponseRecord['status'] = 'ANSWERED'
): CBTResponseRecord {
  return {
    question_id: questionId,
    selected_options: selectedOptions,
    numerical_value: null,
    status,
    time_spent_seconds: 12,
    saved_at: '2026-11-25T10:00:00.000Z',
  };
}

// ============================================================================
// 1. CX-008: Offline Response Queue, Concurrency, Flush & Submission Safety
// ============================================================================

test('CX-008: reconcileResponses overrides stale server responses with local pending cache', () => {
  const server = {
    q1: makeRecord('q1', ['A']),
    q2: makeRecord('q2', ['B']),
  };
  const pending = {
    q2: makeRecord('q2', ['C']),
    q3: makeRecord('q3', ['D']),
  };

  const merged = reconcileResponses(server, pending);
  assert.deepEqual(merged.q1.selected_options, ['A']);
  assert.deepEqual(merged.q2.selected_options, ['C']);
  assert.deepEqual(merged.q3.selected_options, ['D']);
});

test('CX-008: concurrent edit during in-flight save is NOT dropped and NOT clobbered', async () => {
  const pending: Record<string, CBTResponseRecord> = {};
  const persistedSnapshots: Array<Record<string, CBTResponseRecord>> = [];
  const persistCache = (map: Record<string, CBTResponseRecord>) => {
    persistedSnapshots.push(JSON.parse(JSON.stringify(map)));
  };

  let resolveFirstSave!: () => void;
  let saveCalls = 0;
  const savedPayloads: CBTResponseRecord[] = [];

  const runner = createResponseFlushRunner(() => ({
    attemptId: 'att-1',
    pending,
    persistCache,
    saveResponse: (_attemptId, record) => {
      saveCalls += 1;
      savedPayloads.push(record);
      if (saveCalls === 1) {
        return new Promise((resolve) => {
          resolveFirstSave = () => resolve({ status: 'SUCCESS', remaining_seconds: 1800 });
        });
      }
      return Promise.resolve({ status: 'SUCCESS', remaining_seconds: 1799 });
    },
  }));

  const v1 = makeRecord('q1', ['A']);
  pending.q1 = v1;
  persistCache(pending);
  const firstFlushPromise = runner.flush();

  // While v1 is still in flight, user changes q1 to v2 and answers q2
  const v2 = makeRecord('q1', ['B']);
  pending.q1 = v2;
  pending.q2 = makeRecord('q2', ['C']);
  persistCache(pending);

  // Trigger another flush while first is active (must coalesce, never drop)
  const secondFlushPromise = runner.flush();

  // Check identity-safe ack directly as well
  assert.equal(markSyncedIfUnchanged({ q1: v2 }, 'q1', v1), false);
  assert.equal(markSyncedIfUnchanged({ q1: v1 }, 'q1', v1), true);

  resolveFirstSave();
  const [res1, res2] = await Promise.all([firstFlushPromise, secondFlushPromise]);

  assert.equal(res1.status, 'saved');
  assert.equal(res2.status, 'saved');
  assert.equal(hasPendingResponses(pending), false);
  assert.equal(savedPayloads.some((r) => r === v2), true);
  assert.equal(savedPayloads.some((r) => r.question_id === 'q2'), true);
});

test('CX-008: MANUAL_SUBMIT flushes pending before submitExam; on flush error does NOT submit or clear cache', async () => {
  const pending: Record<string, CBTResponseRecord> = {
    q1: makeRecord('q1', ['A']),
  };
  let submitCalled = false;
  let cacheCleared = false;

  await assert.rejects(
    () =>
      submitAttemptWithFlush({
        attemptId: 'att-1',
        reason: 'MANUAL_SUBMIT',
        pending,
        saveResponse: async () => {
          throw new Error('Network offline');
        },
        submitExam: async () => {
          submitCalled = true;
          return {
            status: 'SUCCESS',
            attempt_id: 'att-1',
            submission_status: 'SUBMITTED',
            submitted_at: '2026-11-25T10:05:00Z',
          };
        },
        persistCache: () => {},
        clearCache: () => {
          cacheCleared = true;
        },
      }),
    /Network offline/
  );

  assert.equal(submitCalled, false);
  assert.equal(cacheCleared, false);
  assert.equal(hasPendingResponses(pending), true);
});

test('CX-008: AUTO_TIMER_EXPIRY flushes pending responses before submitExam within grace period', async () => {
  const pending: Record<string, CBTResponseRecord> = {
    q1: makeRecord('q1', ['A']),
    q2: makeRecord('q2', ['D']),
  };
  const callOrder: string[] = [];
  let cacheCleared = false;

  const result = await submitAttemptWithFlush({
    attemptId: 'att-2',
    reason: 'AUTO_TIMER_EXPIRY',
    pending,
    saveResponse: async (_attemptId, record) => {
      callOrder.push(`save:${record.question_id}`);
      return { status: 'SUCCESS', remaining_seconds: 0 };
    },
    submitExam: async (_attemptId, reason) => {
      callOrder.push(`submit:${reason}`);
      return {
        status: 'SUCCESS',
        attempt_id: 'att-2',
        submission_status: 'AUTO_SUBMITTED',
        submitted_at: '2026-11-25T10:05:00Z',
      };
    },
    persistCache: () => {},
    clearCache: () => {
      cacheCleared = true;
    },
  });

  assert.equal(result.submission_status, 'AUTO_SUBMITTED');
  assert.deepEqual(callOrder, ['save:q1', 'save:q2', 'submit:AUTO_TIMER_EXPIRY']);
  assert.equal(hasPendingResponses(pending), false);
  assert.equal(cacheCleared, true);
});

test('CX-008: AUTO_TIMER_EXPIRY tolerates HTTP 403 DEADLINE_EXPIRED/ATTEMPT_LOCKED on saveResponse and still submits', async () => {
  const pending: Record<string, CBTResponseRecord> = {
    q1: makeRecord('q1', ['A']),
    q2: makeRecord('q2', ['B']),
  };
  let submitCalls = 0;
  let cacheCleared = false;

  const result = await submitAttemptWithFlush({
    attemptId: 'att-3',
    reason: 'AUTO_TIMER_EXPIRY',
    pending,
    saveResponse: async () => {
      const err = new Error('Forbidden') as Error & {
        response?: { status: number; data: { code: string } };
      };
      err.response = { status: 403, data: { code: 'DEADLINE_EXPIRED' } };
      throw err;
    },
    submitExam: async (_attemptId, reason) => {
      submitCalls += 1;
      assert.equal(reason, 'AUTO_TIMER_EXPIRY');
      return {
        status: 'SUCCESS',
        attempt_id: 'att-3',
        submission_status: 'AUTO_SUBMITTED',
        submitted_at: '2026-11-25T10:06:00Z',
      };
    },
    persistCache: () => {},
    clearCache: () => {
      cacheCleared = true;
    },
  });

  assert.equal(submitCalls, 1);
  assert.equal(result.status, 'SUCCESS');
  assert.equal(cacheCleared, true);
});

test('CX-008: AUTO_TIMER_EXPIRY does NOT clear localStorage if submitExam fails offline', async () => {
  const pending: Record<string, CBTResponseRecord> = {
    q1: makeRecord('q1', ['A']),
  };
  let cacheCleared = false;

  await assert.rejects(
    () =>
      submitAttemptWithFlush({
        attemptId: 'att-4',
        reason: 'AUTO_TIMER_EXPIRY',
        pending,
        saveResponse: async () => {
          const err = new Error('Forbidden') as Error & {
            response?: { status: number; data: { code: string } };
          };
          err.response = { status: 403, data: { code: 'ATTEMPT_LOCKED' } };
          throw err;
        },
        submitExam: async () => {
          throw new Error('Offline during submit');
        },
        persistCache: () => {},
        clearCache: () => {
          cacheCleared = true;
        },
      }),
    /Offline during submit/
  );

  assert.equal(cacheCleared, false);
  assert.equal(hasPendingResponses(pending), true);
});

test('CX-008: flushPendingQueue reports saved only when pending is empty, otherwise error', async () => {
  const partialPending: Record<string, CBTResponseRecord> = {
    q1: makeRecord('q1', ['A']),
    q2: makeRecord('q2', ['B']),
  };

  const partialRes = await flushPendingQueue({
    attemptId: 'att-5',
    pending: partialPending,
    persistCache: () => {},
    saveResponse: async (_attemptId, record) => {
      if (record.question_id === 'q2') {
        throw new Error('Temporary failure');
      }
      return { status: 'SUCCESS', remaining_seconds: 500 };
    },
  });

  assert.equal(partialRes.status, 'error');
  assert.equal(partialRes.remainingCount, 1);
  assert.equal(hasPendingResponses(partialPending), true);

  const retryRes = await flushPendingQueue({
    attemptId: 'att-5',
    pending: partialPending,
    persistCache: () => {},
    saveResponse: async () => ({ status: 'SUCCESS', remaining_seconds: 495 }),
  });

  assert.equal(retryRes.status, 'saved');
  assert.equal(retryRes.remainingCount, 0);
  assert.equal(hasPendingResponses(partialPending), false);
});

// ============================================================================
// 2. CX-023 / AGY-008: Exam Clock Normalization, Drift Catch-Up & Auto-Submit
// ============================================================================

test('CX-023: normalizeRemainingSeconds preserves 0 (never 3600) and clamps negative/undefined/NaN', () => {
  assert.equal(normalizeRemainingSeconds(0), 0);
  assert.equal(normalizeRemainingSeconds(-15), 0);
  assert.equal(normalizeRemainingSeconds(undefined), 0);
  assert.equal(normalizeRemainingSeconds(null), 0);
  assert.equal(normalizeRemainingSeconds(Number.NaN), 0);
  assert.equal(normalizeRemainingSeconds(42), 42);
});

test('AGY-008: computeClockRemaining catches up accurately after 65s throttling or OS sleep', () => {
  const t0 = 1_700_000_000_000;
  const anchor = createClockAnchor(600, t0);
  assert.equal(computeClockRemaining(anchor, t0 + 65_000), 535);
  assert.equal(computeClockRemaining(anchor, t0 + 700_000), 0);
});

test('AGY-008: heartbeat re-anchor resets drift cleanly including 0', () => {
  const t1 = 1_700_000_000_000;
  const anchor1 = createClockAnchor(500, t1);
  assert.equal(computeClockRemaining(anchor1, t1 + 20_000), 480);

  const t2 = t1 + 20_000;
  const reAnchoredZero = createClockAnchor(0, t2);
  assert.equal(computeClockRemaining(reAnchoredZero, t2), 0);

  const reAnchoredServer = createClockAnchor(475, t2);
  assert.equal(computeClockRemaining(reAnchoredServer, t2 + 5_000), 470);
});

test('CX-023 / AGY-008: shouldAutoSubmitOnTick triggers at <= 0 or isTerminated', () => {
  assert.equal(shouldAutoSubmitOnTick(0), true);
  assert.equal(shouldAutoSubmitOnTick(-1), true);
  assert.equal(shouldAutoSubmitOnTick(10, true), true);
  assert.equal(shouldAutoSubmitOnTick(10, false), false);
});

// ============================================================================
// 3. CX-024: FinishConfirmationModal Focus Trap & Accessible Dialog Semantics
// ============================================================================

interface MockElement {
  tabIndex: number;
  disabled: boolean;
  ariaHidden: string | null;
  focused: boolean;
  focus: () => void;
  hasAttribute: (name: string) => boolean;
  getAttribute: (name: string) => string | null;
  contains?: (el: unknown) => boolean;
  querySelectorAll?: (selector: string) => MockElement[];
}

function createMockButton(disabled = false, ariaHidden: string | null = null): MockElement {
  const el: MockElement = {
    tabIndex: 0,
    disabled,
    ariaHidden,
    focused: false,
    focus() {
      el.focused = true;
    },
    hasAttribute(name: string) {
      return name === 'disabled' ? el.disabled : false;
    },
    getAttribute(name: string) {
      if (name === 'aria-hidden') return el.ariaHidden;
      return null;
    },
  };
  return el;
}

function createMockContainer(children: MockElement[]): MockElement {
  const container: MockElement = {
    tabIndex: -1,
    disabled: false,
    ariaHidden: null,
    focused: false,
    focus() {
      container.focused = true;
    },
    hasAttribute() {
      return false;
    },
    getAttribute() {
      return null;
    },
    contains(target: unknown) {
      return target === container || children.includes(target as MockElement);
    },
    querySelectorAll() {
      return children.filter((c) => !c.disabled);
    },
  };
  return container;
}

test('CX-024: getFocusableElements & trapFocusKeyDown wrap Tab/Shift+Tab, handle 0 focusables, and gate Escape', () => {
  const btnFirst = createMockButton(false);
  const btnDisabled = createMockButton(true);
  const btnLast = createMockButton(false);
  const outsideBtn = createMockButton(false);
  const container = createMockContainer([btnFirst, btnDisabled, btnLast]);

  const focusables = getFocusableElements(container as unknown as HTMLElement);
  assert.deepEqual(focusables, [btnFirst, btnLast]);

  // Tab on last -> wraps to first
  let prevented = false;
  trapFocusKeyDown(
    { key: 'Tab', shiftKey: false, preventDefault: () => { prevented = true; } },
    container as unknown as HTMLElement,
    { activeElement: btnLast as unknown as Element }
  );
  assert.equal(prevented, true);
  assert.equal(btnFirst.focused, true);

  // Shift+Tab on first -> wraps to last
  prevented = false;
  btnLast.focused = false;
  trapFocusKeyDown(
    { key: 'Tab', shiftKey: true, preventDefault: () => { prevented = true; } },
    container as unknown as HTMLElement,
    { activeElement: btnFirst as unknown as Element }
  );
  assert.equal(prevented, true);
  assert.equal(btnLast.focused, true);

  // Shift+Tab when focus is outside container -> wraps to last
  btnLast.focused = false;
  trapFocusKeyDown(
    { key: 'Tab', shiftKey: true, preventDefault: () => {} },
    container as unknown as HTMLElement,
    { activeElement: outsideBtn as unknown as Element }
  );
  assert.equal(btnLast.focused, true);

  // 0 enabled focusables -> falls back to container.focus()
  const emptyContainer = createMockContainer([createMockButton(true)]);
  prevented = false;
  trapFocusKeyDown(
    { key: 'Tab', shiftKey: false, preventDefault: () => { prevented = true; } },
    emptyContainer as unknown as HTMLElement,
    { activeElement: null }
  );
  assert.equal(prevented, true);
  assert.equal(emptyContainer.focused, true);

  // Escape calls onEscape when allowEscape !== false
  let escapeCalls = 0;
  trapFocusKeyDown(
    { key: 'Escape', shiftKey: false, preventDefault: () => {} },
    container as unknown as HTMLElement,
    { onEscape: () => { escapeCalls += 1; }, allowEscape: true }
  );
  assert.equal(escapeCalls, 1);

  // Escape is suppressed when allowEscape === false (isSubmitting === true)
  trapFocusKeyDown(
    { key: 'Escape', shiftKey: false, preventDefault: () => {} },
    container as unknown as HTMLElement,
    { onEscape: () => { escapeCalls += 1; }, allowEscape: false }
  );
  assert.equal(escapeCalls, 1);
});

test('CX-024: FinishConfirmationModal renders accessible dialog attributes and matching title/desc IDs', () => {
  const sampleSections: CBTSection[] = [
    {
      id: 'sec-1',
      name: 'Physics',
      title: 'Physics',
      order: 1,
      total_questions: 1,
      question_ids: ['q1'],
      questions: [
        {
          id: 'q1',
          question_number: 1,
          question_type: 'MCQ_SINGLE',
          content_text: 'Sample question',
          positive_marks: 4,
          negative_marks: 1,
          partial_marks: 0,
        },
      ],
    },
  ];

  const html = renderToStaticMarkup(
    React.createElement(FinishConfirmationModal, {
      isOpen: true,
      sections: sampleSections,
      responses: {},
      visitedQuestionIds: new Set(['q1']),
      onClose: () => {},
      onConfirmSubmit: () => {},
      isSubmitting: false,
    })
  );

  assert.match(html, /role="dialog"/);
  assert.match(html, /aria-modal="true"/);

  const labelledByMatch = html.match(/aria-labelledby="([^"]+)"/);
  assert.ok(labelledByMatch, 'Expected aria-labelledby attribute on dialog');
  const titleId = labelledByMatch[1];
  assert.match(html, new RegExp(`<h3[^>]*id="${titleId.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}"[^>]*>`));

  const describedByMatch = html.match(/aria-describedby="([^"]+)"/);
  assert.ok(describedByMatch, 'Expected aria-describedby attribute on dialog');
  const descId = describedByMatch[1];
  assert.match(html, new RegExp(`<p[^>]*id="${descId.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}"[^>]*>`));

  assert.match(html, /aria-label="Close submission confirmation"/);
});

// ============================================================================
// 4. CX-025: ExamCBTPage UI Copy Hardening
// ============================================================================

test('CX-025: ExamCBTPage.tsx does not claim "AI proctoring"', () => {
  const cbtPath = path.resolve(process.cwd(), 'src/pages/student/ExamCBTPage.tsx');
  const source = fs.readFileSync(cbtPath, 'utf8');
  assert.equal(/ai proctoring/i.test(source), false, 'ExamCBTPage.tsx must not contain "AI proctoring"');
});
