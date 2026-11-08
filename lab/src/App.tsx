import { Route, Routes, useLocation } from "react-router-dom";
import { Toasts } from "./components/Toasts";
import { TopBar } from "./components/TopBar";
import { EmptyState } from "./components/ui";
import { CaseScreen } from "./screens/CaseScreen";
import { EvidenceScreen } from "./screens/EvidenceScreen";
import { HomeScreen } from "./screens/HomeScreen";
import { Link } from "react-router-dom";

function NotFound() {
  const loc = useLocation();
  return (
    <EmptyState
      title="Nothing here"
      body={
        <>
          No page at <span className="font-mono text-slate-300">/lab{loc.pathname}</span>.
        </>
      }
      action={
        <Link to="/" className="btn-secondary mt-2">
          Back to case files
        </Link>
      }
    />
  );
}

export function App() {
  return (
    <div className="relative min-h-screen">
      <div className="lab-backdrop" />
      <div className="relative z-10 flex min-h-screen flex-col">
        <TopBar />
        <main className="mx-auto w-full max-w-[1680px] flex-1 px-5 pb-16 pt-6 lg:px-8">
          <Routes>
            <Route path="/" element={<HomeScreen />} />
            <Route path="/cases/:caseId" element={<CaseScreen />} />
            <Route path="/cases/:caseId/:tab" element={<CaseScreen />} />
            <Route path="/evidence/:evidenceId" element={<EvidenceScreen />} />
            <Route path="*" element={<NotFound />} />
          </Routes>
        </main>
        <footer className="border-t border-white/[0.05] py-4 text-center text-2xs text-slate-600">
          Satyapan Forensic Lab · findings are expressed on the ENFSI verbal scale; the verdict is computed by a fixed rule
          table, never by a model alone · times shown in IST
        </footer>
      </div>
      <Toasts />
    </div>
  );
}
