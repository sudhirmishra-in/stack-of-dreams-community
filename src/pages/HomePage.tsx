import { ArrowRight, Boxes, Cloud, Cpu, Network, Workflow } from 'lucide-react';
import { LinkButton, ExternalLinkButton } from '../components/ui/Button';
import { Card } from '../components/ui/Card';
import { AgentDirectory } from '../components/agents/AgentDirectory';
import { ArchitectureFlow } from '../components/ui/ArchitectureFlow';
import { ExperimentalNotice } from '../components/ui/ExperimentalNotice';

const TECH = [
  { icon: Cloud, name: 'Amazon Bedrock', text: 'Managed access to foundation models.' },
  { icon: Cpu, name: 'Bedrock AgentCore', text: 'Managed runtime for deploying agents.' },
  { icon: Workflow, name: 'Strands Agents', text: 'Open-source SDK for building agents.' },
  { icon: Network, name: 'Multi-Agent Architecture', text: 'Specialized agents working together.' },
  { icon: Boxes, name: 'AWS Cloud', text: 'Serverless, cloud-native hosting.' },
];

export default function HomePage() {
  return (
    <>
      <section className="bg-grid">
        <div className="mx-auto max-w-4xl px-4 py-20 text-center sm:py-28">
          <p className="mb-4 inline-block rounded-full border border-line bg-surface px-3 py-1 text-xs text-muted">
            Experimental AI demo
          </p>
          <h1 className="text-4xl font-semibold tracking-tight sm:text-6xl">
            <span className="text-gradient">Stack of Dreams Labs</span>
          </h1>
          <p className="mt-4 text-xl text-fg sm:text-2xl">Intelligent Agents. Real-World Impact.</p>
          <p className="mx-auto mt-6 max-w-2xl text-muted">
            <strong className="text-fg">Agentic AI</strong> goes beyond answering questions: an
            agent plans, uses tools, observes results and iterates toward a goal. This platform
            explores how to build and present such agents on AWS using Amazon Bedrock AgentCore and
            the Strands Agents framework.
          </p>
          <div className="mt-8 flex flex-wrap justify-center gap-3">
            <LinkButton to="/chat" className="px-6 py-3">
              Launch AI Assistant <ArrowRight size={16} aria-hidden />
            </LinkButton>
            <LinkButton to="/architecture" variant="secondary" className="px-6 py-3">
              View architecture
            </LinkButton>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-14" aria-labelledby="tech">
        <h2 id="tech" className="mb-6 text-2xl font-semibold tracking-tight">
          Technology highlights
        </h2>
        <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
          {TECH.map(({ icon: Icon, name, text }) => (
            <li key={name}>
              <Card className="h-full">
                <Icon size={20} className="text-accent" aria-hidden />
                <h3 className="mt-3 text-sm font-semibold">{name}</h3>
                <p className="mt-1 text-xs text-muted">{text}</p>
              </Card>
            </li>
          ))}
        </ul>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-10" aria-labelledby="agents">
        <h2 id="agents" className="mb-2 text-2xl font-semibold tracking-tight">
          Featured agents
        </h2>
        <p className="mb-6 text-sm text-muted">
          Only the AI Assistant is interactive, and it currently runs in mock mode.
        </p>
        <AgentDirectory />
      </section>

      <section className="mx-auto max-w-6xl px-4 py-14" aria-labelledby="arch">
        <div className="grid items-center gap-8 lg:grid-cols-2">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-accent-2">
              Target architecture
            </p>
            <h2 id="arch" className="mt-1 text-2xl font-semibold tracking-tight">
              Architecture overview
            </h2>
            <p className="mt-3 text-muted">
              The design below is the planned path from browser to foundation model. The backend is
              not connected yet; this frontend runs against a local mock service.
            </p>
            <LinkButton to="/architecture" variant="secondary" className="mt-5">
              Explore each component
            </LinkButton>
          </div>
          <ArchitectureFlow compact />
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 pb-16">
        <Card className="flex flex-col items-start justify-between gap-4 sm:flex-row sm:items-center">
          <div>
            <h2 className="font-semibold">Learn more about the builder</h2>
            <p className="text-sm text-muted">Professional background and other work.</p>
          </div>
          <ExternalLinkButton href="https://sudhirmishra.in">sudhirmishra.in</ExternalLinkButton>
        </Card>
        <ExperimentalNotice className="mt-4" />
      </section>
    </>
  );
}
