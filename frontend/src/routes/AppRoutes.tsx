import React, { Suspense, lazy } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { ProtectedRoute } from './ProtectedRoute';
import { Layout } from '../components/layout/Layout';
import { Spinner } from '../components/common/Spinner';

const Login = lazy(() => import('../pages/auth/Login').then((m) => ({ default: m.Login })));
const Register = lazy(() => import('../pages/auth/Register').then((m) => ({ default: m.Register })));
const Dashboard = lazy(() => import('../pages/dashboard/Dashboard').then((m) => ({ default: m.Dashboard })));
const Documents = lazy(() => import('../pages/documents/Documents').then((m) => ({ default: m.Documents })));
const Courses = lazy(() => import('../pages/courses/Courses').then((m) => ({ default: m.Courses })));
const LessonView = lazy(() => import('../pages/lessons/LessonView').then((m) => ({ default: m.LessonView })));
const TutorChat = lazy(() => import('../pages/tutor/TutorChat').then((m) => ({ default: m.TutorChat })));
const Flashcards = lazy(() => import('../pages/flashcards/Flashcards').then((m) => ({ default: m.Flashcards })));
const Quizzes = lazy(() => import('../pages/quizzes/Quizzes').then((m) => ({ default: m.Quizzes })));
const ProgressView = lazy(() => import('../pages/progress/ProgressView').then((m) => ({ default: m.ProgressView })));
const CodingWorkspace = lazy(() => import('../pages/courses/CodingWorkspace').then((m) => ({ default: m.CodingWorkspace })));

const PageFallback: React.FC = () => (
  <div className="min-h-[60vh] flex flex-col items-center justify-center gap-3 text-ink-secondary">
    <Spinner size="lg" />
    <span className="text-xs font-medium tracking-wide">Loading workspace...</span>
  </div>
);

export const AppRoutes: React.FC = () => {
  return (
    <Suspense fallback={<PageFallback />}>
      <Routes>
        {/* Public routes */}
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />

        {/* Protected application routes */}
        <Route element={<ProtectedRoute />}>
          <Route element={<Layout />}>
            <Route path="/" element={<Dashboard />} />
            <Route path="/documents" element={<Documents />} />
            <Route path="/courses" element={<Courses />} />
            <Route path="/courses/:courseId" element={<LessonView />} />
            <Route path="/lessons/:lessonId/coding/:exerciseId" element={<CodingWorkspace />} />
            <Route path="/lessons/:lessonId/project" element={<CodingWorkspace />} />
            <Route path="/tutor" element={<TutorChat />} />
            <Route path="/flashcards" element={<Flashcards />} />
            <Route path="/quizzes" element={<Quizzes />} />
            <Route path="/progress" element={<ProgressView />} />
          </Route>
        </Route>

        {/* Fallback */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  );
};
