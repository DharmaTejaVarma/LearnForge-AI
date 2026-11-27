import React, { useState, useEffect } from 'react';
import { Card } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { Spinner } from '../../components/common/Spinner';
import { courseService, Course } from '../../services/courseService';
import { documentService, UploadedDocument } from '../../services/documentService';
import { formatDocumentTitle } from '../../utils/formatters';
import {
  BookOpen,
  Clock,
  Trash2,
  Sparkles,
  Plus,
  ChevronRight,
  GraduationCap,
  Target,
  AlertCircle,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';

export const Courses: React.FC = () => {
  const [courses, setCourses] = useState<Course[]>([]);
  const [documents, setDocuments] = useState<UploadedDocument[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const [selectedDocId, setSelectedDocId] = useState<number | null>(null);
  const [selectedDifficulty, setSelectedDifficulty] = useState<string>('intermediate');
  const [targetChapters, setTargetChapters] = useState<number>(18);
  const [showModal, setShowModal] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const navigate = useNavigate();

  const loadData = async () => {
    try {
      const [coursesData, docsData] = await Promise.all([
        courseService.list(),
        documentService.list(),
      ]);
      setCourses(coursesData);
      setDocuments(docsData);
      if (docsData.length > 0 && !selectedDocId) {
        setSelectedDocId(docsData[0].id);
      }
    } catch (err) {
      console.error('Failed to load courses:', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const duplicateCourse = selectedDocId
    ? courses.find(
        (c) =>
          c.document_id === selectedDocId &&
          (c.difficulty_level || 'intermediate').toLowerCase() === selectedDifficulty.toLowerCase(),
      )
    : undefined;

  const handleGenerate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedDocId) return;
    if (duplicateCourse) {
      setErrorMessage(
        `A course for this document and "${selectedDifficulty}" difficulty already exists ("${duplicateCourse.title}").`,
      );
      return;
    }

    setIsGenerating(true);
    setErrorMessage(null);
    try {
      const newCourse = await courseService.generate(selectedDocId, selectedDifficulty, targetChapters);
      setShowModal(false);
      await loadData();
      navigate(`/courses/${newCourse.id}`);
    } catch (err: any) {
      const msg = err.response?.data?.error?.message || err.response?.data?.detail || err.message || 'Failed to synthesize course.';
      setErrorMessage(msg);
    } finally {
      setIsGenerating(false);
    }
  };

  const handleDelete = async (id: number, title: string) => {
    if (!window.confirm(`Delete course "${title}"? This cannot be undone.`)) return;
    try {
      await courseService.delete(id);
      setCourses((prev) => prev.filter((c) => c.id !== id));
    } catch (err: any) {
      alert('Failed to delete course: ' + (err.response?.data?.error?.message || err.message));
    }
  };

  const getDifficultyBadge = (diff: string) => {
    switch (diff?.toLowerCase()) {
      case 'beginner':
        return 'bg-status-success-bg text-status-success-text border-status-success-border';
      case 'advanced':
        return 'bg-status-warning-bg text-status-warning-text border-status-warning-border';
      default:
        return 'bg-brand-soft text-brand border-brand-soft-border';
    }
  };

  return (
    <div className="space-y-8 animate-fadeIn">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="lf-heading-main">Curated Courses</h1>
          <p className="text-sm text-ink-secondary mt-1">
            Structured syllabi, chapters, and modular lessons synthesized from your documents
          </p>
        </div>

        <Button
          variant="primary"
          onClick={() => {
            setErrorMessage(null);
            setShowModal(true);
          }}
          icon={<Plus className="h-4 w-4" />}
          disabled={documents.length === 0}
        >
          Synthesize New Course
        </Button>
      </div>

      {documents.length === 0 && !isLoading && (
        <div className="p-4 rounded-[12px] bg-status-warning-bg border border-status-warning-border text-status-warning-text text-sm flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <span>You need to upload at least one document before synthesizing a course.</span>
          <Button size="sm" variant="outline" onClick={() => navigate('/documents')}>
            Go to Documents
          </Button>
        </div>
      )}

      {isLoading ? (
        <div className="py-20 flex flex-col items-center justify-center space-y-3">
          <Spinner size="lg" />
          <p className="text-sm text-ink-secondary">Loading your learning tracks...</p>
        </div>
      ) : courses.length === 0 ? (
        <Card className="p-12 text-center space-y-4">
          <div className="h-16 w-16 rounded-[12px] bg-brand-soft border border-brand-soft-border flex items-center justify-center mx-auto text-brand">
            <GraduationCap className="h-8 w-8" />
          </div>
          <div>
            <h3 className="lf-heading-card">No courses generated yet</h3>
            <p className="text-xs md:text-sm text-ink-secondary max-w-md mx-auto mt-1">
              Select any uploaded document (PDF, DOCX, TXT, PPTX, or Markdown) to let our AI synthesize an outline with chapters, learning objectives, and comprehensive lessons.
            </p>
          </div>
          <div className="pt-2">
            <Button
              variant="primary"
              onClick={() => {
                setErrorMessage(null);
                setShowModal(true);
              }}
              icon={<Sparkles className="h-4 w-4" />}
              disabled={documents.length === 0}
            >
              Synthesize Your First Course
            </Button>
          </div>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {courses.map((course) => (
            <Card
              key={course.id}
              interactive
              className="flex flex-col justify-between group p-6"
            >
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <span
                    className={`text-[11px] font-semibold uppercase tracking-wider px-2.5 py-0.5 rounded-full border ${getDifficultyBadge(
                      course.difficulty_level
                    )}`}
                  >
                    {course.difficulty_level || 'Intermediate'}
                  </span>
                  <button
                    onClick={() => handleDelete(course.id, course.title)}
                    className="text-ink-secondary hover:text-status-danger-text p-1.5 rounded-[10px] hover:bg-status-danger-bg transition-colors"
                    title="Delete course"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>

                <div>
                  <h3 className="lf-heading-card group-hover:text-brand transition-colors line-clamp-1">
                    {course.title}
                  </h3>
                  <p className="text-xs text-ink-secondary mt-1.5 line-clamp-2 leading-relaxed">
                    {course.description}
                  </p>
                </div>

                <div className="flex items-center gap-4 text-xs text-ink-secondary pt-3 border-t border-line">
                  <span className="flex items-center gap-1.5">
                    <Clock className="h-3.5 w-3.5 text-accent" />
                    ~{course.estimated_duration_hours || 4}h
                  </span>
                  {course.learning_objectives && course.learning_objectives.length > 0 && (
                    <span className="flex items-center gap-1.5">
                      <Target className="h-3.5 w-3.5 text-status-success-text" />
                      {course.learning_objectives.length} Objectives
                    </span>
                  )}
                  <span className="flex items-center gap-1.5">
                    <BookOpen className="h-3.5 w-3.5 text-brand" />
                    Modular
                  </span>
                </div>
              </div>

              <div className="pt-6">
                <Button
                  variant="secondary"
                  className="w-full justify-between group-hover:bg-brand group-hover:text-white group-hover:border-brand transition-all text-xs font-semibold"
                  onClick={() => navigate(`/courses/${course.id}`)}
                >
                  <span>Explore Course &amp; Lessons</span>
                  <ChevronRight className="h-4 w-4" />
                </Button>
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Course Synthesis Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 bg-black/65 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="lf-card shadow-modal max-w-md w-full p-6 space-y-6">
            <div>
              <div className="flex items-center gap-2 text-accent mb-1">
                <Sparkles className="h-5 w-5" />
                <h3 className="lf-heading-card">Synthesize Course</h3>
              </div>
              <p className="text-xs text-ink-secondary">
                Our RAG Pipeline and Document Agent analyze your file to synthesize a grounded curriculum.
              </p>
            </div>

            {(errorMessage || duplicateCourse) && (
              <div className="p-3 rounded-[10px] bg-status-warning-bg border border-status-warning-border text-status-warning-text text-xs space-y-2">
                <div className="flex items-start gap-2">
                  <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
                  <span>
                    {errorMessage ||
                      `A course with this document and "${selectedDifficulty}" difficulty already exists ("${duplicateCourse?.title}"). Change the difficulty/document or open the existing course.`}
                  </span>
                </div>
                {duplicateCourse && (
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    onClick={() => {
                      setShowModal(false);
                      navigate(`/courses/${duplicateCourse.id}`);
                    }}
                  >
                    Open Existing Course
                  </Button>
                )}
              </div>
            )}

            <form onSubmit={handleGenerate} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-ink-primary mb-1.5">
                  Source Educational Document
                </label>
                <select
                  value={selectedDocId || ''}
                  onChange={(e) => setSelectedDocId(Number(e.target.value))}
                  className="lf-control w-full p-2.5 text-xs md:text-sm"
                  required
                >
                  {documents.map((d) => (
                    <option key={d.id} value={d.id}>
                      {formatDocumentTitle(d.original_filename)} ({d.page_count} pages)
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-ink-primary mb-1.5">
                  Pedagogical Difficulty
                </label>
                <select
                  value={selectedDifficulty}
                  onChange={(e) => setSelectedDifficulty(e.target.value)}
                  className="lf-control w-full p-2.5 text-xs md:text-sm"
                >
                  <option value="beginner">Beginner (Foundations &amp; Concepts)</option>
                  <option value="intermediate">Intermediate (Deep Dive &amp; Applications)</option>
                  <option value="advanced">Advanced (Critical Analysis &amp; Synthesis)</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-ink-primary mb-1.5">
                  Curriculum Depth (Modules)
                </label>
                <select
                  value={targetChapters}
                  onChange={(e) => setTargetChapters(Number(e.target.value))}
                  className="lf-control w-full p-2.5 text-xs md:text-sm"
                >
                  <option value={4}>Focused (Up to 4 Modules)</option>
                  <option value={8}>Half Book (Up to 8 Modules)</option>
                  <option value={12}>Extended (Up to 12 Modules)</option>
                  <option value={18}>Full Book (All 18 Chapters)</option>
                  <option value={24}>Extended Textbook (Up to 24 Chapters)</option>
                </select>
              </div>

              <div className="flex justify-end gap-3 pt-3">
                <Button
                  variant="ghost"
                  onClick={() => setShowModal(false)}
                  type="button"
                  disabled={isGenerating}
                >
                  Cancel
                </Button>
                <Button
                  variant="primary"
                  type="submit"
                  isLoading={isGenerating}
                  disabled={Boolean(duplicateCourse)}
                  icon={<Sparkles className="h-4 w-4" />}
                >
                  {isGenerating ? 'Synthesizing...' : 'Start Synthesis'}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
