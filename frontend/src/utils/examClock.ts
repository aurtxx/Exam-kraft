export interface ClockAnchor {
  seconds: number;
  receivedAt: number;
}

/**
 * Returns a monotonic millisecond timestamp using performance.now() so OS
 * wall-clock changes (NTP jumps, manual clock tampering, DST) cannot distort
 * elapsed exam countdown intervals.
 */
export function getMonotonicNowMs(): number {
  if (typeof performance !== 'undefined' && typeof performance.now === 'function') {
    return performance.now();
  }
  return Date.now();
}

export function normalizeRemainingSeconds(raw: unknown): number {
  let num: number;
  if (typeof raw === 'number') {
    num = raw;
  } else if (typeof raw === 'string' && raw.trim() !== '') {
    num = Number(raw);
  } else {
    return 0;
  }

  if (!Number.isFinite(num) || num <= 0) {
    return 0;
  }

  return Math.floor(num);
}

export function createClockAnchor(
  remainingSeconds: unknown,
  nowMs: number = getMonotonicNowMs()
): ClockAnchor {
  return {
    seconds: normalizeRemainingSeconds(remainingSeconds),
    receivedAt: Number.isFinite(nowMs) ? nowMs : getMonotonicNowMs(),
  };
}

export function computeClockRemaining(
  anchor: ClockAnchor,
  nowMs: number = getMonotonicNowMs()
): number {
  const elapsedMs = Math.max(0, nowMs - anchor.receivedAt);
  const elapsedSeconds = Math.floor(elapsedMs / 1000);
  return Math.max(0, normalizeRemainingSeconds(anchor.seconds) - elapsedSeconds);
}

export function shouldAutoSubmitOnTick(
  remainingSeconds: number,
  isTerminated?: boolean
): boolean {
  return remainingSeconds <= 0 || Boolean(isTerminated);
}
