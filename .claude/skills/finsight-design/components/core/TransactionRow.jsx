import React from 'react';
import {Icon} from './Icon';
import {Badge} from './Badge';
export function TransactionRow({name,category,date,amount,icon='shopping-cart'}){
  const neg=amount<0;
  const f=(neg?'− ':'+ ')+'$ '+Math.abs(amount).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2});
  return <div style={{display:'flex',alignItems:'center',gap:12,padding:'12px 0',borderBottom:'1px solid var(--border-subtle)'}}>
    <div style={{width:36,height:36,borderRadius:'var(--radius-lg)',background:'var(--bg-subtle)',color:'var(--text-secondary)',display:'grid',placeItems:'center'}}><Icon name={icon} size={18}/></div>
    <div style={{flex:1,minWidth:0}}><div style={{font:'var(--text-label)',color:'var(--text-primary)'}}>{name}</div><div style={{font:'var(--text-caption)',color:'var(--text-muted)'}}>{date}</div></div>
    <Badge>{category}</Badge>
    <div style={{width:110,textAlign:'right',font:'var(--text-amount)',color:neg?'var(--text-primary)':'var(--positive)'}}>{f}</div>
  </div>;
}