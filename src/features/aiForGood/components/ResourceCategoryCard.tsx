import { Link } from 'react-router';
import { ArrowRight } from 'lucide-react';
import { Card } from '../../../components/ui/Card';
import type { ResourceCategory } from '../../../config/resourceCategories';

export function ResourceCategoryCard({ category }: { category: ResourceCategory }) {
  const Icon = category.icon;
  return (
    <Card className="flex h-full flex-col gap-3 transition hover:border-accent/50">
      <span className="brand-gradient grid h-11 w-11 place-items-center rounded-xl text-white">
        <Icon size={22} aria-hidden />
      </span>
      <div className="flex-1">
        <h3 className="font-semibold">{category.cardTitle}</h3>
        <p className="mt-1 text-sm text-muted">{category.description}</p>
      </div>
      <Link
        to={`/ai-for-good/find?type=${category.id}`}
        aria-label={`${category.action}: ${category.cardTitle}`}
        className="inline-flex min-h-11 items-center gap-1 text-sm font-medium text-accent hover:underline"
      >
        {category.action} <ArrowRight size={14} aria-hidden />
      </Link>
    </Card>
  );
}
