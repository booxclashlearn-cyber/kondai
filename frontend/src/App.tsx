import { Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { OnboardingGate } from "./components/OnboardingGate";
import { ActivityPage } from "./pages/ActivityPage";
import { ApprovalsPage } from "./pages/ApprovalsPage";
import { GrowthPage } from "./pages/GrowthPage";
import { IntelligencePage } from "./pages/IntelligencePage";
import { IntegrationsPage } from "./pages/IntegrationsPage";
import { KnowledgePage } from "./pages/KnowledgePage";
import { SetupPage } from "./pages/SetupPage";
import { SupportPage } from "./pages/SupportPage";
import { TodayPage } from "./pages/TodayPage";

function Workspace() {
  return (
    <OnboardingGate>
      <Layout>
        <Routes>
          <Route path="/" element={<TodayPage />} />
          <Route path="/data" element={<KnowledgePage />} />
          <Route path="/insights" element={<IntelligencePage />} />
          <Route path="/campaigns" element={<GrowthPage />} />
          <Route path="/customers" element={<SupportPage />} />
          <Route path="/approvals" element={<ApprovalsPage />} />
          <Route path="/integrations" element={<IntegrationsPage />} />
          <Route path="/activity" element={<ActivityPage />} />
          <Route path="/knowledge" element={<KnowledgePage />} />
          <Route path="/intelligence" element={<IntelligencePage />} />
          <Route path="/growth" element={<GrowthPage />} />
          <Route path="/support" element={<SupportPage />} />
        </Routes>
      </Layout>
    </OnboardingGate>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/setup" element={<SetupPage />} />
      <Route path="/*" element={<Workspace />} />
    </Routes>
  );
}
