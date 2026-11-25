import React, { useId, useRef } from 'react';
import { AlertTriangle, CheckCircle, X } from 'lucide-react';
import { CBTSection, CBTResponseRecord, ResponseStatusType } from '../types';
import { useFocusTrap } from '../hooks/useFocusTrap';

interface SectionSummary {
  sectionTitle: string;
  total: number;
  answered: number;
  notAnswered: number;
  marked: number;
  answeredMarked: number;
  notVisited: number;
}

interface FinishConfirmationModalProps {
  isOpen: boolean;
  sections: CBTSection[];
  responses: Record<string, CBTResponseRecord>;
  visitedQuestionIds: Set<string | number>;
  onClose: () => void;
  onConfirmSubmit: () => void;
  isSubmitting?: boolean;
}

export const FinishConfirmationModal: React.FC<FinishConfirmationModalProps> = ({
  isOpen,
  sections,
  responses,
  visitedQuestionIds,
  onClose,
  onConfirmSubmit,
  isSubmitting = false,
}) => {
  const dialogRef = useRef<HTMLDivElement>(null);
  const cancelButtonRef = useRef<HTMLButtonElement>(null);
  const titleId = useId();
  const descId = useId();

  useFocusTrap(dialogRef, isOpen, {
    onEscape: onClose,
    allowEscape: !isSubmitting,
    initialFocusRef: cancelButtonRef,
  });

  if (!isOpen) return null;

  const sectionSummaries: SectionSummary[] = sections.map((sec) => {
    let answered = 0;
    let notAnswered = 0;
    let marked = 0;
    let answeredMarked = 0;
    let notVisited = 0;

    sec.questions.forEach((q) => {
      const qidKey = String(q.id);
      const resp = responses[qidKey];
      let st: ResponseStatusType = 'NOT_VISITED';

      if (resp && resp.status) {
        st = resp.status;
      } else if (visitedQuestionIds.has(q.id) || visitedQuestionIds.has(String(q.id))) {
        st = 'UNANSWERED';
      }

      if (st === 'ANSWERED') answered++;
      else if (st === 'MARKED_FOR_REVIEW') marked++;
      else if (st === 'ANSWERED_AND_MARKED') answeredMarked++;
      else if (st === 'UNANSWERED') notAnswered++;
      else notVisited++;
    });

    return {
      sectionTitle: sec.name || sec.title,
      total: sec.questions.length,
      answered,
      notAnswered,
      marked,
      answeredMarked,
      notVisited,
    };
  });

  const totals = sectionSummaries.reduce(
    (acc, curr) => ({
      total: acc.total + curr.total,
      answered: acc.answered + curr.answered,
      notAnswered: acc.notAnswered + curr.notAnswered,
      marked: acc.marked + curr.marked,
      answeredMarked: acc.answeredMarked + curr.answeredMarked,
      notVisited: acc.notVisited + curr.notVisited,
    }),
    { total: 0, answered: 0, notAnswered: 0, marked: 0, answeredMarked: 0, notVisited: 0 }
  );

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs animate-in fade-in duration-200">
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={descId}
        tabIndex={-1}
        className="bg-white rounded-2xl max-w-2xl w-full shadow-2xl border border-slate-200 overflow-hidden flex flex-col focus:outline-none"
      >
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between bg-slate-50">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-full bg-amber-100 flex items-center justify-center text-amber-600">
              <AlertTriangle className="w-5 h-5" />
            </div>
            <div>
              <h3 id={titleId} className="text-base font-bold text-slate-800">Submit Examination</h3>
              <p id={descId} className="text-xs text-slate-500">Review your attempt summary before final submission</p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={isSubmitting}
            aria-label="Close submission confirmation"
            className="text-slate-400 hover:text-slate-600 p-1.5 rounded-lg hover:bg-slate-100 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 overflow-y-auto max-h-[70vh]">
          <div className="border border-slate-200 rounded-xl overflow-hidden mb-5">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="bg-slate-100 border-b border-slate-200 text-slate-700 font-bold">
                  <th className="py-2.5 px-3">Section</th>
                  <th className="py-2.5 px-2 text-center">Total</th>
                  <th className="py-2.5 px-2 text-center text-[#22C969]">Answered</th>
                  <th className="py-2.5 px-2 text-center text-[#FF614D]">Not Ans</th>
                  <th className="py-2.5 px-2 text-center text-[#9967ff]">Marked</th>
                  <th className="py-2.5 px-2 text-center text-purple-700">Ans & Marked</th>
                  <th className="py-2.5 px-2 text-center text-slate-500">Not Visited</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200 font-medium">
                {sectionSummaries.map((s, idx) => (
                  <tr key={idx} className="hover:bg-slate-50/80">
                    <td className="py-2.5 px-3 font-semibold text-slate-800">{s.sectionTitle}</td>
                    <td className="py-2.5 px-2 text-center font-bold">{s.total}</td>
                    <td className="py-2.5 px-2 text-center font-semibold text-emerald-600 bg-emerald-50/30">
                      {s.answered}
                    </td>
                    <td className="py-2.5 px-2 text-center font-semibold text-rose-600 bg-rose-50/30">
                      {s.notAnswered}
                    </td>
                    <td className="py-2.5 px-2 text-center font-semibold text-purple-600">
                      {s.marked}
                    </td>
                    <td className="py-2.5 px-2 text-center font-semibold text-purple-700">
                      {s.answeredMarked}
                    </td>
                    <td className="py-2.5 px-2 text-center text-slate-500">
                      {s.notVisited}
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="bg-slate-100 font-bold border-t-2 border-slate-300 text-slate-900">
                  <td className="py-3 px-3">Overall Total</td>
                  <td className="py-3 px-2 text-center">{totals.total}</td>
                  <td className="py-3 px-2 text-center text-emerald-700">{totals.answered}</td>
                  <td className="py-3 px-2 text-center text-rose-700">{totals.notAnswered}</td>
                  <td className="py-3 px-2 text-center text-purple-700">{totals.marked}</td>
                  <td className="py-3 px-2 text-center text-purple-900">{totals.answeredMarked}</td>
                  <td className="py-3 px-2 text-center text-slate-600">{totals.notVisited}</td>
                </tr>
              </tfoot>
            </table>
          </div>

          <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 flex gap-3 text-amber-900 text-xs leading-relaxed">
            <AlertTriangle className="w-5 h-5 flex-shrink-0 text-amber-600 mt-0.5" />
            <div>
              <span className="font-bold">Are you sure you want to submit your examination?</span>
              <p className="mt-1 text-amber-800">
                Once submitted, you will not be able to change your answers or re-enter this test. Your answers will be submitted for scoring.
              </p>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 bg-slate-50 border-t border-slate-200 flex items-center justify-end gap-3">
          <button
            ref={cancelButtonRef}
            type="button"
            disabled={isSubmitting}
            onClick={onClose}
            className="px-4 py-2 rounded-lg border border-slate-300 text-slate-700 text-xs font-semibold hover:bg-slate-100 transition-colors disabled:opacity-50"
          >
            Return to Exam
          </button>
          <button
            type="button"
            disabled={isSubmitting}
            onClick={onConfirmSubmit}
            className="px-5 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold transition-colors shadow-sm flex items-center gap-1.5 disabled:opacity-50"
          >
            {isSubmitting ? (
              <>
                <span className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin"></span>
                Submitting...
              </>
            ) : (
              <>
                <CheckCircle className="w-4 h-4" />
                Confirm Final Submission
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};

export default FinishConfirmationModal;
