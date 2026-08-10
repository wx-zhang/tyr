import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "react-router-dom";
import { router } from "./routes/Routes";
import { initializeTheme } from "./theme";
import "./tokens.css";
import "./styles.css";

const queryClient = new QueryClient();
initializeTheme();

export function Main() {
  return (
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  );
}

createRoot(document.getElementById("root")!).render(<Main />);
