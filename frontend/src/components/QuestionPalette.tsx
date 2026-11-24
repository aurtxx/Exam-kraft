import React from 'react';
import { Check } from 'lucide-react';
import { CBTQuestion, CBTResponseRecord, ResponseStatusType } from '../types';

interface QuestionPaletteProps {
  questions: CBTQuestion[];
  currentQuestionIndex: number;
  responses: Record<string, CBTResponseRecord>;
  visitedQuestionIds: Set<string | number>;
  onSelectQuestion: (index: number) => void;
  candidateName?: string;
  candidateAvatar?: string;
  rollNumber?: string;
}

export const QuestionPalette: React.FC<QuestionPaletteProps> = ({
  questions,
  currentQuestionIndex,
  responses,
  visitedQuestionIds,
  onSelectQuestion,
  candidateName = 'Aryabhata Sharma',
  candidateAvatar,
  rollNumber = '2026001',
}) => {
  // Determine status for each question
  const getQuestionStatus = (q: CBTQuestion): ResponseStatusType => {
    const qidKey = String(q.id);
    const resp = responses[qidKey];
    if (resp && resp.status) {
      return resp.status;
    }
    if (visitedQuestionIds.has(q.id) || visitedQuestionIds.has(String(q.id))) {
      return 'UNANSWERED';
    }
    return 'NOT_VISITED';
  };

  // Compute live counts
  let countAnswered = 0;
  let countNotAnswered = 0;
  let countNotVisited = 0;
  let countMarked = 0;
  let countAnsweredMarked = 0;

  questions.forEach((q) => {
    const st = getQuestionStatus(q);
    if (st === 'ANSWERED') countAnswered++;
    else if (st === 'MARKED_FOR_REVIEW') countMarked++;
    else if (st === 'ANSWERED_AND_MARKED') countAnsweredMarked++;
    else if (st === 'UNANSWERED') countNotAnswered++;
    else countNotVisited++;
  });

  const legends = [
    { label: 'Answered', count: countAnswered, colorBg: 'bg-[#22C969]', text: 'text-white' },
    { label: 'Not Answered', count: countNotAnswered, colorBg: 'bg-[#FF614D]', text: 'text-white' },
    { label: 'Not Visited', count: countNotVisited, colorBg: 'bg-[#dcdcdc]', text: 'text-slate-700' },
    { label: 'Marked for Review', count: countMarked, colorBg: 'bg-[#9967ff]', text: 'text-white', isRound: true },
    {
      label: 'Ans & Marked (Evaluated)',
      count: countAnsweredMarked,
      colorBg: 'bg-[#9967ff]',
      text: 'text-white',
      hasBadge: true,
    },
  ];

  return (
    <div className="w-80 flex-shrink-0 bg-white border-l border-slate-200 flex flex-col h-full shadow-sm">
      {/* Candidate Profile Widget */}
      <div className="p-3.5 border-b border-slate-200 bg-slate-50 flex items-center gap-3">
        <div className="w-12 h-12 rounded-full overflow-hidden bg-primary-100 border border-primary-200 flex items-center justify-center flex-shrink-0 text-primary-700 font-bold text-base shadow-sm">
          {candidateAvatar ? (
            <img src={candidateAvatar} alt={candidateName} className="w-full h-full object-cover" />
          ) : (
            candidateName.charAt(0).toUpperCase()
          )}
        </div>
        <div className="overflow-hidden">
          <div className="text-sm font-bold text-slate-800 truncate">{candidateName}</div>
          <div className="text-xs text-slate-500 font-mono">Roll: {rollNumber}</div>
          <div className="text-[11px] text-emerald-600 font-medium flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
            Camera Active
          </div>
        </div>
      </div>

      {/* NTA Status Legend Counters */}
      <div className="p-3 border-b border-slate-200 bg-white grid grid-cols-2 gap-2 text-xs">
        {legends.map((lg) => (
          <div key={lg.label} className="flex items-center gap-1.5 py-0.5">
            <div
              className={`w-6 h-6 flex-shrink-0 flex items-center justify-center text-[11px] font-bold ${
                lg.isRound ? 'rounded-full' : 'rounded-md'
              } ${lg.colorBg} ${lg.text} relative shadow-xs`}
            >
              {lg.count}
              {lg.hasBadge && (
                <span className="absolute -top-1 -right-1 w-3 h-3 bg-emerald-400 rounded-full flex items-center justify-center border border-white">
                  <Check className="w-2 h-2 text-white stroke-[3]" />
                </span>
              )}
            </div>
            <span className="text-slate-600 truncate text-[11px]">{lg.label}</span>
          </div>
        ))}
      </div>

      {/* Section / Palette Title */}
      <div className="px-3.5 py-2 bg-slate-100 border-b border-slate-200 flex items-center justify-between">
        <span className="text-xs font-bold text-slate-700 uppercase tracking-wide">
          Question Palette
        </span>
        <span className="text-xs font-semibold text-primary-600">
          Total: {questions.length}
        </span>
      </div>

      {/* Grid of Question Number Buttons */}
      <div className="flex-1 overflow-y-auto p-3.5">
        <div className="grid grid-cols-5 gap-2.5">
          {questions.map((q, idx) => {
            const st = getQuestionStatus(q);
            const isCurrent = idx === currentQuestionIndex;

            let bgClass = 'bg-[#dcdcdc] text-slate-700 hover:bg-slate-300';
            let isRound = false;
            let hasBadge = false;

            if (st === 'ANSWERED') {
              bgClass = 'bg-[#22C969] text-white hover:bg-emerald-600';
            } else if (st === 'UNANSWERED') {
              bgClass = 'bg-[#FF614D] text-white hover:bg-rose-600';
            } else if (st === 'MARKED_FOR_REVIEW') {
              bgClass = 'bg-[#9967ff] text-white hover:bg-purple-600';
              isRound = true;
            } else if (st === 'ANSWERED_AND_MARKED') {
              bgClass = 'bg-[#9967ff] text-white hover:bg-purple-600';
              hasBadge = true;
            }

            return (
              <button
                key={String(q.id)}
                type="button"
                onClick={() => onSelectQuestion(idx)}
                className={`w-10 h-10 font-bold text-xs flex items-center justify-center transition-all relative shadow-xs ${
                  isRound ? 'rounded-full' : 'rounded-md'
                } ${bgClass} ${
                  isCurrent
                    ? 'ring-2 ring-offset-2 ring-primary-500 scale-105 z-10 shadow-md font-extrabold'
                    : ''
                }`}
                title={`Q${q.question_number || idx + 1} (${st})`}
              >
                {q.question_number || idx + 1}
                {hasBadge && (
                  <span className="absolute -top-1 -right-1 w-3.5 h-3.5 bg-emerald-500 rounded-full flex items-center justify-center border-2 border-white shadow-xs">
                    <Check className="w-2.5 h-2.5 text-white stroke-[3]" />
                  </span>
                )}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
};

export default QuestionPalette;
