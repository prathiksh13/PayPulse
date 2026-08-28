import { Menu } from 'lucide-react';
import { DateRangeSelector } from '../ui/DateRangeSelector';
import { NotificationsMenu } from './NotificationsMenu';
import { ProfileMenu } from './ProfileMenu';
import { ROUTE_META } from '../../nav';

export function Topbar({ activeKey, onOpenMobile }) {
  const meta = ROUTE_META[activeKey] || ROUTE_META.overview;
  return (
    <header className="topbar">
      <button className="mobile-menu" onClick={onOpenMobile} aria-label="Open menu">
        <Menu size={20} />
      </button>
      <div className="topbar-title">
        <div className="eyebrow">{meta.eyebrow}</div>
        <h1>{meta.title}</h1>
        <p>{meta.subtitle}</p>
      </div>
      <div className="top-actions">
        <DateRangeSelector />
        <NotificationsMenu />
        <ProfileMenu />
      </div>
    </header>
  );
}