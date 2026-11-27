import React, { useState, useEffect } from 'react';
import {
  courseService,
  LessonExercise,
  ExerciseSubmitResult,
  CodeRunResult,
} from '../../services/courseService';
import { Button } from '../common/Button';
import { MarkdownRenderer } from './MarkdownRenderer';
import {
  Play,
  CheckCircle2,
  XCircle,
  Lightbulb,
  Code2,
  Bug,
  HelpCircle,
  RotateCcw,
  Sparkles,
  PenLine,
  Send,
  Bot,
  ExternalLink,
} from 'lucide-react';

interface LessonExercisesPanelProps {
  lessonId: number;
  exercises: LessonExercise[];
  onAskTutorHint?: (exercise: LessonExercise) => void;
  onExerciseSolved?: (exerciseId: number, isCorrect: boolean) => void;
}

const typeMeta: Record<string, { label: string; icon: React.ReactNode; badge: string }> = {
  mcq: {
    label: 'Concept Check',
    icon: <HelpCircle className="h-3.5 w-3.5" />,
    badge: 'bg-brand-soft text-brand border-brand-soft-border',
  },
  coding: {
    label: 'Coding Lab',
    icon: <Code2 className="h-3.5 w-3.5" />,
    badge: 'bg-status-success-bg text-status-success-text border-status-success-border',
  },
  debugging: {
    label: 'Debug Challenge',
    icon: <Bug className="h-3.5 w-3.5" />,
    badge: 'bg-status-warning-bg text-status-warning-text border-status-warning-border',
  },
  fill_blank: {
    label: 'Fill in the Blank',
    icon: <PenLine className="h-3.5 w-3.5" />,
    badge: 'bg-accent-soft text-accent border-accent-soft-border',
  },
  mini_task: {
    label: 'Applied Mini Task',
    icon: <Sparkles className="h-3.5 w-3.5" />,
    badge: 'bg-brand-soft text-brand border-brand-soft-border',
  },
};

export const LessonExercisesPanel: React.FC<LessonExercisesPanelProps> = ({
  lessonId,
  exercises,
  onAskTutorHint,
  onExerciseSolved,
}) => {
  const [selectedAnswers, setSelectedAnswers] = useState<Record<number, string>>({});
  const [codeInputs, setCodeInputs] = useState<Record<number, string>>({});
  const [revealedHints, setRevealedHints] = useState<Record<number, number>>({});
  const [submissions, setSubmissions] = useState<Record<number, ExerciseSubmitResult>>({});
  const [runOutputs, setRunOutputs] = useState<Record<number, CodeRunResult>>({});
  const [loadingRun, setLoadingRun] = useState<Record<number, boolean>>({});
  const [loadingSubmit, setLoadingSubmit] = useState<Record<number, boolean>>({});
  const [activeFilter, setActiveFilter] = useState<string>('all');

  useEffect(() => {
    let savedState: any = {};
    try {
      const raw = localStorage.getItem(`learnforge_exercises_${lessonId}`);
      if (raw) savedState = JSON.parse(raw);
    } catch {
      savedState = {};
    }

    const initialCode: Record<number, string> = {};
    const initialSubs: Record<number, ExerciseSubmitResult> = { ...(savedState.submissions || {}) };
    const initialRuns: Record<number, CodeRunResult> = { ...(savedState.runOutputs || {}) };

    exercises.forEach((ex) => {
      const wsCode = localStorage.getItem(`learnforge_ex_code_${lessonId}_${ex.id}`);
      const wsSub = localStorage.getItem(`learnforge_ex_submit_${lessonId}_${ex.id}`);
      const wsRun = localStorage.getItem(`learnforge_ex_run_${lessonId}_${ex.id}`);
      if (wsCode !== null) {
        initialCode[ex.id] = wsCode;
      } else if (savedState.codeInputs?.[ex.id] !== undefined) {
        initialCode[ex.id] = savedState.codeInputs[ex.id];
      } else if (ex.starter_code || ex.buggy_code) {
        initialCode[ex.id] = ex.starter_code || ex.buggy_code || '';
      }
      if (wsSub) {
        try { initialSubs[ex.id] = JSON.parse(wsSub); } catch {}
      }
      if (wsRun) {
        try { initialRuns[ex.id] = JSON.parse(wsRun); } catch {}
      }
    });

    setCodeInputs(initialCode);
    setSubmissions(initialSubs);
    setRunOutputs(initialRuns);
    setSelectedAnswers(savedState.selectedAnswers || {});
    setRevealedHints({});
  }, [lessonId, exercises]);

  useEffect(() => {
    try {
      localStorage.setItem(
        `learnforge_exercises_${lessonId}`,
        JSON.stringify({ selectedAnswers, codeInputs, submissions, runOutputs }),
      );
    } catch {
      // ignore storage quota errors
    }
  }, [lessonId, selectedAnswers, codeInputs, submissions, runOutputs]);

  if (!exercises || exercises.length === 0) return null;

  const solvedCount = exercises.filter(
    (ex) => submissions[ex.id]?.is_correct || ex.latest_is_correct,
  ).length;

  const availableTypes = Array.from(new Set(exercises.map((e) => e.exercise_type)));
  const visibleExercises =
    activeFilter === 'all'
      ? exercises
      : exercises.filter((e) => e.exercise_type === activeFilter);

  const handleRunCode = async (ex: LessonExercise) => {
    const code = codeInputs[ex.id] ?? ex.starter_code ?? '';
    setLoadingRun((p) => ({ ...p, [ex.id]: true }));
    try {
      const res = await courseService.runExerciseCode(lessonId, ex.id, code);
      setRunOutputs((p) => ({ ...p, [ex.id]: res }));
    } catch (err: any) {
      setRunOutputs((p) => ({
        ...p,
        [ex.id]: {
          passed: false,
          passed_tests: 0,
          total_tests: ex.test_cases?.length || 0,
          stdout: '',
          stderr: err?.response?.data?.error?.message || err.message || 'Sandbox execution failed',
          results: [],
          timed_out: false,
        },
      }));
    } finally {
      setLoadingRun((p) => ({ ...p, [ex.id]: false }));
    }
  };

  const handleSubmit = async (ex: LessonExercise) => {
    const isCode = ex.exercise_type === 'coding' || ex.exercise_type === 'debugging';
    const payload = isCode
      ? { code: codeInputs[ex.id] ?? ex.starter_code ?? '' }
      : { answer: selectedAnswers[ex.id] || '' };

    setLoadingSubmit((p) => ({ ...p, [ex.id]: true }));
    try {
      const res = await courseService.submitExercise(lessonId, ex.id, payload);
      setSubmissions((p) => ({ ...p, [ex.id]: res }));
      if (onExerciseSolved) {
        onExerciseSolved(ex.id, res.is_correct);
      }
    } catch (err: any) {
      console.error('Submit exercise failed:', err);
    } finally {
      setLoadingSubmit((p) => ({ ...p, [ex.id]: false }));
    }
  };

  return (
    <section
      id="practice-exercises"
      className="mt-10 pt-8 border-t border-line space-y-6"
    >
      {/* Header Row */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h2 className="lf-heading-section flex items-center gap-2.5">
            <span className="h-8 w-8 rounded-[10px] bg-brand-soft border border-brand-soft-border flex items-center justify-center text-brand">
              <Sparkles className="h-4 w-4" />
            </span>
            <span>Practice &amp; Test Your Knowledge</span>
          </h2>
          <p className="text-xs text-ink-secondary mt-1">
            Interactive exercises grounded in this lesson with instant feedback and isolated code checks.
          </p>
        </div>

        <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-subtle border border-line text-xs font-semibold">
          <CheckCircle2 className="h-4 w-4 text-status-success-text" />
          <span className="text-ink-primary">
            {solvedCount} / {exercises.length} Solved
          </span>
        </div>
      </div>

      {/* Filter Pills */}
      {availableTypes.length > 1 && (
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => setActiveFilter('all')}
            className={`px-3 py-1.5 rounded-[10px] text-xs font-medium transition-colors ${
              activeFilter === 'all'
                ? 'bg-brand text-white'
                : 'bg-subtle text-ink-secondary hover:bg-hoverbg hover:text-ink-primary'
            }`}
          >
            All ({exercises.length})
          </button>
          {availableTypes.map((type) => {
            const count = exercises.filter((e) => e.exercise_type === type).length;
            const meta = typeMeta[type] || { label: type };
            return (
              <button
                key={type}
                type="button"
                onClick={() => setActiveFilter(type)}
                className={`px-3 py-1.5 rounded-[10px] text-xs font-medium transition-colors ${
                  activeFilter === type
                    ? 'bg-brand text-white'
                    : 'bg-subtle text-ink-secondary hover:bg-hoverbg hover:text-ink-primary'
                }`}
              >
                {meta.label} ({count})
              </button>
            );
          })}
        </div>
      )}

      {/* Exercise Cards */}
      <div className="space-y-5">
        {visibleExercises.map((ex, idx) => {
          const meta = typeMeta[ex.exercise_type] || typeMeta.mcq;
          const sub = submissions[ex.id];
          const runOut = runOutputs[ex.id];
          const isSolved = Boolean(sub?.is_correct || ex.latest_is_correct);
          const hintCount = revealedHints[ex.id] || 0;
          const totalHints = ex.hints?.length || 0;
          const isCodeEx = ex.exercise_type === 'coding' || ex.exercise_type === 'debugging';

          return (
            <div
              key={ex.id}
              className={`rounded-[12px] border p-5 md:p-6 space-y-4 transition-all ${
                isSolved
                  ? 'bg-status-success-bg/40 border-status-success-border'
                  : 'bg-subtle border-line'
              }`}
            >
              {/* Card Top Meta */}
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span
                    className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold border ${meta.badge}`}
                  >
                    {meta.icon}
                    <span>{meta.label}</span>
                  </span>
                  <span className="text-xs font-semibold text-ink-secondary">
                    #{idx + 1} · {ex.title}
                  </span>
                </div>

                <div className="flex items-center gap-2">
                  {isSolved && (
                    <span className="inline-flex items-center gap-1 text-xs font-semibold text-status-success-text">
                      <CheckCircle2 className="h-4 w-4" />
                      Solved
                    </span>
                  )}
                  {onAskTutorHint && (
                    <button
                      type="button"
                      onClick={() => onAskTutorHint(ex)}
                      className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-[10px] bg-surface hover:bg-hoverbg text-brand text-[11px] font-medium border border-line transition-colors"
                    >
                      <Bot className="h-3.5 w-3.5 text-accent" />
                      Ask Tutor Hint
                    </button>
                  )}
                </div>
              </div>

              {/* Prompt */}
              <div className="text-base text-ink-primary leading-relaxed">
                <MarkdownRenderer content={ex.prompt} className="prose-base" />
              </div>

              {/* MCQ UI */}
              {ex.exercise_type === 'mcq' && ex.options && (
                <div className="space-y-2.5">
                  {ex.options.map((opt, optIdx) => {
                    const selected = selectedAnswers[ex.id] === opt;
                    return (
                      <button
                        key={optIdx}
                        type="button"
                        onClick={() =>
                          setSelectedAnswers((p) => ({ ...p, [ex.id]: opt }))
                        }
                        className={`w-full text-left px-5 py-3.5 rounded-[10px] border text-sm md:text-[15px] transition-all flex items-start gap-3 ${
                          selected
                            ? 'bg-hoverbg border-brand text-ink-primary font-medium'
                            : 'bg-surface border-line text-ink-secondary hover:border-brand-soft-border hover:bg-hoverbg hover:text-ink-primary'
                        }`}
                      >
                        <span
                          className={`mt-0.5 h-5 w-5 rounded-full border flex items-center justify-center shrink-0 text-[10px] font-bold ${
                            selected
                              ? 'border-brand bg-brand text-white'
                              : 'border-line-strong text-ink-secondary'
                          }`}
                        >
                          {String.fromCharCode(65 + optIdx)}
                        </span>
                        <span>{opt}</span>
                      </button>
                    );
                  })}
                </div>
              )}

              {/* Fill-blank / Mini Task */}
              {(ex.exercise_type === 'fill_blank' || ex.exercise_type === 'mini_task') && (
                <div>
                  {ex.exercise_type === 'fill_blank' ? (
                    <input
                      type="text"
                      value={selectedAnswers[ex.id] || ''}
                      onChange={(e) =>
                        setSelectedAnswers((p) => ({ ...p, [ex.id]: e.target.value }))
                      }
                      placeholder="Type the missing technical term..."
                      className="lf-control w-full px-4 py-2.5 text-sm"
                    />
                  ) : (
                    <textarea
                      rows={3}
                      value={selectedAnswers[ex.id] || ''}
                      onChange={(e) =>
                        setSelectedAnswers((p) => ({ ...p, [ex.id]: e.target.value }))
                      }
                      placeholder="Write your concise practical response..."
                      className="lf-control w-full px-4 py-2.5 text-sm"
                    />
                  )}
                </div>
              )}

              {/* Coding / Debugging Isolated Editor */}
              {isCodeEx && (
                <div className="space-y-3">
                  <div className="rounded-[12px] border border-codeblock-border bg-codeblock-bg overflow-hidden shadow-card">
                    <div className="flex items-center justify-between px-3.5 py-2 bg-codeblock-header border-b border-codeblock-border text-[11px] text-codeblock-muted">
                      <span className="font-mono font-semibold text-codeblock-text">
                        python_sandbox.py (Isolated Subprocess)
                      </span>
                      <div className="flex items-center gap-3">
                        <a
                          href={`/lessons/${lessonId}/coding/${ex.id}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 text-indigo-300 hover:text-white transition-colors font-semibold"
                        >
                          <ExternalLink className="h-3 w-3" />
                          Open in New Page
                        </a>
                        <button
                          type="button"
                          onClick={() =>
                            setCodeInputs((p) => ({
                              ...p,
                              [ex.id]: ex.starter_code || ex.buggy_code || '',
                            }))
                          }
                          className="inline-flex items-center gap-1 text-codeblock-muted hover:text-codeblock-text transition-colors"
                        >
                          <RotateCcw className="h-3 w-3" />
                          Reset Starter
                        </button>
                      </div>
                    </div>
                    <textarea
                      rows={9}
                      spellCheck={false}
                      value={codeInputs[ex.id] ?? ''}
                      onKeyDown={(e) => {
                        if (e.key === 'Tab') {
                          e.preventDefault();
                          const target = e.currentTarget;
                          const start = target.selectionStart;
                          const end = target.selectionEnd;
                          const val = codeInputs[ex.id] ?? '';
                          const updated = val.substring(0, start) + '    ' + val.substring(end);
                          setCodeInputs((p) => ({ ...p, [ex.id]: updated }));
                          setTimeout(() => {
                            target.selectionStart = target.selectionEnd = start + 4;
                          }, 0);
                        }
                      }}
                      onChange={(e) =>
                        setCodeInputs((p) => ({ ...p, [ex.id]: e.target.value }))
                      }
                      className="w-full bg-codeblock-bg p-3.5 font-mono text-xs md:text-sm text-emerald-100 focus:outline-none resize-y"
                    />
                  </div>

                  {/* Test Run Results Output */}
                  {runOut && (
                    <div className="rounded-[10px] border border-line bg-surface p-3.5 space-y-2 text-xs">
                      <div className="flex items-center justify-between font-semibold">
                        <span className={runOut.passed ? 'text-status-success-text' : 'text-status-warning-text'}>
                          {runOut.passed
                            ? `All ${runOut.total_tests} test(s) passed`
                            : `${runOut.passed_tests}/${runOut.total_tests} test(s) passed`}
                        </span>
                      </div>
                      {runOut.stdout && (
                        <pre className="p-2.5 rounded-[10px] bg-codeblock-bg text-codeblock-text font-mono overflow-x-auto">
                          {runOut.stdout}
                        </pre>
                      )}
                      {runOut.stderr && (
                        <pre className="p-2.5 rounded-[10px] bg-codeblock-bg text-rose-300 font-mono overflow-x-auto">
                          {runOut.stderr}
                        </pre>
                      )}
                      {runOut.results?.map((r, rIdx) => (
                        <div key={rIdx} className="flex items-center gap-2">
                          {r.passed ? (
                            <CheckCircle2 className="h-3.5 w-3.5 text-status-success-text shrink-0" />
                          ) : (
                            <XCircle className="h-3.5 w-3.5 text-status-danger-text shrink-0" />
                          )}
                          <span className="text-ink-primary">{r.description}</span>
                          {!r.passed && <span className="text-status-danger-text">— {r.message}</span>}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Progressive Hints */}
              {hintCount > 0 && ex.hints && (
                <div className="p-3 rounded-[10px] bg-status-warning-bg border border-status-warning-border space-y-1 text-xs text-status-warning-text">
                  {ex.hints.slice(0, hintCount).map((h, hIdx) => (
                    <p key={hIdx}>
                      <strong>Hint {hIdx + 1}:</strong> {h}
                    </p>
                  ))}
                </div>
              )}

              {/* Action Controls */}
              <div className="flex flex-wrap items-center gap-2.5 pt-1">
                {isCodeEx && (
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => handleRunCode(ex)}
                    isLoading={!!loadingRun[ex.id]}
                    icon={<Play className="h-3.5 w-3.5" />}
                  >
                    Run Tests
                  </Button>
                )}

                <Button
                  size="sm"
                  variant="primary"
                  onClick={() => handleSubmit(ex)}
                  isLoading={!!loadingSubmit[ex.id]}
                  disabled={!isCodeEx && !(selectedAnswers[ex.id] || '').trim()}
                  icon={<Send className="h-3.5 w-3.5" />}
                >
                  {isCodeEx ? 'Submit Solution' : 'Check Answer'}
                </Button>

                {totalHints > 0 && hintCount < totalHints && (
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() =>
                      setRevealedHints((p) => ({ ...p, [ex.id]: (p[ex.id] || 0) + 1 }))
                    }
                    icon={<Lightbulb className="h-3.5 w-3.5 text-status-warning-text" />}
                  >
                    {hintCount === 0 ? 'Show Hint' : 'Next Hint'}
                  </Button>
                )}
              </div>

              {/* Submission Feedback */}
              {sub && (
                <div
                  className={`p-3.5 rounded-[10px] border text-xs md:text-sm space-y-1.5 ${
                    sub.is_correct
                      ? 'bg-status-success-bg border-status-success-border text-status-success-text'
                      : 'bg-status-danger-bg border-status-danger-border text-status-danger-text'
                  }`}
                >
                  <div className="flex items-center gap-2 font-semibold">
                    {sub.is_correct ? (
                      <CheckCircle2 className="h-4 w-4 shrink-0" />
                    ) : (
                      <XCircle className="h-4 w-4 shrink-0" />
                    )}
                    <span>
                      {sub.is_correct ? 'Verified Correct' : 'Needs Revision'} (Attempt #
                      {sub.attempt_number})
                    </span>
                  </div>
                  <p className="text-ink-primary">{sub.feedback}</p>
                  {sub.explanation && (
                    <p className="text-xs text-ink-secondary pt-1 border-t border-line">
                      <strong>Why:</strong> {sub.explanation}
                    </p>
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
