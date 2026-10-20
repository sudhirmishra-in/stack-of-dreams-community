import { Link } from 'react-router';
import { ArrowRight } from 'lucide-react';
import { LinkButton } from '../../../components/ui/Button';
import { RESOURCE_CATEGORIES } from '../../../config/resourceCategories';
import { AIForGoodSubnav } from '../components/AIForGoodSubnav';
import { DEMO_APP_NOTICE, DemoNotice } from '../components/DemoNotice';
import { ResourceCategoryCard } from '../components/ResourceCategoryCard';

const STEPS = [
  'Tell us what you need.',
  'Enter your location.',
  'Explore available resources.',
  'Connect with a provider.',
];

export default function AIForGoodPage() {
  return (
    <>
      <AIForGoodSubnav />
      <section className="bg-grid">
        <div className="mx-auto max-w-4xl px-4 py-16 text-center sm:py-24">
          <p className="mb-3 text-sm font-medium text-accent-2">Community Resource Navigator</p>
          <h1 className="text-4xl font-semibold tracking-tight sm:text-5xl">
            <span className="text-gradient">Find the Help You Need</span>
          </h1>
          <p className="mt-4 text-xl sm:text-2xl">
            Connecting communities with essential resources.
          </p>
          <p className="mx-auto mt-5 max-w-2xl text-muted">
            Search for food, baby formula, diapers, and community assistance using an AI-powered
            resource navigator.
          </p>
          <div className="mt-8 flex flex-wrap justify-center gap-3">
            <LinkButton to="/ai-for-good/find" className="px-6 py-3">
              Find Assistance <ArrowRight size={16} aria-hidden />
            </LinkButton>
            <LinkButton to="/ai-for-good/assistant" variant="secondary" className="px-6 py-3">
              Explore AI Assistant
            </LinkButton>
          </div>
          <p className="mt-3 text-sm text-muted">
            Connecting Families with Essential Resources Through AI
          </p>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-12" aria-labelledby="cats">
        <h2 id="cats" className="mb-6 text-2xl font-semibold tracking-tight">
          What are you looking for?
        </h2>
        <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {RESOURCE_CATEGORIES.map((c) => (
            <li key={c.id}>
              <ResourceCategoryCard category={c} />
            </li>
          ))}
        </ul>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-10" aria-labelledby="how">
        <h2 id="how" className="mb-6 text-2xl font-semibold tracking-tight">
          How It Works
        </h2>
        <ol className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {STEPS.map((s, i) => (
            <li
              key={s}
              className="flex items-start gap-3 rounded-2xl border border-line bg-surface p-4"
            >
              <span className="brand-gradient grid h-8 w-8 shrink-0 place-items-center rounded-full text-sm font-semibold text-white">
                {i + 1}
              </span>
              <div>
                <p className="text-xs uppercase tracking-wider text-muted">Step {i + 1}</p>
                <p className="font-medium">{s}</p>
              </div>
            </li>
          ))}
        </ol>
      </section>

      <section className="mx-auto max-w-6xl space-y-4 px-4 pb-16 pt-6">
        <DemoNotice>{DEMO_APP_NOTICE}</DemoNotice>
        <p className="text-sm text-muted">
          Nonprofit staff can preview the{' '}
          <Link to="/ai-for-good/dashboard" className="text-accent underline">
            coordinator dashboard
          </Link>
          . Learn about the{' '}
          <Link to="/ai-for-good/program" className="text-accent underline">
            AI for Good program and hackathon projects
          </Link>
          .
        </p>
      </section>
    </>
  );
}
