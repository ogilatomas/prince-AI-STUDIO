# Prince AI Studio — Website Prototype

This ZIP contains a responsive front-end prototype for the private, owner-only Prince AI Studio website.

## Files
- `index.html` — dashboard and page structure
- `styles.css` — dark responsive website styling
- `script.js` — page navigation, duration selectors, template preview and prototype interactions

## Run it
1. Extract the ZIP.
2. Open `index.html` in a modern browser.
3. For deployment, upload the files to a GitHub repository and enable GitHub Pages.

## Included screens
- Dashboard
- Text-to-Video setup with duration choices up to 3 minutes
- AI Clipper with video link field, upload input, per-clip duration, clip count and export format
- Caption templates: Bold, Minimal, Karaoke and Highlighted Words
- Automatic spoken-word caption workflow preview
- AI Viral Hook Generator UI: default-on opening hooks, optional relevant emojis, editable hook text and a live preview
- Projects and Settings screens

## Important: prototype, not a functioning AI service
This is the website interface only. It does not yet download platform videos, generate AI hooks from video content, generate video, transcribe speech, render captions, or export clips. Those features need a secure backend, platform-compliant video ingestion, speech-to-text, video processing (for example FFmpeg), storage, authentication and AI generation services.

Platform links may be blocked or restricted. Users should only process videos they own or are authorized to use; an upload alternative is included in the design.

The 3-minute daily text-to-video target is a product design target, not a promise of free compute capacity or generation speed. Never put private API keys or service tokens in browser JavaScript.
