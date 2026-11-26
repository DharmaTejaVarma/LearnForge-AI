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
    badge: 'bg-indigo-500/15 text-indigo-300 border-indigo-500/30',
  },
  coding: {
    label: 'Coding Lab',
    icon: <Code2 className="h-3.5 w-3.5" />,
    badge: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
  },
  debugging: {
    label: 'Debug Challenge',
    icon: <Bug className="h-3.5 w-3.5" />,
    badge: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
  },
  fill_blank: {
    label: 'Fill in the Blank',
    icon: <PenLine className="h-3.5 w-3.5" />,
    badge: 'bg-purple-500/15 text-purple-300 border-purple-500/30',
  },
  mini_task: {
    label: 'Applied Mini Task',
    icon: <Sparkles className="h-3.5 w-3.5" />,
    badge: 'bg-cyan-500/15 text-cyan-300 border-cyan-500/30',
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
    const initialCode: Record<number, string> = {};
    exercises.forEach((ex) => {
      if (ex.starter_code || ex.buggy_code) {
        initialCode[ex.id] = ex.starter_code || ex.buggy_code || '';
      }
    });
    setCodeInputs(initialCode);
    setSubmissions({});
    setRunOutputs({});
    setSelectedAnswers({});
    setRevealedHints({});
  }, [lessonId, exercises]);

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
      className="mt-10 pt-8 border-t border-slate-800 space-y-6"
    >
      {/* Header Row */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2.5">
            <span className="h-8 w-8 rounded-lg bg-indigo-500/15 border border-indigo-500/30 flex items-center justify-center text-indigo-400">
              <Sparkles className="h-4 w-4" />
            </span>
            Practice &amp; Test Your Knowledge
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Interactive exercises grounded in this lesson with instant feedback and isolated code checks.
          </p>
        </div>

        <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-slate-950 border border-slate-800 text-xs font-semibold">
          <CheckCircle2 className="h-4 w-4 text-emerald-400" />
          <span className="text-slate-200">
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
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              activeFilter === 'all'
                ? 'bg-indigo-600 text-white'
                : 'bg-slate-800/70 text-slate-300 hover:bg-slate-800'
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
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                  activeFilter === type
                    ? 'bg-indigo-600 text-white'
                    : 'bg-slate-800/70 text-slate-300 hover:bg-slate-800'
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
              className={`rounded-2xl border p-5 md:p-6 space-y-4 transition-all ${
                isSolved
                  ? 'bg-emerald-950/15 border-emerald-500/30'
                  : 'bg-slate-950/60 border-slate-800'
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
                  <span className="text-xs font-semibold text-slate-400">
                    #{idx + 1} · {ex.title}
                  </span>
                </div>

                <div className="flex items-center gap-2">
                  {isSolved && (
                    <span className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-400">
                      <CheckCircle2 className="h-4 w-4" />
                      Solved
                    </span>
                  )}
                  {onAskTutorHint && (
                    <button
                      type="button"
                      onClick={() => onAskTutorHint(ex)}
                      className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-indigo-300 text-[11px] font-medium border border-slate-700"
                    >
                      <Bot className="h-3.5 w-3.5" />
                      Ask Tutor Hint
                    </button>
                  )}
                </div>
              </div>

              {/* Prompt */}
              <div className="text-base text-slate-100 leading-relaxed">
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
                        className={`w-full text-left px-5 py-3.5 rounded-xl border text-sm md:text-base transition-all flex items-start gap-3 ${
                          selected
                            ? 'bg-indigo-600/20 border-indigo-500 text-white'
                            : 'bg-slate-900/70 border-slate-800 text-slate-300 hover:border-slate-700 hover:bg-slate-900'
                        }`}
                      >
                        <span
                          className={`mt-0.5 h-4 w-4 rounded-full border flex items-center justify-center shrink-0 text-[10px] font-bold ${
                            selected
                              ? 'border-indigo-400 bg-indigo-500 text-white'
                              : 'border-slate-600 text-slate-500'
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
                      className="w-full rounded-xl bg-slate-900 border border-slate-700 px-4 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                    />
                  ) : (
                    <textarea
                      rows={3}
                      value={selectedAnswers[ex.id] || ''}
                      onChange={(e) =>
                        setSelectedAnswers((p) => ({ ...p, [ex.id]: e.target.value }))
                      }
                      placeholder="Write your concise practical response..."
                      className="w-full rounded-xl bg-slate-900 border border-slate-700 px-4 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                    />
                  )}
                </div>
              )}

              {/* Coding / Debugging Isolated Editor */}
              {isCodeEx && (
                <div className="space-y-3">
                  <div className="rounded-xl border border-slate-800 bg-slate-950 overflow-hidden">
                    <div className="flex items-center justify-between px-3.5 py-2 bg-slate-900 border-b border-slate-800 text-[11px] text-slate-400">
                      <span className="font-mono font-semibold text-slate-300">
                        python_sandbox.py (Isolated Subprocess)
                      </span>
                      <button
                        type="button"
                        onClick={() =>
                          setCodeInputs((p) => ({
                            ...p,
                            [ex.id]: ex.starter_code || ex.buggy_code || '',
                          }))
                        }
                        className="inline-flex items-center gap-1 text-slate-400 hover:text-white"
                      >
                        <RotateCcw className="h-3 w-3" />
                        Reset Starter
                      </button>
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
                      className="w-full bg-slate-950 p-3.5 font-mono text-xs md:text-sm text-emerald-100 focus:outline-none resize-y"
                    />
                  </div>

                  {/* Test Run Results Output */}
                  {runOut && (
                    <div className="rounded-xl border border-slate-800 bg-slate-900/90 p-3.5 space-y-2 text-xs">
                      <div className="flex items-center justify-between font-semibold">
                        <span className={runOut.passed ? 'text-emerald-400' : 'text-amber-400'}>
                          {runOut.passed
                            ? `All ${runOut.total_tests} test(s) passed`
                            : `${runOut.passed_tests}/${runOut.total_tests} test(s) passed`}
                        </span>
                      </div>
                      {runOut.stdout && (
                        <pre className="p-2 rounded bg-slate-950 text-slate-300 font-mono overflow-x-auto">
                          {runOut.stdout}
                        </pre>
                      )}
                      {runOut.stderr && (
                        <pre className="p-2 rounded bg-rose-950/40 text-rose-300 font-mono overflow-x-auto">
                          {runOut.stderr}
                        </pre>
                      )}
                      {runOut.results?.map((r, rIdx) => (
                        <div key={rIdx} className="flex items-center gap-2">
                          {r.passed ? (
                            <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400 shrink-0" />
                          ) : (
                            <XCircle className="h-3.5 w-3.5 text-rose-400 shrink-0" />
                          )}
                          <span className="text-slate-300">{r.description}</span>
                          {!r.passed && <span className="text-rose-400">— {r.message}</span>}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Progressive Hints */}
              {hintCount > 0 && ex.hints && (
                <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/20 space-y-1 text-xs text-amber-200">
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
                    icon={<Lightbulb className="h-3.5 w-3.5 text-amber-400" />}
                  >
                    {hintCount === 0 ? 'Show Hint' : 'Next Hint'}
                  </Button>
                )}
              </div>

              {/* Submission Feedback */}
              {sub && (
                <div
                  className={`p-3.5 rounded-xl border text-xs md:text-sm space-y-1.5 ${
                    sub.is_correct
                      ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-200'
                      : 'bg-rose-500/10 border-rose-500/30 text-rose-200'
                  }`}
                >
                  <div className="flex items-center gap-2 font-semibold">
                    {sub.is_correct ? (
                      <CheckCircle2 className="h-4 w-4 text-emerald-400 shrink-0" />
                    ) : (
                      <XCircle className="h-4 w-4 text-rose-400 shrink-0" />
                    )}
                    <span>
                      {sub.is_correct ? 'Verified Correct' : 'Needs Revision'} (Attempt #
                      {sub.attempt_number})
                    </span>
                  </div>
                  <p className="text-slate-200">{sub.feedback}</p>
                  {sub.explanation && (
                    <p className="text-xs text-slate-300 pt-1 border-t border-white/10">
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
