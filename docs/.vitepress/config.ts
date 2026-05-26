import { defineConfig } from 'vitepress'

export default defineConfig({
  title: 'Homeschool Hero',
  description: 'Open-source homeschool learning, grading, and management platform',
  base: '/homeschool-hero/',
  lastUpdated: true,
  themeConfig: {
    nav: [
      { text: 'Home', link: '/' },
      { text: 'Guides', link: '/teacher-guide' },
      { text: 'Architecture', link: '/architecture' },
      { text: 'API Reference', link: '/api/' },
      { text: 'Dev Guide', link: '/dev/' },
      { text: 'GitHub', link: 'https://github.com/x3nc0n/homeschool-hero' },
    ],
    sidebar: [
      {
        text: 'Getting Started',
        items: [
          { text: 'Overview', link: '/' },
          { text: 'Parent & Teacher Guide', link: '/teacher-guide' },
          { text: 'Student Guide', link: '/student-guide' },
          { text: 'Administrator Guide', link: '/admin-guide' },
          { text: 'Training', link: '/training' },
        ],
      },
      {
        text: 'API Reference',
        items: [
          { text: 'Overview', link: '/api/' },
          { text: 'Authentication', link: '/api/authentication' },
          { text: 'Endpoints', link: '/api/endpoints' },
          { text: 'Errors', link: '/api/errors' },
        ],
      },
      {
        text: 'Developer Guide',
        items: [
          { text: 'Overview', link: '/dev/' },
          { text: 'Local Setup', link: '/dev/setup' },
          { text: 'Testing', link: '/dev/testing' },
          { text: 'Contributing', link: '/dev/contributing' },
        ],
      },
      {
        text: 'Development',
        items: [
          { text: 'Development Guide', link: '/development' },
          { text: 'Testing', link: '/testing' },
          { text: 'Migrations', link: '/migrations' },
          { text: 'Maintenance', link: '/maintenance' },
        ],
      },
      {
        text: 'Architecture',
        items: [
          { text: 'MVP Architecture', link: '/architecture' },
          { text: 'Architecture Decisions', link: '/architecture-decisions' },
          { text: 'Unified RBAC Model', link: '/architecture/rbac-unified-model' },
        ],
      },
      {
        text: 'Reference',
        items: [
          { text: 'API Integration', link: '/api-integration' },
          { text: 'Auth Providers', link: '/auth-providers' },
          { text: 'Accessibility Checklist', link: '/accessibility-checklist' },
          { text: 'Security Scanning', link: '/security-scanning' },
          { text: 'TLS Setup', link: '/tls-setup' },
        ],
      },
    ],
    socialLinks: [{ icon: 'github', link: 'https://github.com/x3nc0n/homeschool-hero' }],
    search: {
      provider: 'local',
    },
  },
})
