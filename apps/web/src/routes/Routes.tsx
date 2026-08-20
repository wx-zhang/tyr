import { createBrowserRouter } from "react-router-dom";
import { App } from "../app/App";
import { TaskDetailPage } from "../features/tasks/TaskDetailPage";
import { TaskPage } from "../features/tasks/TaskPage";
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
      { path: "tasks", element: <TaskPage /> },
      { path: "tasks/:taskId", element: <TaskDetailPage /> },
      {
        path: "tasks/:taskId/cases/:caseId",
        element: <TaskDetailPage />,
      },
      { path: "experiments/new", element: <ExperimentPage /> },
      { path: "experiments/:id", element: <ExperimentDetailPage /> },
      { path: "runs/:id", element: <RunPage /> },
      { path: "runs/:id/cases/:caseId", element: <RunPage /> },
      { path: "runs/:id/artifacts", element: <RunPage /> },
    ],
  },
]);
