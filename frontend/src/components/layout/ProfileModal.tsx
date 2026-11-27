import React, { useEffect, useState } from 'react';
import { useAuth } from '../../hooks/useAuth';
import { Input } from '../common/Input';
import { Button } from '../common/Button';
import { formatFriendlyDate } from '../../utils/formatters';
import { User as UserIcon, Mail, Lock, CheckCircle2, AlertCircle, X, Calendar } from 'lucide-react';

interface ProfileModalProps {
  isOpen: boolean;
  onClose: () => void;
}

/**
 * Modal dialog allowing the authenticated user to inspect and update basic profile details.
 */
export const ProfileModal: React.FC<ProfileModalProps> = ({ isOpen, onClose }) => {
  const { user, updateProfile } = useAuth();

  const [fullName, setFullName] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (isOpen && user) {
      setFullName(user.full_name || '');
      setNewPassword('');
      setConfirmPassword('');
      setError(null);
      setSuccess(null);
    }
  }, [isOpen, user]);

  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !isSaving) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, isSaving, onClose]);

  if (!isOpen || !user) return null;

  const displayName = user.full_name || user.email.split('@')[0];
  const initial = displayName.charAt(0).toUpperCase();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);

    const trimmedName = fullName.trim();
    if (!trimmedName) {
      setError('Full name cannot be empty.');
      return;
    }

    if (newPassword || confirmPassword) {
      if (newPassword.length < 6) {
        setError('New password must be at least 6 characters.');
        return;
      }
      if (newPassword !== confirmPassword) {
        setError('Passwords do not match.');
        return;
      }
    }

    setIsSaving(true);
    try {
      const payload: { full_name?: string; password?: string } = {
        full_name: trimmedName,
      };
      if (newPassword) {
        payload.password = newPassword;
      }
      await updateProfile(payload);
      setNewPassword('');
      setConfirmPassword('');
      setSuccess('Profile details updated successfully.');
    } catch (err: any) {
      setError(
        err.response?.data?.error?.message ||
          err.response?.data?.detail ||
          'Unable to update profile right now.',
      );
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4"
      onClick={() => !isSaving && onClose()}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="profile-modal-title"
        onClick={(e) => e.stopPropagation()}
        className="lf-card shadow-modal max-w-md w-full p-6 space-y-5"
      >
        {/* Header */}
        <div className="flex items-start justify-between gap-3 pb-4 border-b border-line">
          <div className="flex items-center gap-3 min-w-0">
            <div className="h-11 w-11 rounded-full bg-brand-soft border border-brand-soft-border flex items-center justify-center text-brand font-bold text-base shrink-0">
              {initial}
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <h3 id="profile-modal-title" className="lf-heading-card truncate">
                  Account Profile
                </h3>
                <span className="px-2 py-0.5 rounded-full text-[11px] font-medium capitalize bg-accent-soft text-accent border border-accent-soft-border">
                  {user.role || 'student'}
                </span>
              </div>
              {user.created_at && (
                <p className="text-xs text-ink-secondary flex items-center gap-1 mt-0.5">
                  <Calendar className="h-3 w-3 shrink-0" />
                  <span>Joined {formatFriendlyDate(user.created_at)}</span>
                </p>
              )}
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            disabled={isSaving}
            aria-label="Close profile dialog"
            className="p-1.5 rounded-[10px] text-ink-secondary hover:text-ink-primary hover:bg-hoverbg transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Alerts */}
        {error && (
          <div className="p-3 rounded-[10px] bg-status-danger-bg border border-status-danger-border text-status-danger-text text-xs flex items-center gap-2">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {success && (
          <div className="p-3 rounded-[10px] bg-status-success-bg border border-status-success-border text-status-success-text text-xs flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 shrink-0" />
            <span>{success}</span>
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <Input
            label="Full Name"
            type="text"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            placeholder="Your full name"
            maxLength={255}
            required
            leftIcon={<UserIcon className="h-4 w-4" />}
          />

          <Input
            label="Email Address"
            type="email"
            value={user.email}
            disabled
            helperText="Account email address cannot be modified."
            className="opacity-70 cursor-not-allowed"
            leftIcon={<Mail className="h-4 w-4" />}
          />

          <div className="pt-2 border-t border-line space-y-3">
            <p className="text-xs font-medium text-ink-secondary">
              Change Password <span className="font-normal">(optional)</span>
            </p>

            <Input
              label="New Password"
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              placeholder="Leave blank to keep current password"
              leftIcon={<Lock className="h-4 w-4" />}
            />

            {newPassword.length > 0 && (
              <Input
                label="Confirm New Password"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="Re-enter new password"
                required
                leftIcon={<Lock className="h-4 w-4" />}
              />
            )}
          </div>

          <div className="flex justify-end gap-2.5 pt-2">
            <Button
              type="button"
              variant="ghost"
              onClick={onClose}
              disabled={isSaving}
            >
              Close
            </Button>
            <Button
              type="submit"
              variant="primary"
              isLoading={isSaving}
            >
              Save Changes
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
};
