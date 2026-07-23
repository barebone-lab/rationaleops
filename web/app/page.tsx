import type { Metadata } from "next";
import { Dashboard } from "./Dashboard";

export const metadata: Metadata = {
  title: "RationaleOps · The code remembers what. We preserve why.",
  description:
    "A DataHub-grounded Cognitive Task Analysis agent that turns hidden SQL logic into confirmed, testable Decision Contracts.",
  openGraph: {
    title: "RationaleOps · Preserve the why behind data logic",
    description:
      "Three filters. Three different truths. One evidence-backed path from DataHub context to safe action.",
    images: ["/rationaleops-og.png"],
  },
};

export default function Home() {
  return <Dashboard />;
}
