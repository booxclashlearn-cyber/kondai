import { Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { CreateProject } from "./pages/CreateProject";
import { Dashboard } from "./pages/Dashboard";
import { ExtractionReview } from "./pages/ExtractionReview";
import { Landing } from "./pages/Landing";
import { Projects } from "./pages/Projects";
import { Status } from "./pages/Status";

export function App() {
  return <Routes><Route element={<Layout />}><Route index element={<Landing />} /><Route path="projects" element={<Projects />} /><Route path="projects/new" element={<CreateProject />} /><Route path="projects/:id" element={<Dashboard />} /><Route path="projects/:id/versions/:versionId/extraction" element={<ExtractionReview />} /><Route path="status" element={<Status />} /></Route></Routes>;
}
