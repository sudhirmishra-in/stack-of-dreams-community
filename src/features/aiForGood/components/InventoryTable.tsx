import { AVAILABILITY_LABELS, availabilityOf } from '../utils/availability';
import { formatNumber } from '../utils/format';
import type { Resource } from '../types/resource';

const badge = {
  in_stock: 'border-emerald-500/40 text-emerald-700 dark:text-emerald-300',
  low: 'border-amber-500/40 text-amber-700 dark:text-amber-300',
  out: 'border-red-500/40 text-red-700 dark:text-red-300',
  unknown: 'border-line text-muted',
} as const;

export function InventoryTable({ resources }: { resources: Resource[] }) {
  return (
    <div className="overflow-x-auto rounded-2xl border border-line">
      <table className="w-full min-w-[40rem] text-left text-sm">
        <caption className="sr-only">
          Baby formula inventory and weekly capacity by food bank (demo data)
        </caption>
        <thead className="bg-surface-2 text-xs uppercase tracking-wider text-muted">
          <tr>
            <th scope="col" className="px-4 py-3">
              Food Bank
            </th>
            <th scope="col" className="px-4 py-3">
              Location
            </th>
            <th scope="col" className="px-4 py-3">
              Available Units
            </th>
            <th scope="col" className="px-4 py-3">
              Weekly Capacity
            </th>
            <th scope="col" className="px-4 py-3">
              Inventory Status
            </th>
          </tr>
        </thead>
        <tbody>
          {resources.map((r) => {
            const s = availabilityOf(r, 'baby_formula');
            return (
              <tr key={r.id} className="border-t border-line">
                <th scope="row" className="px-4 py-3 font-medium">
                  {r.name}
                </th>
                <td className="px-4 py-3">
                  {[r.borough ?? r.city, r.zipCode].filter(Boolean).join(' · ')}
                </td>
                <td className="px-4 py-3">{formatNumber(r.inventory?.baby_formula)}</td>
                <td className="px-4 py-3">{formatNumber(r.weeklyCapacity, 'households/wk')}</td>
                <td className="px-4 py-3">
                  <span className={`rounded-full border px-2.5 py-0.5 text-xs ${badge[s]}`}>
                    {AVAILABILITY_LABELS[s]}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
