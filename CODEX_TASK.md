# CODEX TASK — Exam-Kraft Frontend Bug Fixes
CWD: /Users/aurtx/teamwork_projects/ezexam_reconstruction
Branch: fix/audit-batch-2

## WHAT'S ALREADY DONE (don't redo):
- BUG-01: ExamCBTPage.tsx question types fixed (ONE_WORD, SUBJECTIVE, TRUE_FALSE, SINGLE_DIGIT)
- BUG-02 PARTIAL: VirtualNumpad.tsx imports updated, need body fix

## YOUR TASKS IN ORDER:

### TASK 1 — BUG-02: VirtualNumpad keyboard input (file: frontend/src/components/VirtualNumpad.tsx)
Replace the display `<div>` (the one that shows value or "Enter value...") with a real `<input type="text">`:
- Add `inputRef = useRef<HTMLInputElement>(null)` and `useEffect(() => inputRef.current?.focus(), [])`
- Replace display div with: `<input ref={inputRef} type="text" inputMode="decimal" value={value} readOnly={disabled} onKeyDown={handleKeyDown} onChange={() => {}} aria-label="Numerical answer" className="w-full bg-white border-2 border-primary-500 rounded-lg px-3 py-2 text-right text-xl font-mono font-bold text-slate-800 min-h-[48px] focus:outline-none focus:ring-2 focus:ring-primary-500/30" placeholder="Enter value..." />`
- Add handleKeyDown function that: accepts 0-9, '.', '-', Backspace, calls onChange accordingly; for singleDigit prop only accept 0-9 single char
- singleDigit prop: when true, numpad only shows 0-9 (no . or -), and clears before setting new digit

### TASK 2 — BUG-03: KaTeX (file: frontend/src/components/MathRenderer.tsx)
1. Run: `cd frontend && npm install katex @types/katex --save`
2. Replace entire MathRenderer.tsx with KaTeX implementation:
```tsx
import { createElement } from 'react';
import katex from 'katex';
import 'katex/dist/katex.min.css';

interface MathRendererProps { content: string; className?: string; }

export function MathRenderer({ content, className = '' }: MathRendererProps) {
  if (!content) return null;
  const parts = content.split(/(\$\$[\s\S]*?\$\$|\$[^$\n]+?\$)/g);
  return createElement('div', { className: `whitespace-pre-wrap text-slate-800 leading-relaxed ${className}` },
    parts.map((part, i) => {
      if (part.startsWith('$$')) {
        try { return createElement('span', { key: i, dangerouslySetInnerHTML: { __html: katex.renderToString(part.slice(2,-2), { displayMode: true, throwOnError: false }) } }); }
        catch { return createElement('span', { key: i }, part); }
      }
      if (part.startsWith('$')) {
        try { return createElement('span', { key: i, dangerouslySetInnerHTML: { __html: katex.renderToString(part.slice(1,-1), { displayMode: false, throwOnError: false }) } }); }
        catch { return createElement('span', { key: i }, part); }
      }
      return createElement('span', { key: i }, part);
    })
  );
}
export default MathRenderer;
```

### TASK 3 — BUG-04: Report route fix
File: frontend/src/pages/student/ExamFinishPage.tsx
- Find where it navigates after submission — it should navigate to `/student/attempts/${attemptId}/report` NOT `/student/exam/${examId}/report`
- Use `submitResult.attempt_id` for the route param

File: frontend/src/App.tsx  
- Route `/student/attempts/:id/report` already exists (line 39) — confirm it's there, no change needed

### TASK 4 — BUG-05: ExaminationsPage button label cleanup (frontend/src/pages/staff/ExaminationsPage.tsx)
- Find any button text containing `(#` and remove the `(#...)` fragment from the label text only

### TASK 5 — BUG-07: Rebrand EZExam → Exam-Kraft
- frontend/src/pages/Login.tsx: change "EZ" badge text → "EK", title "EZExam Portal" → "Exam-Kraft Portal"
- frontend/src/pages/student/ExamCBTPage.tsx line ~451: change "EZ" badge → "EK"  
- frontend/index.html: change `<title>EZExam Platform</title>` → `<title>Exam-Kraft</title>`

### TASK 6 — Run tests & build
```bash
cd /Users/aurtx/teamwork_projects/ezexam_reconstruction/backend
.venv/bin/python manage.py test apps --verbosity=1
.venv/bin/pytest tests/ -v
cd ../frontend && npm run build
```
All must pass. Fix any TypeScript errors.

### TASK 7 — Commit all fixes
```bash
cd /Users/aurtx/teamwork_projects/ezexam_reconstruction
git add frontend/
git commit -m "fix(batch-4): VirtualNumpad keyboard, KaTeX math, report routing, branding EZExam→Exam-Kraft"
```

## CONSTRAINTS
- Never push to git remote
- Never touch audit_codex/ or audit_agy/
- One commit total for all 5 bug fixes above
- Backend servers stay running (don't kill tasks 798/800)
