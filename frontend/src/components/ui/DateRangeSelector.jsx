import { CalendarDays, ChevronDown } from 'lucide-react';
import { useApp } from '../../context/AppContext';
import { PRESET_RANGES } from '../../utils/format';
import { Dropdown, DropdownItem } from './Dropdown';
import { useState } from 'react';

export function DateRangeSelector() {
  const { dateRange, applyPreset } = useApp();
  const [customFrom, setCustomFrom] = useState('');
  const [customTo, setCustomTo] = useState('');

  const applyCustom = (close) => {
    if (customFrom && customTo && customFrom <= customTo) {
      applyPreset('custom', { from: customFrom, to: customTo });
      close();
    }
  };

  return (
    <Dropdown
      width={280}
      trigger={({ open }) => (
        <button className={`date-btn ${open ? 'active' : ''}`} aria-label="Date range">
          <CalendarDays size={14} />
          <span>{dateRange.label}</span>
          <ChevronDown size={14} />
        </button>
      )}
    >
      {({ close }) => (
        <div className="date-menu">
          <div className="menu-label">Date range</div>
          {PRESET_RANGES.map((r) => (
            <DropdownItem
              key={r.key}
              active={dateRange.preset === r.key}
              onClick={() => applyPreset(r.key)}
              close={false}
              closeMenu={close}
            >
              {r.label}
            </DropdownItem>
          ))}
          <div className="menu-divider" />
          <div className="custom-range">
            <label>
              <span>From</span>
              <input
                type="date"
                value={customFrom}
                max={customTo || undefined}
                onChange={(e) => setCustomFrom(e.target.value)}
              />
            </label>
            <label>
              <span>To</span>
              <input
                type="date"
                value={customTo}
                min={customFrom || undefined}
                onChange={(e) => setCustomTo(e.target.value)}
              />
            </label>
            <button
              className="btn btn-primary btn-sm"
              disabled={!customFrom || !customTo || customFrom > customTo}
              onClick={() => applyCustom(close)}
            >
              Apply custom
            </button>
          </div>
        </div>
      )}
    </Dropdown>
  );
}