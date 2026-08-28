import { createContext, useCallback, useContext, useMemo } from 'react';
import { useLocalStorage } from '../hooks/useLocalStorage';
import { useHashRoute } from '../hooks/useHashRoute';
import { presetRange } from '../utils/format';

const AppContext = createContext(null);

const DEFAULT_SETTINGS = {
  merchantName: 'My Workspace',
  workspaceName: 'Primary',
  environment: 'Test',
  aiEnabled: true,
  autoRecovery: false,
  requireApproval: true,
  maxRetryAttempts: 2,
  maxRecoveryAmount: 50000,
  riskThreshold: 'medium',
  notifyEmail: true,
  notifyFailureSpike: true,
  notifyRecovery: true,
  notifyDailyReport: false,
  auditLogging: true,
};

export function AppProvider({ children }) {
  const route = useHashRoute();
  const [merchant, setMerchant] = useLocalStorage('pulseops.merchant', {
    name: DEFAULT_SETTINGS.merchantName,
    workspace: DEFAULT_SETTINGS.workspaceName,
    environment: DEFAULT_SETTINGS.environment,
  });
  const [dateRange, setDateRange] = useLocalStorage('pulseops.range', presetRange('last_7'));
  const [settings, setSettings] = useLocalStorage('pulseops.settings', DEFAULT_SETTINGS);

  const applyPreset = useCallback(
    (preset, custom) => {
      setDateRange(presetRange(preset, custom));
    },
    [setDateRange],
  );

  const updateMerchant = useCallback(
    (patch) => setMerchant((m) => ({ ...m, ...patch })),
    [setMerchant],
  );

  const patchSettings = useCallback(
    (patch) => setSettings((s) => ({ ...s, ...patch })),
    [setSettings],
  );

  const value = useMemo(
    () => ({
      route,
      merchant,
      updateMerchant,
      dateRange,
      setDateRange,
      applyPreset,
      settings,
      patchSettings,
    }),
    [route, merchant, updateMerchant, dateRange, setDateRange, applyPreset, settings, patchSettings],
  );

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error('useApp must be used inside <AppProvider>');
  return ctx;
}