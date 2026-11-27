import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';
import { Input } from '../../components/common/Input';
import { Button } from '../../components/common/Button';
import { Card } from '../../components/common/Card';
import { ThemeToggle } from '../../components/common/ThemeToggle';
import { Sparkles, Mail, Lock, User, AlertCircle } from 'lucide-react';

export const Register: React.FC = () => {
  const { register } = useAuth();
  const navigate = useNavigate();

  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (password !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    if (password.length < 6) {
      setError('Password must be at least 6 characters');
      return;
    }

    setIsSubmitting(true);
    try {
      await register({ email, password, full_name: fullName });
      navigate('/');
    } catch (err: any) {
      const message =
        err.response?.data?.error?.message ||
        err.response?.data?.detail ||
        'Registration failed';
      setError(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-page flex flex-col justify-center items-center px-4 py-12 relative">
      <div className="absolute top-4 right-4 md:top-6 md:right-6">
        <ThemeToggle showLabel />
      </div>

      <div className="w-full max-w-md space-y-6">
        <div className="text-center space-y-2">
          <div className="inline-flex h-12 w-12 rounded-[12px] lf-gradient-primary items-center justify-center shadow-card mb-2">
            <Sparkles className="h-6 w-6 text-white" />
          </div>
          <h1 className="lf-heading-main">Create an account</h1>
          <p className="text-sm text-ink-secondary">Start your personalized AI learning journey</p>
        </div>

        <Card className="p-6 md:p-8">
          {error && (
            <div className="mb-5 p-3 rounded-[10px] bg-status-danger-bg border border-status-danger-border text-status-danger-text text-sm flex items-center gap-2">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <Input
              label="Full Name"
              type="text"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder="Alex Johnson"
              required
              leftIcon={<User className="h-4 w-4" />}
            />

            <Input
              label="Email Address"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="alex@learnforge.ai"
              required
              leftIcon={<Mail className="h-4 w-4" />}
            />

            <Input
              label="Password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              required
              leftIcon={<Lock className="h-4 w-4" />}
            />

            <Input
              label="Confirm Password"
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder="••••••••"
              required
              leftIcon={<Lock className="h-4 w-4" />}
            />

            <Button
              type="submit"
              variant="primary"
              className="w-full mt-2"
              isLoading={isSubmitting}
            >
              Sign Up
            </Button>
          </form>

          <div className="mt-6 text-center text-xs text-ink-secondary">
            Already have an account?{' '}
            <Link
              to="/login"
              className="text-accent hover:text-accent-hover font-semibold underline underline-offset-4"
            >
              Sign In
            </Link>
          </div>
        </Card>
      </div>
    </div>
  );
};
