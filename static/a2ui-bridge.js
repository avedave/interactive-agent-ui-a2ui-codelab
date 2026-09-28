/**
 * A2UI Client Bridge (v0.9 Specification)
 * Powered by official @a2ui/web_core and @a2ui/lit packages.
 *
 * Implements the official two-tier architecture:
 * 1. Protocol & State: MessageProcessor from @a2ui/web_core
 * 2. Component Renderer: <a2ui-surface> and basicCatalog from @a2ui/lit
 * 3. Graceful offline fallback if remote CDN is unreachable.
 */

let processor = null;
let basicCatalog = null;
let officialSdkReady = false;
let surfaceCounter = 0;

// Initialize official A2UI Web packages via modern browser ESM
async function initOfficialSdk() {
  try {
    const core = await import('https://esm.sh/@a2ui/web_core@0.11.0/v0_9');
    const lit = await import('https://esm.sh/@a2ui/lit@0.11.0/v0_9');

    basicCatalog = lit.basicCatalog;
    processor = new core.MessageProcessor([basicCatalog]);

    if (typeof core.injectBasicCatalogStyles === 'function') {
      core.injectBasicCatalogStyles(document);
    }

    officialSdkReady = true;
    console.info('A2UI: Official @a2ui/web_core and @a2ui/lit initialized successfully.');
  } catch (err) {
    console.warn('A2UI: CDN packages unavailable. Activating resilient offline fallback.', err);
    initOfflineFallback();
  }
}

// Resilient offline fallback element when network CDN is unavailable
function initOfflineFallback() {
  if (!customElements.get('a2ui-surface')) {
    class OfflineA2UISurface extends HTMLElement {
      constructor() {
        super();
        this.attachShadow({ mode: 'open' });
        this.componentsMap = new Map();
        this.rootId = null;
      }

      updateSurface(surfaceData) {
        if (!surfaceData) return;
        let components = null;
        const messages = Array.isArray(surfaceData) ? surfaceData : [surfaceData];
        for (const msg of messages) {
          if (msg.updateComponents && msg.updateComponents.components) {
            components = msg.updateComponents.components;
          } else if (msg.components) {
            components = msg.components;
          }
        }
        if (!components || !components.length) return;
        this.componentsMap.clear();
        for (const c of components) this.componentsMap.set(c.id, c);
        this.rootId = this.componentsMap.has('root') ? 'root' : components[0]?.id;
        this.render();
      }

      render() {
        if (!this.rootId || !this.componentsMap.has(this.rootId)) return;
        const styles = `
          :host { display: block; font-family: system-ui, sans-serif; color: #202124; }
          .col { display: flex; flex-direction: column; gap: 0.75rem; width: 100%; }
          .row { display: flex; flex-direction: row; align-items: center; gap: 0.5rem; flex-wrap: wrap; }
          .row.between { justify-content: space-between; }
          .card { background: #fff; border: 1px solid #dadce0; border-radius: 12px; padding: 1rem; box-shadow: 0 1px 3px rgba(0,0,0,0.08); display: flex; flex-direction: column; gap: 0.5rem; }
          .txt-h1 { font-size: 1.15rem; font-weight: 700; color: #1a73e8; }
          .txt-h2 { font-size: 1rem; font-weight: 600; color: #202124; }
          .txt-body { font-size: 0.9rem; color: #3c4043; line-height: 1.4; }
          .txt-caption { font-size: 0.78rem; font-weight: 600; padding: 0.2rem 0.55rem; border-radius: 12px; background: #f1f3f4; color: #5f6368; display: inline-flex; }
          .alert-crit { background: #fce8e6; color: #c5221f; border: 1px solid #ea4335; }
          .alert-warn { background: #fef7e0; color: #b06000; border: 1px solid #f9ab00; }
        `;
        this.shadowRoot.innerHTML = `<style>${styles}</style>`;
        const root = this.renderNode(this.rootId);
        if (root) this.shadowRoot.appendChild(root);
      }

      renderNode(id) {
        const comp = this.componentsMap.get(id);
        if (!comp) return null;
        const el = document.createElement('div');
        switch (comp.component) {
          case 'Column':
            el.className = 'col';
            for (const childId of comp.children || []) {
              const child = this.renderNode(childId);
              if (child) el.appendChild(child);
            }
            break;
          case 'Row':
            el.className = `row ${(comp.justify === 'spaceBetween' || comp.justify === 'space-between') ? 'between' : ''}`;
            for (const childId of comp.children || []) {
              const child = this.renderNode(childId);
              if (child) el.appendChild(child);
            }
            break;
          case 'Card':
            el.className = 'card';
            if (comp.child) {
              const child = this.renderNode(comp.child);
              if (child) el.appendChild(child);
            }
            break;
          case 'Text': {
            const v = comp.variant || 'body';
            const text = typeof comp.text === 'object' ? (comp.text.literalString || '') : String(comp.text || '');
            let alertCls = '';
            if (v === 'caption') {
              const l = text.toLowerCase();
              if (l.includes('crit') || l.includes('alert')) alertCls = 'alert-crit';
              else if (l.includes('warn') || l.includes('low')) alertCls = 'alert-warn';
            }
            el.className = `txt-${v} ${alertCls}`.trim();
            el.textContent = text;
            break;
          }
          default:
            el.textContent = `[${comp.component}]`;
        }
        return el;
      }
    }
    customElements.define('a2ui-surface', OfflineA2UISurface);
  }
}

// Start initialization immediately
const sdkInitPromise = initOfficialSdk();

/**
 * Main rendering entrypoint called by chat UI.
 * Feeds messages to MessageProcessor and mounts the official <a2ui-surface>.
 */
export async function renderA2UIMessages(container, rawMessages) {
  if (!container || !rawMessages) return null;
  await sdkInitPromise;

  const messages = Array.isArray(rawMessages) ? rawMessages : [rawMessages];
  surfaceCounter++;

  // Determine surfaceId and create a unique session surface key to prevent history collision
  let baseSurfaceId = 'default';
  for (const m of messages) {
    if (m.createSurface?.surfaceId) baseSurfaceId = m.createSurface.surfaceId;
    else if (m.updateComponents?.surfaceId) baseSurfaceId = m.updateComponents.surfaceId;
  }
  const sessionSurfaceId = `${baseSurfaceId}-${surfaceCounter}`;

  // Normalize messages with unique surfaceId and version
  const normalizedMessages = messages.map(msg => {
    const copy = JSON.parse(JSON.stringify(msg));
    copy.version = copy.version || 'v0.9';
    if (copy.createSurface) {
      copy.createSurface.surfaceId = sessionSurfaceId;
      copy.createSurface.catalogId = copy.createSurface.catalogId || (basicCatalog ? basicCatalog.id : 'https://a2ui.org/specification/v0_9/catalogs/basic/catalog.json');
    }
    if (copy.updateComponents) {
      copy.updateComponents.surfaceId = sessionSurfaceId;
      // Normalise enum values if needed
      if (Array.isArray(copy.updateComponents.components)) {
        for (const comp of copy.updateComponents.components) {
          if (comp.justify === 'space-between') comp.justify = 'spaceBetween';
        }
      }
    }
    return copy;
  });

  if (officialSdkReady && processor) {
    try {
      processor.processMessages(normalizedMessages);
      const surface = processor.model.surfacesMap.get(sessionSurfaceId);
      if (surface) {
        const surfaceEl = document.createElement('a2ui-surface');
        surfaceEl.surface = surface;
        container.appendChild(surfaceEl);
        if (surfaceEl.updateComplete) {
          await surfaceEl.updateComplete;
        }
        return surfaceEl;
      }
    } catch (err) {
      console.warn('A2UI: MessageProcessor error, trying fallback:', err);
    }
  }

  // Resilient offline fallback if processor was not available or encountered an issue
  const fallbackEl = document.createElement('a2ui-surface');
  container.appendChild(fallbackEl);
  if (typeof fallbackEl.updateSurface === 'function') {
    fallbackEl.updateSurface(normalizedMessages);
  }
  return fallbackEl;
}

// Expose globally for vanilla browser scripts
window.renderA2UIMessages = renderA2UIMessages;
