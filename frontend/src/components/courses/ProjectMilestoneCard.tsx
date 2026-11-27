import React, { useState, useEffect } from 'react';
import { ProjectStepData, CodeRunResult, courseService } from '../../services/courseService';
import { Rocket, CheckCircle2, Copy, Check, RotateCcw, Play, Lightbulb, ChevronDown, ChevronUp, ExternalLink } from 'lucide-react';
import { Button } from '../common/Button';

interface ProjectMilestoneCardProps {
  lessonId: number;
  projectStep: ProjectStepData;
}

export const ProjectMilestoneCard: React.FC<ProjectMilestoneCardProps> = ({
  lessonId,
  projectStep,
}) => {
  const storageKey = `learnforge_project_done_${lessonId}`;
  const codeKey = `learnforge_project_code_${lessonId}`;
  const [done, setDone] = useState<boolean>(false);
  const [copied, setCopied] = useState<boolean>(false);
  const [code, setCode] = useState<string>(projectStep.starter_code || '');
  const [running, setRunning] = useState<boolean>(false);
  const [runResult, setRunResult] = useState<CodeRunResult | null>(null);
  const [showHints, setShowHints] = useState<boolean>(false);
  const [showExplanation, setShowExplanation] = useState<boolean>(false);

  useEffect(() => {
    setDone(localStorage.getItem(storageKey) === '1');
    const savedCode = localStorage.getItem(codeKey);
    setCode(savedCode !== null ? savedCode : projectStep.starter_code || '');
    setRunResult(null);
  }, [storageKey, codeKey, projectStep.starter_code]);

  const toggleDone = () => {
    const next = !done;
    setDone(next);
    localStorage.setItem(storageKey, next ? '1' : '0');
  };

  const handleCodeChange = (val: string) => {
    setCode(val);
    localStorage.setItem(codeKey, val);
  };

  const resetCode = () => {
    const starter = projectStep.starter_code || '';
    setCode(starter);
    localStorage.removeItem(codeKey);
    setRunResult(null);
  };

  const copyCode = async () => {
    if (!code) return;
    await navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  };

  const runMilestoneTests = async () => {
    if (!code.trim()) return;
    setRunning(true);
    try {
      const res = await courseService.runSandboxCode(code, projectStep.test_cases || []);
      setRunResult(res);
    } catch {
      setRunResult({
        passed: false,
        passed_tests: 0,
        total_tests: projectStep.test_cases?.length || 0,
        stdout: '',
        stderr: 'Failed to connect to sandbox runner.',
        results: [],
        timed_out: false,
      });
    } finally {
      setRunning(false);
    }
  };

  return (
    <section className="mt-8 rounded-[12px] border border-brand-soft-border bg-subtle p-5 md:p-6 space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <span className="text-[11px] font-bold uppercase tracking-wider text-accent">
            Continuous Course Project · {projectStep.project_name} (Stage {projectStep.step_number})
          </span>
          <h3 className="lf-heading-card flex items-center gap-2 mt-0.5">
            <Rocket className="h-5 w-5 text-brand" />
            <span>{projectStep.milestone_title}</span>
          </h3>
        </div>

        <div className="flex flex-wrap items-center gap-2 self-start">
          <a
            href={`/lessons/${lessonId}/project`}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold border border-brand-soft-border bg-brand-soft text-brand hover:bg-brand hover:text-white transition-all"
          >
            <ExternalLink className="h-3.5 w-3.5" />
            <span>Open in New Page</span>
          </a>
          <button
            type="button"
            onClick={toggleDone}
            className={`inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-xs font-semibold border transition-all ${
              done
                ? 'bg-status-success-bg border-status-success-border text-status-success-text'
                : 'bg-surface border-line text-ink-primary hover:border-brand-soft-border'
            }`}
          >
            <CheckCircle2 className="h-4 w-4" />
            <span>{done ? 'Milestone Completed' : 'Mark Milestone Applied'}</span>
          </button>
        </div>
      </div>

      {projectStep.learning_objective && (
        <p className="text-xs text-brand bg-brand-soft border border-brand-soft-border rounded-[10px] px-3 py-2">
          <span className="font-semibold">Objective: </span>
          {projectStep.learning_objective}
        </p>
      )}

      <p className="text-sm text-ink-primary leading-relaxed">{projectStep.deliverable}</p>

      {projectStep.requirements && projectStep.requirements.length > 0 && (
        <ul className="space-y-1.5 text-xs text-ink-primary bg-surface border border-line rounded-[10px] p-3.5">
          {projectStep.requirements.map((req, idx) => (
            <li key={idx} className="flex items-start gap-2">
              <span className="text-accent font-bold">•</span>
              <span>{req}</span>
            </li>
          ))}
        </ul>
      )}

      {projectStep.starter_code && (
        <div className="rounded-[12px] border border-codeblock-border bg-codeblock-bg overflow-hidden shadow-card">
          <div className="flex items-center justify-between px-3.5 py-2 bg-codeblock-header border-b border-codeblock-border text-xs">
            <span className="font-mono text-indigo-300 font-semibold">
              project_step_{projectStep.step_number}.py
            </span>
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={resetCode}
                className="inline-flex items-center gap-1 text-codeblock-muted hover:text-codeblock-text transition-colors"
              >
                <RotateCcw className="h-3.5 w-3.5" />
                <span>Reset</span>
              </button>
              <button
                type="button"
                onClick={copyCode}
                className="inline-flex items-center gap-1 text-codeblock-muted hover:text-codeblock-text transition-colors"
              >
                {copied ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
                <span>{copied ? 'Copied' : 'Copy'}</span>
              </button>
            </div>
          </div>
          <textarea
            rows={Math.min(12, Math.max(5, code.split('\n').length + 1))}
            spellCheck={false}
            value={code}
            onChange={(e) => handleCodeChange(e.target.value)}
            className="w-full p-3.5 bg-codeblock-bg font-mono text-xs md:text-sm text-codeblock-text focus:outline-none"
          />
          <div className="flex flex-wrap items-center justify-between gap-2 px-3.5 py-2.5 bg-codeblock-header border-t border-codeblock-border">
            <Button
              type="button"
              variant="primary"
              size="sm"
              onClick={runMilestoneTests}
              isLoading={running}
              icon={<Play className="h-3.5 w-3.5" />}
            >
              {running ? 'Running...' : 'Run Milestone Tests'}
            </Button>
            {projectStep.expected_output && (
              <span className="text-[11px] font-mono text-codeblock-muted">
                Expected: <span className="text-codeblock-text">{projectStep.expected_output}</span>
              </span>
            )}
          </div>
        </div>
      )}

      {runResult && (
        <div
          className={`rounded-[10px] border p-3.5 text-xs space-y-2 ${
            runResult.passed
              ? 'bg-status-success-bg border-status-success-border text-status-success-text'
              : 'bg-status-danger-bg border-status-danger-border text-status-danger-text'
          }`}
        >
          <div className="font-semibold">
            {runResult.passed
              ? `Passed (${runResult.passed_tests}/${runResult.total_tests} tests)`
              : `Failed (${runResult.passed_tests}/${runResult.total_tests} tests)`}
          </div>
          {runResult.stdout && (
            <pre className="p-2.5 rounded-[10px] bg-codeblock-bg text-codeblock-text font-mono overflow-x-auto">
              {runResult.stdout}
            </pre>
          )}
          {runResult.stderr && (
            <pre className="p-2.5 rounded-[10px] bg-codeblock-bg text-rose-300 font-mono overflow-x-auto">
              {runResult.stderr}
            </pre>
          )}
        </div>
      )}

      {((projectStep.hints && projectStep.hints.length > 0) || projectStep.explanation) && (
        <div className="flex flex-wrap gap-3 pt-1">
          {projectStep.hints && projectStep.hints.length > 0 && (
            <button
              type="button"
              onClick={() => setShowHints((v) => !v)}
              className="inline-flex items-center gap-1.5 text-xs font-medium text-status-warning-text hover:opacity-80"
            >
              <Lightbulb className="h-3.5 w-3.5" />
              <span>{showHints ? 'Hide Hints' : 'Show Hints'}</span>
            </button>
          )}
          {projectStep.explanation && (
            <button
              type="button"
              onClick={() => setShowExplanation((v) => !v)}
              className="inline-flex items-center gap-1 text-xs font-medium text-accent hover:text-accent-hover"
            >
              {showExplanation ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
              <span>{showExplanation ? 'Hide Architecture Note' : 'Architecture Note'}</span>
            </button>
          )}
        </div>
      )}

      {showHints && projectStep.hints && projectStep.hints.length > 0 && (
        <ul className="space-y-1 text-xs text-status-warning-text bg-status-warning-bg border border-status-warning-border rounded-[10px] p-3">
          {projectStep.hints.map((h, i) => (
            <li key={i}>• {h}</li>
          ))}
        </ul>
      )}

      {showExplanation && projectStep.explanation && (
        <p className="text-xs text-ink-primary bg-surface border border-line rounded-[10px] p-3 leading-relaxed">
          {projectStep.explanation}
        </p>
      )}
    </section>
  );
};
