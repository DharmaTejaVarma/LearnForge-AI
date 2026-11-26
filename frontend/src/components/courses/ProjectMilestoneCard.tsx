import React, { useState, useEffect } from 'react';
import { ProjectStepData, CodeRunResult, courseService } from '../../services/courseService';
import { Rocket, CheckCircle2, Copy, Check, RotateCcw, Play, Lightbulb, ChevronDown, ChevronUp } from 'lucide-react';

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
    <section className="mt-8 rounded-2xl border border-emerald-500/25 bg-gradient-to-br from-emerald-950/25 via-slate-950 to-slate-900 p-5 md:p-6 space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <span className="text-[11px] font-bold uppercase tracking-wider text-emerald-400">
            Continuous Course Project · {projectStep.project_name} (Stage {projectStep.step_number})
          </span>
          <h3 className="text-lg font-bold text-white flex items-center gap-2 mt-0.5">
            <Rocket className="h-5 w-5 text-emerald-400" />
            <span>{projectStep.milestone_title}</span>
          </h3>
        </div>

        <button
          type="button"
          onClick={toggleDone}
          className={`inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-xs font-semibold border transition-all self-start ${
            done
              ? 'bg-emerald-500/20 border-emerald-500/40 text-emerald-300'
              : 'bg-slate-900 border-slate-700 text-slate-300 hover:border-emerald-500/40'
          }`}
        >
          <CheckCircle2 className="h-4 w-4" />
          <span>{done ? 'Milestone Completed' : 'Mark Milestone Applied'}</span>
        </button>
      </div>

      {projectStep.learning_objective && (
        <p className="text-xs text-emerald-300/90 bg-emerald-500/10 border border-emerald-500/20 rounded-lg px-3 py-2">
          <span className="font-semibold">Objective: </span>
          {projectStep.learning_objective}
        </p>
      )}

      <p className="text-sm text-slate-200 leading-relaxed">{projectStep.deliverable}</p>

      {projectStep.requirements && projectStep.requirements.length > 0 && (
        <ul className="space-y-1.5 text-xs text-slate-300 bg-slate-950/60 border border-slate-800/80 rounded-xl p-3.5">
          {projectStep.requirements.map((req, idx) => (
            <li key={idx} className="flex items-start gap-2">
              <span className="text-emerald-400 font-bold">•</span>
              <span>{req}</span>
            </li>
          ))}
        </ul>
      )}

      {projectStep.starter_code && (
        <div className="rounded-xl border border-slate-800 bg-slate-950 overflow-hidden">
          <div className="flex items-center justify-between px-3.5 py-2 bg-slate-900 border-b border-slate-800 text-xs">
            <span className="font-mono text-emerald-300 font-semibold">
              creature_api_step_{projectStep.step_number}.py
            </span>
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={resetCode}
                className="inline-flex items-center gap-1 text-slate-400 hover:text-white"
              >
                <RotateCcw className="h-3.5 w-3.5" />
                <span>Reset</span>
              </button>
              <button
                type="button"
                onClick={copyCode}
                className="inline-flex items-center gap-1 text-slate-300 hover:text-white"
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
            className="w-full p-3.5 bg-slate-950 font-mono text-xs md:text-sm text-slate-200 focus:outline-none focus:ring-1 focus:ring-emerald-500/40"
          />
          <div className="flex flex-wrap items-center justify-between gap-2 px-3.5 py-2.5 bg-slate-900/90 border-t border-slate-800">
            <button
              type="button"
              onClick={runMilestoneTests}
              disabled={running}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-emerald-600 hover:bg-emerald-500 text-white disabled:opacity-50"
            >
              <Play className="h-3.5 w-3.5" />
              <span>{running ? 'Running...' : 'Run Milestone Tests'}</span>
            </button>
            {projectStep.expected_output && (
              <span className="text-[11px] font-mono text-slate-400">
                Expected: <span className="text-slate-200">{projectStep.expected_output}</span>
              </span>
            )}
          </div>
        </div>
      )}

      {runResult && (
        <div
          className={`rounded-xl border p-3.5 text-xs space-y-2 ${
            runResult.passed
              ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-200'
              : 'bg-rose-500/10 border-rose-500/30 text-rose-200'
          }`}
        >
          <div className="font-semibold">
            {runResult.passed
              ? `Passed (${runResult.passed_tests}/${runResult.total_tests} tests)`
              : `Failed (${runResult.passed_tests}/${runResult.total_tests} tests)`}
          </div>
          {runResult.stdout && (
            <pre className="p-2 rounded bg-slate-950 text-slate-200 font-mono overflow-x-auto">
              {runResult.stdout}
            </pre>
          )}
          {runResult.stderr && (
            <pre className="p-2 rounded bg-slate-950 text-rose-300 font-mono overflow-x-auto">
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
              className="inline-flex items-center gap-1.5 text-xs text-amber-300 hover:text-amber-200"
            >
              <Lightbulb className="h-3.5 w-3.5" />
              <span>{showHints ? 'Hide Hints' : 'Show Hints'}</span>
            </button>
          )}
          {projectStep.explanation && (
            <button
              type="button"
              onClick={() => setShowExplanation((v) => !v)}
              className="inline-flex items-center gap-1 text-xs text-indigo-300 hover:text-indigo-200"
            >
              {showExplanation ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
              <span>{showExplanation ? 'Hide Architecture Note' : 'Architecture Note'}</span>
            </button>
          )}
        </div>
      )}

      {showHints && projectStep.hints && projectStep.hints.length > 0 && (
        <ul className="space-y-1 text-xs text-amber-200/90 bg-amber-500/10 border border-amber-500/20 rounded-xl p-3">
          {projectStep.hints.map((h, i) => (
            <li key={i}>• {h}</li>
          ))}
        </ul>
      )}

      {showExplanation && projectStep.explanation && (
        <p className="text-xs text-slate-300 bg-slate-950/70 border border-slate-800 rounded-xl p-3 leading-relaxed">
          {projectStep.explanation}
        </p>
      )}
    </section>
  );
};
