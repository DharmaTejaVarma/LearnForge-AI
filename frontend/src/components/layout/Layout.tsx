import React, { useState } from 'react';
import { Outlet, useMatch } from 'react-router-dom';
import { Navbar } from './Navbar';
import { Sidebar } from './Sidebar';

export const Layout: React.FC = () => {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const isCourseWorkspace = !!useMatch('/courses/:courseId');

  return (
    <div className="min-h-screen bg-page text-ink-primary flex">
      <Sidebar
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        hideOnDesktop={isCourseWorkspace}
      />
      <div className="flex-1 min-w-0 flex flex-col min-h-screen">
        <Navbar
          onMenuToggle={() => setSidebarOpen((prev) => !prev)}
          showLogo={isCourseWorkspace}
        />
        <main
          className={
            isCourseWorkspace
              ? 'flex-1 p-4 md:px-6 md:py-5 max-w-[1600px] mx-auto w-full'
              : 'flex-1 p-4 md:p-8 max-w-7xl mx-auto w-full'
          }
        >
          <Outlet />
        </main>
      </div>
    </div>
  );
};
