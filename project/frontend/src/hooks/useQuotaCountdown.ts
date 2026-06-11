import { useState, useEffect, useCallback } from 'react';

export function useQuotaCountdown() {
  const [quotaCountdown, setQuotaCountdown] = useState<number | null>(null);

  useEffect(() => {
    if (quotaCountdown !== null && quotaCountdown > 0) {
      const timer = setTimeout(() => setQuotaCountdown(quotaCountdown - 1), 1000);
      return () => clearTimeout(timer);
    }
    if (quotaCountdown === 0) {
      setQuotaCountdown(null);
    }
  }, [quotaCountdown]);

  const startCountdown = useCallback((seconds: number = 60) => {
    setQuotaCountdown(seconds);
  }, []);

  return { quotaCountdown, startCountdown };
}