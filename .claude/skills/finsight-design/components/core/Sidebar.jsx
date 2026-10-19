import React from 'react';
import {Icon} from './Icon';
export function Sidebar({items,active,onSelect}){
  return <nav style={{width:'var(--sidebar-width)',flex:'none',background:'var(--bg-sidebar)',borderRight:'1px solid var(--border-default)',display:'flex',flexDirection:'column',alignItems:'center',gap:8,padding:'20px 0',boxSizing:'border-box'}}>
    <svg width="64" height="55" viewBox="6 8 56 48" style={{marginBottom:16}} aria-label="Finsight">
      <rect x="19" y="10" width="26" height="12" rx="4" fill="var(--logo-body)" fillOpacity=".45"/><rect x="8" y="17" width="48" height="36" rx="10" fill="var(--logo-body)"/><rect x="33" y="29" width="26" height="14" rx="7" fill="var(--logo-clasp)"/><circle cx="46" cy="36" r="3" fill="var(--logo-dot)"/>
    </svg>
    {items.map(it=>{const on=it.id===active;return <button key={it.id} onClick={()=>onSelect&&onSelect(it.id)} style={{width:72,padding:'10px 0',border:0,borderRadius:'var(--radius-lg)',cursor:'pointer',display:'flex',flexDirection:'column',alignItems:'center',gap:4,background:on?'var(--brand-soft)':'transparent',color:on?'var(--brand)':'var(--text-muted)',font:'var(--text-caption)'}}><Icon name={it.icon} size={20}/>{it.label}</button>;})}
  </nav>;
}