import { Check, Heart, Sparkles, CalendarDays } from 'lucide-react';
export default function Celebration() {
  return <div className="celebration" role="img" aria-label="Pastel balloon arch, a celebration cake, and a ready-to-celebrate event plan">
    <div className="scene-glow" /><div className="orbit orbit-one" /><div className="orbit orbit-two" />
    <span className="scene-spark spark-one">✧</span><span className="scene-spark spark-two">✦</span><span className="scene-spark spark-three">✧</span>
    <div className="floating-note note-top"><span className="rounded-xl bg-mint p-2 text-[#6f967f]"><Check size={18} /></span><div><strong>Big day. Little stress.</strong><small>You’ve got this. We’ve got the plan.</small></div></div>
    <div className="stage"><div className="arch"><div className="arch-inner" /></div><div className="balloon b1" /><div className="balloon b2" /><div className="balloon b3" /><div className="balloon b4" /><div className="balloon b5" /><div className="balloon b6" /><div className="balloon b7" />
      <div className="cake-table"><div className="cake"><span className="candle c1"/><span className="candle c2"/><span className="candle c3"/><div className="icing"/><div className="cake-dots">• &nbsp; • &nbsp; • &nbsp; •</div></div><div className="cake-plate"/><div className="table-top"/><div className="table-leg"/></div>
      <div className="gift gift-one"><div /></div><div className="gift gift-two"><div /></div><div className="plant"><span/><span/><span/><div/></div>
    </div>
    <div className="floating-note note-bottom"><span className="rounded-xl bg-peach p-2.5 text-[#bc8a73]"><CalendarDays size={20}/></span><div><small>THE NEXT CHAPTER</small><strong>Something wonderful awaits.</strong></div><Heart size={17} className="ml-2 text-[#b995ae]" /></div>
    <div className="floating-badge"><Sparkles size={15}/><span>A little AI magic</span></div>
  </div>;
}
