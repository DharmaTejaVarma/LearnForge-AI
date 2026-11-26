import React, { useMemo, useState } from 'react';
import { MatchingExerciseData } from '../../services/courseService';
import { Shuffle, CheckCircle2, XCircle, RotateCcw } from 'lucide-react';

interface InteractiveMatchingCardProps {
  matching: MatchingExerciseData;
}

export const InteractiveMatchingCard: React.FC<InteractiveMatchingCardProps> = ({ matching }) => {
  const pairs = matching.pairs || [];

  const shuffledDescriptions = useMemo(() => {
    const items = pairs.map((p) => ({ id: p.id, description: p.description }));
    if (items.length <= 1) return items;
    // Deterministic rotation so options don't align 1:1 initially
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
    <section className="mt-8 rounded-2xl border border-indigo-500/25 bg-slate-950/70 p-5 md:p-6 space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
        <div>
          <span className="text-[11px] font-bold uppercase tracking-wider text-indigo-400 flex items-center gap-1.5">
            <Shuffle className="h-3.5 w-3.5" />
            Interactive Matching Exercise
          </span>
          <h3 className="text-lg font-bold text-white mt-0.5">{matching.title}</h3>
          <p className="text-xs text-slate-400 mt-0.5">{matching.instructions}</p>
        </div>

        <div className="flex items-center gap-2 self-start">
          <button
            type="button"
            onClick={reset}
            className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-900 border border-slate-700 text-slate-300 hover:text-white"
          >
            <RotateCcw className="h-3.5 w-3.5" />
            Reset
          </button>
          <button
            type="button"
            disabled={!allAssigned}
            onClick={() => setChecked(true)}
            className="px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-indigo-600 text-white hover:bg-indigo-500 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            Check Matches
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="space-y-2">
          <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
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
                className={`w-full text-left p-3 rounded-xl border text-xs md:text-sm transition-all flex items-center justify-between gap-2 ${
                  isSelected
                    ? 'bg-indigo-600/25 border-indigo-400 text-white'
                    : isCorrect
                    ? 'bg-emerald-500/15 border-emerald-500/40 text-emerald-200'
                    : isWrong
                    ? 'bg-rose-500/15 border-rose-500/40 text-rose-200'
                    : 'bg-slate-900/90 border-slate-800 text-slate-200 hover:border-slate-700'
                }`}
              >
                <span className="font-semibold">
                  {idx + 1}. {p.term}
                </span>
                <span className="text-[11px] text-slate-400 shrink-0">
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
          <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
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
                className={`w-full text-left p-3 rounded-xl border text-xs md:text-sm transition-all ${
                  selectedTermId
                    ? 'bg-slate-900 border-indigo-500/40 hover:bg-indigo-500/10 text-slate-200 cursor-pointer'
                    : 'bg-slate-900/60 border-slate-800 text-slate-300 cursor-default'
                }`}
              >
                <div className="flex items-start gap-2">
                  <span className="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-md bg-slate-800 text-[11px] font-bold text-indigo-300">
                    {letter}
                  </span>
                  <span className="leading-relaxed flex-1">{d.description}</span>
                  {assignedTo && (
                    <span className="text-[11px] font-semibold text-indigo-300 shrink-0">
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
          className={`flex items-center gap-2 rounded-xl px-4 py-2.5 text-xs font-semibold border ${
            correctCount === pairs.length
              ? 'bg-emerald-500/15 border-emerald-500/30 text-emerald-300'
              : 'bg-amber-500/15 border-amber-500/30 text-amber-300'
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
