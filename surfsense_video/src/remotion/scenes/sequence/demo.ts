/** Sample sequence data for Remotion Studio preview. */
import type { SequenceSceneInput } from "./types";

export const DEMO_SEQUENCE: SequenceSceneInput = {
  type: "sequence",
  title: "Product Launch Pipeline",
  subtitle: "From ideation to market release",
  items: [
    { label: "Research & Discovery", color: "#6c7dff", desc: "Identify market gaps and validate problem space with user interviews and competitive analysis" },
    { label: "Concept Design", color: "#00c9a7", desc: "Create wireframes and interactive prototypes exploring multiple solution approaches" },
    { label: "Technical Planning", color: "#ff6b6b", desc: "Define architecture, select technology stack, and estimate development timeline" },
    { label: "MVP Development", color: "#ffd93d", desc: "Build core features with iterative sprints and continuous integration pipeline" },
    { label: "Quality Assurance", color: "#c084fc", desc: "Comprehensive testing including unit, integration, and user acceptance testing" },
    { label: "Beta Launch", color: "#f97316", desc: "Release to select users, gather feedback, and measure key performance metrics" },
    { label: "Iteration & Polish", color: "#14b8a6", desc: "Address feedback, optimize performance, and refine the user experience" },
    { label: "Go to Market", color: "#8b5cf6", desc: "Full public launch with marketing campaign, press outreach, and partner activations" },
    { label: "Growth & Scale", color: "#ec4899", desc: "Monitor adoption metrics, scale infrastructure, and expand to new market segments" },
    { label: "Continuous Improvement", color: "#22c55e", desc: "Ongoing feature development driven by data analytics and user feedback loops" },
  ],
};
