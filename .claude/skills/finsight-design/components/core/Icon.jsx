import React from 'react';
const cache={};
export function Icon({name,size=20,color='currentColor'}){
  const [svg,setSvg]=React.useState(cache[name]||'');
  React.useEffect(()=>{
    if(cache[name]){setSvg(cache[name]);return;}
    let live=true;
    fetch('https://unpkg.com/lucide-static@0.468.0/icons/'+name+'.svg').then(r=>r.text()).then(t=>{
      const inner=t.replace(/^[\s\S]*?<svg[^>]*>/,'').replace(/<\/svg>[\s\S]*$/,'').replace(/<!--[\s\S]*?-->/g,'');
      cache[name]=inner;if(live)setSvg(inner);
    }).catch(()=>{});
    return()=>{live=false;};
  },[name]);
  return <svg aria-hidden="true" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{flex:'none',display:'block'}} dangerouslySetInnerHTML={{__html:svg}}/>;
}