'use client';

import { ReactNode } from 'react';
import { useUIStore } from '@/lib/stores';
import { Header } from './Header';
import { Sidebar } from './Sidebar';
import { ChatPanel } from './ChatPanel';
import { cn } from '@/lib/utils';

interface AppLayoutProps {
  children: ReactNode;
}

export function AppLayout({ children }: AppLayoutProps) {
  const { 
    sidebarOpen, 
    chatPanelOpen, 
    theme 
  } = useUIStore();

  return (
    <div className={cn(
      "min-h-screen bg-background text-foreground transition-colors duration-200",
      theme === 'dark' && 'dark'
    )}>
      {/* Header */}
      <Header />
      
      <div className="flex h-[calc(100vh-4rem)]">
        {/* Sidebar */}
        <Sidebar />
        
        {/* Main Content Area */}
        <main className={cn(
          "flex-1 transition-all duration-300 ease-in-out",
          sidebarOpen ? "ml-64" : "ml-16",
          chatPanelOpen ? "mr-80" : "mr-0"
        )}>
          <div className="h-full overflow-auto">
            {children}
          </div>
        </main>
        
        {/* Chat Panel */}
        <ChatPanel />
      </div>
    </div>
  );
}