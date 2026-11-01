import { useState } from 'react';
import { Check, GitCompareArrows } from 'lucide-react';
import { Card } from './ui';
import { compareVendors } from '../lib/vendors';
import { categoryLabel } from '../lib/budget';
import { cn, money } from '../lib/utils';
import type { VendorQuote } from '../types';

export default function VendorComparison({ vendors }: { vendors: VendorQuote[] }) {
  const [first, setFirst] = useState(0);
  const [second, setSecond] = useState(1);
  const leftIndex = first < vendors.length ? first : 0;
  const rightIndex = second < vendors.length && second !== leftIndex ? second : vendors.findIndex((_, index) => index !== leftIndex);
  const left = vendors[leftIndex];
  const right = vendors[rightIndex];
  if (!left || !right) return null;
  const comparison = compareVendors(left, right);
  const columns = [left, right];
  return <Card className="p-5 sm:p-7"><div className="mb-6 flex items-start gap-3"><span className="icon-tile !h-11 !w-11 shrink-0 bg-powder"><GitCompareArrows size={21}/></span><div><h3 id="vendor-comparison-title" className="font-display text-xl font-bold tracking-[-.5px]">A little clarity, side by side.</h3><p className="mt-2 text-xs leading-6 text-muted">Compare the quoted figures and scope before choosing your people. Prices below are in INR.</p></div></div>
    <div className="mb-5 grid grid-cols-1 gap-4 sm:grid-cols-2"><label htmlFor="compare-first">First quote<select id="compare-first" value={leftIndex} onChange={event => { const index = Number(event.target.value); setFirst(index); if (index === rightIndex) setSecond(leftIndex); }}>{vendors.map((vendor, index) => <option key={index} value={index}>{vendor.vendor_name} · {categoryLabel(vendor.category)} · Quote {index + 1}</option>)}</select></label><label htmlFor="compare-second">Second quote<select id="compare-second" value={rightIndex} onChange={event => setSecond(Number(event.target.value))}>{vendors.map((vendor, index) => <option key={index} value={index} disabled={index === leftIndex}>{vendor.vendor_name} · {categoryLabel(vendor.category)} · Quote {index + 1}</option>)}</select></label></div>
    <p className={cn('mb-5 rounded-xl px-4 py-3 text-xs leading-6', comparison.sameCategory ? 'bg-mint/60 text-[#527760]' : 'bg-peach text-[#8c6554]')}>{comparison.priceDifference === 0 ? 'These headline quotes have the same price.' : `The headline quotes differ by ${money(comparison.priceDifference, 'INR')}.`} {comparison.sameCategory ? 'Flagged fees and differences in scope can change the final cost.' : 'These quotes cover different service categories, so their prices aren’t directly comparable.'}</p>
    <p className="mb-3 text-[10px] leading-5 text-muted">Scroll sideways on smaller screens. Blue inclusion tags have wording that appears only in that quote.</p>
    <div className="overflow-x-auto rounded-2xl border border-charcoal/5"><table className="vendor-comparison w-full min-w-[650px] table-fixed text-left text-xs" aria-labelledby="vendor-comparison-title"><thead><tr><th scope="col" className="w-[20%] bg-cream p-4 font-medium text-muted">A closer look</th>{columns.map((vendor, index) => <th scope="col" key={index} className={cn('p-4 font-display text-sm leading-6', index === 0 ? 'bg-lavender/60' : 'bg-powder/70')}>{vendor.vendor_name}<span className="mt-1 block font-sans text-[10px] font-normal text-muted">{categoryLabel(vendor.category)} · Quote {(index === 0 ? leftIndex : rightIndex) + 1}</span></th>)}</tr></thead><tbody>
      <tr><th scope="row">Quoted price</th>{columns.map((vendor, index) => <td key={index}><p className="font-display text-xl font-semibold tracking-[-.5px]">{money(vendor.total_quoted, 'INR')}</p>{comparison.sameCategory && comparison.lowerPrice === (index === 0 ? 'left' : 'right') && <span className="mt-2 inline-block rounded-full bg-mint px-2.5 py-1 text-[10px] text-[#527760]">Lower headline quote</span>}</td>)}</tr>
      <tr><th scope="row">Flagged fees</th>{columns.map((vendor, index) => <td key={index}><span className={cn('inline-block rounded-full px-2.5 py-1 text-[10px]', vendor.hidden_fees.length ? 'bg-peach text-[#986552]' : 'bg-cream text-muted')}>{vendor.hidden_fees.length} flagged</span>{vendor.hidden_fees.length ? <ul className="mt-3 space-y-2">{vendor.hidden_fees.map((fee, i) => <li key={i} className="rounded-xl bg-peach/50 px-3 py-2 leading-6 text-[#8c6554]">{fee}</li>)}</ul> : <p className="mt-3 leading-6 text-muted">No fees flagged in this quote. Confirm taxes and extras.</p>}</td>)}</tr>
      <tr><th scope="row">Inclusions</th>{[comparison.leftInclusions, comparison.rightInclusions].map((items, index) => <td key={index}>{items.length ? <ul className="space-y-2">{items.map((item, i) => <li key={i} className={cn('flex items-start gap-1.5 rounded-xl px-3 py-2 leading-6', item.shared ? 'bg-cream text-muted' : 'bg-powder/70 text-[#546f80]')}><Check size={12} className="mt-1.5 shrink-0"/>{item.text}</li>)}</ul> : <p className="leading-6 text-muted">No inclusions specified.</p>}</td>)}</tr>
      <tr><th scope="row">Exclusions</th>{columns.map((vendor, index) => <td key={index}>{vendor.exclusions.length ? <ul className="space-y-2">{vendor.exclusions.map((item, i) => <li key={i} className="leading-6 text-muted">{item}</li>)}</ul> : <span className="text-muted">Not specified</span>}</td>)}</tr>
      <tr><th scope="row">Payment terms</th>{columns.map((vendor, index) => <td key={index} className="leading-6 text-muted">{vendor.payment_schedule || 'Not specified'}</td>)}</tr>
      <tr><th scope="row">Capacity</th>{columns.map((vendor, index) => <td key={index} className="text-muted">{vendor.capacity === null ? 'Not specified' : vendor.capacity.toLocaleString('en-IN')}</td>)}</tr>
    </tbody></table></div>
  </Card>;
}
