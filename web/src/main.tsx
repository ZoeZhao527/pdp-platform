import React from "react";
import ReactDOM from "react-dom/client";

import App from "./App";
import "./styles.css";

// Static demo mode: intercepts all API calls with mock data
import "./staticMock";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);

// cache-bust 1787375025
;(window as any).__BUILD_TS = "1787375026"
