import { useState } from 'react';
import { Building2, ChevronDown, LogOut, Settings, User } from 'lucide-react';
import { navigate } from '../../hooks/useHashRoute';
import { useApp } from '../../context/AppContext';
import { useToast } from '../../context/ToastContext';
import { Dropdown, DropdownItem } from '../ui/Dropdown';
import { ConfirmDialog } from '../ui/ConfirmDialog';

function initials(name) {
  return String(name || 'U')
    .split(/\s+/)
    .map((w) => w[0])
    .slice(0, 2)
    .join('')
    .toUpperCase();
}

export function ProfileMenu() {
  const toast = useToast();
  const { merchant } = useApp();
  const [logoutOpen, setLogoutOpen] = useState(false);

  const handleLogout = async () => {
    setLogoutOpen(false);
    toast('Signed out', 'success', { description: 'This is a demo session. Reconnect the backend for real auth.' });
  };

  return (
    <>
      <Dropdown
        width={230}
        trigger={({ open }) => (
          <button className={`avatar ${open ? 'active' : ''}`} aria-label="Account menu">
            {initials(merchant.name)}
            <ChevronDown size={13} />
          </button>
        )}
      >
        {({ close }) => (
          <>
            <div className="menu-head">
              <strong>{merchant.name}</strong>
              <span>{merchant.environment} environment</span>
            </div>
            <div className="menu-divider" />
            <DropdownItem
              icon={User}
              closeMenu={close}
              onClick={() => toast('Account page is a placeholder', 'info', { description: 'Connect the merchant API to manage users and roles.' })}
            >
              Account
            </DropdownItem>
            <DropdownItem
              icon={Building2}
              closeMenu={close}
              onClick={() => toast('Workspace updated', 'info', { description: 'Workspace details sync from the backend.' })}
            >
              Workspace
            </DropdownItem>
            <DropdownItem icon={Settings} closeMenu={close} onClick={() => navigate('/settings')}>
              Settings
            </DropdownItem>
            <div className="menu-divider" />
            <DropdownItem icon={LogOut} danger closeMenu={close} onClick={() => setLogoutOpen(true)}>
              Logout
            </DropdownItem>
          </>
        )}
      </Dropdown>

      <ConfirmDialog
        open={logoutOpen}
        onClose={() => setLogoutOpen(false)}
        onConfirm={handleLogout}
        title="Sign out of PulseOps?"
        description="You will need to reconnect your workspace to monitor payments again."
        confirmLabel="Sign out"
        danger
      />
    </>
  );
}