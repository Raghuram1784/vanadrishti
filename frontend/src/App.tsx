import { BrowserRouter, Routes, Route, Link } from "react-router-dom";
import { Toaster } from "sonner";
import { Layout } from "@/components/layout/Layout";
import Dashboard from "@/pages/Dashboard";
import Monitor from "@/pages/Monitor";
import Alerts from "@/pages/Alerts";
import Events from "@/pages/Events";
export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="monitor" element={<Monitor />} />
          <Route path="alerts" element={<Alerts />} />
          <Route path="events" element={<Events />} />
          <Route
            path="*"
            element={
              <div className="empty">
                <h1>Page not found</h1>
                <Link to="/">Return to Overview</Link>
              </div>
            }
          />
        </Route>
      </Routes>
      <Toaster theme="dark" position="bottom-right" richColors closeButton />
    </BrowserRouter>
  );
}
