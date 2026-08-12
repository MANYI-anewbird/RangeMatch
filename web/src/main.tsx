import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { IntakePage } from "./pages/IntakePage";
import { InvestigationPage } from "./pages/InvestigationPage";
import { AdvisorDemoPage } from "./pages/AdvisorDemoPage";
import "./styles/global.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<IntakePage />} />
        <Route path="/advisor-demo" element={<AdvisorDemoPage />} />
        <Route path="/investigations/:id" element={<InvestigationPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  </StrictMode>,
);
