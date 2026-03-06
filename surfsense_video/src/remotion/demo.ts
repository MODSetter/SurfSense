import type { VideoInput } from "./types";

export const DEMO_VIDEO: VideoInput = {
  scenes: [
    { type: "intro", title: "The Future of AI", subtitle: "A visual exploration of artificial intelligence" },

    {
      type: "spotlight",
      items: [
        { category: "stat", title: "AI Market Size", value: "$407B", desc: "Projected global AI market value by 2027, growing at 36.2% CAGR.", color: "#6c7dff" },
      ],
    },

    {
      type: "hierarchy",
      title: "AI Landscape",
      items: [{
        label: "Artificial Intelligence",
        desc: "Broad field of intelligent systems",
        color: "#6c7dff",
        children: [
          { label: "Machine Learning", desc: "Learning from data", color: "#3b82f6", children: [
            { label: "Supervised Learning", desc: "Labeled training data", color: "#60a5fa" },
            { label: "Unsupervised Learning", desc: "Pattern discovery", color: "#60a5fa" },
            { label: "Reinforcement Learning", desc: "Reward-based optimization", color: "#60a5fa" },
          ]},
          { label: "Deep Learning", desc: "Multi-layer neural networks", color: "#8b5cf6", children: [
            { label: "CNNs", desc: "Image recognition", color: "#a78bfa" },
            { label: "Transformers", desc: "Language understanding", color: "#a78bfa" },
            { label: "GANs", desc: "Generative models", color: "#a78bfa" },
            { label: "Diffusion Models", desc: "Image synthesis", color: "#a78bfa" },
          ]},
          { label: "NLP", desc: "Language processing", color: "#ec4899", children: [
            { label: "Sentiment Analysis", color: "#f472b6" },
            { label: "Machine Translation", color: "#f472b6" },
            { label: "Text Generation", color: "#f472b6" },
          ]},
          { label: "Computer Vision", desc: "Visual understanding", color: "#f59e0b", children: [
            { label: "Object Detection", color: "#fbbf24" },
            { label: "Image Segmentation", color: "#fbbf24" },
          ]},
        ],
      }],
    },

    {
      type: "list",
      title: "Key Applications by Industry",
      items: [
        { label: "Healthcare", desc: "Medical imaging diagnostics, drug discovery, and patient monitoring", color: "#ef4444" },
        { label: "Finance", desc: "Fraud detection, algorithmic trading, and risk assessment", color: "#3b82f6" },
        { label: "Manufacturing", desc: "Predictive maintenance, quality control, and supply chain optimization", color: "#f59e0b" },
        { label: "Retail", desc: "Recommendation engines, demand forecasting, and dynamic pricing", color: "#10b981" },
        { label: "Transportation", desc: "Autonomous vehicles, route optimization, and traffic management", color: "#8b5cf6" },
        { label: "Education", desc: "Personalized learning paths, automated grading, and adaptive tutoring", color: "#ec4899" },
        { label: "Energy", desc: "Grid optimization, consumption forecasting, and renewable integration", color: "#06b6d4" },
      ],
    },

    {
      type: "sequence",
      title: "Machine Learning Pipeline",
      items: [
        { label: "Data Collection", desc: "Gather raw data from multiple sources and APIs", color: "#3b82f6" },
        { label: "Data Cleaning", desc: "Handle missing values, outliers, and inconsistencies", color: "#06b6d4" },
        { label: "Feature Engineering", desc: "Transform raw data into meaningful model inputs", color: "#10b981" },
        { label: "Model Training", desc: "Fit the model to training data using optimization", color: "#f59e0b" },
        { label: "Evaluation", desc: "Measure performance with test data and metrics", color: "#ef4444" },
        { label: "Deployment", desc: "Serve the model in production via APIs", color: "#8b5cf6" },
        { label: "Monitoring", desc: "Track model drift, latency, and accuracy over time", color: "#ec4899" },
      ],
    },

    {
      type: "chart",
      title: "Global AI Investment by Sector",
      subtitle: "Billions USD (2024)",
      yTitle: "Investment ($B)",
      items: [
        { label: "Healthcare", value: 45, color: "#ef4444" },
        { label: "Finance", value: 38, color: "#3b82f6" },
        { label: "Automotive", value: 32, color: "#f59e0b" },
        { label: "Retail", value: 28, color: "#10b981" },
        { label: "Manufacturing", value: 24, color: "#8b5cf6" },
        { label: "Telecom", value: 19, color: "#06b6d4" },
        { label: "Energy", value: 15, color: "#ec4899" },
        { label: "Education", value: 12, color: "#f97316" },
      ],
    },

    {
      type: "spotlight",
      items: [
        { category: "quote", quote: "AI is probably the most important thing humanity has ever worked on. I think of it as something more profound than electricity or fire.", author: "Sundar Pichai", role: "CEO, Alphabet", color: "#f59e0b" },
      ],
    },

    {
      type: "relation",
      title: "AI Technology Ecosystem",
      nodes: [
        { id: "llm", label: "Large Language Models", desc: "Foundation models for text", color: "#6c7dff" },
        { id: "rag", label: "RAG", desc: "Retrieval-augmented generation", color: "#3b82f6" },
        { id: "vec", label: "Vector Databases", desc: "Semantic search storage", color: "#10b981" },
        { id: "emb", label: "Embeddings", desc: "Dense vector representations", color: "#8b5cf6" },
        { id: "agent", label: "AI Agents", desc: "Autonomous task execution", color: "#ef4444" },
        { id: "tools", label: "Tool Use", desc: "External API integration", color: "#f59e0b" },
        { id: "ft", label: "Fine-Tuning", desc: "Domain-specific adaptation", color: "#ec4899" },
        { id: "eval", label: "Evaluation", desc: "Benchmarks and testing", color: "#06b6d4" },
        { id: "deploy", label: "Inference APIs", desc: "Serving infrastructure", color: "#14b8a6" },
      ],
      edges: [
        { from: "llm", to: "rag", label: "powers" },
        { from: "rag", to: "vec", label: "queries" },
        { from: "emb", to: "vec", label: "indexes into" },
        { from: "llm", to: "emb", label: "generates" },
        { from: "llm", to: "agent", label: "drives" },
        { from: "agent", to: "tools", label: "invokes" },
        { from: "ft", to: "llm", label: "specializes" },
        { from: "eval", to: "llm", label: "measures" },
        { from: "llm", to: "deploy", label: "served via" },
        { from: "eval", to: "ft", label: "guides" },
      ],
    },

    {
      type: "comparison",
      title: "Traditional Software vs AI-Powered",
      groups: [
        {
          label: "Traditional Software",
          color: "#3b82f6",
          items: [
            { label: "Rule-Based Logic", desc: "Manually coded decision trees and if-else chains" },
            { label: "Static Analysis", desc: "Fixed algorithms that don't improve over time" },
            { label: "Manual Testing", desc: "Human-driven QA processes with scripted test cases" },
            { label: "Scheduled Updates", desc: "Quarterly release cycles with waterfall planning" },
          ],
        },
        {
          label: "AI-Powered Software",
          color: "#10b981",
          items: [
            { label: "Learned Patterns", desc: "Models that discover rules from data automatically" },
            { label: "Adaptive Analysis", desc: "Continuously improving with new data streams" },
            { label: "Automated Validation", desc: "Self-testing systems that detect regressions instantly" },
            { label: "Continuous Learning", desc: "Real-time model updates based on production feedback" },
          ],
        },
      ],
    },

    {
      type: "list",
      title: "Challenges & Ethical Considerations",
      items: [
        { label: "Bias & Fairness", desc: "Models can perpetuate or amplify societal biases present in training data", color: "#ef4444" },
        { label: "Privacy", desc: "Training on personal data raises consent and compliance concerns", color: "#f59e0b" },
        { label: "Transparency", desc: "Black-box models make it difficult to explain decisions to stakeholders", color: "#8b5cf6" },
        { label: "Job Displacement", desc: "Automation may displace workers faster than new roles are created", color: "#3b82f6" },
        { label: "Security", desc: "Adversarial attacks can manipulate model outputs in dangerous ways", color: "#ec4899" },
        { label: "Energy Consumption", desc: "Training large models requires massive computational resources", color: "#06b6d4" },
      ],
    },

    {
      type: "chart",
      title: "Enterprise AI Adoption Rate",
      subtitle: "Percentage of enterprises using AI",
      yTitle: "Adoption (%)",
      items: [
        { label: "2018", value: 15, color: "#94a3b8" },
        { label: "2019", value: 22, color: "#94a3b8" },
        { label: "2020", value: 31, color: "#64748b" },
        { label: "2021", value: 42, color: "#64748b" },
        { label: "2022", value: 50, color: "#3b82f6" },
        { label: "2023", value: 58, color: "#3b82f6" },
        { label: "2024", value: 72, color: "#6c7dff" },
        { label: "2025", value: 78, color: "#6c7dff" },
        { label: "2026", value: 86, color: "#8b5cf6" },
      ],
    },

    {
      type: "spotlight",
      items: [
        { category: "definition", term: "Retrieval-Augmented Generation", definition: "A technique that combines large language models with external knowledge retrieval to produce more accurate, up-to-date, and verifiable responses.", example: "A chatbot that searches company documents before answering customer questions.", color: "#10b981" },
      ],
    },

    {
      type: "sequence",
      title: "AI Implementation Roadmap",
      items: [
        { label: "Identify Use Cases", desc: "Map business problems to AI solution patterns", color: "#3b82f6" },
        { label: "Data Assessment", desc: "Audit data quality, availability, and governance", color: "#06b6d4" },
        { label: "Proof of Concept", desc: "Build and validate a small-scale prototype", color: "#10b981" },
        { label: "Infrastructure Setup", desc: "Provision compute, storage, and MLOps tooling", color: "#f59e0b" },
        { label: "Production Deployment", desc: "Scale the solution with monitoring and rollback", color: "#8b5cf6" },
        { label: "Continuous Improvement", desc: "Iterate based on user feedback and performance metrics", color: "#ec4899" },
      ],
    },

    {
      type: "comparison",
      title: "Open-Source vs Proprietary AI",
      groups: [
        {
          label: "Open-Source",
          color: "#10b981",
          items: [
            { label: "Full Transparency", desc: "Complete visibility into model weights and training data" },
            { label: "Community-Driven", desc: "Rapid innovation from global contributor ecosystems" },
            { label: "Cost Effective", desc: "No licensing fees, self-hosted on your infrastructure" },
            { label: "Customizable", desc: "Fine-tune and modify for specific domain needs" },
          ],
        },
        {
          label: "Proprietary",
          color: "#6c7dff",
          items: [
            { label: "Enterprise Support", desc: "Dedicated SLAs, uptime guarantees, and support teams" },
            { label: "Managed Infrastructure", desc: "No need to handle scaling, updates, or maintenance" },
            { label: "Advanced Capabilities", desc: "Access to cutting-edge models before public release" },
            { label: "Compliance Ready", desc: "Built-in certifications for regulated industries" },
          ],
        },
      ],
    },

    {
      type: "spotlight",
      items: [
        { category: "fact", statement: "By 2030, AI is expected to contribute $15.7 trillion to the global economy — more than the current output of China and India combined.", source: "PwC Global AI Study", color: "#f59e0b" },
      ],
    },

    { type: "outro", title: "Thank You", subtitle: "Generated with SurfSense" },
  ],
};
