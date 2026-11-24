import React from 'react';
import { NavLink } from 'react-router-dom';
import { 
  LayoutDashboard, 
  FileText, 
  BookOpen, 
  Bot, 
  Layers, 
  HelpCircle, 
  BarChart3 
} from 'lucide-react';

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ isOpen, onClose }) => {
  const navigation = [
    { name: 'Dashboard', to: '/', icon: LayoutDashboard },
    { name: 'Documents', to: '/documents', icon: FileText },
    { name: 'Courses', to: '/courses', icon: BookOpen },
    { name: 'AI Tutor', to: '/tutor', icon: Bot },
    { name: 'Flashcards', to: '/flashcards', icon: Layers },
    { name: 'Quizzes', to: '/quizzes', icon: HelpCircle },
    { name: 'Progress & Mastery', to: '/progress', icon: BarChart3 },
  ];

  return (
    <>
      {/* Mobile backdrop */}
      {isOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm md:hidden"
          onClick={onClose}
        />
      )}

      <aside
        className={`fixed md:sticky top-0 md:top-16 z-40 md:z-20 h-screen md:h-[calc(100vh-4rem)] w-64 bg-slate-900 border-r border-slate-800 transition-transform duration-200 ease-in-out ${
          isOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'
        } flex flex-col justify-between p-4`}
      >
        <div className="space-y-6">
          <div className="md:hidden flex items-center justify-between pb-3 border-b border-slate-800">
            <span className="font-bold text-white text-base">Menu</span>
            <button onClick={onClose} className="p-1 rounded text-slate-400 hover:text-white">
              ✕
            </button>
          </div>

          <nav className="space-y-1">
            {navigation.map((item) => (
              <NavLink
                key={item.name}
                to={item.to}
                onClick={() => onClose()}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                    isActive
                      ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/30'
                      : 'text-slate-400 hover:text-slate-100 hover:bg-slate-800'
                  }`
                }
              >
                <item.icon className="h-5 w-5" />
                <span>{item.name}</span>
              </NavLink>
            ))}
          </nav>
        </div>

        <div className="p-3 bg-slate-800/50 rounded-xl border border-slate-800 text-xs text-slate-400 space-y-1">
          <p className="font-semibold text-slate-300">LearnForge Engine</p>
          <p>Local SQLite & ChromaDB</p>
          <p className="text-[10px] text-slate-500">v0.1.0 • Hybrid AI Active</p>
        </div>
      </aside>
    </>
  );
};
