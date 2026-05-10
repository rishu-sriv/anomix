import React from "react"
import ReactDOM from "react-dom/client"
import { Providers } from "@/app/providers"
import { Dashboard } from "@/pages/Dashboard"
import "./index.css"

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <Providers>
      <Dashboard />
    </Providers>
  </React.StrictMode>
)
