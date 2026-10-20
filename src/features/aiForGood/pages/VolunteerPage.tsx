import { HeartHandshake } from 'lucide-react';
import { LinkButton } from '../../../components/ui/Button';
import { AIForGoodSubnav } from '../components/AIForGoodSubnav';
import { DemoNotice } from '../components/DemoNotice';

export default function VolunteerPage() {
  return (
    <>
      <AIForGoodSubnav />
      <div className="mx-auto max-w-xl px-4 py-20 text-center">
        <span className="brand-gradient mx-auto grid h-14 w-14 place-items-center rounded-2xl text-white">
          <HeartHandshake size={24} aria-hidden />
        </span>
        <h1 className="mt-5 text-3xl font-semibold tracking-tight">Volunteer tools</h1>
        <p className="mt-3 text-muted">
          Volunteers will eventually help keep resource information up to date. This area is a
          placeholder: no inventory can be viewed or changed here yet.
        </p>
        <DemoNotice className="mt-6 text-left">
          Updating inventory will require signing in. It is intentionally not available in this
          demo.
        </DemoNotice>
        <LinkButton to="/ai-for-good" variant="secondary" className="mt-6">
          Back to overview
        </LinkButton>
      </div>
    </>
  );
}
