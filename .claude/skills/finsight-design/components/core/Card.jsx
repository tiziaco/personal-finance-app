import React from 'react';
export function Card({title,action,padding=20,children,style}){
  return <section style={{background:'var(--bg-surface)',border:'1px solid var(--border-default)',borderRadius:'var(--radius-xl)',boxShadow:'var(--shadow-sm)',padding,display:'flex',flexDirection:'column',gap:16,...style}}>
    {(title||action)&&<header style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}><h3 style={{margin:0,font:'var(--text-h3)',color:'var(--text-primary)'}}>{title}</h3>{action}</header>}
    {children}
  </section>;
}