import React from "react";
import ReactDOM from "react-dom/client";
import { Theme } from "@radix-ui/themes";
import "@radix-ui/themes/styles.css";
import App from "./App";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <Theme accentColor="gray" grayColor="sand" radius="large" scaling="95%" appearance="light">
      <App />
    </Theme>
  </React.StrictMode>,
);
