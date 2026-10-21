import { getCategory } from '../../../config/resourceCategories';
import type { Resource, ResourceSearchRequest, ResourceType } from '../types/resource';
import { formatNumber, NOT_AVAILABLE } from './format';

// Each of these was run against the live runtime and got a grounded answer. Real providers have no inventory or
// capacity data, so prompts must not ask for it as fact (the third one deliberately gets "unknown").
export const AI_FOR_GOOD_STARTER_PROMPTS = [
  'Find food pantries near ZIP 10027 in Manhattan.',
  'Which food banks are closest to ZIP 11201 in Brooklyn?',
  'Does the Community Kitchen and Pantry on West 116th Street have food today?',
  'How much food assistance activity has NYC reported recently?',
];

const GUARDRAIL =
  'Use only the facts listed below. If something is not listed, say it is unknown and suggest contacting the organization. Do not invent addresses, phone numbers, hours, or eligibility rules. This is demonstration data, not verified inventory.';

function describe(r: Resource, type?: ResourceType): string {
  const parts = [
    `${r.name} (${r.borough ?? r.city}${r.zipCode ? `, ZIP ${r.zipCode}` : ''})`,
    `weekly capacity: ${r.weeklyCapacity !== undefined ? `${r.weeklyCapacity} households` : NOT_AVAILABLE}`,
  ];
  if (type && type !== 'food_assistance') {
    const unit = getCategory(type).quantityUnit;
    parts.push(
      `${getCategory(type).label.toLowerCase()} available: ${formatNumber(r.availableQuantity ?? r.inventory?.[type], unit)}`,
    );
  }
  if (r.operatingDays?.length) parts.push(`open days: ${r.operatingDays.join(', ')}`);
  parts.push(r.isDemoData ? 'DEMO DATA' : r.verified ? 'verified' : 'not verified');
  return parts.join('; ');
}

export function buildResourcePrompt(r: Resource): string {
  const inv = Object.entries(r.inventory ?? {})
    .map(([t, q]) => `${getCategory(t as ResourceType).label}: ${q}`)
    .join(', ');
  return [
    `I want to know more about ${r.name}.`,
    GUARDRAIL,
    `Facts: ${describe(r)}.${inv ? ` Inventory: ${inv}.` : ''}`,
    'What should I know before contacting them, and what should I ask them?',
  ].join('\n');
}

export function buildResultsPrompt(
  resources: Resource[],
  req: ResourceSearchRequest,
  notes?: string,
): string {
  const cat = getCategory(req.resourceType);
  const list = resources
    .slice(0, 6)
    .map((r, i) => `${i + 1}. ${describe(r, req.resourceType)}`)
    .join('\n');
  return [
    `I searched for ${cat.label.toLowerCase()} near ZIP ${req.zipCode}${req.urgency ? ` (needed ${req.urgency.replace('_', ' ')})` : ''}.`,
    notes?.trim() ? `Note from me: ${notes.trim().slice(0, 300)}` : '',
    GUARDRAIL,
    resources.length ? `Results:\n${list}` : 'No matching resources were found.',
    'Which should I contact first, and why?',
  ]
    .filter(Boolean)
    .join('\n');
}
