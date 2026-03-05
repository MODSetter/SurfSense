/** Sample data for Remotion Studio preview — one set per card category. */
import type { CardItem } from "./types";

const COLORS = ["#3b82f6", "#8b5cf6", "#06b6d4", "#10b981"];

export const DEMO_ITEMS: Record<CardItem["category"], CardItem[]> = {
  stat: [
    { category: "stat", title: "Natural Language Processing", value: "$43B", desc: "Text understanding and generation powering human-computer interaction across enterprise applications and consumer products worldwide.", color: COLORS[0] },
    { category: "stat", title: "Computer Vision", value: "$28B", desc: "Image recognition and video analysis transforming manufacturing quality control, medical imaging diagnostics, and autonomous navigation systems.", color: COLORS[1] },
    { category: "stat", title: "Generative AI", value: "$67B", desc: "Content creation, code generation, and synthetic data production reshaping creative workflows and software development pipelines.", color: COLORS[2] },
    { category: "stat", title: "Robotics & Automation", value: "$12B", desc: "Intelligent machines revolutionizing warehouse logistics, surgical procedures, and hazardous environment exploration.", color: COLORS[3] },
    { category: "stat", title: "Autonomous Systems", value: "$35B", desc: "Self-driving vehicles, delivery drones, and industrial robots operating independently in complex real-world environments.", color: "#f59e0b" },
    { category: "stat", title: "Edge Computing", value: "$19B", desc: "Processing data closer to the source enabling real-time inference on mobile devices, IoT sensors, and embedded systems.", color: "#ef4444" },
    { category: "stat", title: "Quantum ML", value: "$4.2B", desc: "Leveraging quantum computing to accelerate model training, combinatorial optimization, and cryptographic applications.", color: "#ec4899" },
  ],
  info: [
    { category: "info", title: "Transformer Architecture", subtitle: "Deep Learning", desc: "Self-attention mechanisms enabling parallel processing of sequential data, forming the backbone of modern language and vision models.", tag: "Core", color: COLORS[0] },
    { category: "info", title: "Reinforcement Learning", subtitle: "Decision Making", desc: "Agents learn optimal strategies through trial-and-error interactions with complex environments, powering game AI and robotics control.", tag: "Advanced", color: COLORS[1] },
    { category: "info", title: "Federated Learning", subtitle: "Privacy-Preserving", desc: "Training models across decentralized edge devices without sharing raw data, enabling privacy-compliant collaborative intelligence.", color: COLORS[2] },
    { category: "info", title: "Neural Architecture Search", desc: "Automating the design of neural network architectures using meta-learning and evolutionary algorithms to discover optimal topologies.", tag: "AutoML", color: COLORS[3] },
    { category: "info", title: "Mixture of Experts", subtitle: "Scaling Laws", desc: "Routing inputs to specialized sub-networks for efficient large-scale inference, enabling trillion-parameter models with sparse activation.", tag: "MoE", color: "#f59e0b" },
    { category: "info", title: "Retrieval Augmented Generation", subtitle: "RAG Pipeline", desc: "Grounding LLM outputs in retrieved documents for factual accuracy, reducing hallucinations and enabling knowledge-base integration.", tag: "RAG", color: "#ef4444" },
    { category: "info", title: "Constitutional AI", subtitle: "Alignment Research", desc: "Training models to follow ethical principles through iterative self-critique, revision, and reinforcement from human feedback.", color: "#ec4899" },
  ],
  quote: [
    { category: "quote", quote: "The best way to predict the future is to invent it.", author: "Alan Kay", role: "Computer Scientist", color: COLORS[0] },
    { category: "quote", quote: "Any sufficiently advanced technology is indistinguishable from magic.", author: "Arthur C. Clarke", role: "Author", color: COLORS[1] },
    { category: "quote", quote: "Move fast and break things. Unless you are breaking stuff, you are not moving fast enough.", author: "Mark Zuckerberg", role: "CEO, Meta", color: COLORS[2] },
    { category: "quote", quote: "Simplicity is the ultimate sophistication.", author: "Leonardo da Vinci", color: COLORS[3] },
  ],
  profile: [
    { category: "profile", name: "Ada Lovelace", role: "First Programmer", desc: "Wrote the first algorithm intended for machine processing.", tag: "Pioneer", color: COLORS[0] },
    { category: "profile", name: "Alan Turing", role: "Father of CS", desc: "Formalized computation and broke the Enigma code.", tag: "Legend", color: COLORS[1] },
    { category: "profile", name: "Grace Hopper", role: "Rear Admiral", desc: "Invented the first compiler and popularized machine-independent languages.", color: COLORS[2] },
    { category: "profile", name: "Tim Berners-Lee", role: "Inventor of WWW", desc: "Created the World Wide Web and HTML.", color: COLORS[3] },
  ],
  progress: [
    { category: "progress", title: "Model Training", value: 87, desc: "Epoch 43 of 50 completed.", color: COLORS[0] },
    { category: "progress", title: "Data Ingestion", value: 62, desc: "Processing 620K of 1M records.", color: COLORS[1] },
    { category: "progress", title: "Test Coverage", value: 94, desc: "Unit and integration tests passing.", color: COLORS[2] },
    { category: "progress", title: "Migration", value: 45, max: 100, desc: "Migrating legacy services to microservices.", color: COLORS[3] },
  ],
  fact: [
    { category: "fact", statement: "GPT-4 was trained on over 13 trillion tokens of text data.", source: "OpenAI Technical Report", color: COLORS[0] },
    { category: "fact", statement: "The global AI market will reach $407B by 2027.", source: "MarketsAndMarkets", color: COLORS[1] },
    { category: "fact", statement: "90% of the world's data was created in the last two years.", source: "IBM Research", color: COLORS[2] },
    { category: "fact", statement: "A single large model training run can emit as much CO2 as five cars over their lifetimes.", source: "MIT Study", color: COLORS[3] },
  ],
  definition: [
    { category: "definition", term: "Overfitting", definition: "When a model learns noise in training data rather than the underlying pattern, performing well on training but poorly on unseen data.", example: "99% train accuracy, 60% test accuracy", color: COLORS[0] },
    { category: "definition", term: "Gradient Descent", definition: "An optimization algorithm that iteratively adjusts parameters by moving in the direction of steepest decrease of the loss function.", color: COLORS[1] },
    { category: "definition", term: "Tokenization", definition: "Breaking text into smaller units (tokens) that a model can process, such as words, subwords, or characters.", example: "'running' → ['run', 'ning']", color: COLORS[2] },
    { category: "definition", term: "Embedding", definition: "A dense vector representation of data in a continuous space where similar items are mapped to nearby points.", color: COLORS[3] },
  ],
};
