import React, { useState } from 'react';
import { ConceptCardData } from '../../services/courseService';
import { ChevronDown, ChevronRight, Layers, CheckCircle2, XCircle, Sparkles } from 'lucide-react';

interface InteractiveConceptDeckProps {
  cards: ConceptCardData[];
}

export const InteractiveConceptDeck: React.FC<InteractiveConceptDeckProps> = ({ cards }) => {
  const [expandedIdx, setExpandedIdx] = useState<number>(0);
  const [selectedAnswers, setSelectedAnswers] = useState<Record<number, string>>({});

  if (!cards || cards.length === 0) return null;

  return (
    <section className="mt-8 pt-7 border-t border-slate-800 space-y-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <span className="text-[11px] font-bold uppercase tracking-wider text-indigo-400">
            Interactive Exploration
          </span>
          <h2 className="text-xl font-bold text-white flex items-center gap-2 mt-0.5">
            <Layers className="h-5 w-5 text-indigo-400" />
            <span>Concept Cards ({cards.length})</span>
          </h2>
        </div>
        <span className="text-xs text-slate-400">Click any card to expand &amp; check</span>
      </div>

      <div className="space-y-3">
        {cards.map((card, idx) => {
          const isOpen = expandedIdx === idx;
          const qc = card.quick_check;
          const picked = selectedAnswers[idx];
          const isCorrect = qc && picked === qc.correct_answer;

          return (
            <div
              key={idx}
              className={`rounded-2xl border transition-all overflow-hidden ${
                isOpen
                  ? 'border-indigo-500/40 bg-slate-950/90 shadow-lg'
                  : 'border-slate-800 bg-slate-950/50 hover:border-slate-700'
              }`}
            >
              <button
                type="button"
                onClick={() => setExpandedIdx(isOpen ? -1 : idx)}
                className="w-full flex items-center justify-between px-5 py-4 text-left"
              >
                <div className="flex items-center gap-3 min-w-0">
                  <span className="h-7 w-7 rounded-lg bg-indigo-500/15 border border-indigo-500/30 text-indigo-300 text-xs font-bold flex items-center justify-center shrink-0">
                    {idx + 1}
                  </span>
                  <span className="text-base font-bold text-white truncate">{card.term}</span>
                </div>
                {isOpen ? (
                  <ChevronDown className="h-4 w-4 text-indigo-400 shrink-0" />
                ) : (
                  <ChevronRight className="h-4 w-4 text-slate-400 shrink-0" />
                )}
              </button>

              {isOpen && (
                <div className="px-5 pb-5 pt-1 border-t border-slate-800/80 space-y-4 text-sm md:text-base">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5 pt-2">
                    <div className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800 space-y-1">
                      <p className="text-[11px] font-bold uppercase tracking-wider text-indigo-400">
                        What It Is
                      </p>
                      <p className="text-slate-200 leading-relaxed text-sm">{card.what_it_is}</p>
                    </div>
                    <div className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800 space-y-1">
                      <p className="text-[11px] font-bold uppercase tracking-wider text-purple-400">
                        Why It Exists
                      </p>
                      <p className="text-slate-200 leading-relaxed text-sm">{card.why_it_exists}</p>
                    </div>
                    <div className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800 space-y-1">
                      <p className="text-[11px] font-bold uppercase tracking-wider text-emerald-400">
                        How It Works
                      </p>
                      <p className="text-slate-200 leading-relaxed text-sm">{card.how_it_works}</p>
                    </div>
                    {card.difference && (
                      <div className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800 space-y-1">
                        <p className="text-[11px] font-bold uppercase tracking-wider text-amber-400">
                          Key Difference
                        </p>
                        <p className="text-slate-200 leading-relaxed text-sm">{card.difference}</p>
                      </div>
                    )}
                  </div>

                  {card.example && (
                    <div className="p-3.5 rounded-xl bg-indigo-950/25 border border-indigo-500/20 text-sm text-indigo-100">
                      <strong className="text-indigo-300">Practical Example:</strong> {card.example}
                    </div>
                  )}

                  {qc && qc.options && qc.options.length > 0 && (
                    <div className="p-4 rounded-xl bg-slate-900/90 border border-slate-800 space-y-2.5">
                      <p className="text-xs font-bold uppercase tracking-wider text-cyan-400 flex items-center gap-1.5">
                        <Sparkles className="h-3.5 w-3.5" /> Quick Check
                      </p>
                      <p className="text-sm font-medium text-white">{qc.question}</p>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                        {qc.options.map((opt, oIdx) => (
                          <button
                            key={oIdx}
                            type="button"
                            onClick={() => setSelectedAnswers((p) => ({ ...p, [idx]: opt }))}
                            className={`text-left px-3.5 py-2.5 rounded-lg border text-xs md:text-sm transition-all ${
                              picked === opt
                                ? opt === qc.correct_answer
                                  ? 'bg-emerald-500/20 border-emerald-500 text-emerald-200'
                                  : 'bg-rose-500/20 border-rose-500 text-rose-200'
                                : 'bg-slate-950/70 border-slate-800 text-slate-300 hover:border-slate-700'
                            }`}
                          >
                            {opt}
                          </button>
                        ))}
                      </div>
                      {picked && (
                        <div
                          className={`text-xs flex items-start gap-2 pt-1 ${
                            isCorrect ? 'text-emerald-300' : 'text-rose-300'
                          }`}
                        >
                          {isCorrect ? (
                            <CheckCircle2 className="h-4 w-4 shrink-0 mt-0.5" />
                          ) : (
                            <XCircle className="h-4 w-4 shrink-0 mt-0.5" />
                          )}
                          <span>
                            {isCorrect ? 'Correct! ' : 'Try another option. '}
                            {isCorrect && qc.explanation}
                          </span>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
};
