import { api } from './api';

export interface LessonExercise {
  id: number;
  lesson_id: number;
  order_index: number;
  exercise_type: 'mcq' | 'coding' | 'debugging' | 'fill_blank' | 'mini_task' | string;
  title: string;
  prompt: string;
  starter_code?: string | null;
  buggy_code?: string | null;
  options?: string[];
  option_explanations?: string[];
  expected_output?: string | null;
  test_cases?: Array<{
    description?: string;
    assert_code?: string;
    expected_contains?: string;
  }>;
  hints?: string[];
  difficulty?: string;
  latest_is_correct?: boolean | null;
  latest_score?: number | null;
  attempts_count?: number;
}

export interface ExerciseSubmitResult {
  exercise_id: number;
  is_correct: boolean;
  score: number;
  attempt_number: number;
  feedback: string;
  explanation?: string | null;
  option_feedback?: string | null;
  stdout?: string | null;
  stderr?: string | null;
  test_results?: Array<{ description: string; passed: boolean; message: string }>;
}

export interface CodeRunResult {
  passed: boolean;
  passed_tests: number;
  total_tests: number;
  stdout: string;
  stderr: string;
  results: Array<{ description: string; passed: boolean; message: string }>;
  timed_out: boolean;
}

export interface LessonNote {
  lesson_id: number;
  content: string;
  is_bookmarked: boolean;
  updated_at?: string | null;
}

export interface ConceptCardData {
  term: string;
  what_it_is: string;
  why_it_exists: string;
  how_it_works: string;
  example?: string;
  difference?: string;
  quick_check?: {
    question: string;
    options: string[];
    correct_answer: string;
    explanation?: string;
  };
}

export interface ArchitectureNodeData {
  id: string;
  label: string;
  role: string;
  input: string;
  process: string;
  output: string;
  connects_to?: string[];
}

export interface ArchitectureDiagramData {
  title: string;
  subtitle?: string;
  nodes: ArchitectureNodeData[];
}

export interface SimulatorConfigData {
  type: 'http_request' | 'layered_architecture' | 'concurrency_trace' | 'api_communication' | string;
  title: string;
  description?: string;
  default_method?: string;
  default_endpoint?: string;
}

export interface MatchingPair {
  id: string;
  term: string;
  description: string;
}

export interface MatchingExerciseData {
  title: string;
  instructions: string;
  pairs: MatchingPair[];
}

export interface ProjectTestCase {
  description: string;
  assert_code?: string;
  expected_contains?: string;
}

export interface ProjectStepData {
  project_name: string;
  step_number: number;
  milestone_title: string;
  learning_objective?: string;
  deliverable: string;
  requirements?: string[];
  starter_code?: string | null;
  expected_output?: string | null;
  test_cases?: ProjectTestCase[];
  hints?: string[];
  explanation?: string;
}

export interface Lesson {
  id: number;
  topic_id: number;
  title: string;
  content: string;
  summary?: string;
  key_takeaways?: string[];
  source_pages?: number[];
  printed_pages?: string[];
  estimated_minutes?: number;
  prerequisites?: string[];
  learning_objectives?: string[];
  structured_sections?: {
    toc?: Array<{ title: string; slug: string }>;
    subtopics?: string[];
    concept_cards?: ConceptCardData[];
    matching_exercise?: MatchingExerciseData | null;
    architecture_diagram?: ArchitectureDiagramData | null;
    simulator?: SimulatorConfigData | null;
    project_step?: ProjectStepData | null;
    grounding_map?: {
      chapter?: string;
      printed_pages?: string[];
      pdf_pages?: number[];
      objectives?: string[];
      subtopics?: string[];
      chunks?: Array<{ page_number?: number; printed_page?: string; preview?: string }>;
    } | null;
    has_code?: boolean;
    has_mermaid?: boolean;
    word_count?: number;
  };
  is_completed: boolean;
  page_start?: number;
  page_end?: number;
  generation_status?: string;
  generation_error?: string;
  exercises?: LessonExercise[];
  note?: LessonNote | null;
}

export interface Topic {
  id: number;
  chapter_id: number;
  title: string;
  order_index: number;
  lesson?: Lesson;
}

export interface Chapter {
  id: number;
  course_id: number;
  title: string;
  description?: string;
  order_index: number;
  page_start?: number;
  page_end?: number;
  printed_page_start?: string;
  printed_page_end?: string;
  learning_outcomes?: string[];
  topics: Topic[];
}

export interface GenerationJob {
  id: number;
  course_id: number;
  job_type: string;
  status: string;
  total_items: number;
  completed_items: number;
  current_stage: string;
  error_message?: string | null;
  updated_at: string;
}

export interface LessonJobStatus {
  job_id?: number;
  lesson_id: number;
  course_id?: number;
  status:
    | 'PENDING'
    | 'QUEUED'
    | 'WAITING_FOR_WORKER'
    | 'WAITING_FOR_MODEL'
    | 'CHECKING_CACHE'
    | 'CHECKING_DOCUMENT'
    | 'RETRIEVING_SOURCE'
    | 'PREPARING_CONTEXT'
    | 'GENERATING'
    | 'VALIDATING'
    | 'REPAIRING_CODE'
    | 'PREPARING_EXERCISES'
    | 'SAVING'
    | 'COMPLETED'
    | 'FAILED'
    | 'CANCELLED'
    | string;
  current_stage: string;
  stage_started_at?: string | null;
  elapsed_seconds: number;
  stage_duration_ms?: number | null;
  completed_stages?: number;
  total_stages?: number;
  progress_percentage?: number | null;
  generated_tokens?: number | null;
  target_tokens?: number | null;
  error_code?: string | null;
  error_message?: string | null;
  retry_count: number;
  heartbeat_at?: string | null;
  updated_at?: string;
  metrics?: Record<string, any>;
}

export interface DocumentProgressItem {
  document_id: number;
  filename: string;
  extraction_status: string;
  embedding_status: string;
  indexing_status: string;
  chunks_total: number;
  chunks_embedded: number;
}

export interface CourseGenerationProgress {
  course_id: number;
  total_lessons: number;
  ready_lessons: number;
  queued_lessons: number;
  generating_lessons: number;
  failed_lessons: number;
  cancelled_lessons: number;
  curriculum_status: string;
  curriculum_percentage: number;
  content_readiness_percentage: number;
  course_generation_status: string;
  active_job_id?: number | null;
  active_lesson_id?: number | null;
  active_lesson_title?: string | null;
  active_stage?: string | null;
  active_elapsed_seconds: number;
  prefetch_paused: boolean;
  documents_progress?: DocumentProgressItem[];
  updated_at: string;
}

export interface Course {
  id: number;
  user_id: number;
  document_id?: number;
  title: string;
  description: string;
  category?: string;
  difficulty_level: string;
  estimated_duration_hours: number;
  learning_objectives: string[];
  prerequisites?: string[];
  created_at: string;
  chapters?: Chapter[];
  active_job?: GenerationJob | null;
}

export interface CourseAssessmentQuestion {
  id: string;
  question_type: string;
  prompt: string;
  options: string[];
  topic_id?: number | null;
  topic_title?: string | null;
  lesson_id?: number | null;
}

export interface CourseAssessment {
  id: number;
  course_id: number;
  chapter_id?: number | null;
  assessment_type: 'module' | 'final' | string;
  title: string;
  description?: string | null;
  passing_score: number;
  questions: CourseAssessmentQuestion[];
  best_score?: number | null;
  passed: boolean;
}

export interface AssessmentResult {
  assessment_id: number;
  score: number;
  passed: boolean;
  correct_count: number;
  total_questions: number;
  topic_breakdown: Array<{
    topic_title: string;
    lesson_id?: number | null;
    correct: number;
    total: number;
    percentage: number;
  }>;
  recommended_lesson_ids: number[];
  question_feedback: Array<{
    id: string;
    is_correct: boolean;
    selected_answer: string;
    correct_answer: string;
    explanation: string;
    topic_title?: string;
    lesson_id?: number | null;
  }>;
}

export const courseService = {
  async list(): Promise<Course[]> {
    const res = await api.get<Course[]>('/courses');
    return res.data;
  },

  async get(id: number): Promise<Course> {
    const res = await api.get<Course>(`/courses/${id}`);
    return res.data;
  },

  async generate(documentId: number, difficulty = 'intermediate', targetChapters = 18): Promise<Course> {
    const res = await api.post<Course>('/courses/generate', {
      document_id: documentId,
      difficulty_level: difficulty,
      target_chapters_count: targetChapters,
      prevent_duplicate: true,
    }, { timeout: 180000 });
    return res.data;
  },

  async delete(id: number): Promise<{ message: string }> {
    const res = await api.delete(`/courses/${id}`);
    return res.data;
  },

  async getGenerationStatus(courseId: number): Promise<GenerationJob | null> {
    const res = await api.get<GenerationJob | null>(`/courses/${courseId}/generation-status`);
    return res.data;
  },

  async getCourseGenerationProgress(courseId: number): Promise<CourseGenerationProgress> {
    const res = await api.get<CourseGenerationProgress>(`/courses/${courseId}/generation-progress`);
    return res.data;
  },

  async pausePrefetch(courseId: number): Promise<{ course_id: number; prefetch_paused: boolean }> {
    const res = await api.post<{ course_id: number; prefetch_paused: boolean }>(`/courses/${courseId}/prefetch/pause`);
    return res.data;
  },

  async resumePrefetch(courseId: number): Promise<{ course_id: number; prefetch_paused: boolean }> {
    const res = await api.post<{ course_id: number; prefetch_paused: boolean }>(`/courses/${courseId}/prefetch/resume`);
    return res.data;
  },

  async retryFailedLessons(courseId: number): Promise<{ course_id: number; requeued_lessons: number }> {
    const res = await api.post<{ course_id: number; requeued_lessons: number }>(`/courses/${courseId}/retry-failed`);
    return res.data;
  },

  async getLesson(lessonId: number): Promise<Lesson> {
    const res = await api.get<Lesson>(`/lessons/${lessonId}`, { timeout: 300000 });
    return res.data;
  },

  async toggleComplete(lessonId: number): Promise<Lesson> {
    const res = await api.post<Lesson>(`/lessons/${lessonId}/toggle-complete`);
    return res.data;
  },

  async regenerateLesson(lessonId: number): Promise<Lesson> {
    const res = await api.post<Lesson>(`/lessons/${lessonId}/regenerate`, undefined, { timeout: 300000 });
    return res.data;
  },

  async validateLesson(lessonId: number): Promise<any> {
    const res = await api.post<any>(`/lessons/${lessonId}/validate`);
    return res.data;
  },

  async getLessonStatus(lessonId: number): Promise<LessonJobStatus> {
    const res = await api.get<LessonJobStatus>(`/lessons/${lessonId}/status`);
    return res.data;
  },

  async cancelLesson(lessonId: number): Promise<{ lesson_id: number; status: string }> {
    const res = await api.post<{ lesson_id: number; status: string }>(`/lessons/${lessonId}/cancel`);
    return res.data;
  },

  async runExerciseCode(lessonId: number, exerciseId: number, code: string): Promise<CodeRunResult> {
    const res = await api.post<CodeRunResult>(`/lessons/${lessonId}/exercises/${exerciseId}/run`, { code });
    return res.data;
  },

  async runSandboxCode(code: string, testCases?: ProjectTestCase[]): Promise<CodeRunResult> {
    const res = await api.post<CodeRunResult>(`/courses/sandbox/run`, {
      code,
      test_cases: testCases || [],
    });
    return res.data;
  },

  async submitExercise(
    lessonId: number,
    exerciseId: number,
    payload: { answer?: string; code?: string },
  ): Promise<ExerciseSubmitResult> {
    const res = await api.post<ExerciseSubmitResult>(
      `/lessons/${lessonId}/exercises/${exerciseId}/submit`,
      payload,
    );
    return res.data;
  },

  async saveLessonNote(
    lessonId: number,
    payload: { content?: string; is_bookmarked?: boolean },
  ): Promise<LessonNote> {
    const res = await api.put<LessonNote>(`/lessons/${lessonId}/notes`, payload);
    return res.data;
  },

  async getModuleAssessment(courseId: number, chapterId: number): Promise<CourseAssessment> {
    const res = await api.get<CourseAssessment>(`/courses/${courseId}/modules/${chapterId}/assessment`);
    return res.data;
  },

  async getFinalAssessment(courseId: number): Promise<CourseAssessment> {
    const res = await api.get<CourseAssessment>(`/courses/${courseId}/final-assessment`);
    return res.data;
  },

  async submitAssessment(
    courseId: number,
    assessmentId: number,
    answers: Record<string, string>,
  ): Promise<AssessmentResult> {
    const res = await api.post<AssessmentResult>(
      `/courses/${courseId}/assessments/${assessmentId}/submit`,
      { answers },
    );
    return res.data;
  },
};
