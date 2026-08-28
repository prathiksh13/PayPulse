import { useEffect, useState } from 'react';
import { AlertTriangle } from 'lucide-react';
import { Modal } from './Modal';
import { Button } from './Button';

export function ConfirmDialog({ open, onClose, onConfirm, title = 'Are you sure?', description, confirmLabel = 'Confirm', danger = false, loading = false }) {
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    if (open) setChecked(false);
  }, [open]);

  const handleConfirm = async () => {
    await onConfirm();
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={title}
      size="md"
      footer={
        <>
          <Button variant="outline" onClick={onClose} disabled={loading}>
            Cancel
          </Button>
          {danger ? (
            <Button
              variant="danger"
              onClick={handleConfirm}
              loading={loading}
              disabled={danger && !checked}
            >
              {confirmLabel}
            </Button>
          ) : (
            <Button onClick={handleConfirm} loading={loading}>
              {confirmLabel}
            </Button>
          )}
        </>
      }
    >
      <div className="confirm-body">
        <div className={`confirm-icon ${danger ? 'danger' : ''}`}>
          <AlertTriangle size={22} />
        </div>
        {description ? <p>{description}</p> : null}
        {danger ? (
          <label className="confirm-check">
            <input type="checkbox" checked={checked} onChange={(e) => setChecked(e.target.checked)} />
            <span>I understand this action cannot be undone automatically.</span>
          </label>
        ) : null}
        {!danger && <div className="confirm-note">This action will be sent to the backend for approval and execution.</div>}
      </div>
    </Modal>
  );
}