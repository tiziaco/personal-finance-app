import React from 'react';
const T={neutral:['var(--bg-subtle)','var(--text-secondary)'],income:['var(--income-50)','var(--income-700)'],expense:['var(--expense-50)','var(--expense-700)'],warning:['var(--gold-50)','var(--gold-700)'],info:['var(--info-50)','#2F5BB0']};
export function Badge({tone='neutral',children}){
  const [bg,fg]=T[tone];
  return <span style={{display:'inline-flex',alignItems:'center',height:24,padding:'0 10px',borderRadius:'var(--radius-pill)',background:bg,color:fg,font:'var(--text-caption)'}}>{children}</span>;
}