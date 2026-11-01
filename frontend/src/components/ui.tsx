import { forwardRef, type ButtonHTMLAttributes, type HTMLAttributes } from 'react';
import { Link } from 'react-router-dom';
import { Asterisk, ArrowUpRight } from 'lucide-react';
import { cn } from '../lib/utils';
export const Button = forwardRef<HTMLButtonElement, ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'secondary' }>(({ className, variant = 'primary', ...props }, ref) => <button ref={ref} className={cn('button', variant === 'primary' ? 'bg-lavender' : 'bg-white/70', className)} {...props} />);
Button.displayName = 'Button';
export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) { return <div className={cn('min-w-0 rounded-3xl bg-white/80 shadow-clay', className)} {...props} />; }
export function Logo() { return <Link to="/" className="flex items-center gap-2.5" aria-label="Gather home"><span className="logo-mark"><Asterisk size={26} strokeWidth={2.8} /></span><span className="font-display text-2xl font-extrabold tracking-[-1px]">gather<span className="text-lilac">.</span></span></Link>; }
export function Footer() { return <footer className="page-container flex flex-wrap items-center justify-between gap-5 border-t border-charcoal/10 py-7 text-xs text-muted"><span>Made for the moments that matter.</span><span className="flex items-center gap-1">Gather · Your GenAI event planner <ArrowUpRight size={13} /></span></footer>; }
