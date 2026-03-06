/** Sample hierarchy data for Remotion Studio preview. */
import type { HierarchySceneInput } from "./types";

export const DEMO_HIERARCHY: HierarchySceneInput = {
  type: "hierarchy",
  title: "AI Architecture",
  items: [
    {
      label: "AI Platform",
      color: "#6c7dff",
      desc: "Enterprise-grade intelligent automation system",
      children: [
        {
          label: "Data Pipeline",
          color: "#00c9a7",
          desc: "ETL & streaming",
          children: [
            { label: "Real-time Data Ingestion", color: "#00c9a7", desc: "High-throughput event streaming via Kafka and Kinesis" },
            { label: "Stream Processing Engine", color: "#00c9a7", desc: "Stateful transformations with Apache Flink" },
            { label: "Distributed Storage Layer", color: "#00c9a7", desc: "Petabyte-scale lakehouse on S3 and Delta Lake" },
          ],
        },
        {
          label: "ML Engine",
          color: "#ff6b6b",
          desc: "Model lifecycle",
          children: [
            { label: "Training", color: "#ff6b6b", desc: "Distributed GPU clusters with auto-scaling" },
            { label: "Inference", color: "#ff6b6b", desc: "Sub-100ms latency model serving at scale" },
          ],
        },
        {
          label: "API Layer",
          color: "#ffd93d",
          desc: "Client interfaces",
          children: [
            { label: "REST", color: "#ffd93d", desc: "CRUD endpoints" },
            { label: "GraphQL", color: "#ffd93d", desc: "Flexible queries" },
            { label: "WebSocket", color: "#ffd93d", desc: "Real-time events" },
          ],
        },
        {
          label: "Monitoring",
          color: "#c084fc",
          desc: "Observability",
          children: [
            { label: "Metrics", color: "#c084fc", desc: "Prometheus, Grafana" },
            { label: "Alerts", color: "#c084fc", desc: "PagerDuty, Slack" },
          ],
        },
      ],
    },
  ],
};
