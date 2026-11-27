import React, { useEffect, useState } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import {
  courseService,
  Lesson,
  LessonExercise,
  CodeRunResult,
  ExerciseSubmitResult,
} from '../../services/courseService';
import { MarkdownRenderer } from '../../components/courses/MarkdownRenderer';
import { Button } from '../../components/common/Button';
import { Spinner } from '../../components/common/Spinner';
import {
  ArrowLeft,
  Play,
  Send,
  RotateCcw,
  Copy,
  Check,
  CheckCircle2,
  XCircle,
  Lightbulb,
  Terminal,
  Code2,
  Bug,
  Rocket,
  Trash2,
} from 'lucide-react';

export const CodingWorkspace: React.FC = () => {
  const { lessonId, exerciseId } = useParams<{ lessonId: string; exerciseId?: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  const handleBackToLesson = () => {
    const cid =
      searchParams.get('courseId') ||
      (lessonId ? localStorage.getItem(`learnforge_lesson_course_${lessonId}`) : null);
    if (cid && lessonId) {
      localStorage.setItem(`learnforge_last_lesson_${cid}`, String(lessonId));
      navigate(`/courses/${cid}`);
      return;
    }
    if (cid) {
      navigate(`/courses/${cid}`);
      return;
    }
    if (window.history.length > 1) {
      navigate(-1);
    } else {
      navigate('/courses');
    }
  };

  const [lesson, setLesson] = useState<Lesson | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [activeMode, setActiveMode] = useState<'exercise' | 'project'>(
    exerciseId ? 'exercise' : 'project',
  );
  const [selectedExId, setSelectedExId] = useState<number | null>(
    exerciseId ? Number(exerciseId) : null,
  );

  const [code, setCode] = useState<string>('');
  const [copied, setCopied] = useState<boolean>(false);
  const [running, setRunning] = useState<boolean>(false);
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [runResult, setRunResult] = useState<CodeRunResult | null>(null);
  const [submitResult, setSubmitResult] = useState<ExerciseSubmitResult | null>(null);
  const [revealedHints, setRevealedHints] = useState<number>(0);
  const [showSolutionNote, setShowSolutionNote] = useState<boolean>(false);

  useEffect(() => {
    const load = async () => {
      if (!lessonId) return;
      setIsLoading(true);
      setLoadError(null);
      try {
        const data = await courseService.getLesson(Number(lessonId));
        setLesson(data);
        const codeExercises = (data.exercises || []).filter(
          (e) => e.exercise_type === 'coding' || e.exercise_type === 'debugging',
        );
        if (exerciseId) {
          const found = codeExercises.find((e) => e.id === Number(exerciseId)) || codeExercises[0];
          if (found) {
            setActiveMode('exercise');
            setSelectedExId(found.id);
            const savedCode = localStorage.getItem(`learnforge_ex_code_${data.id}_${found.id}`);
            const savedRun = localStorage.getItem(`learnforge_ex_run_${data.id}_${found.id}`);
            const savedSub = localStorage.getItem(`learnforge_ex_submit_${data.id}_${found.id}`);
            setCode(savedCode ?? (found.starter_code || found.buggy_code || ''));
            if (savedRun) try { setRunResult(JSON.parse(savedRun)); } catch {}
            if (savedSub) try { setSubmitResult(JSON.parse(savedSub)); } catch {}
          }
        } else if (data.structured_sections?.project_step) {
          setActiveMode('project');
          const savedProjCode = localStorage.getItem(`learnforge_project_code_${data.id}`);
          const savedProjRun = localStorage.getItem(`learnforge_project_run_${data.id}`);
          setCode(savedProjCode ?? (data.structured_sections.project_step.starter_code || ''));
          if (savedProjRun) try { setRunResult(JSON.parse(savedProjRun)); } catch {}
        } else if (codeExercises[0]) {
          setActiveMode('exercise');
          setSelectedExId(codeExercises[0].id);
          const savedCode = localStorage.getItem(`learnforge_ex_code_${data.id}_${codeExercises[0].id}`);
          setCode(savedCode ?? (codeExercises[0].starter_code || codeExercises[0].buggy_code || ''));
        }
      } catch (err: any) {
        setLoadError(err?.response?.data?.detail || 'Failed to load coding workspace.');
      } finally {
        setIsLoading(false);
      }
    };
    load();
  }, [lessonId, exerciseId]);

  const codeExercises: LessonExercise[] = (lesson?.exercises || []).filter(
    (e) => e.exercise_type === 'coding' || e.exercise_type === 'debugging',
  );
  const activeExercise =
    activeMode === 'exercise'
      ? codeExercises.find((e) => e.id === selectedExId) || codeExercises[0] || null
      : null;
  const projectStep = lesson?.structured_sections?.project_step || null;

  const selectExerciseTab = (ex: LessonExercise) => {
    setActiveMode('exercise');
    setSelectedExId(ex.id);
    const savedCode = lesson ? localStorage.getItem(`learnforge_ex_code_${lesson.id}_${ex.id}`) : null;
    const savedRun = lesson ? localStorage.getItem(`learnforge_ex_run_${lesson.id}_${ex.id}`) : null;
    const savedSub = lesson ? localStorage.getItem(`learnforge_ex_submit_${lesson.id}_${ex.id}`) : null;
    setCode(savedCode ?? (ex.starter_code || ex.buggy_code || ''));
    try { setRunResult(savedRun ? JSON.parse(savedRun) : null); } catch { setRunResult(null); }
    try { setSubmitResult(savedSub ? JSON.parse(savedSub) : null); } catch { setSubmitResult(null); }
    setRevealedHints(0);
    setShowSolutionNote(false);
  };

  const selectProjectTab = () => {
    if (!projectStep) return;
    setActiveMode('project');
    const savedProjCode = lesson ? localStorage.getItem(`learnforge_project_code_${lesson.id}`) : null;
    const savedProjRun = lesson ? localStorage.getItem(`learnforge_project_run_${lesson.id}`) : null;
    setCode(savedProjCode ?? (projectStep.starter_code || ''));
    try { setRunResult(savedProjRun ? JSON.parse(savedProjRun) : null); } catch { setRunResult(null); }
    setSubmitResult(null);
    setRevealedHints(0);
    setShowSolutionNote(false);
  };

  const handleRunTests = async () => {
    if (!lesson) return;
    setRunning(true);
    setRunResult(null);
    try {
      if (activeMode === 'exercise' && activeExercise) {
        const res = await courseService.runExerciseCode(lesson.id, activeExercise.id, code);
        setRunResult(res);
        localStorage.setItem(`learnforge_ex_run_${lesson.id}_${activeExercise.id}`, JSON.stringify(res));
      } else if (activeMode === 'project' && projectStep) {
        const res = await courseService.runSandboxCode(code, projectStep.test_cases || []);
        setRunResult(res);
        localStorage.setItem(`learnforge_project_run_${lesson.id}`, JSON.stringify(res));
        if (res.passed) {
          localStorage.setItem(`learnforge_project_done_${lesson.id}`, 'true');
        }
      }
    } catch (err: any) {
      setRunResult({
        passed: false,
        passed_tests: 0,
        total_tests: 0,
        stdout: '',
        stderr: err?.response?.data?.detail || 'Execution failed.',
        results: [],
        timed_out: false,
      });
    } finally {
      setRunning(false);
    }
  };

  const handleSubmit = async () => {
    if (!lesson || activeMode !== 'exercise' || !activeExercise) return;
    setSubmitting(true);
    try {
      const res = await courseService.submitExercise(lesson.id, activeExercise.id, { code });
      setSubmitResult(res);
      localStorage.setItem(`learnforge_ex_submit_${lesson.id}_${activeExercise.id}`, JSON.stringify(res));
      if (res.test_results) {
        const runRes: CodeRunResult = {
          passed: res.is_correct,
          passed_tests: res.test_results.filter((t: any) => t.passed).length,
          total_tests: res.test_results.length,
          stdout: res.stdout || '',
          stderr: res.stderr || '',
          results: res.test_results as any,
          timed_out: false,
        };
        setRunResult(runRes);
        localStorage.setItem(`learnforge_ex_run_${lesson.id}_${activeExercise.id}`, JSON.stringify(runRes));
      }
    } catch (err: any) {
      setSubmitResult({
        exercise_id: activeExercise.id,
        is_correct: false,
        score: 0,
        attempt_number: 1,
        feedback: err?.response?.data?.detail || 'Submission failed.',
      });
    } finally {
      setSubmitting(false);
    }
  };

  const handleReset = () => {
    if (activeMode === 'exercise' && activeExercise) {
      setCode(activeExercise.starter_code || activeExercise.buggy_code || '');
    } else if (activeMode === 'project' && projectStep) {
      setCode(projectStep.starter_code || '');
    }
    setRunResult(null);
    setSubmitResult(null);
  };

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      // ignore clipboard errors
    }
  };

  if (isLoading) {
    return (
      <div className="min-h-[70vh] flex flex-col items-center justify-center gap-3">
        <Spinner size="lg" />
        <p className="text-sm text-ink-secondary">Loading Coding Workspace...</p>
      </div>
    );
  }

  if (loadError || !lesson) {
    return (
      <div className="max-w-xl mx-auto mt-16 lf-card p-6 text-center space-y-4">
        <p className="text-sm text-status-danger-text">{loadError || 'Workspace not found.'}</p>
        <Button variant="secondary" onClick={handleBackToLesson} icon={<ArrowLeft className="h-4 w-4" />}>
          Back to Lesson
        </Button>
      </div>
    );
  }

  const title =
    activeMode === 'exercise' && activeExercise
      ? activeExercise.title
      : projectStep?.milestone_title || lesson.title;
  const promptText =
    activeMode === 'exercise' && activeExercise
      ? activeExercise.prompt
      : projectStep?.deliverable || '';
  const testCases =
    activeMode === 'exercise' && activeExercise
      ? activeExercise.test_cases || []
      : projectStep?.test_cases || [];
  const hints =
    activeMode === 'exercise' && activeExercise
      ? activeExercise.hints || []
      : projectStep?.hints || [];
  const expectedOutput =
    activeMode === 'exercise' && activeExercise
      ? activeExercise.expected_output
      : projectStep?.expected_output;
  const explanation =
    activeMode === 'project' ? projectStep?.explanation : submitResult?.explanation;

  return (
    <div className="space-y-4">
      {/* Top Workspace Header */}
      <div className="lf-card px-4 py-3 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3 min-w-0">
          <Button
            variant="secondary"
            size="sm"
            onClick={handleBackToLesson}
            icon={<ArrowLeft className="h-4 w-4" />}
          >
            Back to Lesson
          </Button>
          <div className="min-w-0">
            <p className="text-[11px] uppercase tracking-wider font-semibold text-ink-secondary truncate">
              {lesson.title}
            </p>
            <h1 className="text-base md:text-lg font-bold text-ink-primary truncate">{title}</h1>
          </div>
        </div>

        {/* Switch between coding exercises & project milestone in this lesson */}
        <div className="flex flex-wrap items-center gap-1.5">
          {codeExercises.map((ex, idx) => {
            const active = activeMode === 'exercise' && activeExercise?.id === ex.id;
            const savedSubRaw = localStorage.getItem(`learnforge_ex_submit_${lesson.id}_${ex.id}`);
            let savedSub: any = null;
            try { savedSub = savedSubRaw ? JSON.parse(savedSubRaw) : null; } catch {}
            const isPassed = Boolean(ex.latest_is_correct || savedSub?.is_correct || (active && submitResult?.is_correct));
            const isAttempted = Boolean(!isPassed && ((ex.attempts_count || 0) > 0 || savedSub || (active && submitResult)));
            return (
              <button
                key={ex.id}
                type="button"
                onClick={() => selectExerciseTab(ex)}
                className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-[10px] text-xs font-semibold border transition-colors ${
                  active
                    ? isPassed
                      ? 'bg-emerald-600 text-white border-emerald-600'
                      : 'bg-brand text-white border-brand'
                    : isPassed
                    ? 'bg-status-success-bg text-status-success-text border-status-success-border'
                    : isAttempted
                    ? 'bg-status-warning-bg text-status-warning-text border-status-warning-border'
                    : 'bg-subtle text-ink-secondary border-line hover:text-ink-primary'
                }`}
              >
                {isPassed ? (
                  <CheckCircle2 className="h-3.5 w-3.5" />
                ) : ex.exercise_type === 'debugging' ? (
                  <Bug className="h-3.5 w-3.5" />
                ) : (
                  <Code2 className="h-3.5 w-3.5" />
                )}
                <span>Lab {idx + 1}{isPassed ? ' ✓' : ''}</span>
              </button>
            );
          })}
          {projectStep && (() => {
            const projDone = localStorage.getItem(`learnforge_project_done_${lesson.id}`) === 'true';
            return (
              <button
                type="button"
                onClick={selectProjectTab}
                className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-[10px] text-xs font-semibold border transition-colors ${
                  activeMode === 'project'
                    ? projDone
                      ? 'bg-emerald-600 text-white border-emerald-600'
                      : 'bg-brand text-white border-brand'
                    : projDone
                    ? 'bg-status-success-bg text-status-success-text border-status-success-border'
                    : 'bg-subtle text-ink-secondary border-line hover:text-ink-primary'
                }`}
              >
                {projDone ? <CheckCircle2 className="h-3.5 w-3.5" /> : <Rocket className="h-3.5 w-3.5" />}
                <span>Project Step {projectStep.step_number}{projDone ? ' ✓' : ''}</span>
              </button>
            );
          })()}
        </div>
      </div>

      {/* Split-Pane IDE */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 items-start">
        {/* Left Pane: Problem, Test Cases, Hints */}
        <div className="lg:col-span-5 lf-card p-5 space-y-5 max-h-[calc(100vh-11rem)] overflow-y-auto">
          <div className="space-y-2">
            <h2 className="text-xs font-bold uppercase tracking-wider text-accent">
              Problem &amp; Requirements
            </h2>
            <MarkdownRenderer content={promptText} />
            {activeMode === 'project' && projectStep?.requirements && projectStep.requirements.length > 0 && (
              <ul className="space-y-1.5 text-xs text-ink-secondary pt-1">
                {projectStep.requirements.map((req, i) => (
                  <li key={i} className="flex items-start gap-2">
                    <span className="text-brand font-bold">•</span>
                    <span>{req}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {expectedOutput && (
            <div className="rounded-[10px] border border-line bg-subtle p-3 space-y-1">
              <p className="text-[11px] font-bold uppercase tracking-wider text-ink-secondary">
                Expected Output
              </p>
              <pre className="text-xs font-mono text-ink-primary whitespace-pre-wrap">{expectedOutput}</pre>
            </div>
          )}

          {/* Visible Test Cases */}
          <div className="space-y-2.5">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-bold uppercase tracking-wider text-ink-primary">
                Test Cases ({testCases.length})
              </h3>
              {runResult && (
                <span
                  className={`text-xs font-semibold ${
                    runResult.passed ? 'text-status-success-text' : 'text-status-warning-text'
                  }`}
                >
                  {runResult.passed_tests}/{runResult.total_tests} Passed
                </span>
              )}
            </div>

            {testCases.length === 0 ? (
              <p className="text-xs text-ink-secondary">
                No automated assertions attached — run your script to verify stdout output.
              </p>
            ) : (
              <div className="space-y-2">
                {testCases.map((tc: any, idx: number) => {
                  const resItem = runResult?.results?.[idx];
                  return (
                    <div
                      key={idx}
                      className={`rounded-[10px] border p-3 text-xs space-y-1.5 ${
                        resItem
                          ? resItem.passed
                            ? 'bg-status-success-bg border-status-success-border'
                            : 'bg-status-danger-bg border-status-danger-border'
                          : 'bg-subtle border-line'
                      }`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-semibold text-ink-primary">
                          Test {idx + 1}: {tc.description}
                        </span>
                        {resItem &&
                          (resItem.passed ? (
                            <CheckCircle2 className="h-4 w-4 text-status-success-text shrink-0" />
                          ) : (
                            <XCircle className="h-4 w-4 text-status-danger-text shrink-0" />
                          ))}
                      </div>
                      {tc.assert_code && (
                        <pre className="font-mono text-[11px] text-ink-secondary bg-surface px-2.5 py-1.5 rounded border border-line overflow-x-auto">
                          {tc.assert_code}
                        </pre>
                      )}
                      {resItem && !resItem.passed && resItem.message && (
                        <p className="text-status-danger-text font-medium">{resItem.message}</p>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Progressive Hints */}
          {hints.length > 0 && (
            <div className="space-y-2 pt-2 border-t border-line">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold uppercase tracking-wider text-ink-secondary flex items-center gap-1.5">
                  <Lightbulb className="h-3.5 w-3.5 text-status-warning-text" />
                  Hints ({revealedHints}/{hints.length})
                </span>
                {revealedHints < hints.length && (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => setRevealedHints((h) => Math.min(hints.length, h + 1))}
                  >
                    Reveal Next Hint
                  </Button>
                )}
              </div>
              {hints.slice(0, revealedHints).map((h, i) => (
                <div
                  key={i}
                  className="p-2.5 rounded-[10px] bg-status-warning-bg border border-status-warning-border text-xs text-status-warning-text"
                >
                  {h}
                </div>
              ))}
            </div>
          )}

          {explanation && (
            <div className="pt-2 border-t border-line space-y-1.5">
              <button
                type="button"
                onClick={() => setShowSolutionNote((v) => !v)}
                className="text-xs font-semibold text-brand hover:underline"
              >
                {showSolutionNote ? 'Hide Explanation' : 'View Explanation'}
              </button>
              {showSolutionNote && (
                <div className="p-3 rounded-[10px] bg-subtle border border-line text-xs text-ink-primary">
                  <MarkdownRenderer content={explanation} />
                </div>
              )}
            </div>
          )}
        </div>

        {/* Right Pane: Code Editor & Live Console */}
        <div className="lg:col-span-7 space-y-3">
          <div className="rounded-[12px] border border-codeblock-border bg-codeblock-bg overflow-hidden shadow-card">
            <div className="flex items-center justify-between px-4 py-2.5 bg-codeblock-header border-b border-codeblock-border text-xs">
              <span className="font-mono font-semibold text-codeblock-text">
                {activeMode === 'project' && projectStep
                  ? `project_step_${projectStep.step_number}.py`
                  : 'solution_sandbox.py'}
              </span>
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={handleReset}
                  className="inline-flex items-center gap-1 text-codeblock-muted hover:text-codeblock-text transition-colors"
                >
                  <RotateCcw className="h-3.5 w-3.5" />
                  <span>Reset</span>
                </button>
                <button
                  type="button"
                  onClick={handleCopy}
                  className="inline-flex items-center gap-1 text-codeblock-muted hover:text-codeblock-text transition-colors"
                >
                  {copied ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
                  <span>{copied ? 'Copied' : 'Copy'}</span>
                </button>
              </div>
            </div>

            <textarea
              rows={18}
              spellCheck={false}
              value={code}
              onKeyDown={(e) => {
                if (e.key === 'Tab') {
                  e.preventDefault();
                  const target = e.currentTarget;
                  const start = target.selectionStart;
                  const end = target.selectionEnd;
                  const updated = code.substring(0, start) + '    ' + code.substring(end);
                  setCode(updated);
                  setTimeout(() => {
                    target.selectionStart = target.selectionEnd = start + 4;
                  }, 0);
                }
              }}
              onChange={(e) => {
                const val = e.target.value;
                setCode(val);
                if (lesson) {
                  if (activeMode === 'exercise' && activeExercise) {
                    localStorage.setItem(`learnforge_ex_code_${lesson.id}_${activeExercise.id}`, val);
                  } else if (activeMode === 'project') {
                    localStorage.setItem(`learnforge_project_code_${lesson.id}`, val);
                  }
                }
              }}
              className="w-full p-4 bg-codeblock-bg font-mono text-xs md:text-sm text-codeblock-text focus:outline-none resize-y leading-relaxed"
            />

            <div className="flex flex-wrap items-center justify-between gap-2 px-4 py-3 bg-codeblock-header border-t border-codeblock-border">
              <div className="flex items-center gap-2">
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={handleRunTests}
                  isLoading={running}
                  icon={<Play className="h-3.5 w-3.5" />}
                >
                  Run Tests
                </Button>
                {activeMode === 'exercise' && activeExercise && (() => {
                  const isCurrentPassed = Boolean(submitResult?.is_correct || activeExercise.latest_is_correct);
                  const isCurrentAttempted = Boolean(!isCurrentPassed && (submitResult || (activeExercise.attempts_count || 0) > 0));
                  return (
                    <Button
                      type="button"
                      variant={isCurrentPassed ? 'secondary' : 'primary'}
                      size="sm"
                      onClick={handleSubmit}
                      isLoading={submitting}
                      className={
                        isCurrentPassed
                          ? '!bg-emerald-600 hover:!bg-emerald-500 !text-white !border-emerald-600'
                          : isCurrentAttempted
                          ? '!bg-amber-600 hover:!bg-amber-500 !text-white !border-amber-600'
                          : ''
                      }
                      icon={isCurrentPassed ? <CheckCircle2 className="h-3.5 w-3.5" /> : <Send className="h-3.5 w-3.5" />}
                    >
                      {isCurrentPassed ? 'Submitted ✓' : isCurrentAttempted ? 'Resubmit Solution' : 'Submit Solution'}
                    </Button>
                  );
                })()}
              </div>

              {runResult && (
                <button
                  type="button"
                  onClick={() => {
                    setRunResult(null);
                    setSubmitResult(null);
                  }}
                  className="inline-flex items-center gap-1 text-xs text-codeblock-muted hover:text-codeblock-text"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                  <span>Clear Output</span>
                </button>
              )}
            </div>
          </div>

          {/* Submission Feedback */}
          {submitResult && (
            <div
              className={`rounded-[10px] border p-3.5 text-xs flex items-start gap-2.5 ${
                submitResult.is_correct
                  ? 'bg-status-success-bg border-status-success-border text-status-success-text'
                  : 'bg-status-danger-bg border-status-danger-border text-status-danger-text'
              }`}
            >
              {submitResult.is_correct ? (
                <CheckCircle2 className="h-4 w-4 shrink-0 mt-0.5" />
              ) : (
                <XCircle className="h-4 w-4 shrink-0 mt-0.5" />
              )}
              <div>
                <p className="font-semibold">
                  {submitResult.is_correct ? 'Solution Accepted!' : 'Needs Revision'} — Score:{' '}
                  {submitResult.score}%
                </p>
                <p className="mt-0.5">{submitResult.feedback}</p>
              </div>
            </div>
          )}

          {/* Console Output */}
          {runResult && (
            <div className="lf-card p-4 space-y-2.5 text-xs">
              <div className="flex items-center justify-between">
                <span className="font-bold uppercase tracking-wider text-ink-secondary flex items-center gap-1.5">
                  <Terminal className="h-3.5 w-3.5" />
                  Sandbox Console Output
                </span>
                <span
                  className={`font-semibold ${
                    runResult.passed ? 'text-status-success-text' : 'text-status-danger-text'
                  }`}
                >
                  {runResult.timed_out
                    ? 'Execution Timed Out'
                    : runResult.passed
                    ? 'Passed'
                    : 'Failed'}
                </span>
              </div>
              {runResult.stdout && (
                <pre className="p-3 rounded-[10px] bg-codeblock-bg text-codeblock-text font-mono overflow-x-auto">
                  {runResult.stdout}
                </pre>
              )}
              {runResult.stderr && (
                <pre className="p-3 rounded-[10px] bg-codeblock-bg text-rose-300 font-mono overflow-x-auto">
                  {runResult.stderr}
                </pre>
              )}
              {!runResult.stdout && !runResult.stderr && (
                <p className="text-ink-secondary italic">No stdout/stderr output produced.</p>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
