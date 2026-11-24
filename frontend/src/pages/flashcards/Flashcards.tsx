import React, { useState, useEffect, useCallback } from 'react';
import { Card } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { Spinner } from '../../components/common/Spinner';
import { learningService, Flashcard } from '../../services/learningService';
import { documentService, UploadedDocument } from '../../services/documentService';
import { courseService, Course } from '../../services/courseService';
import { formatDocumentTitle } from '../../utils/formatters';
import {
  Layers,
  RotateCw,
  CheckCircle,
  XCircle,
  Sparkles,
  Trash2,
  ChevronLeft,
  ChevronRight,
  BookOpen,
  AlertCircle,
  RefreshCw,
} from 'lucide-react';

type MasteryLevel = 'new' | 'reviewing' | 'mastered';

const MASTERY_COLORS: Record<MasteryLevel, string> = {
  new: 'bg-slate-700 text-slate-300',
  reviewing: 'bg-amber-500/20 text-amber-300 border border-amber-500/30',
  mastered: 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30',
};

const MASTERY_LABELS: Record<MasteryLevel, string> = {
  new: 'New',
  reviewing: 'Learning',
  mastered: 'Mastered',
};

type ScopeType = 'document' | 'course';

export const Flashcards: React.FC = () => {
  const [cards, setCards] = useState<Flashcard[]>([]);
  const [currentIndex, setCurrentIndex] = useState<number>(0);
  const [isFlipped, setIsFlipped] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const [documents, setDocuments] = useState<UploadedDocument[]>([]);
  const [courses, setCourses] = useState<Course[]>([]);
  const [selectedDocId, setSelectedDocId] = useState<number | null>(null);
  const [selectedCourseId, setSelectedCourseId] = useState<number | null>(null);
  const [scopeType, setScopeType] = useState<ScopeType>('document');
  const [count, setCount] = useState<number>(5);
  const [difficulty, setDifficulty] = useState<string>('medium');
  const [filterMastery, setFilterMastery] = useState<string>('');
  const [error, setError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  const loadData = useCallback(async () => {
    setError(null);
    try {
      const [cardsData, docsData, coursesData] = await Promise.all([
        learningService.listFlashcards(),
        documentService.list(),
        courseService.list(),
      ]);
      setCards(cardsData);
      setDocuments(docsData);
      setCourses(coursesData);
      if (docsData.length > 0 && !selectedDocId) {
        setSelectedDocId(docsData[0].id);
      }
      if (coursesData.length > 0 && !selectedCourseId) {
        setSelectedCourseId(coursesData[0].id);
      }
    } catch (err) {
      setError('Failed to load flashcards. Please try again.');
      console.error('Failed to load flashcards:', err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const displayedCards = filterMastery
    ? cards.filter((c) => c.mastery_level === filterMastery)
    : cards;

  const currentCard = displayedCards[currentIndex] ?? null;

  const handleGenerate = async () => {
    const docId = scopeType === 'document' ? selectedDocId : undefined;
    const courseId = scopeType === 'course' ? selectedCourseId : undefined;
    if (!docId && !courseId) return;

    setIsGenerating(true);
    setError(null);
    try {
      const newCards = await learningService.generateFlashcards(
        docId ?? undefined,
        courseId ?? undefined,
        count,
        difficulty,
      );
      setCards((prev) => [...newCards, ...prev]);
      setCurrentIndex(0);
      setIsFlipped(false);
    } catch (err: any) {
      setError('Failed to generate flashcards: ' + (err.response?.data?.error?.message || err.message));
    } finally {
      setIsGenerating(false);
    }
  };

  const handleFlip = () => setIsFlipped((v) => !v);

  const handleNav = (dir: 'prev' | 'next') => {
    setIsFlipped(false);
    if (dir === 'prev') {
      setCurrentIndex((i) => (i > 0 ? i - 1 : displayedCards.length - 1));
    } else {
      setCurrentIndex((i) => (i < displayedCards.length - 1 ? i + 1 : 0));
    }
  };

  const handleReview = async (mastered: boolean) => {
    if (!currentCard) return;
    try {
      const updated = await learningService.reviewFlashcard(currentCard.id, mastered);
      setCards((prev) => prev.map((c) => (c.id === updated.id ? updated : c)));
      setIsFlipped(false);
      // Move to next
      if (currentIndex < displayedCards.length - 1) {
        setCurrentIndex((prev) => prev + 1);
      } else {
        setCurrentIndex(0);
      }
    } catch (err) {
      console.error('Review failed:', err);
    }
  };

  const handleDelete = async (id: number) => {
    setDeletingId(id);
    try {
      await learningService.deleteFlashcard(id);
      const newCards = cards.filter((c) => c.id !== id);
      setCards(newCards);
      if (currentIndex >= newCards.length) {
        setCurrentIndex(Math.max(0, newCards.length - 1));
      }
      setIsFlipped(false);
    } catch (err) {
      console.error('Delete failed:', err);
    } finally {
      setDeletingId(null);
    }
  };

  const masteryStats = {
    new: cards.filter((c) => c.mastery_level === 'new').length,
    reviewing: cards.filter((c) => c.mastery_level === 'reviewing').length,
    mastered: cards.filter((c) => c.mastery_level === 'mastered').length,
  };

  return (
    <div className="space-y-6 max-w-3xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl md:text-3xl font-bold text-white tracking-tight flex items-center gap-2">
            <Layers className="h-7 w-7 text-indigo-400" />
            Flashcards
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Active recall study deck with spaced repetition
          </p>
        </div>

        {/* Mastery Stats */}
        {cards.length > 0 && (
          <div className="flex items-center gap-2 text-xs flex-wrap">
            {(['new', 'reviewing', 'mastered'] as MasteryLevel[]).map((level) => (
              <button
                key={level}
                onClick={() => {
                  setFilterMastery(filterMastery === level ? '' : level);
                  setCurrentIndex(0);
                  setIsFlipped(false);
                }}
                className={`px-2.5 py-1 rounded-full font-medium transition-all ${
                  MASTERY_COLORS[level]
                } ${filterMastery === level ? 'ring-2 ring-white/30' : ''}`}
              >
                {MASTERY_LABELS[level]} · {masteryStats[level]}
              </button>
            ))}
            {filterMastery && (
              <button
                onClick={() => { setFilterMastery(''); setCurrentIndex(0); }}
                className="text-slate-400 hover:text-white px-1"
              >
                ✕ All
              </button>
            )}
          </div>
        )}
      </div>

      {/* Generation Controls */}
      <Card className="bg-slate-900/60 border-slate-800 p-4">
        <div className="flex flex-col gap-3">
          {/* Scope Selector */}
          <div className="flex gap-2">
            <button
              onClick={() => setScopeType('document')}
              className={`flex-1 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                scopeType === 'document'
                  ? 'bg-indigo-600 text-white'
                  : 'bg-slate-800 text-slate-400 hover:text-white'
              }`}
            >
              By Document
            </button>
            <button
              onClick={() => setScopeType('course')}
              className={`flex-1 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                scopeType === 'course'
                  ? 'bg-indigo-600 text-white'
                  : 'bg-slate-800 text-slate-400 hover:text-white'
              }`}
            >
              By Course
            </button>
          </div>

          <div className="flex flex-wrap gap-2 items-center">
            {/* Source Selector */}
            {scopeType === 'document' ? (
              <select
                value={selectedDocId || ''}
                onChange={(e) => setSelectedDocId(Number(e.target.value))}
                className="bg-slate-800 border border-slate-700 text-xs rounded-lg px-3 py-2 text-white focus:outline-none flex-1 min-w-[140px]"
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
                className="bg-slate-800 border border-slate-700 text-xs rounded-lg px-3 py-2 text-white focus:outline-none flex-1 min-w-[140px]"
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

            {/* Count */}
            <select
              value={count}
              onChange={(e) => setCount(Number(e.target.value))}
              className="bg-slate-800 border border-slate-700 text-xs rounded-lg px-3 py-2 text-white focus:outline-none"
            >
              <option value={5}>5 Cards</option>
              <option value={10}>10 Cards</option>
              <option value={15}>15 Cards</option>
            </select>

            {/* Difficulty */}
            <select
              value={difficulty}
              onChange={(e) => setDifficulty(e.target.value)}
              className="bg-slate-800 border border-slate-700 text-xs rounded-lg px-3 py-2 text-white focus:outline-none"
            >
              <option value="easy">Easy</option>
              <option value="medium">Medium</option>
              <option value="hard">Hard</option>
            </select>

            <Button
              variant="primary"
              size="sm"
              onClick={handleGenerate}
              isLoading={isGenerating}
              disabled={
                (scopeType === 'document' && !selectedDocId) ||
                (scopeType === 'course' && !selectedCourseId)
              }
              icon={<Sparkles className="h-4 w-4" />}
            >
              Generate
            </Button>
          </div>
        </div>
      </Card>

      {/* Error */}
      {error && (
        <div className="flex items-start gap-3 p-3 bg-red-500/10 border border-red-500/30 rounded-xl text-red-300 text-sm">
          <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Card Area */}
      {isLoading ? (
        <Spinner size="lg" />
      ) : displayedCards.length === 0 ? (
        <Card className="p-12 text-center bg-slate-900 border-slate-800">
          <div className="h-14 w-14 rounded-2xl bg-indigo-600/10 border border-indigo-500/20 flex items-center justify-center mx-auto text-indigo-400 mb-4">
            <BookOpen className="h-7 w-7" />
          </div>
          <h3 className="text-lg font-bold text-white">
            {filterMastery ? `No ${MASTERY_LABELS[filterMastery as MasteryLevel]} cards` : 'No flashcards yet'}
          </h3>
          <p className="text-xs text-slate-400 max-w-sm mx-auto mt-1 mb-6">
            {filterMastery
              ? 'Try another filter or generate more cards.'
              : 'Generate flashcard pairs from your documents or courses to start active recall.'}
          </p>
        </Card>
      ) : (
        <div className="space-y-4">
          {/* Progress Bar */}
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>
              Card {currentIndex + 1} of {displayedCards.length}
              {filterMastery && ` (${MASTERY_LABELS[filterMastery as MasteryLevel]} only)`}
            </span>
            <span>
              {masteryStats.mastered} / {cards.length} mastered
            </span>
          </div>
          <div className="h-1 bg-slate-800 rounded-full">
            <div
              className="h-1 bg-indigo-500 rounded-full transition-all"
              style={{ width: `${((currentIndex + 1) / displayedCards.length) * 100}%` }}
            />
          </div>

          {/* Flashcard */}
          <div
            className="relative cursor-pointer select-none"
            onClick={handleFlip}
            style={{ perspective: '1200px', minHeight: '240px' }}
          >
            <div
              className="relative w-full transition-transform duration-500"
              style={{
                transformStyle: 'preserve-3d',
                transform: isFlipped ? 'rotateY(180deg)' : 'rotateY(0deg)',
                minHeight: '240px',
              }}
            >
              {/* Front */}
              <div
                className="absolute inset-0 w-full rounded-2xl bg-slate-900 border border-slate-700 p-8 flex flex-col items-center justify-center"
                style={{ backfaceVisibility: 'hidden' }}
              >
                <div className="mb-3">
                  <span className="text-xs font-semibold uppercase tracking-widest text-indigo-400">
                    Question
                  </span>
                </div>
                <p className="text-xl font-semibold text-white text-center leading-relaxed">
                  {currentCard?.front_prompt}
                </p>
                <p className="text-xs text-slate-500 mt-6 flex items-center gap-1">
                  <RotateCw className="h-3 w-3" /> Click to reveal answer
                </p>
                {/* Mastery Badge */}
                <div className="absolute top-4 right-4">
                  <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${MASTERY_COLORS[currentCard?.mastery_level as MasteryLevel ?? 'new']}`}>
                    {MASTERY_LABELS[currentCard?.mastery_level as MasteryLevel ?? 'new']}
                  </span>
                </div>
              </div>

              {/* Back */}
              <div
                className="absolute inset-0 w-full rounded-2xl bg-indigo-900/30 border border-indigo-500/40 p-8 flex flex-col items-center justify-center"
                style={{ backfaceVisibility: 'hidden', transform: 'rotateY(180deg)' }}
              >
                <div className="mb-3">
                  <span className="text-xs font-semibold uppercase tracking-widest text-indigo-400">
                    Answer
                  </span>
                </div>
                <p className="text-lg text-white text-center leading-relaxed">
                  {currentCard?.back_answer}
                </p>
              </div>
            </div>
          </div>

          {/* Action Buttons — only shown when flipped */}
          {isFlipped ? (
            <div className="flex items-center justify-center gap-3 pt-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => handleReview(false)}
                icon={<XCircle className="h-4 w-4 text-red-400" />}
                className="border border-red-500/30 hover:bg-red-500/10"
              >
                Got it wrong
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => handleReview(true)}
                icon={<CheckCircle className="h-4 w-4 text-emerald-400" />}
                className="border border-emerald-500/30 hover:bg-emerald-500/10"
              >
                Got it right
              </Button>
            </div>
          ) : (
            <div className="flex items-center justify-between pt-2">
              <div className="flex gap-2">
                <Button variant="ghost" size="sm" onClick={() => handleNav('prev')} icon={<ChevronLeft className="h-4 w-4" />}>
                  Prev
                </Button>
                <Button variant="ghost" size="sm" onClick={() => handleNav('next')} icon={<ChevronRight className="h-4 w-4" />}>
                  Next
                </Button>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => currentCard && handleDelete(currentCard.id)}
                isLoading={deletingId === currentCard?.id}
                icon={<Trash2 className="h-4 w-4 text-red-400" />}
                className="text-red-400 hover:bg-red-500/10"
              >
                Delete
              </Button>
            </div>
          )}

          {/* Keyboard hint */}
          <p className="text-center text-xs text-slate-600">
            Tip: Click the card to flip · Use Prev / Next to navigate
          </p>
        </div>
      )}

      {/* Card List Preview */}
      {cards.length > 0 && (
        <div className="mt-8">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-white">All Cards ({cards.length})</h2>
            <button
              onClick={loadData}
              className="text-xs text-slate-400 hover:text-white flex items-center gap-1"
            >
              <RefreshCw className="h-3 w-3" /> Refresh
            </button>
          </div>
          <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
            {cards.map((card) => (
              <div
                key={card.id}
                onClick={() => {
                  const dispIdx = displayedCards.findIndex((c) => c.id === card.id);
                  if (dispIdx >= 0) {
                    setCurrentIndex(dispIdx);
                    setIsFlipped(false);
                    window.scrollTo({ top: 0, behavior: 'smooth' });
                  }
                }}
                className={`flex items-center justify-between p-3 rounded-xl border cursor-pointer transition-colors ${
                  currentCard?.id === card.id
                    ? 'bg-indigo-600/20 border-indigo-500/40'
                    : 'bg-slate-900/50 border-slate-800 hover:border-slate-700'
                }`}
              >
                <div className="flex-1 min-w-0">
                  <p className="text-xs text-white truncate">{card.front_prompt}</p>
                </div>
                <div className="flex items-center gap-2 ml-2 shrink-0">
                  <span className={`text-xs px-2 py-0.5 rounded-full ${MASTERY_COLORS[card.mastery_level as MasteryLevel ?? 'new']}`}>
                    {MASTERY_LABELS[card.mastery_level as MasteryLevel ?? 'new']}
                  </span>
                  <button
                    onClick={(e) => { e.stopPropagation(); handleDelete(card.id); }}
                    className="text-slate-500 hover:text-red-400 transition-colors"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
