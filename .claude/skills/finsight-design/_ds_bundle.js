/* @ds-bundle: {"format":4,"namespace":"FinsightDesignSystem_dd687d","components":[{"name":"Badge","sourcePath":"components/core/Badge.jsx"},{"name":"Button","sourcePath":"components/core/Button.jsx"},{"name":"Card","sourcePath":"components/core/Card.jsx"},{"name":"Icon","sourcePath":"components/core/Icon.jsx"},{"name":"Input","sourcePath":"components/core/Input.jsx"},{"name":"Sidebar","sourcePath":"components/core/Sidebar.jsx"},{"name":"StatCard","sourcePath":"components/core/StatCard.jsx"},{"name":"TransactionRow","sourcePath":"components/core/TransactionRow.jsx"}],"sourceHashes":{"components/core/Badge.jsx":"b4f9f0b626fe","components/core/Button.jsx":"3b2438170666","components/core/Card.jsx":"5f5f2148b329","components/core/Icon.jsx":"09bf3f3205a5","components/core/Input.jsx":"d226db60bd5f","components/core/Sidebar.jsx":"f4c2546da7d0","components/core/StatCard.jsx":"a185418c4af5","components/core/TransactionRow.jsx":"488f52aab185"},"inlinedExternals":[],"unexposedExports":[]} */

(() => {

const __ds_ns = (window.FinsightDesignSystem_dd687d = window.FinsightDesignSystem_dd687d || {});

const __ds_scope = {};

(__ds_ns.__errors = __ds_ns.__errors || []);

// components/core/Badge.jsx
try { (() => {
const T = {
  neutral: ['var(--bg-subtle)', 'var(--text-secondary)'],
  income: ['var(--income-50)', 'var(--income-700)'],
  expense: ['var(--expense-50)', 'var(--expense-700)'],
  warning: ['var(--gold-50)', 'var(--gold-700)'],
  info: ['var(--info-50)', '#2F5BB0']
};
function Badge({
  tone = 'neutral',
  children
}) {
  const [bg, fg] = T[tone];
  return /*#__PURE__*/React.createElement("span", {
    style: {
      display: 'inline-flex',
      alignItems: 'center',
      height: 24,
      padding: '0 10px',
      borderRadius: 'var(--radius-pill)',
      background: bg,
      color: fg,
      font: 'var(--text-caption)'
    }
  }, children);
}
Object.assign(__ds_scope, { Badge });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Badge.jsx", error: String((e && e.message) || e) }); }

// components/core/Button.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
const V = {
  primary: {
    background: 'var(--brand)',
    color: 'var(--text-on-brand)',
    border: '1px solid transparent'
  },
  secondary: {
    background: 'var(--bg-surface)',
    color: 'var(--text-primary)',
    border: '1px solid var(--border-default)'
  },
  ghost: {
    background: 'transparent',
    color: 'var(--text-secondary)',
    border: '1px solid transparent'
  },
  accent: {
    background: 'var(--accent)',
    color: 'var(--navy-700)',
    border: '1px solid transparent'
  }
};
const S = {
  sm: {
    height: 32,
    padding: '0 12px',
    font: 'var(--text-label)'
  },
  md: {
    height: 40,
    padding: '0 16px',
    font: 'var(--text-label)'
  },
  lg: {
    height: 48,
    padding: '0 20px',
    font: 'var(--text-h3)'
  }
};
function Button({
  variant = 'primary',
  size = 'md',
  disabled = false,
  children,
  ...rest
}) {
  return /*#__PURE__*/React.createElement("button", _extends({
    disabled: disabled
  }, rest, {
    style: {
      display: 'inline-flex',
      alignItems: 'center',
      justifyContent: 'center',
      gap: 8,
      borderRadius: 'var(--radius-lg)',
      cursor: disabled ? 'not-allowed' : 'pointer',
      opacity: disabled ? .5 : 1,
      fontWeight: 600,
      whiteSpace: 'nowrap',
      ...S[size],
      ...V[variant],
      ...rest.style
    }
  }), children);
}
Object.assign(__ds_scope, { Button });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Button.jsx", error: String((e && e.message) || e) }); }

// components/core/Card.jsx
try { (() => {
function Card({
  title,
  action,
  padding = 20,
  children,
  style
}) {
  return /*#__PURE__*/React.createElement("section", {
    style: {
      background: 'var(--bg-surface)',
      border: '1px solid var(--border-default)',
      borderRadius: 'var(--radius-xl)',
      boxShadow: 'var(--shadow-sm)',
      padding,
      display: 'flex',
      flexDirection: 'column',
      gap: 16,
      ...style
    }
  }, (title || action) && /*#__PURE__*/React.createElement("header", {
    style: {
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center'
    }
  }, /*#__PURE__*/React.createElement("h3", {
    style: {
      margin: 0,
      font: 'var(--text-h3)',
      color: 'var(--text-primary)'
    }
  }, title), action), children);
}
Object.assign(__ds_scope, { Card });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Card.jsx", error: String((e && e.message) || e) }); }

// components/core/Icon.jsx
try { (() => {
const cache = {};
function Icon({
  name,
  size = 20,
  color = 'currentColor'
}) {
  const [svg, setSvg] = React.useState(cache[name] || '');
  React.useEffect(() => {
    if (cache[name]) {
      setSvg(cache[name]);
      return;
    }
    let live = true;
    fetch('https://unpkg.com/lucide-static@0.468.0/icons/' + name + '.svg').then(r => r.text()).then(t => {
      const inner = t.replace(/^[\s\S]*?<svg[^>]*>/, '').replace(/<\/svg>[\s\S]*$/, '').replace(/<!--[\s\S]*?-->/g, '');
      cache[name] = inner;
      if (live) setSvg(inner);
    }).catch(() => {});
    return () => {
      live = false;
    };
  }, [name]);
  return /*#__PURE__*/React.createElement("svg", {
    "aria-hidden": "true",
    width: size,
    height: size,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: color,
    strokeWidth: "2",
    strokeLinecap: "round",
    strokeLinejoin: "round",
    style: {
      flex: 'none',
      display: 'block'
    },
    dangerouslySetInnerHTML: {
      __html: svg
    }
  });
}
Object.assign(__ds_scope, { Icon });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Icon.jsx", error: String((e && e.message) || e) }); }

// components/core/Input.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
function Input({
  label,
  hint,
  ...rest
}) {
  return /*#__PURE__*/React.createElement("label", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 6
    }
  }, label && /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--text-label)',
      color: 'var(--text-secondary)'
    }
  }, label), /*#__PURE__*/React.createElement("input", _extends({}, rest, {
    style: {
      height: 40,
      padding: '0 12px',
      borderRadius: 'var(--radius-lg)',
      border: '1px solid var(--border-default)',
      background: 'var(--bg-surface)',
      color: 'var(--text-primary)',
      font: 'var(--text-body)',
      outline: 'none',
      ...rest.style
    }
  })), hint && /*#__PURE__*/React.createElement("span", {
    style: {
      font: 'var(--text-caption)',
      color: 'var(--text-muted)'
    }
  }, hint));
}
Object.assign(__ds_scope, { Input });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Input.jsx", error: String((e && e.message) || e) }); }

// components/core/Sidebar.jsx
try { (() => {
function Sidebar({
  items,
  active,
  onSelect
}) {
  return /*#__PURE__*/React.createElement("nav", {
    style: {
      width: 'var(--sidebar-width)',
      flex: 'none',
      background: 'var(--bg-sidebar)',
      borderRight: '1px solid var(--border-default)',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      gap: 8,
      padding: '20px 0',
      boxSizing: 'border-box'
    }
  }, /*#__PURE__*/React.createElement("svg", {
    width: "64",
    height: "55",
    viewBox: "6 8 56 48",
    style: {
      marginBottom: 16
    },
    "aria-label": "Finsight"
  }, /*#__PURE__*/React.createElement("rect", {
    x: "19",
    y: "10",
    width: "26",
    height: "12",
    rx: "4",
    fill: "var(--logo-body)",
    fillOpacity: ".45"
  }), /*#__PURE__*/React.createElement("rect", {
    x: "8",
    y: "17",
    width: "48",
    height: "36",
    rx: "10",
    fill: "var(--logo-body)"
  }), /*#__PURE__*/React.createElement("rect", {
    x: "33",
    y: "29",
    width: "26",
    height: "14",
    rx: "7",
    fill: "var(--logo-clasp)"
  }), /*#__PURE__*/React.createElement("circle", {
    cx: "46",
    cy: "36",
    r: "3",
    fill: "var(--logo-dot)"
  })), items.map(it => {
    const on = it.id === active;
    return /*#__PURE__*/React.createElement("button", {
      key: it.id,
      onClick: () => onSelect && onSelect(it.id),
      style: {
        width: 72,
        padding: '10px 0',
        border: 0,
        borderRadius: 'var(--radius-lg)',
        cursor: 'pointer',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 4,
        background: on ? 'var(--brand-soft)' : 'transparent',
        color: on ? 'var(--brand)' : 'var(--text-muted)',
        font: 'var(--text-caption)'
      }
    }, /*#__PURE__*/React.createElement(__ds_scope.Icon, {
      name: it.icon,
      size: 20
    }), it.label);
  }));
}
Object.assign(__ds_scope, { Sidebar });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Sidebar.jsx", error: String((e && e.message) || e) }); }

// components/core/StatCard.jsx
try { (() => {
function StatCard({
  label,
  value,
  delta,
  trend = 'up',
  hero = false
}) {
  const c = trend === 'up' ? 'var(--positive)' : 'var(--negative)';
  return /*#__PURE__*/React.createElement("div", {
    style: {
      background: 'var(--bg-surface)',
      border: '1px solid var(--border-default)',
      borderRadius: 'var(--radius-xl)',
      boxShadow: 'var(--shadow-sm)',
      padding: 20,
      display: 'flex',
      flexDirection: 'column',
      gap: 4,
      minWidth: 0
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      font: 'var(--text-label)',
      color: 'var(--text-muted)'
    }
  }, label), /*#__PURE__*/React.createElement("div", {
    style: {
      font: hero ? 'var(--text-balance)' : 'var(--text-h1)',
      letterSpacing: 'var(--tracking-tight)',
      color: 'var(--text-primary)'
    }
  }, value), delta && /*#__PURE__*/React.createElement("div", {
    style: {
      font: 'var(--text-amount)',
      color: c
    }
  }, delta));
}
Object.assign(__ds_scope, { StatCard });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/StatCard.jsx", error: String((e && e.message) || e) }); }

// components/core/TransactionRow.jsx
try { (() => {
function TransactionRow({
  name,
  category,
  date,
  amount,
  icon = 'shopping-cart'
}) {
  const neg = amount < 0;
  const f = (neg ? '− ' : '+ ') + '$ ' + Math.abs(amount).toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  });
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 12,
      padding: '12px 0',
      borderBottom: '1px solid var(--border-subtle)'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      width: 36,
      height: 36,
      borderRadius: 'var(--radius-lg)',
      background: 'var(--bg-subtle)',
      color: 'var(--text-secondary)',
      display: 'grid',
      placeItems: 'center'
    }
  }, /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: icon,
    size: 18
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      minWidth: 0
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      font: 'var(--text-label)',
      color: 'var(--text-primary)'
    }
  }, name), /*#__PURE__*/React.createElement("div", {
    style: {
      font: 'var(--text-caption)',
      color: 'var(--text-muted)'
    }
  }, date)), /*#__PURE__*/React.createElement(__ds_scope.Badge, null, category), /*#__PURE__*/React.createElement("div", {
    style: {
      width: 110,
      textAlign: 'right',
      font: 'var(--text-amount)',
      color: neg ? 'var(--text-primary)' : 'var(--positive)'
    }
  }, f));
}
Object.assign(__ds_scope, { TransactionRow });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/TransactionRow.jsx", error: String((e && e.message) || e) }); }

__ds_ns.Badge = __ds_scope.Badge;

__ds_ns.Button = __ds_scope.Button;

__ds_ns.Card = __ds_scope.Card;

__ds_ns.Icon = __ds_scope.Icon;

__ds_ns.Input = __ds_scope.Input;

__ds_ns.Sidebar = __ds_scope.Sidebar;

__ds_ns.StatCard = __ds_scope.StatCard;

__ds_ns.TransactionRow = __ds_scope.TransactionRow;

})();
