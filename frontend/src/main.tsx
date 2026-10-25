import React from "react";
import ReactDOM from "react-dom/client";
import { HashRouter } from "react-router-dom";
import App from "./App";
import "./styles.css";
import "./redesign.css";
import "./readerSettings.css";

if (window.location.pathname.startsWith("/admin/app") && !window.location.hash) {
  window.location.hash = "/admin";
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  // HashRouter သုံးသဖြင့် /app#/stories ကဲ့သို့ # နောက်က path ကို React က ကိုင်တွယ်သည်။
  <React.StrictMode>
    <HashRouter>
      <App />
    </HashRouter>
  </React.StrictMode>,
);
