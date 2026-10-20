import React from 'react';
const V={
  primary:{background:'var(--brand)',color:'var(--text-on-brand)',border:'1px solid transparent'},
  secondary:{background:'var(--bg-surface)',color:'var(--text-primary)',border:'1px solid var(--border-default)'},
  ghost:{background:'transparent',color:'var(--text-secondary)',border:'1px solid transparent'},
  accent:{background:'var(--accent)',color:'var(--navy-700)',border:'1px solid transparent'}
};
const S={sm:{height:32,padding:'0 12px',font:'var(--text-label)'},md:{height:40,padding:'0 16px',font:'var(--text-label)'},lg:{height:48,padding:'0 20px',font:'var(--text-h3)'}};
export function Button({variant='primary',size='md',disabled=false,children,...rest}){
  return <button disabled={disabled} {...rest} style={{display:'inline-flex',alignItems:'center',justifyContent:'center',gap:8,borderRadius:'var(--radius-lg)',cursor:disabled?'not-allowed':'pointer',opacity:disabled?.5:1,fontWeight:600,whiteSpace:'nowrap',...S[size],...V[variant],...rest.style}}>{children}</button>;
}