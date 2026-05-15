import { lazy, Suspense } from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { StrategyLayout } from "./components/StrategyLayout";

const ReportPage = lazy(() => import("./pages/ReportPage"));

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<StrategyLayout />} />
        <Route
          path="/runs/:run_id/report"
          element={
            <Suspense fallback={
              <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100vh", color: "var(--text-secondary)" }}>
                加载中…
              </div>
            }>
              <ReportPage />
            </Suspense>
          }
        />
        {/* Fallback */}
        <Route path="*" element={<StrategyLayout />} />
      </Routes>
    </BrowserRouter>
  );
}
