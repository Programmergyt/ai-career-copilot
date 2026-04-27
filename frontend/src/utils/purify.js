const ALLOWED_TAGS = new Set([
  'a',
  'blockquote',
  'br',
  'code',
  'del',
  'div',
  'em',
  'h1',
  'h2',
  'h3',
  'h4',
  'h5',
  'h6',
  'hr',
  'li',
  'ol',
  'p',
  'pre',
  'span',
  'strong',
  'table',
  'tbody',
  'td',
  'th',
  'thead',
  'tr',
  'ul',
])

const GLOBAL_ATTRS = new Set(['class'])
const TAG_ATTRS = {
  a: new Set(['href', 'title', 'target', 'rel']),
  code: new Set(['class']),
  pre: new Set(['class']),
}

const SAFE_URL_PATTERN = /^(https?:|mailto:|tel:|#|\/)/i

function isAllowedAttr(tagName, attrName) {
  return GLOBAL_ATTRS.has(attrName) || TAG_ATTRS[tagName]?.has(attrName)
}

function isSafeUrl(value) {
  return SAFE_URL_PATTERN.test(value.trim())
}

function sanitizeElement(element) {
  for (const child of Array.from(element.children)) {
    const tagName = child.tagName.toLowerCase()

    if (!ALLOWED_TAGS.has(tagName)) {
      child.replaceWith(document.createTextNode(child.textContent || ''))
      continue
    }

    for (const attr of Array.from(child.attributes)) {
      const attrName = attr.name.toLowerCase()
      const attrValue = attr.value

      if (!isAllowedAttr(tagName, attrName)) {
        child.removeAttribute(attr.name)
        continue
      }

      if ((attrName === 'href' || attrName === 'src') && !isSafeUrl(attrValue)) {
        child.removeAttribute(attr.name)
      }
    }

    if (tagName === 'a') {
      child.setAttribute('target', '_blank')
      child.setAttribute('rel', 'noreferrer noopener')
    }

    sanitizeElement(child)
  }
}

function fallbackSanitize(html) {
  return String(html)
    .replace(/<script[\s\S]*?<\/script>/gi, '')
    .replace(/<style[\s\S]*?<\/style>/gi, '')
    .replace(/\son\w+\s*=\s*("[^"]*"|'[^']*'|[^\s>]*)/gi, '')
    .replace(/\s(?:href|src)\s*=\s*("javascript:[^"]*"|'javascript:[^']*'|javascript:[^\s>]*)/gi, '')
}

export default function purify(html) {
  if (typeof window === 'undefined' || typeof DOMParser === 'undefined') {
    return fallbackSanitize(html)
  }

  const parser = new DOMParser()
  const doc = parser.parseFromString(`<div>${html}</div>`, 'text/html')
  const root = doc.body.firstElementChild

  if (!root) return ''

  sanitizeElement(root)
  return root.innerHTML
}
