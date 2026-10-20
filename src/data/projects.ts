import type { ChallengeCategory, HackathonProject, ProjectStatus } from '../types/project';

/**
 * Hackathon project registry. To add a project, append an entry here.
 * Only include demoUrl / repoUrl / details once they really exist.
 */
export const PROJECTS: HackathonProject[] = [
  {
    id: 'aws-breaking-barriers-2026',
    name: 'AWS Breaking Barriers 2026',
    description:
      'A collaborative AI solution to be developed during the AWS Breaking Barriers 2026 hackathon.',
    category: 'AI for Good',
    status: 'upcoming',
  },
  {
    id: 'community-resource-navigator',
    name: 'Community Resource Navigator',
    description:
      'Connecting families with essential resources through AI. Demo application with synthetic data.',
    category: 'AI for Good',
    status: 'in-progress',
    agentId: 'assistant',
    details: {
      overview:
        'A resource-finding application for families, with a read-only coordinator dashboard. It currently runs on synthetic demo data.',
      problemStatement:
        'Families can struggle to find out which nearby organizations have essential items such as baby formula in stock.',
      proposedSolution:
        'Guided resource search with structured results, plus an AI assistant that explains and compares results using only supplied facts.',
      techStack: [
        'React',
        'TypeScript',
        'Tailwind CSS',
        'AWS Lambda',
        'Amazon Bedrock AgentCore',
        'Strands Agents',
      ],
    },
  },
];

export const CHALLENGES: ChallengeCategory[] = [
  {
    id: 'education',
    title: 'Education',
    areas: ['Personalized learning', 'Accessibility', 'Educational assistance'],
  },
  {
    id: 'healthcare',
    title: 'Healthcare',
    areas: ['Healthcare navigation', 'Community health information', 'Accessibility'],
  },
  {
    id: 'climate',
    title: 'Climate Resilience',
    areas: ['Disaster preparedness', 'Environmental information', 'Community assistance'],
  },
];

export const STATUS_LABELS: Record<ProjectStatus, string> = {
  upcoming: 'Upcoming',
  'in-progress': 'In progress',
  completed: 'Completed',
  archived: 'Archived',
};

export const getProject = (id: string | undefined, projects = PROJECTS) =>
  projects.find((p) => p.id === id);
