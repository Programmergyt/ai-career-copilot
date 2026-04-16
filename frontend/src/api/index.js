import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 300000, //请求超时时间(毫秒)
  headers: { 'Content-Type': 'application/json' },
})

/** POST /api/chat */
export function sendChat(sessionId, message, attachments = []) {
  return api.post('/chat', {
    session_id: sessionId,
    message,
    attachments,
  })
}

/** GET /api/resume/content */
export function getResumeContent(sessionId) {
  return api.get('/resume/content', { params: { session_id: sessionId } })
}

/** GET /api/resume/html */
export function getResumeHtml(sessionId) {
  return api.get('/resume/html', { params: { session_id: sessionId } })
}

/** POST /api/resume/render */
export function renderResume(sessionId, instruction) {
  return api.post('/resume/render', {
    session_id: sessionId,
    render_instruction: instruction,
  })
}

/** POST /api/export */
export function exportResume(sessionId, format = 'html') {
  return api.post('/export', { session_id: sessionId, format }, {
    responseType: format === 'json' ? 'json' : 'blob',
  })
}

/** GET /health */
export function healthCheck() {
  return axios.get('/health')
}
