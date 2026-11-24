import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { ProtectedRoute } from './ProtectedRoute';
import { Layout } from '../components/layout/Layout';
import { Login } from '../pages/auth/Login';
import { Register } from '../pages/auth/Register';
import { Dashboard } from '../pages/dashboard/Dashboard';
import { Documents } from '../pages/documents/Documents';
import { Courses } from '../pages/courses/Courses';
import { LessonView } from '../pages/lessons/LessonView';
import { TutorChat } from '../pages/tutor/TutorChat';
import { Flashcards } from '../pages/flashcards/Flashcards';
import { Quizzes } from '../pages/quizzes/Quizzes';
import { ProgressView } from '../pages/progress/ProgressView';

export const AppRoutes: React.FC = () => {
  return (
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
          <Route path="/tutor" element={<TutorChat />} />
          <Route path="/flashcards" element={<Flashcards />} />
          <Route path="/quizzes" element={<Quizzes />} />
          <Route path="/progress" element={<ProgressView />} />
        </Route>
      </Route>

      {/* Fallback */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
};
