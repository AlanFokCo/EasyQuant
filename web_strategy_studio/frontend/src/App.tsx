import { useState } from "react";
import { lazy, Suspense } from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { StrategyLayout } from "./components/StrategyLayout";
import { LoginPage } from "./pages/LoginPage";
import { getToken } from "./api/client";

const ReportPage = lazy(() => import("./pages/ReportPage"));

export default function App() {
  const [authed, setAuthed] = useState(!!getToken());

  return (
    <BrowserRouter>
      {!authed ? (
        <LoginPage onLogin={() => setAuthed(true)} />
      ) : (
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
          <Route path="*" element={<StrategyLayout />} />
        </Routes>
      )}
    </BrowserRouter>
  );
}
