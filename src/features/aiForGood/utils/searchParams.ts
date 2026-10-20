import { isResourceType } from '../../../config/resourceCategories';
import type { ResourceSearchRequest, ResourceType, Urgency } from '../types/resource';

export interface SearchFormValues {
  resourceType: ResourceType | '';
  zipCode: string;
  quantity: string;
  formulaType: string;
  urgency: Urgency | '';
  notes: string;
}

export type SearchFormErrors = Partial<Record<'resourceType' | 'zipCode' | 'quantity', string>>;

export const ZIP_PATTERN = /^\d{5}$/;
const URGENCIES: Urgency[] = ['today', 'three_days', 'this_week'];

export function validateSearchForm(v: SearchFormValues): {
  errors: SearchFormErrors;
  request?: ResourceSearchRequest;
} {
  const errors: SearchFormErrors = {};
  if (!v.resourceType) errors.resourceType = 'Choose the type of help you need.';
  if (!ZIP_PATTERN.test(v.zipCode.trim()))
    errors.zipCode = 'Enter a 5-digit ZIP code, for example 10027.';

  let quantity: number | undefined;
  if (v.quantity.trim() !== '') {
    quantity = Number(v.quantity);
    if (!Number.isInteger(quantity) || quantity <= 0) {
      errors.quantity = 'Quantity must be a whole number greater than 0, or left blank.';
      quantity = undefined;
    }
  }
  if (Object.keys(errors).length > 0 || !v.resourceType) return { errors };

  return {
    errors,
    request: {
      resourceType: v.resourceType,
      zipCode: v.zipCode.trim(),
      quantity,
      formulaType: v.resourceType === 'baby_formula' && v.formulaType ? v.formulaType : undefined,
      urgency: v.urgency || undefined,
    },
  };
}

/** Only non-sensitive search criteria go in the URL. Free-text notes never do. */
export function toSearchParams(r: ResourceSearchRequest): URLSearchParams {
  const p = new URLSearchParams({ type: r.resourceType, zip: r.zipCode });
  if (r.quantity) p.set('qty', String(r.quantity));
  if (r.formulaType) p.set('formula', r.formulaType);
  if (r.urgency) p.set('urgency', r.urgency);
  return p;
}

export function parseSearchParams(p: URLSearchParams): ResourceSearchRequest | null {
  const type = p.get('type');
  const zip = p.get('zip') ?? '';
  if (!isResourceType(type) || !ZIP_PATTERN.test(zip)) return null;
  const qty = Number(p.get('qty'));
  const urgency = p.get('urgency') as Urgency | null;
  return {
    resourceType: type,
    zipCode: zip,
    quantity: Number.isInteger(qty) && qty > 0 ? qty : undefined,
    formulaType: p.get('formula')?.slice(0, 40) || undefined,
    urgency: urgency && URGENCIES.includes(urgency) ? urgency : undefined,
  };
}
