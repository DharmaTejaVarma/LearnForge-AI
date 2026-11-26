import React, { useState } from 'react';
import { Outlet, useMatch } from 'react-router-dom';
import { Navbar } from './Navbar';
import { Sidebar } from './Sidebar';

export const Layout: React.FC = () => {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const isCourseWorkspace = !!useMatch('/courses/:courseId');

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      <Navbar onMenuToggle={() => setSidebarOpen((prev) => !prev)} />
      <div className="flex-1 flex">
        <Sidebar
          isOpen={sidebarOpen}
          onClose={() => setSidebarOpen(false)}
          hideOnDesktop={isCourseWorkspace}
        />
        <main
          className={
            isCourseWorkspace
              ? 'flex-1 p-4 md:px-6 md:py-5 max-w-[1600px] mx-auto w-full overflow-y-auto'
              : 'flex-1 p-4 md:p-8 max-w-7xl mx-auto w-full overflow-y-auto'
          }
        >
          <Outlet />
        </main>
      </div>
    </div>
  );
};
