import React from 'react';
export function StatCard({label,value,delta,trend='up',hero=false}){
  const c=trend==='up'?'var(--positive)':'var(--negative)';
  return <div style={{background:'var(--bg-surface)',border:'1px solid var(--border-default)',borderRadius:'var(--radius-xl)',boxShadow:'var(--shadow-sm)',padding:20,display:'flex',flexDirection:'column',gap:4,minWidth:0}}>
    <div style={{font:'var(--text-label)',color:'var(--text-muted)'}}>{label}</div>
    <div style={{font:hero?'var(--text-balance)':'var(--text-h1)',letterSpacing:'var(--tracking-tight)',color:'var(--text-primary)'}}>{value}</div>
    {delta&&<div style={{font:'var(--text-amount)',color:c}}>{delta}</div>}
  </div>;
}