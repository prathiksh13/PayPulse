import { useCallback, useState } from 'react';
import { CreditCard, Loader2, ShieldCheck } from 'lucide-react';
import { Modal } from '../ui/Modal';
import { Button } from '../ui/Button';
import { Field, TextInput } from '../ui/Field';
import { invalidateCache, createTestPayOrder, reportCheckoutEvent, verifyTestPayment, syncTestPayment } from '../../api';
import { loadRazorpaySdk } from './razorpaySdk';
import { useToast } from '../../context/ToastContext';

const TEST_CARD = '4111 1111 1111 1111 · any future expiry · any CVV';

export function TestPaymentModal({ open, onClose, onComplete }) {
  const toast = useToast();
  const [amount, setAmount] = useState('');
  const [busy, setBusy] = useState(false);
  const [phase, setPhase] = useState('idle'); // idle | creating | opening | paying | verify
  const [error, setError] = useState(null);

  const reset = useCallback(() => {
    setBusy(false);
    setPhase('idle');
    setError(null);
  }, []);

  const handleClose = () => {
    reset();
    onClose();
  };

  const handlePaymentComplete = async (resp) => {
    setPhase('verify');
    const status = await verifyTestPayment({
      razorpay_order_id: resp.razorpay_order_id,
      razorpay_payment_id: resp.razorpay_payment_id,
      razorpay_signature: resp.razorpay_signature,
    });
    if (status.ok) {
      toast('Payment recorded', 'success', {
        description: `${status.data.payment_id} · ${status.data.status}`,
      });
      await invalidateCache().catch(() => {});
      onComplete?.(status.data);
      handleClose();
    } else {
      setPhase('idle');
      setBusy(false);
      setError(status.error || 'Payment verification failed on the backend');
      toast('Verification failed', 'error', { description: status.error });
    }
  };

  const handlePaymentFailed = async (resp) => {
    toast('Payment failed', 'error', {
      description: resp?.error?.description || resp?.error?.code || 'The checkout was not completed',
    });
    const pid = resp?.error?.metadata?.payment_id;
    if (pid) {
      // sync the failed payment so it shows up in the list
      const synced = await syncTestPayment(pid);
      if (synced.ok) {
        toast('Failed payment recorded', 'info', { description: pid });
        await invalidateCache().catch(() => {});
        onComplete?.(synced.data);
      }
    }
    setPhase('idle');
    setBusy(false);
  };

  const openCheckout = async (order) => {
    setPhase('opening');
    try {
      const Razorpay = await loadRazorpaySdk();
      setPhase('paying');
      const rzp = new Razorpay({
        key: order.key_id,
        amount: order.amount_paise,
        currency: order.currency || 'INR',
        name: order.merchant || 'PayPulse',
        description: `Test payment · ${order.order_id}`,
        order_id: order.order_id,
        prefill: { name: 'Test Customer', email: 'test@example.com', contact: '9999999999' },
        theme: { color: '#4f46e5' },
        handler: handlePaymentComplete,
        modal: {
          ondismiss: () => {
            setPhase('idle');
            setBusy(false);
            reportCheckoutEvent({
              session_id: order.order_id,
              event_type: 'checkout_closed',
              order_id: order.order_id,
              occurred_at: new Date().toISOString(),
            }).catch(() => {});
            toast('Checkout cancelled', 'info');
          },
        },
      });
      rzp.on('payment.failed', handlePaymentFailed);
      rzp.open();
    } catch (err) {
      setPhase('idle');
      setBusy(false);
      setError(err?.message || 'Could not open the Razorpay Checkout');
      toast('Checkout error', 'error', { description: err?.message });
    }
  };

  const handlePay = async () => {
    const value = Number(amount);
    if (!amount || !Number.isFinite(value) || value <= 0) {
      setError('Enter a valid amount in ₹ (min ₹1)');
      return;
    }
    setError(null);
    setBusy(true);
    setPhase('creating');
    const res = await createTestPayOrder({ amount: value, currency: 'INR' });
    if (!res.ok) {
      setPhase('idle');
      setBusy(false);
      setError(res.error || 'Could not create the payment order');
      toast('Order creation failed', 'error', { description: res.error });
      return;
    }
    await openCheckout(res.data);
  };

  return (
    <Modal
      open={open}
      onClose={busy ? () => {} : handleClose}
      title="Make a test payment"
      size="sm"
      footer={
        <>
          <Button variant="outline" onClick={handleClose} disabled={busy}>
            Cancel
          </Button>
          <Button icon={CreditCard} onClick={handlePay} loading={busy} disabled={phase === 'paying'}>
            {phase === 'creating'
              ? 'Creating order…'
              : phase === 'opening'
                ? 'Opening Razorpay…'
                : phase === 'paying'
                  ? 'Complete payment in the popup'
                  : 'Pay with Razorpay'}
          </Button>
        </>
      }
    >
      <div className="field-group" style={{ gap: 14 }}>
        <Field label="Amount (INR)" hint="Test Mode — no real charge is made.">
          <TextInput
            type="number"
            min="1"
            max="200000"
            placeholder="e.g. 199"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            disabled={busy}
            autoFocus
          />
        </Field>

        <div className="test-card-hint">
          <ShieldCheck size={14} />
          <span>
            Use test card <code className="mono">{TEST_CARD}</code>
          </span>
        </div>

        {error ? <div className="inline-error">{error}</div> : null}

        {phase === 'verify' ? (
          <div className="inline-info">
            <Loader2 size={13} className="spin" /> Verifying payment signature…
          </div>
        ) : null}
      </div>
    </Modal>
  );
}
