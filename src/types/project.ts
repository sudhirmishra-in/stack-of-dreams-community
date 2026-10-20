import type { AppBranding } from './branding';
import type { ArchNode } from '../components/ui/ArchitectureFlow';

export type ProjectStatus = 'upcoming' | 'in-progress' | 'completed' | 'archived';

export interface TeamMember {
  name: string;
  role?: string;
}

export interface ProjectDetails {
  overview?: string;
  problemStatement?: string;
  proposedSolution?: string;
  techStack?: string[];
  /** Custom architecture; the shared proposed architecture is shown when omitted. */
  architecture?: ArchNode[];
  team?: TeamMember[];
}

export interface HackathonProject {
  id: string;
  name: string;
  description: string;
  /** e.g. "AI for Good" or one of the challenge categories. */
  category: string;
  status: ProjectStatus;
  /** Agent (from the branding's agent list) this project uses, once one exists. */
  agentId?: string;
  demoUrl?: string;
  repoUrl?: string;
  details?: ProjectDetails;
  /** Overrides applied on top of the default branding inside the project's app route. */
  branding?: Partial<AppBranding>;
}

export interface ChallengeCategory {
  id: string;
  title: string;
  areas: string[];
}
