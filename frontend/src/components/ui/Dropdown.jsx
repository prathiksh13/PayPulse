import { useRef, useState, useEffect } from 'react';
import { ChevronDown } from 'lucide-react';
import { useOnClickOutside } from '../../hooks/useOnClickOutside';

export function Dropdown({
  trigger,
  children,
  align = 'left',
  width = 240,
  className = '',
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  useOnClickOutside(ref, () => setOpen(false), open);

  const toggle = () => setOpen((o) => !o);

  const triggerWithProps =
    typeof trigger === 'function'
      ? trigger({ open })
      : trigger;

  return (
    <div className={`dropdown ${className}`} ref={ref}>
      <div className="dropdown-trigger" onClick={toggle}>
        {triggerWithProps}
      </div>
      {open && (
        <div className={`dropdown-menu align-${align}`} style={{ width }}>
          {typeof children === 'function' ? children({ open, close: () => setOpen(false) }) : children}
        </div>
      )}
    </div>
  );
}

export function DropdownItem({ icon: Icon, children, onClick, active = false, danger = false, close = true, closeMenu }) {
  const handle = () => {
    if (closeMenu) closeMenu();
    if (onClick) onClick();
  };
  return (
    <button className={`dropdown-item ${active ? 'active' : ''} ${danger ? 'danger' : ''}`} onClick={handle}>
      {Icon ? <Icon size={15} /> : null}
      <span>{children}</span>
    </button>
  );
}

export { ChevronDown };

export function useDropdownMenu() {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  useEffect(() => setOpen(false), []);
  return { open, setOpen, ref };
}