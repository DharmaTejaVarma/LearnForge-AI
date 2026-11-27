import React, { useState, useEffect, useRef } from 'react';
import { useLocation, useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';
import { courseService, Course } from '../../services/courseService';
import {
  LogOut,
  User,
  Sparkles,
  Menu,
  Search,
  BookOpen,
  FileText,
  Bot,
  Layers,
  HelpCircle,
  BarChart3,
  LayoutDashboard,
} from 'lucide-react';
import { Button } from '../common/Button';
import { ThemeToggle } from '../common/ThemeToggle';
import { ProfileModal } from './ProfileModal';

const PAGE_TITLES: Array<{ match: (path: string) => boolean; title: string }> = [
  { match: (p) => p === '/', title: 'Dashboard' },
  { match: (p) => p.startsWith('/documents'), title: 'Study Materials' },
  { match: (p) => /^\/courses\/\d+/.test(p), title: 'Course Workspace' },
  { match: (p) => p.startsWith('/courses'), title: 'Curated Courses' },
  { match: (p) => p.startsWith('/tutor'), title: 'AI Tutor' },
  { match: (p) => p.startsWith('/flashcards'), title: 'Flashcards' },
  { match: (p) => p.startsWith('/quizzes'), title: 'Quizzes' },
  { match: (p) => p.startsWith('/progress'), title: 'Progress & Mastery' },
];

const QUICK_ROUTES = [
  { label: 'Dashboard', path: '/', icon: LayoutDashboard },
  { label: 'Study Materials & Upload', path: '/documents', icon: FileText },
  { label: 'Curated Courses', path: '/courses', icon: BookOpen },
  { label: 'Socratic AI Tutor', path: '/tutor', icon: Bot },
  { label: 'Flashcards & SM-2 Deck', path: '/flashcards', icon: Layers },
  { label: 'Adaptive Quizzes', path: '/quizzes', icon: HelpCircle },
  { label: 'Progress & Mastery Analytics', path: '/progress', icon: BarChart3 },
];

export const Navbar: React.FC<{ onMenuToggle: () => void; showLogo?: boolean }> = ({
  onMenuToggle,
  showLogo = false,
}) => {
  const { user, logout } = useAuth();
  const { pathname } = useLocation();
  const navigate = useNavigate();

  const [query, setQuery] = useState('');
  const [searchOpen, setSearchOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [courses, setCourses] = useState<Course[]>([]);
  const [coursesLoaded, setCoursesLoaded] = useState(false);

  const searchRef = useRef<HTMLDivElement>(null);

  const pageTitle = PAGE_TITLES.find((item) => item.match(pathname))?.title ?? 'Workspace';

  useEffect(() => {
    const handleOutside = (e: MouseEvent) => {
      if (searchRef.current && !searchRef.current.contains(e.target as Node)) {
        setSearchOpen(false);
      }
    };
    document.addEventListener('mousedown', handleOutside);
    return () => document.removeEventListener('mousedown', handleOutside);
  }, []);

  const handleOpenSearch = () => {
    setSearchOpen(true);
    if (!coursesLoaded) {
      setCoursesLoaded(true);
      courseService
        .list()
        .then(setCourses)
        .catch(() => {});
    }
  };

  const normalized = query.trim().toLowerCase();
  const matchedRoutes = QUICK_ROUTES.filter((r) =>
    !normalized || r.label.toLowerCase().includes(normalized),
  );
  const matchedCourses = normalized
    ? courses.filter((c) => c.title.toLowerCase().includes(normalized)).slice(0, 4)
    : courses.slice(0, 3);

  return (
    <>
      <header className="h-16 border-b border-line bg-surface sticky top-0 z-30 px-4 md:px-6 flex items-center justify-between gap-4 transition-colors">
      <div className="flex items-center gap-3 min-w-0">
        <button
          onClick={onMenuToggle}
          className={`${showLogo ? '' : 'md:hidden'} p-2 rounded-[10px] text-ink-secondary hover:text-ink-primary hover:bg-hoverbg transition-colors`}
          aria-label="Toggle navigation"
        >
          <Menu className="h-5 w-5" />
        </button>

        <Link
          to="/"
          className={`${showLogo ? 'flex' : 'flex md:hidden'} items-center gap-2.5 shrink-0`}
        >
          <div className="h-8 w-8 rounded-[10px] lf-gradient-primary flex items-center justify-center shadow-sm">
            <Sparkles className="h-4 w-4 text-white" />
          </div>
          <span className="text-base font-bold text-ink-primary tracking-tight hidden sm:inline">
            LearnForge <span className="text-accent">AI</span>
          </span>
        </Link>

        {showLogo && <span className="hidden lg:block h-5 w-px bg-line mx-1" aria-hidden="true" />}

        <h2 className="hidden md:block text-[18px] font-semibold text-ink-primary tracking-tight truncate">
          {pageTitle}
        </h2>
      </div>

      {/* Quick Search */}
      <div ref={searchRef} className="relative hidden lg:block flex-1 max-w-sm">
        <Search className="h-4 w-4 text-ink-secondary absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
        <input
          type="text"
          value={query}
          onFocus={handleOpenSearch}
          onChange={(e) => {
            setQuery(e.target.value);
            setSearchOpen(true);
          }}
          onKeyDown={(e) => {
            if (e.key === 'Escape') setSearchOpen(false);
            if (e.key === 'Enter') {
              if (matchedCourses.length > 0 && normalized) {
                navigate(`/courses/${matchedCourses[0].id}`);
                setSearchOpen(false);
                setQuery('');
              } else if (matchedRoutes.length > 0) {
                navigate(matchedRoutes[0].path);
                setSearchOpen(false);
                setQuery('');
              }
            }
          }}
          placeholder="Search courses or pages..."
          aria-label="Quick workspace search"
          className="lf-control w-full pl-9 pr-3 py-1.5 text-sm"
        />

        {searchOpen && (
          <div className="absolute left-0 right-0 mt-2 rounded-[12px] border border-line bg-surface shadow-modal p-2 z-50 max-h-80 overflow-y-auto space-y-2">
            {matchedCourses.length > 0 && (
              <div>
                <p className="px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wider text-ink-secondary">
                  Courses
                </p>
                {matchedCourses.map((c) => (
                  <button
                    key={c.id}
                    type="button"
                    onClick={() => {
                      navigate(`/courses/${c.id}`);
                      setSearchOpen(false);
                      setQuery('');
                    }}
                    className="w-full flex items-center gap-2.5 px-2.5 py-2 rounded-[10px] text-left text-xs font-medium text-ink-primary hover:bg-hoverbg hover:text-brand transition-colors"
                  >
                    <BookOpen className="h-4 w-4 text-accent shrink-0" />
                    <span className="truncate">{c.title}</span>
                  </button>
                ))}
              </div>
            )}

            {matchedRoutes.length > 0 && (
              <div>
                <p className="px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wider text-ink-secondary">
                  Navigation
                </p>
                {matchedRoutes.map((route) => (
                  <button
                    key={route.path}
                    type="button"
                    onClick={() => {
                      navigate(route.path);
                      setSearchOpen(false);
                      setQuery('');
                    }}
                    className="w-full flex items-center gap-2.5 px-2.5 py-2 rounded-[10px] text-left text-xs font-medium text-ink-primary hover:bg-hoverbg hover:text-brand transition-colors"
                  >
                    <route.icon className="h-4 w-4 text-brand shrink-0" />
                    <span className="truncate">{route.label}</span>
                  </button>
                ))}
              </div>
            )}

            {matchedCourses.length === 0 && matchedRoutes.length === 0 && (
              <p className="px-3 py-4 text-xs text-ink-secondary text-center">
                No matching courses or sections found.
              </p>
            )}
          </div>
        )}
      </div>

      <div className="flex items-center gap-2.5 sm:gap-3">
        <ThemeToggle showLabel />

        {user && (
          <div className="flex items-center gap-2 pl-2.5 sm:pl-3 border-l border-line">
            <button
              type="button"
              onClick={() => setProfileOpen(true)}
              aria-label="Edit user profile"
              title="Edit profile details"
              className="flex items-center gap-2.5 px-2 py-1 rounded-[10px] hover:bg-hoverbg transition-colors text-left group focus:outline-none focus-visible:ring-2 focus-visible:ring-brand"
            >
              <div className="hidden sm:block text-right">
                <p className="text-sm font-medium text-ink-primary group-hover:text-brand leading-tight transition-colors">
                  {user.full_name || user.email.split('@')[0]}
                </p>
                <p className="text-xs text-ink-secondary leading-tight">{user.email}</p>
              </div>
              <div className="h-9 w-9 rounded-full bg-brand-soft border border-brand-soft-border flex items-center justify-center text-brand font-semibold text-sm shrink-0 group-hover:border-brand transition-colors">
                {user.full_name ? user.full_name.charAt(0).toUpperCase() : <User className="h-4 w-4" />}
              </div>
            </button>
            <Button
              variant="ghost"
              size="sm"
              onClick={logout}
              title="Sign Out"
              aria-label="Sign Out"
              className="text-ink-secondary hover:text-status-danger-text"
            >
              <LogOut className="h-4 w-4" />
            </Button>
          </div>
        )}
      </div>
      </header>
      <ProfileModal isOpen={profileOpen} onClose={() => setProfileOpen(false)} />
    </>
  );
};
