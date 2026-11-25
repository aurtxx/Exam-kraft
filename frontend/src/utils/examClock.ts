export interface ClockAnchor {
  seconds: number;
  receivedAt: number;
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
  nowMs: number = Date.now()
): ClockAnchor {
  return {
    seconds: normalizeRemainingSeconds(remainingSeconds),
    receivedAt: Number.isFinite(nowMs) ? nowMs : Date.now(),
  };
}

export function computeClockRemaining(
  anchor: ClockAnchor,
  nowMs: number = Date.now()
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
