import React, { useState } from 'react';
import { ConceptCardData } from '../../services/courseService';
import { ChevronDown, ChevronRight, Layers, CheckCircle2, XCircle, Sparkles } from 'lucide-react';

interface InteractiveConceptDeckProps {
  cards: ConceptCardData[];
  lessonId?: number;
}

export const InteractiveConceptDeck: React.FC<InteractiveConceptDeckProps> = ({ cards, lessonId }) => {
  const storageKey = lessonId ? `learnforge_concept_checks_${lessonId}` : null;
  const [expandedIdx, setExpandedIdx] = useState<number>(0);
  const [selectedAnswers, setSelectedAnswers] = useState<Record<number, string>>(() => {
    if (!storageKey) return {};
    try {
      const raw = localStorage.getItem(storageKey);
      return raw ? JSON.parse(raw) : {};
    } catch {
      return {};
    }
  });

  const handleSelectQuickCheck = (idx: number, opt: string) => {
    setSelectedAnswers((prev) => {
      const next = { ...prev, [idx]: opt };
      if (storageKey) {
        try {
          localStorage.setItem(storageKey, JSON.stringify(next));
        } catch {
          // ignore
        }
      }
      return next;
    });
  };

  if (!cards || cards.length === 0) return null;

  return (
    <section className="mt-8 pt-7 border-t border-line space-y-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <span className="text-[11px] font-bold uppercase tracking-wider text-accent">
            Interactive Exploration
          </span>
          <h2 className="lf-heading-section flex items-center gap-2 mt-0.5">
            <Layers className="h-5 w-5 text-brand" />
            <span>Concept Cards ({cards.length})</span>
          </h2>
        </div>
        <span className="text-xs text-ink-secondary">Click any card to expand &amp; check</span>
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
              className={`rounded-[12px] border transition-all overflow-hidden ${
                isOpen
                  ? 'border-brand bg-surface shadow-card'
                  : 'border-line bg-subtle hover:border-brand-soft-border'
              }`}
            >
              <button
                type="button"
                onClick={() => setExpandedIdx(isOpen ? -1 : idx)}
                className="w-full flex items-center justify-between px-5 py-4 text-left"
              >
                <div className="flex items-center gap-3 min-w-0">
                  <span className="h-7 w-7 rounded-[10px] bg-brand-soft border border-brand-soft-border text-brand text-xs font-bold flex items-center justify-center shrink-0">
                    {idx + 1}
                  </span>
                  <span className="text-base font-semibold text-ink-primary truncate">{card.term}</span>
                </div>
                {isOpen ? (
                  <ChevronDown className="h-4 w-4 text-accent shrink-0" />
                ) : (
                  <ChevronRight className="h-4 w-4 text-ink-secondary shrink-0" />
                )}
              </button>

              {isOpen && (
                <div className="px-5 pb-5 pt-2 border-t border-line space-y-4 text-sm md:text-base">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5 pt-2">
                    <div className="p-3.5 rounded-[10px] bg-subtle border border-line space-y-1">
                      <p className="text-[11px] font-bold uppercase tracking-wider text-brand">
                        What It Is
                      </p>
                      <p className="text-ink-primary leading-relaxed text-sm">{card.what_it_is}</p>
                    </div>
                    <div className="p-3.5 rounded-[10px] bg-subtle border border-line space-y-1">
                      <p className="text-[11px] font-bold uppercase tracking-wider text-accent">
                        Why It Exists
                      </p>
                      <p className="text-ink-primary leading-relaxed text-sm">{card.why_it_exists}</p>
                    </div>
                    <div className="p-3.5 rounded-[10px] bg-subtle border border-line space-y-1">
                      <p className="text-[11px] font-bold uppercase tracking-wider text-status-success-text">
                        How It Works
                      </p>
                      <p className="text-ink-primary leading-relaxed text-sm">{card.how_it_works}</p>
                    </div>
                    {card.difference && (
                      <div className="p-3.5 rounded-[10px] bg-subtle border border-line space-y-1">
                        <p className="text-[11px] font-bold uppercase tracking-wider text-status-warning-text">
                          Key Difference
                        </p>
                        <p className="text-ink-primary leading-relaxed text-sm">{card.difference}</p>
                      </div>
                    )}
                  </div>

                  {card.example && (
                    <div className="p-3.5 rounded-[10px] bg-brand-soft border border-brand-soft-border text-sm text-ink-primary">
                      <strong className="text-brand">Practical Example:</strong> {card.example}
                    </div>
                  )}

                  {qc && qc.options && qc.options.length > 0 && (
                    <div className="p-4 rounded-[12px] bg-subtle border border-line space-y-2.5">
                      <p className="text-xs font-bold uppercase tracking-wider text-accent flex items-center gap-1.5">
                        <Sparkles className="h-3.5 w-3.5" /> Quick Check
                      </p>
                      <p className="text-sm font-medium text-ink-primary">{qc.question}</p>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                        {qc.options.map((opt, oIdx) => (
                          <button
                            key={oIdx}
                            type="button"
                            onClick={() => handleSelectQuickCheck(idx, opt)}
                            className={`text-left px-3.5 py-2.5 rounded-[10px] border text-xs md:text-sm transition-all ${
                              picked === opt
                                ? opt === qc.correct_answer
                                  ? 'bg-status-success-bg border-status-success-border text-status-success-text font-medium'
                                  : 'bg-status-danger-bg border-status-danger-border text-status-danger-text font-medium'
                                : 'bg-surface border-line text-ink-secondary hover:bg-hoverbg hover:text-ink-primary hover:border-brand-soft-border'
                            }`}
                          >
                            {opt}
                          </button>
                        ))}
                      </div>
                      {picked && (
                        <div
                          className={`text-xs flex items-start gap-2 pt-1 font-medium ${
                            isCorrect ? 'text-status-success-text' : 'text-status-danger-text'
                          }`}
                        >
                          {isCorrect ? (
                            <CheckCircle2 className="h-4 w-4 shrink-0 mt-0.5" />
                          ) : (
                            <XCircle className="h-4 w-4 shrink-0 mt-0.5" />
                          )}
                          <span>
                            {isCorrect ? 'Correct! ' : 'Not quite — '}
                            {qc.explanation || (!isCorrect ? 'try another option.' : '')}
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
