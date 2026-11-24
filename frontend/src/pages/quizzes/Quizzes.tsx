import React, { useState, useEffect, useCallback } from 'react';
import { Card } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { Spinner } from '../../components/common/Spinner';
import { learningService, Quiz, QuizAttemptDetail } from '../../services/learningService';
import { documentService, UploadedDocument } from '../../services/documentService';
import { courseService, Course } from '../../services/courseService';
import { formatDocumentTitle } from '../../utils/formatters';
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
} from 'lucide-react';

type ScopeType = 'document' | 'course';

interface QuestionResultProps {
  idx: number;
  questionText: string;
  options: string[];
  correctAnswer: string;
  selectedAnswer: string;
  isCorrect: boolean;
  explanation: string;
}

const QuestionResultCard: React.FC<QuestionResultProps> = ({
  idx,
  questionText,
  options,
  correctAnswer,
  selectedAnswer,
  isCorrect,
  explanation,
}) => {
  const [expanded, setExpanded] = useState(!isCorrect);

  return (
    <Card className={`p-5 border ${isCorrect ? 'bg-slate-900 border-slate-800' : 'bg-red-900/10 border-red-500/30'}`}>
      <div className="flex items-start gap-3">
        <div className={`shrink-0 mt-0.5 rounded-full p-0.5 ${isCorrect ? 'text-emerald-400' : 'text-red-400'}`}>
          {isCorrect ? <CheckCircle2 className="h-5 w-5" /> : <XCircle className="h-5 w-5" />}
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-white leading-snug mb-2">
            <span className="text-slate-400 mr-1">Q{idx + 1}.</span>
            {questionText}
          </p>

          {/* Options */}
          <div className="space-y-1.5 mb-3">
            {options.map((opt, oi) => {
              const isSelected = opt === selectedAnswer;
              const isCorrectOpt = opt === correctAnswer;
              return (
                <div
                  key={oi}
                  className={`px-3 py-2 rounded-lg text-xs border flex items-center justify-between ${
                    isCorrectOpt
                      ? 'bg-emerald-500/20 border-emerald-500/40 text-emerald-200'
                      : isSelected
                      ? 'bg-red-500/20 border-red-500/40 text-red-200'
                      : 'bg-slate-800/40 border-slate-700/40 text-slate-400'
                  }`}
                >
                  <span>{opt}</span>
                  {isCorrectOpt && <CheckCircle2 className="h-3.5 w-3.5 shrink-0" />}
                  {isSelected && !isCorrectOpt && <XCircle className="h-3.5 w-3.5 shrink-0" />}
                </div>
              );
            })}
          </div>

          {/* Explanation toggle */}
          {explanation && (
            <button
              onClick={() => setExpanded((v) => !v)}
              className="flex items-center gap-1 text-xs text-indigo-400 hover:text-indigo-300 transition-colors"
            >
              {expanded ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
              {expanded ? 'Hide' : 'Show'} explanation
            </button>
          )}
          {expanded && explanation && (
            <div className="mt-2 p-3 bg-indigo-500/10 border border-indigo-500/20 rounded-lg text-xs text-slate-300 leading-relaxed">
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
  const [selectedDocId, setSelectedDocId] = useState<number | null>(null);
  const [selectedCourseId, setSelectedCourseId] = useState<number | null>(null);
  const [scopeType, setScopeType] = useState<ScopeType>('document');
  const [questionCount, setQuestionCount] = useState<number>(5);
  const [difficulty, setDifficulty] = useState<string>('medium');
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [activeQuiz, setActiveQuiz] = useState<Quiz | null>(null);
  const [selectedAnswers, setSelectedAnswers] = useState<Record<number, string>>({});
  const [quizResult, setQuizResult] = useState<QuizAttemptDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    try {
      const [docsData, coursesData] = await Promise.all([
        documentService.list(),
        courseService.list(),
      ]);
      setDocuments(docsData);
      setCourses(coursesData);
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
      );
      setActiveQuiz(quiz);
      setSelectedAnswers({});
      setQuizResult(null);
    } catch (err: any) {
      setError('Failed to generate quiz: ' + (err.response?.data?.error?.message || err.message));
    } finally {
      setIsGenerating(false);
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

  const answeredCount = Object.keys(selectedAnswers).length;
  const totalCount = activeQuiz?.questions.length ?? 0;

  const scoreColor =
    (quizResult?.score_percentage ?? 0) >= 80
      ? 'text-emerald-400'
      : (quizResult?.score_percentage ?? 0) >= 60
      ? 'text-amber-400'
      : 'text-red-400';

  if (isLoading) return <Spinner size="lg" />;

  return (
    <div className="space-y-6 max-w-3xl mx-auto">
      {/* Header */}
      <div>
        <h1 className="text-2xl md:text-3xl font-bold text-white tracking-tight flex items-center gap-2">
          <BookOpen className="h-7 w-7 text-indigo-400" />
          Quizzes
        </h1>
        <p className="text-sm text-slate-400 mt-1">
          AI-generated knowledge assessments from your course materials
        </p>
      </div>

      {/* Error */}
      {error && (
        <div className="flex items-start gap-3 p-3 bg-red-500/10 border border-red-500/30 rounded-xl text-red-300 text-sm">
          <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {!activeQuiz ? (
        /* Generation Form */
        <Card className="bg-slate-900 border-slate-800 p-6 space-y-5">
          <h2 className="text-base font-semibold text-white">Generate a New Quiz</h2>

          <form onSubmit={handleGenerate} className="space-y-4">
            {/* Scope Toggle */}
            <div>
              <label className="text-xs font-medium text-slate-400 mb-1.5 block">Source</label>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => setScopeType('document')}
                  className={`flex-1 py-2 rounded-lg text-xs font-medium transition-colors ${
                    scopeType === 'document' ? 'bg-indigo-600 text-white' : 'bg-slate-800 text-slate-400 hover:text-white'
                  }`}
                >
                  By Document
                </button>
                <button
                  type="button"
                  onClick={() => setScopeType('course')}
                  className={`flex-1 py-2 rounded-lg text-xs font-medium transition-colors ${
                    scopeType === 'course' ? 'bg-indigo-600 text-white' : 'bg-slate-800 text-slate-400 hover:text-white'
                  }`}
                >
                  By Course
                </button>
              </div>
            </div>

            {/* Source Selector */}
            <div>
              <label className="text-xs font-medium text-slate-400 mb-1.5 block">
                {scopeType === 'document' ? 'Document' : 'Course'}
              </label>
              {scopeType === 'document' ? (
                <select
                  value={selectedDocId || ''}
                  onChange={(e) => setSelectedDocId(Number(e.target.value))}
                  className="w-full bg-slate-800 border border-slate-700 text-sm rounded-lg px-3 py-2 text-white focus:outline-none focus:border-indigo-500"
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
                  className="w-full bg-slate-800 border border-slate-700 text-sm rounded-lg px-3 py-2 text-white focus:outline-none focus:border-indigo-500"
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

            {/* Count & Difficulty row */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-medium text-slate-400 mb-1.5 block">Questions</label>
                <select
                  value={questionCount}
                  onChange={(e) => setQuestionCount(Number(e.target.value))}
                  className="w-full bg-slate-800 border border-slate-700 text-sm rounded-lg px-3 py-2 text-white focus:outline-none focus:border-indigo-500"
                >
                  <option value={5}>5 Questions</option>
                  <option value={10}>10 Questions</option>
                  <option value={15}>15 Questions</option>
                </select>
              </div>
              <div>
                <label className="text-xs font-medium text-slate-400 mb-1.5 block">Difficulty</label>
                <select
                  value={difficulty}
                  onChange={(e) => setDifficulty(e.target.value)}
                  className="w-full bg-slate-800 border border-slate-700 text-sm rounded-lg px-3 py-2 text-white focus:outline-none focus:border-indigo-500"
                >
                  <option value="easy">Easy — Definitions & Recognition</option>
                  <option value="medium">Medium — Application & Analysis</option>
                  <option value="hard">Hard — Synthesis & Complex Scenarios</option>
                </select>
              </div>
            </div>

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
      ) : quizResult ? (
        /* Results Panel */
        <div className="space-y-5">
          {/* Score Summary */}
          <Card className="bg-slate-900 border-slate-800 p-8 text-center">
            <div className="h-16 w-16 rounded-full bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center mx-auto text-indigo-400 mb-4">
              <Trophy className="h-8 w-8" />
            </div>
            <span className="text-xs font-semibold uppercase tracking-wider text-indigo-400">
              Assessment Complete
            </span>
            <h2 className={`text-4xl font-extrabold mt-2 ${scoreColor}`}>
              {quizResult.score_percentage}%
            </h2>
            <p className="text-sm text-slate-400 mt-1">
              {quizResult.correct_answers_count} of {quizResult.total_questions} correct
            </p>

            {/* Feedback */}
            <div className="mt-4 p-4 rounded-xl bg-slate-800/60 border border-slate-700 text-sm text-slate-200 text-left max-w-md mx-auto">
              <p className="font-semibold text-indigo-300 text-xs uppercase mb-1">Feedback</p>
              <p className="text-xs text-slate-300 leading-relaxed">{quizResult.feedback}</p>
            </div>

            <div className="flex justify-center gap-3 mt-6">
              <Button
                variant="secondary"
                onClick={() => { setActiveQuiz(null); setQuizResult(null); }}
                icon={<RotateCcw className="h-4 w-4" />}
              >
                New Quiz
              </Button>
            </div>
          </Card>

          {/* Per-question Results */}
          {quizResult.question_results && quizResult.question_results.length > 0 && (
            <div className="space-y-3">
              <h3 className="text-sm font-semibold text-white">Question Review</h3>
              {quizResult.question_results.map((qr, idx) => (
                <QuestionResultCard
                  key={qr.question_id}
                  idx={idx}
                  questionText={qr.question_text}
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
          {/* Quiz Header */}
          <div className="flex items-center justify-between pb-2 border-b border-slate-800">
            <div>
              <h2 className="text-base font-semibold text-white">{activeQuiz.title}</h2>
              {activeQuiz.description && (
                <p className="text-xs text-slate-400 mt-0.5">{activeQuiz.description}</p>
              )}
            </div>
            <span className="text-xs text-slate-400 shrink-0 ml-3">
              {answeredCount} / {totalCount} answered
            </span>
          </div>

          {/* Progress Bar */}
          <div className="h-1 bg-slate-800 rounded-full">
            <div
              className="h-1 bg-indigo-500 rounded-full transition-all"
              style={{ width: `${totalCount > 0 ? (answeredCount / totalCount) * 100 : 0}%` }}
            />
          </div>

          {/* Questions */}
          <div className="space-y-5">
            {activeQuiz.questions.map((q, qIdx) => (
              <Card key={q.id} className="bg-slate-900 border-slate-800 p-5 space-y-4">
                <div className="flex items-start gap-3">
                  <span className="h-6 w-6 rounded-full bg-indigo-600/20 text-indigo-400 border border-indigo-500/30 text-xs flex items-center justify-center font-bold shrink-0">
                    {qIdx + 1}
                  </span>
                  <h4 className="text-sm font-semibold text-white leading-relaxed">{q.question_text}</h4>
                </div>

                <div className="space-y-2 pl-9">
                  {q.options.map((opt, optIdx) => {
                    const isSelected = selectedAnswers[q.id] === opt;
                    return (
                      <div
                        key={optIdx}
                        onClick={() => handleSelectOption(q.id, opt)}
                        className={`cursor-pointer p-3 rounded-lg border text-sm transition-all flex items-center justify-between ${
                          isSelected
                            ? 'bg-indigo-600/20 border-indigo-500 text-white font-medium'
                            : 'bg-slate-800/40 border-slate-700/60 text-slate-300 hover:bg-slate-800 hover:border-slate-600'
                        }`}
                      >
                        <span>{opt}</span>
                        {isSelected && <CheckCircle2 className="h-4 w-4 text-indigo-400 shrink-0" />}
                      </div>
                    );
                  })}
                </div>
              </Card>
            ))}
          </div>

          {/* Submit */}
          <div className="flex justify-between items-center pt-2">
            <Button
              variant="ghost"
              onClick={() => { setActiveQuiz(null); setQuizResult(null); }}
            >
              Cancel
            </Button>
            <div className="flex items-center gap-3">
              {answeredCount < totalCount && (
                <span className="text-xs text-amber-400">
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
