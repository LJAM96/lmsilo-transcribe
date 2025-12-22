# Frontend & Design System Guide

The frontend is a modern React application built with **Vite**, **TypeScript**, and **Tailwind CSS**. 
This document details the design system, theming, and instructions for reusing this aesthetic in other projects.

## 🎨 Design System

The application uses a custom "Cream & Olive" aesthetic inspired by premium editorial design. It moves away from standard "SaaS Blue" to a warmer, more organic palette.

### Color Palette
The theme relies on four primary color scales defined in `tailwind.config.js`:

#### 1. Cream (Backgrounds & Warmth)
Used for backgrounds, borders, and subtle separating lines in light mode.
*   `cream-50` (`#fefdfb`): Main app background.
*   `cream-100` (`#fdf9f3`): Secondary backgrounds.
*   `cream-200` (`#f9f1e4`): Borders and accents.

#### 2. Olive (Brand & Action)
Used for primary buttons, active states, and highlights.
*   `olive-600` (`#6d7a4e`): Primary button background.
*   `olive-500` (`#8a9766`): Hover states.
*   `olive-100` (`#eef0e8`): Success badges and active backgrounds.

#### 3. Surface (Text & Elements)
Warm grays for typography, avoiding harsh pure black.
*   `surface-800` (`#514d49`): Primary text.
*   `surface-500` (`#918b83`): Secondary text / metadata.

#### 4. Dark (Dark Mode)
Rich, warm brownish-blacks for dark mode, not pure hex `#000000`.
*   `dark-600` (`#151413`): Main background.
*   `dark-200` (`#2d2b29`): Cards and elevated surfaces.

### Typography
The system uses a mixed typeface approach:
*   **Headings**: `Instrument Serif` (Google Font) - Adds editorial character.
*   **Body**: `Inter` - Clean, legible sans-serif.
*   **Code**: `JetBrains Mono` - Tech/timestamp display.

## 🧩 Component Architecture

Reusable UI components are located in `fronted/src/components`.

### Design Tokens (CSS Classes)
Common patterns are abstracted into CSS classes in `index.css`:

*   **.card**: Standard container with `bg-white`, `rounded-2xl`, and soft shadow.
*   **.btn-primary**: Actions. Olive background, white text, rounded-xl.
*   **.btn-secondary**: Actions. Cream background, surface text, border.
*   **.input**: Form inputs. Cream-50 background, warm focus ring.
*   **.upload-zone**: Dashed border drop area with interactive states.

### Dark Mode Support
Dark mode is implemented via the `.dark` class.
*   **Tailwind Config**: `darkMode: 'class'`
*   **Implementation**: `index.css` contains specific overrides to remap colors in dark mode (e.g., `html.dark .bg-white` becomes a dark gray).

## 🚀 Porting the Theme to Another Tool

To deploy another tool with this **identical theming**, follow these steps:

### 1. Install Dependencies
You will need Tailwind CSS and standard React icons.
```bash
npm install -D tailwindcss postcss autoprefixer
npm install lucide-react
```

### 2. Copy Configuration
Copy the `theme` object from `frontend/tailwind.config.js` to your new project's config. This imports all color scales (`cream`, `olive`, etc.) and font settings.

### 3. Copy Global Styles
Copy the contents of `frontend/src/index.css` to your project's main CSS file. This includes:
*   Base layer resets.
*   Component classes (`.btn-primary`, `.card`).
*   Dark mode color overrides.

### 4. Import Fonts
Add the Google Fonts import to your `index.html` `head`:
```html
<link href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
```

### 5. Reuse Loading State
If utilizing the WebSocket hooks, copy `src/hooks/useWebSocket.ts` to maintain the real-time progress architecture.

## Deployment

### Docker Deployment
The project includes a multi-stage `Dockerfile.frontend`.

1.  **Build Stage**: Uses Node.js to compile React/Vite to static HTML/JS/CSS.
2.  **Production Stage**: Uses Nginx (Alpine) to serve the static files.

**Build Command**:
```bash
docker build -t my-app-frontend -f Dockerfile.frontend .
```

### Environment Variables
*   `VITE_API_URL`: (Optional) URL of the backend API if not proxied.
*   `VITE_WS_URL`: (Optional) WebSocket URL.
