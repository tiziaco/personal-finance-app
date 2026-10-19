import React from 'react';
export function Input({label,hint,...rest}){
  return <label style={{display:'flex',flexDirection:'column',gap:6}}>
    {label&&<span style={{font:'var(--text-label)',color:'var(--text-secondary)'}}>{label}</span>}
    <input {...rest} style={{height:40,padding:'0 12px',borderRadius:'var(--radius-lg)',border:'1px solid var(--border-default)',background:'var(--bg-surface)',color:'var(--text-primary)',font:'var(--text-body)',outline:'none',...rest.style}}/>
    {hint&&<span style={{font:'var(--text-caption)',color:'var(--text-muted)'}}>{hint}</span>}
  </label>;
}