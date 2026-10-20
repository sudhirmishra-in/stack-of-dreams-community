import { useId, useState, type FormEvent } from 'react';
import {
  RESOURCE_CATEGORIES,
  FORMULA_TYPES,
  URGENCY_OPTIONS,
  getCategory,
} from '../../../config/resourceCategories';
import { Button } from '../../../components/ui/Button';
import {
  validateSearchForm,
  type SearchFormErrors,
  type SearchFormValues,
} from '../utils/searchParams';
import type { ResourceSearchRequest } from '../types/resource';

interface Props {
  initial?: Partial<SearchFormValues>;
  onSubmit: (request: ResourceSearchRequest, notes: string) => void;
}

const inputClass =
  'min-h-11 w-full rounded-xl border border-line bg-surface px-3 py-2 text-sm outline-none focus:border-accent aria-[invalid=true]:border-red-500';

function FieldError({ id, message }: { id: string; message?: string }) {
  if (!message) return null;
  return (
    <p id={id} className="mt-1 text-sm text-red-600 dark:text-red-300">
      {message}
    </p>
  );
}

export function ResourceSearchForm({ initial, onSubmit }: Props) {
  const uid = useId();
  const [values, setValues] = useState<SearchFormValues>({
    resourceType: '',
    zipCode: '',
    quantity: '',
    formulaType: '',
    urgency: '',
    notes: '',
    ...initial,
  });
  const [errors, setErrors] = useState<SearchFormErrors>({});
  const set = <K extends keyof SearchFormValues>(k: K, v: SearchFormValues[K]) =>
    setValues((s) => ({ ...s, [k]: v }));

  const category = values.resourceType ? getCategory(values.resourceType) : undefined;
  const errorCount = Object.keys(errors).length;

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const { errors: errs, request } = validateSearchForm(values);
    setErrors(errs);
    if (request) onSubmit(request, values.notes);
  };

  return (
    <form onSubmit={submit} noValidate className="space-y-6">
      {errorCount > 0 && (
        <div
          role="alert"
          className="rounded-xl border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm"
        >
          <p className="font-medium">
            Please fix {errorCount === 1 ? '1 problem' : `${errorCount} problems`}:
          </p>
          <ul className="mt-1 list-disc pl-5 text-muted">
            {Object.values(errors).map((m) => (
              <li key={m}>{m}</li>
            ))}
          </ul>
        </div>
      )}

      <fieldset aria-describedby={errors.resourceType ? `${uid}-type-err` : undefined}>
        <legend className="mb-2 text-sm font-medium">What do you need?</legend>
        <div className="grid gap-2 sm:grid-cols-2">
          {RESOURCE_CATEGORIES.map((c) => {
            const Icon = c.icon;
            const selected = values.resourceType === c.id;
            return (
              <label
                key={c.id}
                className={`flex min-h-14 cursor-pointer items-center gap-3 rounded-xl border px-3 py-2 transition has-[:focus-visible]:outline has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-accent ${
                  selected
                    ? 'border-accent bg-surface-2'
                    : 'border-line bg-surface hover:bg-surface-2'
                }`}
              >
                <input
                  type="radio"
                  name="resourceType"
                  value={c.id}
                  checked={selected}
                  onChange={() => set('resourceType', c.id)}
                  className="sr-only"
                />
                <Icon size={20} className="text-accent" aria-hidden />
                <span className="text-sm font-medium">{c.label}</span>
              </label>
            );
          })}
        </div>
        <FieldError id={`${uid}-type-err`} message={errors.resourceType} />
      </fieldset>

      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label htmlFor={`${uid}-zip`} className="mb-1 block text-sm font-medium">
            ZIP code
          </label>
          <input
            id={`${uid}-zip`}
            inputMode="numeric"
            autoComplete="postal-code"
            maxLength={5}
            placeholder="10027"
            value={values.zipCode}
            onChange={(e) => set('zipCode', e.target.value.replace(/\D/g, ''))}
            aria-invalid={!!errors.zipCode}
            aria-describedby={errors.zipCode ? `${uid}-zip-err` : undefined}
            className={inputClass}
          />
          <FieldError id={`${uid}-zip-err`} message={errors.zipCode} />
        </div>

        {category?.quantityUnit && (
          <div>
            <label htmlFor={`${uid}-qty`} className="mb-1 block text-sm font-medium">
              Quantity needed{' '}
              <span className="font-normal text-muted">(optional, {category.quantityUnit})</span>
            </label>
            <input
              id={`${uid}-qty`}
              inputMode="numeric"
              value={values.quantity}
              onChange={(e) => set('quantity', e.target.value)}
              aria-invalid={!!errors.quantity}
              aria-describedby={errors.quantity ? `${uid}-qty-err` : undefined}
              className={inputClass}
            />
            <FieldError id={`${uid}-qty-err`} message={errors.quantity} />
          </div>
        )}

        {values.resourceType === 'baby_formula' && (
          <div>
            <label htmlFor={`${uid}-formula`} className="mb-1 block text-sm font-medium">
              Formula type
            </label>
            <select
              id={`${uid}-formula`}
              value={values.formulaType}
              onChange={(e) => set('formulaType', e.target.value)}
              className={inputClass}
            >
              <option value="">No preference</option>
              {FORMULA_TYPES.map((f) => (
                <option key={f.value} value={f.value}>
                  {f.label}
                </option>
              ))}
            </select>
          </div>
        )}

        <div>
          <label htmlFor={`${uid}-urgency`} className="mb-1 block text-sm font-medium">
            How soon do you need it?
          </label>
          <select
            id={`${uid}-urgency`}
            value={values.urgency}
            onChange={(e) => set('urgency', e.target.value as SearchFormValues['urgency'])}
            className={inputClass}
          >
            <option value="">Not sure</option>
            {URGENCY_OPTIONS.map((u) => (
              <option key={u.value} value={u.value}>
                {u.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div>
        <label htmlFor={`${uid}-notes`} className="mb-1 block text-sm font-medium">
          Additional notes <span className="font-normal text-muted">(optional)</span>
        </label>
        <textarea
          id={`${uid}-notes`}
          rows={3}
          maxLength={300}
          value={values.notes}
          onChange={(e) => set('notes', e.target.value)}
          aria-describedby={`${uid}-notes-help`}
          className={inputClass}
        />
        <p id={`${uid}-notes-help`} className="mt-1 text-xs text-muted">
          Please don't include names, phone numbers, or health details. Notes are only used if you
          ask the AI assistant for help.
        </p>
      </div>

      <Button type="submit" className="w-full sm:w-auto">
        Find Resources
      </Button>
    </form>
  );
}
