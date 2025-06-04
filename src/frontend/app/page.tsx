'use client';

import { AppLayout } from '@/components/layout/AppLayout';

export default function HomePage() {
  return (
    <AppLayout>
      <div className="flex-1 flex items-center justify-center">
        <div className="text-center space-y-4">
          <h1 className="text-4xl font-bold text-foreground">
            YouTube Analysis Platform
          </h1>
          <p className="text-lg text-muted-foreground max-w-2xl">
            Analyze YouTube videos with AI-powered insights. Get summaries, key points, 
            sentiment analysis, and more. Chat with our AI about video content.
          </p>
          <div className="flex gap-4 justify-center mt-8">
            <div className="bg-card p-6 rounded-lg border shadow-sm">
              <h3 className="font-semibold mb-2">Video Analysis</h3>
              <p className="text-sm text-muted-foreground">
                Upload a YouTube URL to get comprehensive analysis
              </p>
            </div>
            <div className="bg-card p-6 rounded-lg border shadow-sm">
              <h3 className="font-semibold mb-2">AI Chat</h3>
              <p className="text-sm text-muted-foreground">
                Ask questions about video content and get instant answers
              </p>
            </div>
            <div className="bg-card p-6 rounded-lg border shadow-sm">
              <h3 className="font-semibold mb-2">Smart Insights</h3>
              <p className="text-sm text-muted-foreground">
                Get summaries, key points, and sentiment analysis
              </p>
            </div>
          </div>
        </div>
      </div>
    </AppLayout>
  );
}