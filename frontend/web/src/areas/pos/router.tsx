import { useEffect } from 'react';
import { Route, Routes, Link } from 'react-router';
import { BillingShell } from './components/BillingShell';
import { BillingPage } from './pages/BillingPage';
import { prewarm } from './lib/prewarm';
import printCSS from './print.css?inline';

export default function PosArea() {
  useEffect(() => {
    prewarm('/api');
  }, []);
  return (
    <>
      <style media="print">{printCSS}</style>
      <Routes>
        <Route element={<BillingShell />}>
          <Route index element={<BillingPage />} />
          <Route
            path="*"
            element={
              <div>
                Page not found. <Link to="/">Home</Link>
              </div>
            }
          />
        </Route>
      </Routes>
    </>
  );
}
