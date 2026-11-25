import { useEffect, useRef } from 'react';
import type React from 'react';

const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

export function getFocusableElements(container: HTMLElement): HTMLElement[] {
  const nodes = Array.from(container.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR));
  return nodes.filter(
    (el) =>
      el.getAttribute('aria-hidden') !== 'true' &&
      !el.hasAttribute('disabled') &&
      el.tabIndex >= 0
  );
}

export interface TrapFocusKeyDownOptions {
  activeElement?: Element | null;
  onEscape?: () => void;
  allowEscape?: boolean;
}

export function trapFocusKeyDown(
  e: Pick<KeyboardEvent, 'key' | 'shiftKey' | 'preventDefault'>,
  container: HTMLElement,
  options?: TrapFocusKeyDownOptions
): void {
  if (e.key === 'Escape') {
    if (options?.allowEscape !== false && options?.onEscape) {
      e.preventDefault();
      options.onEscape();
    }
    return;
  }

  if (e.key !== 'Tab') {
    return;
  }

  const focusables = getFocusableElements(container);
  if (focusables.length === 0) {
    e.preventDefault();
    container.focus();
    return;
  }

  const first = focusables[0];
  const last = focusables[focusables.length - 1];
  const active =
    options?.activeElement !== undefined
      ? options.activeElement
      : typeof document !== 'undefined'
      ? document.activeElement
      : null;

  if (e.shiftKey) {
    if (active === first || active === container || !active || !container.contains(active)) {
      e.preventDefault();
      last.focus();
    }
  } else {
    if (active === last || !active || !container.contains(active)) {
      e.preventDefault();
      first.focus();
    }
  }
}

export interface UseFocusTrapOptions {
  onEscape?: () => void;
  allowEscape?: boolean;
  initialFocusRef?: React.RefObject<HTMLElement | null>;
}

export function useFocusTrap(
  containerRef: React.RefObject<HTMLElement | null>,
  isOpen: boolean,
  options?: UseFocusTrapOptions
): void {
  const onEscapeRef = useRef(options?.onEscape);
  const allowEscapeRef = useRef(options?.allowEscape);

  onEscapeRef.current = options?.onEscape;
  allowEscapeRef.current = options?.allowEscape;

  const initialFocusRef = options?.initialFocusRef;

  useEffect(() => {
    const container = containerRef.current;
    if (!isOpen || !container || typeof document === 'undefined') {
      return;
    }

    const previousFocus = document.activeElement as HTMLElement | null;
    const focusables = getFocusableElements(container);
    const initialTarget = initialFocusRef?.current ?? focusables[0] ?? container;

    if (initialTarget && typeof initialTarget.focus === 'function') {
      initialTarget.focus();
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      trapFocusKeyDown(event, container, {
        onEscape: onEscapeRef.current,
        allowEscape: allowEscapeRef.current,
      });
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      if (
        previousFocus &&
        previousFocus.isConnected &&
        typeof previousFocus.focus === 'function'
      ) {
        previousFocus.focus();
      }
    };
  }, [containerRef, isOpen, initialFocusRef]);
}

export default useFocusTrap;
