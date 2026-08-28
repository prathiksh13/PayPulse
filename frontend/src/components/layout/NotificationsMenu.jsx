import { Bell, CheckCheck, Inbox } from 'lucide-react';
import { useApi } from '../../hooks/useApi';
import { getNotifications } from '../../api';
import { useToast } from '../../context/ToastContext';
import { Dropdown } from '../ui/Dropdown';
import { timeAgo } from '../../utils/format';

export function NotificationsMenu() {
  const toast = useToast();
  const notif = useApi(getNotifications, []);
  const items = notif.data && Array.isArray(notif.data) ? notif.data : [];
  const count = notif.data?.unread ?? items.length;

  return (
    <Dropdown
      width={300}
      trigger={({ open }) => (
        <button className={`icon-btn round-btn ${open ? 'active' : ''}`} aria-label="Notifications">
          <Bell size={17} />
          {count > 0 ? <b className="dot-badge">{count}</b> : null}
        </button>
      )}
    >
      {({ close }) => (
        <div className="notif-menu">
          <div className="menu-head">
            <strong>Notifications</strong>
            <button
              className="text-btn"
              onClick={() => {
                toast('All notifications marked as read', 'success');
                close();
              }}
            >
              <CheckCheck size={13} /> Mark all read
            </button>
          </div>
          {notif.loading ? <div className="menu-hint pad">Loading…</div> : notif.networkError ? (
            <div className="menu-hint pad">Backend offline — start the FastAPI server.</div>
          ) : notif.unavailable ? (
            <div className="menu-hint pad">Notifications appear here once GET /api/notifications is live.</div>
          ) : items.length === 0 ? (
            <div className="notif-empty">
              <Inbox size={18} />
              <span>No notifications yet</span>
            </div>
          ) : (
            items.map((n, i) => (
              <div className="notif-item" key={i}>
                <span className={`notif-dot ${n.read ? '' : 'unread'}`} />
                <div>
                  <strong>{n.title}</strong>
                  <p>{n.message}</p>
                  <span className="muted">{timeAgo(n.created_at || n.createdAt || n.at)}</span>
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </Dropdown>
  );
}