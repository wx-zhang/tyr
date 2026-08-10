import { createBrowserRouter } from "react-router-dom";
import { App } from "../app/App";
import { DatasetDetailPage } from "../features/datasets/DatasetDetailPage";
import { DatasetPage } from "../features/datasets/DatasetPage";
import { ExperimentDetailPage } from "../features/experiments/ExperimentDetailPage";
import { DashboardPage } from "../features/runs/DashboardPage";
import { RunPage } from "../features/runs/RunPage";
import { ExperimentPage } from "../features/experiments/ExperimentPage";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <App />,
    children: [
      { index: true, element: <DashboardPage /> },
      { path: "datasets", element: <DatasetPage /> },
      { path: "datasets/:datasetId", element: <DatasetDetailPage /> },
      {
        path: "datasets/:datasetId/cases/:caseId",
        element: <DatasetDetailPage />,
      },
      { path: "experiments/new", element: <ExperimentPage /> },
      { path: "experiments/:id", element: <ExperimentDetailPage /> },
      { path: "runs/:id", element: <RunPage /> },
      { path: "runs/:id/cases/:caseId", element: <RunPage /> },
      { path: "runs/:id/artifacts", element: <RunPage /> },
    ],
  },
]);
