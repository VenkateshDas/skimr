'use client';

import { useUIStore } from '@/lib/stores';
import { Button } from '@/components/ui/button';
import { 
  Home, 
  Video, 
  History, 
  Settings, 
  ChevronLeft,
  ChevronRight
} from 'lucide-react';
import { cn } from '@/lib/utils';

export function Sidebar() {
  const { sidebarOpen, toggleSidebar } = useUIStore();

  const navigationItems = [
    { icon: Home, label: 'Home', href: '/' },
    { icon: Video, label: 'Analyze Video', href: '/analyze' },
    { icon: History, label: 'History', href: '/history' },
    { icon: Settings, label: 'Settings', href: '/settings' },
  ];

  return (
    <aside className={cn(
      "fixed left-0 top-16 h-[calc(100vh-4rem)] bg-background border-r transition-all duration-300 ease-in-out z-40",
      sidebarOpen ? "w-64" : "w-16"
    )}>
      <div className="flex flex-col h-full">
        {/* Sidebar Header */}
        <div className="flex items-center justify-between p-4 border-b">
          {sidebarOpen && (
            <h2 className="font-semibold text-sm text-muted-foreground">
              Navigation
            </h2>
          )}
          <Button
            variant="ghost"
            size="sm"
            onClick={toggleSidebar}
            className="h-8 w-8 p-0"
          >
            {sidebarOpen ? (
              <ChevronLeft className="h-4 w-4" />
            ) : (
              <ChevronRight className="h-4 w-4" />
            )}
            <span className="sr-only">Toggle sidebar</span>
          </Button>
        </div>

        {/* Navigation Items */}
        <nav className="flex-1 p-2">
          <ul className="space-y-1">
            {navigationItems.map((item) => (
              <li key={item.href}>
                <Button
                  variant="ghost"
                  className={cn(
                    "w-full justify-start h-10",
                    !sidebarOpen && "justify-center px-2"
                  )}
                >
                  <item.icon className="h-4 w-4" />
                  {sidebarOpen && (
                    <span className="ml-3">{item.label}</span>
                  )}
                </Button>
              </li>
            ))}
          </ul>
        </nav>

        {/* Sidebar Footer */}
        <div className="p-4 border-t">
          {sidebarOpen ? (
            <div className="text-xs text-muted-foreground">
              <p>YouTube Analysis Tool</p>
              <p>v1.0.0</p>
            </div>
          ) : (
            <div className="flex justify-center">
              <div className="h-2 w-2 rounded-full bg-green-500" />
            </div>
          )}
        </div>
      </div>
    </aside>
  );
}