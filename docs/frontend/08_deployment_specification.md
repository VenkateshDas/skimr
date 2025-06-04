# Deployment Specification

## Overview

This specification defines deployment strategies, environment configurations, and CI/CD pipelines for the Next.js frontend, ensuring reliable production deployments with proper monitoring and rollback capabilities.

## Deployment Architecture

### Environment Configuration
```typescript
// Pseudocode: Environment setup and configuration
ENVIRONMENT_CONFIGS:
  DEVELOPMENT:
    NODE_ENV: 'development'
    NEXT_PUBLIC_API_URL: 'http://localhost:8000'
    NEXT_PUBLIC_WS_URL: 'ws://localhost:8000'
    NEXT_PUBLIC_SUPABASE_URL: process.env.NEXT_PUBLIC_SUPABASE_URL
    NEXT_PUBLIC_SUPABASE_ANON_KEY: process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
    NEXT_PUBLIC_APP_ENV: 'development'
    
  STAGING:
    NODE_ENV: 'production'
    NEXT_PUBLIC_API_URL: 'https://api-staging.yourdomain.com'
    NEXT_PUBLIC_WS_URL: 'wss://api-staging.yourdomain.com'
    NEXT_PUBLIC_SUPABASE_URL: process.env.NEXT_PUBLIC_SUPABASE_URL_STAGING
    NEXT_PUBLIC_SUPABASE_ANON_KEY: process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY_STAGING
    NEXT_PUBLIC_APP_ENV: 'staging'
    
  PRODUCTION:
    NODE_ENV: 'production'
    NEXT_PUBLIC_API_URL: 'https://api.yourdomain.com'
    NEXT_PUBLIC_WS_URL: 'wss://api.yourdomain.com'
    NEXT_PUBLIC_SUPABASE_URL: process.env.NEXT_PUBLIC_SUPABASE_URL_PROD
    NEXT_PUBLIC_SUPABASE_ANON_KEY: process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY_PROD
    NEXT_PUBLIC_APP_ENV: 'production'

// Environment validation
FUNCTION validateEnvironment():
  requiredVars = [
    'NEXT_PUBLIC_API_URL',
    'NEXT_PUBLIC_SUPABASE_URL',
    'NEXT_PUBLIC_SUPABASE_ANON_KEY'
  ]
  
  FOR EACH variable IN requiredVars:
    IF NOT process.env[variable]:
      THROW Error(`Missing required environment variable: ${variable}`)
  
  // Validate URL formats
  IF NOT isValidURL(process.env.NEXT_PUBLIC_API_URL):
    THROW Error('Invalid API URL format')
  
  IF NOT isValidURL(process.env.NEXT_PUBLIC_SUPABASE_URL):
    THROW Error('Invalid Supabase URL format')
```

### Build Configuration
```typescript
// Pseudocode: Next.js build optimization
NEXT_CONFIG:
  experimental:
    appDir: true
    serverComponentsExternalPackages: ['@supabase/supabase-js']
  
  images:
    domains: ['img.youtube.com', 'i.ytimg.com']
    formats: ['image/webp', 'image/avif']
  
  env:
    CUSTOM_KEY: process.env.CUSTOM_KEY
  
  async headers():
    RETURN [
      {
        source: '/api/:path*',
        headers: [
          { key: 'Access-Control-Allow-Origin', value: '*' },
          { key: 'Access-Control-Allow-Methods', value: 'GET,POST,PUT,DELETE,OPTIONS' },
          { key: 'Access-Control-Allow-Headers', value: 'Content-Type,Authorization' }
        ]
      }
    ]
  
  async rewrites():
    RETURN [
      {
        source: '/api/proxy/:path*',
        destination: `${process.env.NEXT_PUBLIC_API_URL}/api/:path*`
      }
    ]
  
  webpack: (config, { buildId, dev, isServer, defaultLoaders, webpack }) => {
    // Bundle analyzer in development
    IF dev AND process.env.ANALYZE === 'true':
      config.plugins.push(
        new BundleAnalyzerPlugin({
          analyzerMode: 'server',
          openAnalyzer: true
        })
      )
    
    // Optimize bundle splitting
    config.optimization.splitChunks = {
      chunks: 'all',
      cacheGroups: {
        vendor: {
          test: /[\\/]node_modules[\\/]/,
          name: 'vendors',
          chunks: 'all'
        },
        common: {
          name: 'common',
          minChunks: 2,
          chunks: 'all',
          enforce: true
        }
      }
    }
    
    RETURN config
  }

// Build scripts
BUILD_SCRIPTS:
  "build": "next build"
  "build:analyze": "ANALYZE=true next build"
  "build:staging": "NODE_ENV=production next build"
  "build:production": "NODE_ENV=production next build && next export"
  "start": "next start"
  "start:production": "NODE_ENV=production next start -p 3000"
```

## CI/CD Pipeline

### GitHub Actions Workflow
```yaml
# Pseudocode: CI/CD pipeline configuration
GITHUB_ACTIONS_WORKFLOW:
  name: 'Deploy Frontend'
  
  on:
    push:
      branches: [main, develop]
    pull_request:
      branches: [main]
  
  env:
    NODE_VERSION: '18'
    PNPM_VERSION: '8'
  
  jobs:
    test:
      runs-on: ubuntu-latest
      steps:
        - name: Checkout code
          uses: actions/checkout@v4
        
        - name: Setup Node.js
          uses: actions/setup-node@v4
          with:
            node-version: ${{ env.NODE_VERSION }}
            cache: 'pnpm'
        
        - name: Install pnpm
          uses: pnpm/action-setup@v2
          with:
            version: ${{ env.PNPM_VERSION }}
        
        - name: Install dependencies
          run: pnpm install --frozen-lockfile
        
        - name: Run linting
          run: pnpm lint
        
        - name: Run type checking
          run: pnpm type-check
        
        - name: Run unit tests
          run: pnpm test:unit --coverage
        
        - name: Upload coverage reports
          uses: codecov/codecov-action@v3
          with:
            file: ./coverage/lcov.info
    
    e2e-test:
      runs-on: ubuntu-latest
      needs: test
      steps:
        - name: Checkout code
          uses: actions/checkout@v4
        
        - name: Setup Node.js
          uses: actions/setup-node@v4
          with:
            node-version: ${{ env.NODE_VERSION }}
            cache: 'pnpm'
        
        - name: Install dependencies
          run: pnpm install --frozen-lockfile
        
        - name: Install Playwright browsers
          run: pnpm exec playwright install --with-deps
        
        - name: Build application
          run: pnpm build
          env:
            NEXT_PUBLIC_API_URL: 'http://localhost:8000'
            NEXT_PUBLIC_SUPABASE_URL: ${{ secrets.SUPABASE_URL_TEST }}
            NEXT_PUBLIC_SUPABASE_ANON_KEY: ${{ secrets.SUPABASE_ANON_KEY_TEST }}
        
        - name: Start application
          run: pnpm start &
          env:
            PORT: 3000
        
        - name: Wait for application
          run: npx wait-on http://localhost:3000
        
        - name: Run E2E tests
          run: pnpm test:e2e
        
        - name: Upload test results
          uses: actions/upload-artifact@v3
          if: failure()
          with:
            name: playwright-report
            path: playwright-report/
    
    build-staging:
      runs-on: ubuntu-latest
      needs: [test, e2e-test]
      if: github.ref == 'refs/heads/develop'
      steps:
        - name: Checkout code
          uses: actions/checkout@v4
        
        - name: Setup Node.js
          uses: actions/setup-node@v4
          with:
            node-version: ${{ env.NODE_VERSION }}
            cache: 'pnpm'
        
        - name: Install dependencies
          run: pnpm install --frozen-lockfile
        
        - name: Build for staging
          run: pnpm build
          env:
            NEXT_PUBLIC_API_URL: ${{ secrets.API_URL_STAGING }}
            NEXT_PUBLIC_SUPABASE_URL: ${{ secrets.SUPABASE_URL_STAGING }}
            NEXT_PUBLIC_SUPABASE_ANON_KEY: ${{ secrets.SUPABASE_ANON_KEY_STAGING }}
        
        - name: Deploy to Vercel Staging
          uses: amondnet/vercel-action@v25
          with:
            vercel-token: ${{ secrets.VERCEL_TOKEN }}
            vercel-org-id: ${{ secrets.VERCEL_ORG_ID }}
            vercel-project-id: ${{ secrets.VERCEL_PROJECT_ID }}
            working-directory: ./
            scope: ${{ secrets.VERCEL_ORG_ID }}
    
    build-production:
      runs-on: ubuntu-latest
      needs: [test, e2e-test]
      if: github.ref == 'refs/heads/main'
      steps:
        - name: Checkout code
          uses: actions/checkout@v4
        
        - name: Setup Node.js
          uses: actions/setup-node@v4
          with:
            node-version: ${{ env.NODE_VERSION }}
            cache: 'pnpm'
        
        - name: Install dependencies
          run: pnpm install --frozen-lockfile
        
        - name: Run Lighthouse CI
          run: |
            pnpm build
            pnpm start &
            npx wait-on http://localhost:3000
            npx lhci autorun
          env:
            LHCI_GITHUB_APP_TOKEN: ${{ secrets.LHCI_GITHUB_APP_TOKEN }}
        
        - name: Build for production
          run: pnpm build
          env:
            NEXT_PUBLIC_API_URL: ${{ secrets.API_URL_PRODUCTION }}
            NEXT_PUBLIC_SUPABASE_URL: ${{ secrets.SUPABASE_URL_PRODUCTION }}
            NEXT_PUBLIC_SUPABASE_ANON_KEY: ${{ secrets.SUPABASE_ANON_KEY_PRODUCTION }}
        
        - name: Deploy to Vercel Production
          uses: amondnet/vercel-action@v25
          with:
            vercel-token: ${{ secrets.VERCEL_TOKEN }}
            vercel-org-id: ${{ secrets.VERCEL_ORG_ID }}
            vercel-project-id: ${{ secrets.VERCEL_PROJECT_ID }}
            vercel-args: '--prod'
            working-directory: ./
            scope: ${{ secrets.VERCEL_ORG_ID }}
```

### Docker Configuration
```dockerfile
# Pseudocode: Docker containerization
DOCKERFILE:
  # Multi-stage build for optimization
  FROM node:18-alpine AS base
  
  # Install dependencies only when needed
  FROM base AS deps
  RUN apk add --no-cache libc6-compat
  WORKDIR /app
  
  # Install dependencies based on the preferred package manager
  COPY package.json pnpm-lock.yaml* ./
  RUN corepack enable pnpm && pnpm i --frozen-lockfile
  
  # Rebuild the source code only when needed
  FROM base AS builder
  WORKDIR /app
  COPY --from=deps /app/node_modules ./node_modules
  COPY . .
  
  # Build arguments for environment variables
  ARG NEXT_PUBLIC_API_URL
  ARG NEXT_PUBLIC_SUPABASE_URL
  ARG NEXT_PUBLIC_SUPABASE_ANON_KEY
  
  ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
  ENV NEXT_PUBLIC_SUPABASE_URL=$NEXT_PUBLIC_SUPABASE_URL
  ENV NEXT_PUBLIC_SUPABASE_ANON_KEY=$NEXT_PUBLIC_SUPABASE_ANON_KEY
  
  RUN corepack enable pnpm && pnpm build
  
  # Production image, copy all the files and run next
  FROM base AS runner
  WORKDIR /app
  
  ENV NODE_ENV=production
  
  RUN addgroup --system --gid 1001 nodejs
  RUN adduser --system --uid 1001 nextjs
  
  COPY --from=builder /app/public ./public
  
  # Set the correct permission for prerender cache
  RUN mkdir .next
  RUN chown nextjs:nodejs .next
  
  # Automatically leverage output traces to reduce image size
  COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
  COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
  
  USER nextjs
  
  EXPOSE 3000
  
  ENV PORT=3000
  ENV HOSTNAME="0.0.0.0"
  
  CMD ["node", "server.js"]

# Docker Compose for local development
DOCKER_COMPOSE:
  version: '3.8'
  services:
    frontend:
      build:
        context: .
        dockerfile: Dockerfile
        args:
          NEXT_PUBLIC_API_URL: http://localhost:8000
          NEXT_PUBLIC_SUPABASE_URL: ${SUPABASE_URL}
          NEXT_PUBLIC_SUPABASE_ANON_KEY: ${SUPABASE_ANON_KEY}
      ports:
        - "3000:3000"
      environment:
        - NODE_ENV=production
      depends_on:
        - backend
      networks:
        - app-network
    
    backend:
      image: your-backend-image:latest
      ports:
        - "8000:8000"
      networks:
        - app-network
  
  networks:
    app-network:
      driver: bridge
```

## Monitoring and Analytics

### Performance Monitoring
```typescript
// Pseudocode: Performance monitoring setup
PERFORMANCE_MONITORING:
  // Web Vitals tracking
  FUNCTION reportWebVitals(metric: NextWebVitalsMetric):
    // Send to analytics service
    IF process.env.NODE_ENV === 'production':
      analytics.track('Web Vitals', {
        name: metric.name,
        value: metric.value,
        id: metric.id,
        label: metric.label
      })
    
    // Send to monitoring service (e.g., Sentry)
    Sentry.addBreadcrumb({
      category: 'web-vital',
      message: `${metric.name}: ${metric.value}`,
      level: 'info'
    })
  
  // Error tracking
  FUNCTION setupErrorTracking():
    Sentry.init({
      dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,
      environment: process.env.NEXT_PUBLIC_APP_ENV,
      tracesSampleRate: process.env.NODE_ENV === 'production' ? 0.1 : 1.0,
      beforeSend: (event) => {
        // Filter out development errors
        IF process.env.NODE_ENV === 'development':
          RETURN null
        RETURN event
      }
    })
  
  // Custom metrics
  FUNCTION trackCustomMetrics():
    // Track API response times
    apiClient.interceptors.response.use(
      (response) => {
        duration = Date.now() - response.config.metadata.startTime
        analytics.track('API Response Time', {
          endpoint: response.config.url,
          method: response.config.method,
          duration: duration,
          status: response.status
        })
        RETURN response
      },
      (error) => {
        analytics.track('API Error', {
          endpoint: error.config?.url,
          method: error.config?.method,
          status: error.response?.status,
          message: error.message
        })
        RETURN Promise.reject(error)
      }
    )

// Analytics configuration
ANALYTICS_CONFIG:
  // Google Analytics 4
  GA4_CONFIG:
    measurementId: process.env.NEXT_PUBLIC_GA_MEASUREMENT_ID
    config:
      page_title: document.title
      page_location: window.location.href
      custom_map:
        custom_parameter_1: 'user_type'
        custom_parameter_2: 'analysis_type'
  
  // Custom event tracking
  FUNCTION trackAnalysisEvent(videoId: string, analysisType: string):
    gtag('event', 'video_analysis', {
      video_id: videoId,
      analysis_type: analysisType,
      user_type: isAuthenticated ? 'authenticated' : 'guest'
    })
  
  FUNCTION trackChatEvent(sessionId: string, messageCount: number):
    gtag('event', 'chat_interaction', {
      session_id: sessionId,
      message_count: messageCount,
      user_type: isAuthenticated ? 'authenticated' : 'guest'
    })
```

### Health Checks and Monitoring
```typescript
// Pseudocode: Application health monitoring
HEALTH_MONITORING:
  // Health check endpoint
  API_ROUTE '/api/health':
    FUNCTION GET():
      healthStatus = {
        status: 'healthy',
        timestamp: new Date().toISOString(),
        version: process.env.npm_package_version,
        environment: process.env.NEXT_PUBLIC_APP_ENV,
        checks: {
          database: await checkDatabaseConnection(),
          api: await checkAPIConnection(),
          cache: await checkCacheConnection()
        }
      }
      
      allHealthy = Object.values(healthStatus.checks).every(check => check.status === 'healthy')
      
      RETURN Response.json(
        healthStatus,
        { status: allHealthy ? 200 : 503 }
      )
  
  // Uptime monitoring
  FUNCTION setupUptimeMonitoring():
    // Ping health endpoint every 5 minutes
    setInterval(async () => {
      TRY:
        response = await fetch('/api/health')
        IF response.ok:
          console.log('Health check passed')
        ELSE:
          console.error('Health check failed:', response.status)
          // Send alert to monitoring service
          sendAlert('Health check failed', { status: response.status })
      CATCH error:
        console.error('Health check error:', error)
        sendAlert('Health check error', { error: error.message })
    }, 5 * 60 * 1000)
  
  // Performance monitoring
  FUNCTION monitorPerformance():
    // Monitor bundle size
    IF typeof window !== 'undefined':
      observer = new PerformanceObserver((list) => {
        FOR EACH entry IN list.getEntries():
          IF entry.entryType === 'navigation':
            analytics.track('Page Load Performance', {
              loadTime: entry.loadEventEnd - entry.loadEventStart,
              domContentLoaded: entry.domContentLoadedEventEnd - entry.domContentLoadedEventStart,
              firstPaint: entry.responseEnd - entry.requestStart
            })
      })
      observer.observe({ entryTypes: ['navigation'] })
```

This deployment specification provides comprehensive guidance for deploying the Next.js frontend with proper CI/CD pipelines, monitoring, and production-ready configurations.