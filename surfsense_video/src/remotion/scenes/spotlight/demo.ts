/** Sample data for Remotion Studio preview. */
import type { SpotlightSceneInput } from "./types";

export const DEMO_SPOTLIGHT_SINGLE: SpotlightSceneInput = {
  type: "spotlight",
  items: [
    { category: "stat", title: "Generative AI Market", value: "$67B", desc: "Content creation, code generation, and synthetic data production reshaping creative workflows and software development pipelines.", color: "#6c7dff" },
  ],
};

export const DEMO_SPOTLIGHT_STATS: SpotlightSceneInput = {
  type: "spotlight",
  items: [
    { category: "stat", title: "Natural Language Processing", value: "$43B", desc: "Text understanding and generation powering human-computer interaction across enterprise applications and consumer products worldwide.", color: "#3b82f6" },
    { category: "stat", title: "Computer Vision", value: "$28B", desc: "Image recognition and video analysis transforming manufacturing quality control, medical imaging diagnostics, and autonomous navigation systems.", color: "#8b5cf6" },
    { category: "stat", title: "Generative AI", value: "$67B", desc: "Content creation, code generation, and synthetic data production reshaping creative workflows and software development pipelines.", color: "#06b6d4" },
  ],
};

export const DEMO_SPOTLIGHT_MIXED: SpotlightSceneInput = {
  type: "spotlight",
  items: [
    { category: "stat", title: "AI Market Size", value: "$407B", desc: "Projected global AI market value by 2027.", color: "#3b82f6" },
    { category: "quote", quote: "The best way to predict the future is to invent it.", author: "Alan Kay", role: "Computer Scientist", color: "#8b5cf6" },
    { category: "definition", term: "Overfitting", definition: "When a model learns noise in training data rather than the underlying pattern, performing well on training but poorly on unseen data.", example: "99% train accuracy, 60% test accuracy", color: "#06b6d4" },
    { category: "fact", statement: "GPT-4 was trained on over 13 trillion tokens of text data.", source: "OpenAI Technical Report", color: "#10b981" },
    { category: "progress", title: "Model Training", value: 87, desc: "Epoch 43 of 50 completed.", color: "#f59e0b" },
  ],
};
