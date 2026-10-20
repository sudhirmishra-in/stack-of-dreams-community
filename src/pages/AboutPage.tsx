import { ExternalLinkButton } from '../components/ui/Button';
import { Card } from '../components/ui/Card';

const FOCUS = [
  'Enterprise AI architecture',
  'Agentic AI systems',
  'Cloud-native applications',
  'Computer vision',
  'Multimodal AI',
  'Advanced computing',
];

export default function AboutPage() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-12">
      <h1 className="text-3xl font-semibold tracking-tight">Sudhir Mishra</h1>
      <p className="mt-1 text-accent">AI Architect | Agentic AI | Cloud | Advanced Computing</p>
      <p className="mt-6 text-muted">
        I design and build AI systems with a focus on how they fit into real enterprise and
        cloud-native environments. Stack of Dreams Labs is a personal space where I prototype
        agentic AI ideas and present the architecture behind them.
      </p>
      <h2 className="mt-8 mb-3 text-lg font-semibold">Areas of focus</h2>
      <ul className="grid gap-3 sm:grid-cols-2">
        {FOCUS.map((f) => (
          <li key={f}>
            <Card className="!p-4 text-sm">{f}</Card>
          </li>
        ))}
      </ul>
      <div className="mt-8">
        <ExternalLinkButton href="https://sudhirmishra.in">
          Visit sudhirmishra.in
        </ExternalLinkButton>
      </div>
    </div>
  );
}
