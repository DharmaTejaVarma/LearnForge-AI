import React from 'react';
import { NavLink, Link } from 'react-router-dom';
import {
  LayoutDashboard,
  FileText,
  BookOpen,
  Bot,
  Layers,
  HelpCircle,
  BarChart3,
  Sparkles,
  X,
} from 'lucide-react';

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
  hideOnDesktop?: boolean;
}

const NAV_GROUPS = [
  {
    label: 'Learning',
    items: [
      { name: 'Dashboard', to: '/', icon: LayoutDashboard },
      { name: 'Documents', to: '/documents', icon: FileText },
      { name: 'Courses', to: '/courses', icon: BookOpen },
    ],
  },
  {
    label: 'Practice & AI',
    items: [
      { name: 'AI Tutor', to: '/tutor', icon: Bot },
      { name: 'Flashcards', to: '/flashcards', icon: Layers },
      { name: 'Quizzes', to: '/quizzes', icon: HelpCircle },
      { name: 'Progress & Mastery', to: '/progress', icon: BarChart3 },
    ],
  },
];

export const Sidebar: React.FC<SidebarProps> = ({ isOpen, onClose, hideOnDesktop = false }) => {
  return (
    <>
      {isOpen && (
        <div
          className={`fixed inset-0 z-40 bg-black/60 backdrop-blur-sm ${hideOnDesktop ? '' : 'md:hidden'}`}
          onClick={onClose}
        />
      )}

      <aside
        className={`fixed ${hideOnDesktop ? '' : 'md:sticky'} top-0 z-50 ${hideOnDesktop ? '' : 'md:z-20'
          } h-screen w-64 shrink-0 bg-sidebar border-r border-sidebar-border text-sidebar-text transition-transform duration-200 ease-in-out ${isOpen ? 'translate-x-0' : `-translate-x-full ${hideOnDesktop ? '' : 'md:translate-x-0'}`
          } flex flex-col justify-between`}
      >
        <div className="flex flex-col min-h-0 flex-1">
          {/* Sidebar Brand Header */}
          <div className="h-16 px-4 flex items-center justify-between border-b border-sidebar-border shrink-0">
            <Link to="/" onClick={onClose} className="flex items-center gap-2.5 min-w-0">
              <div className="h-9 w-9 rounded-[10px] lf-gradient-primary flex items-center justify-center shadow-sm shrink-0">
                <Sparkles className="h-5 w-5 text-white" />
              </div>
              <div className="min-w-0">
                <span className="text-base font-bold text-sidebar-text tracking-tight block leading-tight">
                  LearnForge <span className="text-violet-300">AI</span>
                </span>
                <span className="text-[11px] text-sidebar-muted block leading-tight">
                  Adaptive Platform
                </span>
              </div>
            </Link>

            <button
              onClick={onClose}
              aria-label="Close navigation"
              className="md:hidden p-1.5 rounded-[10px] text-sidebar-muted hover:text-sidebar-text hover:bg-sidebar-hover transition-colors"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          {/* Structured Navigation Groups */}
          <nav className="flex-1 overflow-y-auto px-3 py-5 space-y-6" aria-label="Main navigation">
            {NAV_GROUPS.map((group) => (
              <div key={group.label} className="space-y-1.5">
                <p className="px-3 text-[11px] font-semibold uppercase tracking-wider text-sidebar-muted/75">
                  {group.label}
                </p>
                <div className="space-y-1">
                  {group.items.map((item) => (
                    <NavLink
                      key={item.name}
                      to={item.to}
                      end={item.to === '/'}
                      onClick={() => onClose()}
                      className={({ isActive }) =>
                        `flex items-center gap-3 px-3 py-2.5 rounded-[10px] lf-nav-text transition-all duration-150 ${isActive
                          ? 'bg-sidebar-active text-white shadow-sm'
                          : 'text-sidebar-muted hover:text-sidebar-text hover:bg-sidebar-hover'
                        }`
                      }
                    >
                      <item.icon className="h-[18px] w-[18px] shrink-0" />
                      <span className="truncate">{item.name}</span>
                    </NavLink>
                  ))}
                </div>
              </div>
            ))}
          </nav>
        </div>
      </aside>
    </>
  );
};
