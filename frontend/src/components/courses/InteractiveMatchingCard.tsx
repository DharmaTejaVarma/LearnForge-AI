import React, { useMemo, useState } from 'react';
import { MatchingExerciseData } from '../../services/courseService';
import { Shuffle, CheckCircle2, XCircle, RotateCcw } from 'lucide-react';
import { Button } from '../common/Button';

interface InteractiveMatchingCardProps {
  matching: MatchingExerciseData;
}

export const InteractiveMatchingCard: React.FC<InteractiveMatchingCardProps> = ({ matching }) => {
  const pairs = matching.pairs || [];

  const shuffledDescriptions = useMemo(() => {
    const items = pairs.map((p) => ({ id: p.id, description: p.description }));
    if (items.length <= 1) return items;
    return [...items.slice(1), items[0]];
  }, [pairs]);

  const [selectedTermId, setSelectedTermId] = useState<string | null>(null);
  const [matches, setMatches] = useState<Record<string, string>>({});
  const [checked, setChecked] = useState<boolean>(false);

  if (pairs.length === 0) return null;

  const handleSelectDescription = (descId: string) => {
    if (!selectedTermId) return;
    setMatches((prev) => ({ ...prev, [selectedTermId]: descId }));
    setSelectedTermId(null);
    setChecked(false);
  };

  const reset = () => {
    setMatches({});
    setSelectedTermId(null);
    setChecked(false);
  };

  const correctCount = pairs.filter((p) => matches[p.id] === p.id).length;
  const allAssigned = Object.keys(matches).length === pairs.length;

  return (
    <section className="mt-8 rounded-[12px] border border-brand-soft-border bg-subtle p-5 md:p-6 space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
        <div>
          <span className="text-[11px] font-bold uppercase tracking-wider text-accent flex items-center gap-1.5">
            <Shuffle className="h-3.5 w-3.5" />
            Interactive Matching Exercise
          </span>
          <h3 className="lf-heading-card mt-0.5">{matching.title}</h3>
          <p className="text-xs text-ink-secondary mt-0.5">{matching.instructions}</p>
        </div>

        <div className="flex items-center gap-2 self-start">
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={reset}
            icon={<RotateCcw className="h-3.5 w-3.5" />}
          >
            Reset
          </Button>
          <Button
            type="button"
            variant="primary"
            size="sm"
            disabled={!allAssigned}
            onClick={() => setChecked(true)}
          >
            Check Matches
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="space-y-2">
          <p className="text-[11px] font-semibold uppercase tracking-wider text-ink-secondary">
            1. Select a Concept
          </p>
          {pairs.map((p, idx) => {
            const isSelected = selectedTermId === p.id;
            const assignedDescId = matches[p.id];
            const isCorrect = checked && assignedDescId === p.id;
            const isWrong = checked && assignedDescId && assignedDescId !== p.id;
            return (
              <button
                key={p.id}
                type="button"
                onClick={() => setSelectedTermId(p.id)}
                className={`w-full text-left p-3 rounded-[10px] border text-xs md:text-sm transition-all flex items-center justify-between gap-2 ${
                  isSelected
                    ? 'bg-hoverbg border-brand text-ink-primary font-semibold'
                    : isCorrect
                    ? 'bg-status-success-bg border-status-success-border text-status-success-text'
                    : isWrong
                    ? 'bg-status-danger-bg border-status-danger-border text-status-danger-text'
                    : 'bg-surface border-line text-ink-primary hover:border-brand-soft-border'
                }`}
              >
                <span className="font-semibold">
                  {idx + 1}. {p.term}
                </span>
                <span className="text-[11px] text-ink-secondary shrink-0">
                  {assignedDescId
                    ? `→ ${String.fromCharCode(
                        65 + shuffledDescriptions.findIndex((d) => d.id === assignedDescId),
                      )}`
                    : isSelected
                    ? 'Pick description →'
                    : 'Unmatched'}
                </span>
              </button>
            );
          })}
        </div>

        <div className="space-y-2">
          <p className="text-[11px] font-semibold uppercase tracking-wider text-ink-secondary">
            2. Click Matching Description
          </p>
          {shuffledDescriptions.map((d, idx) => {
            const letter = String.fromCharCode(65 + idx);
            const assignedTo = Object.entries(matches).find(([, v]) => v === d.id)?.[0];
            return (
              <button
                key={d.id}
                type="button"
                onClick={() => handleSelectDescription(d.id)}
                disabled={!selectedTermId}
                className={`w-full text-left p-3 rounded-[10px] border text-xs md:text-sm transition-all ${
                  selectedTermId
                    ? 'bg-surface border-brand-soft-border hover:bg-hoverbg text-ink-primary cursor-pointer'
                    : 'bg-surface border-line text-ink-secondary cursor-default'
                }`}
              >
                <div className="flex items-start gap-2">
                  <span className="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-md bg-brand-soft text-[11px] font-bold text-brand">
                    {letter}
                  </span>
                  <span className="leading-relaxed flex-1 text-ink-primary">{d.description}</span>
                  {assignedTo && (
                    <span className="text-[11px] font-semibold text-accent shrink-0">
                      #{pairs.findIndex((p) => p.id === assignedTo) + 1}
                    </span>
                  )}
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {checked && (
        <div
          className={`flex items-center gap-2 rounded-[10px] px-4 py-2.5 text-xs font-semibold border ${
            correctCount === pairs.length
              ? 'bg-status-success-bg border-status-success-border text-status-success-text'
              : 'bg-status-warning-bg border-status-warning-border text-status-warning-text'
          }`}
        >
          {correctCount === pairs.length ? (
            <CheckCircle2 className="h-4 w-4 shrink-0" />
          ) : (
            <XCircle className="h-4 w-4 shrink-0" />
          )}
          <span>
            Matched {correctCount} / {pairs.length} pairs correctly.
          </span>
        </div>
      )}
    </section>
  );
};
