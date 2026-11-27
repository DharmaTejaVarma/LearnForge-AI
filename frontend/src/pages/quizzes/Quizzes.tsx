import React, { useState, useEffect, useCallback } from 'react';
import { Card } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { Spinner } from '../../components/common/Spinner';
import { learningService, Quiz, QuizListItem, QuizAttemptDetail } from '../../services/learningService';
import { documentService, UploadedDocument } from '../../services/documentService';
import { courseService, Course } from '../../services/courseService';
import { formatDocumentTitle, formatFriendlyDate } from '../../utils/formatters';
import {
  Trophy,
  BookOpen,
  CheckCircle2,
  XCircle,
  ArrowRight,
  RotateCcw,
  Sparkles,
  AlertCircle,
  ChevronDown,
  ChevronRight,
  Clock,
  Trash2,
  Play,
} from 'lucide-react';

type ScopeType = 'document' | 'course';

interface QuestionResultProps {
  idx: number;
  questionText: string;
  questionType?: string;
  options: string[];
  correctAnswer: string;
  selectedAnswer: string;
  isCorrect: boolean;
  explanation: string;
}

const QuestionResultCard: React.FC<QuestionResultProps> = ({
  idx,
  questionText,
  questionType,
  options,
  correctAnswer,
  selectedAnswer,
  isCorrect,
  explanation,
}) => {
  const [expanded, setExpanded] = useState(!isCorrect);

  return (
    <Card
      className={`p-5 ${
        isCorrect ? '' : 'border-status-danger-border bg-status-danger-bg'
      }`}
    >
      <div className="flex items-start gap-3">
        <div
          className={`shrink-0 mt-0.5 rounded-full p-0.5 ${
            isCorrect ? 'text-status-success-text' : 'text-status-danger-text'
          }`}
        >
          {isCorrect ? <CheckCircle2 className="h-5 w-5" /> : <XCircle className="h-5 w-5" />}
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-ink-primary leading-snug mb-2">
            <span className="text-ink-secondary mr-1">Q{idx + 1}.</span>
            {questionText}
          </p>

          {questionType === 'short_answer' || !options || options.length === 0 ? (
            <div className="space-y-1.5 mb-3 text-xs">
              <div className="px-3 py-2 rounded-[10px] bg-subtle border border-line text-ink-primary">
                <span className="text-ink-secondary font-medium">Your answer: </span>
                {selectedAnswer || <em className="text-ink-secondary">Unanswered</em>}
              </div>
              <div className="px-3 py-2 rounded-[10px] bg-status-success-bg border border-status-success-border text-status-success-text">
                <span className="font-medium">Reference answer: </span>
                {correctAnswer}
              </div>
            </div>
          ) : (
            <div className="space-y-1.5 mb-3">
              {options.map((opt, oi) => {
                const isSelected = opt === selectedAnswer;
                const isCorrectOpt = opt === correctAnswer;
                return (
                  <div
                    key={oi}
                    className={`px-3 py-2 rounded-[10px] text-xs border flex items-center justify-between ${
                      isCorrectOpt
                        ? 'bg-status-success-bg border-status-success-border text-status-success-text font-medium'
                        : isSelected
                        ? 'bg-status-danger-bg border-status-danger-border text-status-danger-text font-medium'
                        : 'bg-subtle border-line text-ink-secondary'
                    }`}
                  >
                    <span>{opt}</span>
                    {isCorrectOpt && <CheckCircle2 className="h-3.5 w-3.5 shrink-0" />}
                    {isSelected && !isCorrectOpt && <XCircle className="h-3.5 w-3.5 shrink-0" />}
                  </div>
                );
              })}
            </div>
          )}

          {explanation && (
            <button
              type="button"
              onClick={() => setExpanded((v) => !v)}
              className="flex items-center gap-1 text-xs font-medium text-accent hover:text-accent-hover transition-colors"
            >
              {expanded ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
              {expanded ? 'Hide' : 'Show'} explanation
            </button>
          )}
          {expanded && explanation && (
            <div className="mt-2 p-3 bg-brand-soft border border-brand-soft-border rounded-[10px] text-xs text-ink-primary leading-relaxed">
              {explanation}
            </div>
          )}
        </div>
      </div>
    </Card>
  );
};

export const Quizzes: React.FC = () => {
  const [documents, setDocuments] = useState<UploadedDocument[]>([]);
  const [courses, setCourses] = useState<Course[]>([]);
  const [pastQuizzes, setPastQuizzes] = useState<QuizListItem[]>([]);
  const [selectedDocId, setSelectedDocId] = useState<number | null>(null);
  const [selectedCourseId, setSelectedCourseId] = useState<number | null>(null);
  const [scopeType, setScopeType] = useState<ScopeType>('document');
  const [questionCount, setQuestionCount] = useState<number>(5);
  const [difficulty, setDifficulty] = useState<string>('medium');
  const [questionType, setQuestionType] = useState<string>('mcq');
  const [useTimer, setUseTimer] = useState<boolean>(false);
  const [elapsedSeconds, setElapsedSeconds] = useState<number>(0);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [activeQuiz, setActiveQuiz] = useState<Quiz | null>(null);
  const [selectedAnswers, setSelectedAnswers] = useState<Record<number, string>>({});
  const [quizResult, setQuizResult] = useState<QuizAttemptDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    try {
      const [docsData, coursesData, quizzesData] = await Promise.all([
        documentService.list(),
        courseService.list(),
        learningService.listQuizzes(),
      ]);
      setDocuments(docsData);
      setCourses(coursesData);
      setPastQuizzes(quizzesData);
      if (docsData.length > 0 && !selectedDocId) {
        setSelectedDocId(docsData[0].id);
      }
      if (coursesData.length > 0 && !selectedCourseId) {
        setSelectedCourseId(coursesData[0].id);
      }
    } catch (err) {
      console.error('Failed to load quiz resources:', err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  useEffect(() => {
    if (!activeQuiz || quizResult || !useTimer) return;
    const timer = setInterval(() => setElapsedSeconds((s) => s + 1), 1000);
    return () => clearInterval(timer);
  }, [activeQuiz, quizResult, useTimer]);

  const formatTimer = (secs: number) => {
    const mins = Math.floor(secs / 60);
    const rem = secs % 60;
    return `${String(mins).padStart(2, '0')}:${String(rem).padStart(2, '0')}`;
  };

  const handleGenerate = async (e: React.FormEvent) => {
    e.preventDefault();
    const docId = scopeType === 'document' ? selectedDocId : undefined;
    const courseId = scopeType === 'course' ? selectedCourseId : undefined;
    if (!docId && !courseId) return;

    setIsGenerating(true);
    setError(null);
    try {
      const quiz = await learningService.generateQuiz(
        docId ?? undefined,
        courseId ?? undefined,
        questionCount,
        difficulty,
        questionType,
      );
      setActiveQuiz(quiz);
      setSelectedAnswers({});
      setQuizResult(null);
      setElapsedSeconds(0);
      loadData();
    } catch (err: any) {
      setError('Failed to generate quiz: ' + (err.response?.data?.error?.message || err.message));
    } finally {
      setIsGenerating(false);
    }
  };

  const handleOpenQuiz = async (quizId: number) => {
    setError(null);
    try {
      const quiz = await learningService.getQuiz(quizId);
      setActiveQuiz(quiz);
      setSelectedAnswers({});
      setQuizResult(null);
      setElapsedSeconds(0);
    } catch (err: any) {
      setError('Unable to load selected quiz.');
    }
  };

  const handleDeleteQuiz = async (quizId: number) => {
    try {
      await learningService.deleteQuiz(quizId);
      setPastQuizzes((prev) => prev.filter((q) => q.id !== quizId));
    } catch (err) {
      console.error('Delete quiz failed:', err);
    }
  };

  const handleSelectOption = (questionId: number, option: string) => {
    setSelectedAnswers((prev) => ({ ...prev, [questionId]: option }));
  };

  const handleSubmit = async () => {
    if (!activeQuiz) return;
    setIsSubmitting(true);
    setError(null);
    try {
      const result = await learningService.submitQuiz(activeQuiz.id, selectedAnswers);
      setQuizResult(result);
    } catch (err: any) {
      setError('Failed to submit quiz: ' + (err.response?.data?.error?.message || err.message));
    } finally {
      setIsSubmitting(false);
    }
  };

  const answeredCount = Object.values(selectedAnswers).filter((v) => v && v.trim().length > 0).length;
  const totalCount = activeQuiz?.questions.length ?? 0;

  const scoreColor =
    (quizResult?.score_percentage ?? 0) >= 80
      ? 'text-status-success-text'
      : (quizResult?.score_percentage ?? 0) >= 60
      ? 'text-status-warning-text'
      : 'text-status-danger-text';

  if (isLoading) return <Spinner size="lg" />;

  return (
    <div className="space-y-6 max-w-3xl mx-auto">
      {/* Header */}
      <div>
        <h1 className="lf-heading-main flex items-center gap-2.5">
          <BookOpen className="h-7 w-7 text-accent" />
          <span>Quizzes</span>
        </h1>
        <p className="text-sm text-ink-secondary mt-1">
          Adaptive assessments (MCQ, True/False, Short Answer) grounded in your study materials
        </p>
      </div>

      {/* Error */}
      {error && (
        <div className="flex items-start gap-3 p-3.5 bg-status-danger-bg border border-status-danger-border rounded-[12px] text-status-danger-text text-sm">
          <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {!activeQuiz ? (
        <div className="space-y-6">
          {/* Generation Form */}
          <Card className="p-6 space-y-5">
            <h2 className="lf-heading-card">Generate a New Quiz</h2>

            <form onSubmit={handleGenerate} className="space-y-4">
              <div>
                <label className="lf-label-sm mb-1.5 block">Source</label>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => setScopeType('document')}
                    className={`flex-1 py-2 rounded-[10px] text-xs font-medium transition-colors ${
                      scopeType === 'document'
                        ? 'bg-brand text-white'
                        : 'bg-subtle text-ink-secondary hover:text-ink-primary hover:bg-hoverbg'
                    }`}
                  >
                    By Document
                  </button>
                  <button
                    type="button"
                    onClick={() => setScopeType('course')}
                    className={`flex-1 py-2 rounded-[10px] text-xs font-medium transition-colors ${
                      scopeType === 'course'
                        ? 'bg-brand text-white'
                        : 'bg-subtle text-ink-secondary hover:text-ink-primary hover:bg-hoverbg'
                    }`}
                  >
                    By Course
                  </button>
                </div>
              </div>

              <div>
                <label className="lf-label-sm mb-1.5 block">
                  {scopeType === 'document' ? 'Document' : 'Course'}
                </label>
                {scopeType === 'document' ? (
                  <select
                    value={selectedDocId || ''}
                    onChange={(e) => setSelectedDocId(Number(e.target.value))}
                    className="lf-control w-full text-sm px-3 py-2"
                    required
                  >
                    {documents.length === 0 ? (
                      <option value="">No documents uploaded</option>
                    ) : (
                      documents.map((d) => (
                        <option key={d.id} value={d.id}>
                          {formatDocumentTitle(d.original_filename)}
                        </option>
                      ))
                    )}
                  </select>
                ) : (
                  <select
                    value={selectedCourseId || ''}
                    onChange={(e) => setSelectedCourseId(Number(e.target.value))}
                    className="lf-control w-full text-sm px-3 py-2"
                    required
                  >
                    {courses.length === 0 ? (
                      <option value="">No courses available</option>
                    ) : (
                      courses.map((c) => (
                        <option key={c.id} value={c.id}>
                          {c.title}
                        </option>
                      ))
                    )}
                  </select>
                )}
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div>
                  <label className="lf-label-sm mb-1.5 block">Questions</label>
                  <select
                    value={questionCount}
                    onChange={(e) => setQuestionCount(Number(e.target.value))}
                    className="lf-control w-full text-sm px-3 py-2"
                  >
                    <option value={5}>5 Questions</option>
                    <option value={10}>10 Questions</option>
                    <option value={15}>15 Questions</option>
                  </select>
                </div>
                <div>
                  <label className="lf-label-sm mb-1.5 block">Difficulty</label>
                  <select
                    value={difficulty}
                    onChange={(e) => setDifficulty(e.target.value)}
                    className="lf-control w-full text-sm px-3 py-2"
                  >
                    <option value="easy">Easy</option>
                    <option value="medium">Medium</option>
                    <option value="hard">Hard</option>
                  </select>
                </div>
                <div>
                  <label className="lf-label-sm mb-1.5 block">Question Format</label>
                  <select
                    value={questionType}
                    onChange={(e) => setQuestionType(e.target.value)}
                    className="lf-control w-full text-sm px-3 py-2"
                  >
                    <option value="mcq">Multiple Choice (MCQ)</option>
                    <option value="true_false">True / False</option>
                    <option value="short_answer">Short Answer</option>
                    <option value="mixed">Mixed Format</option>
                  </select>
                </div>
              </div>

              <label className="flex items-center gap-2 text-xs text-ink-primary cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={useTimer}
                  onChange={(e) => setUseTimer(e.target.checked)}
                  className="rounded border-line-strong text-brand focus:ring-brand accent-brand"
                />
                <span>Enable session stopwatch during assessment</span>
              </label>

              <Button
                type="submit"
                variant="primary"
                className="w-full"
                isLoading={isGenerating}
                disabled={
                  (scopeType === 'document' && !selectedDocId && documents.length === 0) ||
                  (scopeType === 'course' && !selectedCourseId && courses.length === 0)
                }
                icon={<Sparkles className="h-4 w-4" />}
              >
                Generate Quiz
              </Button>
            </form>
          </Card>

          {/* Past Quizzes */}
          {pastQuizzes.length > 0 && (
            <Card title={`Recent Quizzes (${pastQuizzes.length})`}>
              <div className="divide-y divide-line">
                {pastQuizzes.slice(0, 6).map((q) => (
                  <div key={q.id} className="py-3 flex items-center justify-between gap-3">
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-ink-primary truncate">{q.title}</p>
                      <p className="text-xs text-ink-secondary mt-0.5">
                        {q.question_count} questions • {formatFriendlyDate(q.created_at)}
                      </p>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <Button size="sm" variant="secondary" onClick={() => handleOpenQuiz(q.id)} icon={<Play className="h-3.5 w-3.5" />}>
                        Take
                      </Button>
                      <button
                        type="button"
                        onClick={() => handleDeleteQuiz(q.id)}
                        className="p-2 rounded-[10px] text-ink-secondary hover:text-status-danger-text hover:bg-status-danger-bg transition-colors"
                        title="Delete quiz"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          )}
        </div>
      ) : quizResult ? (
        /* Results Panel */
        <div className="space-y-5">
          <Card className="p-8 text-center">
            <div className="h-16 w-16 rounded-full bg-brand-soft border border-brand-soft-border flex items-center justify-center mx-auto text-brand mb-4">
              <Trophy className="h-8 w-8" />
            </div>
            <span className="text-xs font-semibold uppercase tracking-wider text-accent">
              Assessment Complete
            </span>
            <h2 className={`text-4xl font-bold mt-2 ${scoreColor}`}>
              {quizResult.score_percentage}%
            </h2>
            <p className="text-sm text-ink-secondary mt-1">
              {quizResult.correct_answers_count} of {quizResult.total_questions} correct
              {useTimer && elapsedSeconds > 0 ? ` • Time: ${formatTimer(elapsedSeconds)}` : ''}
            </p>

            <div className="mt-4 p-4 rounded-[12px] bg-subtle border border-line text-sm text-ink-primary text-left max-w-md mx-auto">
              <p className="font-semibold text-accent text-xs uppercase mb-1">Feedback</p>
              <p className="text-xs text-ink-secondary leading-relaxed">{quizResult.feedback}</p>
            </div>

            <div className="flex justify-center gap-3 mt-6">
              <Button
                variant="secondary"
                onClick={() => {
                  setActiveQuiz(null);
                  setQuizResult(null);
                }}
                icon={<RotateCcw className="h-4 w-4" />}
              >
                Back to Quizzes
              </Button>
            </div>
          </Card>

          {quizResult.question_results && quizResult.question_results.length > 0 && (
            <div className="space-y-3">
              <h3 className="text-sm font-semibold text-ink-primary">Question Review</h3>
              {quizResult.question_results.map((qr, idx) => (
                <QuestionResultCard
                  key={qr.question_id}
                  idx={idx}
                  questionText={qr.question_text}
                  questionType={qr.question_type}
                  options={qr.options}
                  correctAnswer={qr.correct_answer}
                  selectedAnswer={qr.selected_answer}
                  isCorrect={qr.is_correct}
                  explanation={qr.explanation}
                />
              ))}
            </div>
          )}
        </div>
      ) : (
        /* Quiz Taker */
        <div className="space-y-5">
          <div className="flex items-center justify-between pb-3 border-b border-line">
            <div>
              <h2 className="lf-heading-card">{activeQuiz.title}</h2>
              {activeQuiz.description && (
                <p className="text-xs text-ink-secondary mt-0.5">{activeQuiz.description}</p>
              )}
            </div>
            <div className="flex items-center gap-3 shrink-0 ml-3 text-xs text-ink-secondary">
              {useTimer && (
                <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-[10px] bg-brand-soft border border-brand-soft-border text-brand font-mono">
                  <Clock className="h-3 w-3" />
                  {formatTimer(elapsedSeconds)}
                </span>
              )}
              <span>
                {answeredCount} / {totalCount} answered
              </span>
            </div>
          </div>

          <div className="h-1.5 bg-subtle rounded-full overflow-hidden">
            <div
              className="h-full bg-accent rounded-full transition-all"
              style={{ width: `${totalCount > 0 ? (answeredCount / totalCount) * 100 : 0}%` }}
            />
          </div>

          <div className="space-y-5">
            {activeQuiz.questions.map((q, qIdx) => (
              <Card key={q.id} className="p-5 space-y-4">
                <div className="flex items-start gap-3">
                  <span className="h-6 w-6 rounded-full bg-brand-soft text-brand border border-brand-soft-border text-xs flex items-center justify-center font-bold shrink-0">
                    {qIdx + 1}
                  </span>
                  <div className="space-y-1 flex-1">
                    <h4 className="text-sm font-semibold text-ink-primary leading-relaxed">{q.question_text}</h4>
                    <span className="inline-block text-[10px] uppercase tracking-wider px-2 py-0.5 rounded bg-subtle text-ink-secondary border border-line">
                      {(q.question_type || 'mcq').replace('_', ' ')}
                    </span>
                  </div>
                </div>

                {q.question_type === 'short_answer' || !q.options || q.options.length === 0 ? (
                  <div className="pl-9">
                    <textarea
                      rows={3}
                      value={selectedAnswers[q.id] || ''}
                      onChange={(e) => handleSelectOption(q.id, e.target.value)}
                      placeholder="Type your concise answer grounded in course concepts..."
                      className="lf-control w-full p-3 text-sm"
                    />
                  </div>
                ) : (
                  <div className="space-y-2 pl-9">
                    {q.options.map((opt, optIdx) => {
                      const isSelected = selectedAnswers[q.id] === opt;
                      return (
                        <div
                          key={optIdx}
                          onClick={() => handleSelectOption(q.id, opt)}
                          className={`cursor-pointer p-3 rounded-[10px] border text-sm transition-all flex items-center justify-between ${
                            isSelected
                              ? 'bg-hoverbg border-brand text-ink-primary font-medium'
                              : 'bg-surface border-line text-ink-secondary hover:bg-hoverbg hover:text-ink-primary hover:border-brand-soft-border'
                          }`}
                        >
                          <span>{opt}</span>
                          {isSelected && <CheckCircle2 className="h-4 w-4 text-accent shrink-0" />}
                        </div>
                      );
                    })}
                  </div>
                )}
              </Card>
            ))}
          </div>

          <div className="flex justify-between items-center pt-2">
            <Button
              variant="ghost"
              onClick={() => {
                setActiveQuiz(null);
                setQuizResult(null);
              }}
            >
              Cancel
            </Button>
            <div className="flex items-center gap-3">
              {answeredCount < totalCount && (
                <span className="text-xs text-status-warning-text font-medium">
                  {totalCount - answeredCount} question{totalCount - answeredCount !== 1 ? 's' : ''} unanswered
                </span>
              )}
              <Button
                variant="primary"
                onClick={handleSubmit}
                isLoading={isSubmitting}
                disabled={answeredCount === 0}
                icon={<ArrowRight className="h-4 w-4" />}
              >
                Submit Assessment
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
