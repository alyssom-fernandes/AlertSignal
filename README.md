# DeepChat — Cross-Validation AI Chat

A browser-based chat interface that queries **DeepSeek** for answers and uses **ChatGPT as a critical reviewer** — no backend, no server, no installation required.

The idea is simple: instead of trusting a single AI model, every response goes through a second model that evaluates it for accuracy, highlights strengths, points out gaps, and suggests improvements.

---

## How it works

When you send a message:

1. DeepSeek generates a detailed response
2. ChatGPT receives both the question and DeepSeek's answer, then produces a structured critical review covering factual accuracy, strong points, areas for improvement, and a revised version when necessary

There is also an **inverted mode** where ChatGPT responds first and DeepSeek acts as the reviewer.

---

## Getting started

You will need API keys from both platforms. Both offer free tiers suitable for testing.

**DeepSeek**
1. Create an account at [platform.deepseek.com](https://platform.deepseek.com)
2. Go to **API Keys** and generate a new key

**OpenAI**
1. Create an account at [platform.openai.com](https://platform.openai.com)
2. Go to **API Keys** and generate a new secret key

Once you have both keys, open `index.html` in your browser or access the live demo, enter your credentials, and start chatting.

No build step, no package manager, no dependencies.

---

## Privacy

All credentials are stored exclusively in your browser's `localStorage`. No data is sent to any server other than DeepSeek's and OpenAI's own APIs. The application has no analytics, no telemetry, and no external requests beyond the AI calls you explicitly trigger.

> Note: if you share your device or browser profile, clear your localStorage before doing so.

---

## Features

- Dual-model validation with structured review format
- Inverted mode (ChatGPT responds, DeepSeek reviews)
- Conversation history stored locally with search
- Export conversation as Markdown
- File attachments: images, plain text, CSV, Markdown (up to 5 MB)
- Regenerate responses without restarting the conversation
- Reply to specific messages
- Model selector (GPT-4o-mini / GPT-4o)
- Request cancellation with timeout handling
- Offline detection
- Mobile-friendly with long-press context menu

---

## Project structure

```
deepchat/
├── index.html        # Markup and layout
├── css/
│   └── style.css     # All styles
└── js/
    ├── api.js        # API communication (DeepSeek and OpenAI)
    └── app.js        # Application logic, state and UI
```

Built with plain HTML, CSS, and JavaScript. No frameworks, no dependencies.

---

## Estimated cost per conversation

| Model | Cost per question + review |
|---|---|
| GPT-4o-mini (default) | ~$0.001 |
| GPT-4o | ~$0.005 |
| DeepSeek | ~$0.0001 |

Figures are approximate. Check current pricing on each platform.

---

## Roadmap

- Streaming responses
- Support for additional models (Claude, Gemini)
- Light theme
- PWA support

---

## License

MIT
