import { Package, Baby, Building2, ShoppingBasket, type LucideIcon } from 'lucide-react';
import type { ResourceType } from '../features/aiForGood/types/resource';

export interface ResourceCategory {
  id: ResourceType;
  label: string;
  /** Short name for the landing card. */
  cardTitle: string;
  description: string;
  action: string;
  icon: LucideIcon;
  /** Unit label for the quantity field; undefined means quantity does not apply. */
  quantityUnit?: string;
  /** Stock below this (but above 0) is shown as "Low stock". */
  lowThreshold?: number;
}

export const RESOURCE_CATEGORIES: ResourceCategory[] = [
  {
    id: 'baby_formula',
    label: 'Baby Formula',
    cardTitle: 'Baby Formula',
    description: 'Find organizations with infant formula on hand.',
    action: 'Find formula',
    icon: Baby,
    quantityUnit: 'units',
    lowThreshold: 50,
  },
  {
    id: 'groceries',
    label: 'Groceries',
    cardTitle: 'Groceries',
    description: 'Produce, canned goods and dairy from local pantries.',
    action: 'Find groceries',
    icon: ShoppingBasket,
    quantityUnit: 'lbs',
    lowThreshold: 1000,
  },
  {
    id: 'diapers',
    label: 'Diapers',
    cardTitle: 'Diapers',
    description: 'Look for diaper supplies for infants and toddlers.',
    action: 'Find diapers',
    icon: Package,
    quantityUnit: 'units',
    lowThreshold: 50,
  },
  {
    id: 'food_assistance',
    label: 'Food Assistance',
    cardTitle: 'Food Banks',
    description: 'See nearby food banks and how many households they serve.',
    action: 'Find food banks',
    icon: Building2,
  },
];

export const getCategory = (id: ResourceType): ResourceCategory =>
  RESOURCE_CATEGORIES.find((c) => c.id === id) ?? RESOURCE_CATEGORIES[0];

export const isResourceType = (v: unknown): v is ResourceType =>
  RESOURCE_CATEGORIES.some((c) => c.id === v);

export const FORMULA_TYPES = [
  { value: 'standard', label: 'Standard' },
  { value: 'sensitive', label: 'Sensitive' },
  { value: 'hypoallergenic', label: 'Hypoallergenic' },
  { value: 'other', label: 'Other / Specific Brand' },
];

export const URGENCY_OPTIONS = [
  { value: 'today', label: 'Today' },
  { value: 'three_days', label: 'Within 3 days' },
  { value: 'this_week', label: 'This week' },
];
