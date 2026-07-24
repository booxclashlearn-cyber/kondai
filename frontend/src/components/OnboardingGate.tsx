import { useEffect, useState, type ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { api } from "../lib/api";
import type { OnboardingStatus } from "../types";

export function OnboardingGate({ children }: { children: ReactNode }) {
  const location = useLocation();
  const [status, setStatus] = useState<OnboardingStatus | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .get<OnboardingStatus>("/onboarding/status")
      .then(setStatus)
      .catch((requestError: Error) => setError(requestError.message));
  }, [location.key]);

  if (error) {
    return (
      <div className="setup-loading">
        <div className="setup-loading-card">
          <h2>Kondai could not check your setup</h2>
          <p>{error}</p>
          <button onClick={() => window.location.reload()}>Try again</button>
        </div>
      </div>
    );
  }

  if (!status) {
    return (
      <div className="setup-loading">
        <div className="setup-spinner" />
        <p>Checking your workspace…</p>
      </div>
    );
  }

  if (!status.complete) {
    return <Navigate to="/setup" replace />;
  }

  return children;
}
