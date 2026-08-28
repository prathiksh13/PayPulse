import { Inbox, Clock3 } from 'lucide-react';

export function EmptyState({ icon: Icon = Inbox, title = 'No data available', description, action }) {
  return (
    <div className="empty-state">
      <div className="empty-icon">
        <Icon size={20} />
      </div>
      <strong>{title}</strong>
      {description ? <p>{description}</p> : null}
      {action ? <div className="empty-action">{action}</div> : null}
    </div>
  );
}

export function WaitingState({ title = 'Waiting for payment events', description, action }) {
  return <EmptyState icon={Clock3} title={title} description={description} action={action} />;
}